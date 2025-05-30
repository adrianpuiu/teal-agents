import logging
from collections.abc import AsyncIterable
from contextlib import nullcontext
import asyncio
from asyncio import Task, CancelledError

import aiohttp
from httpx_sse import ServerSentEvent
from ska_utils import get_telemetry

from collab_orchestrator.agents import TaskAgent
from collab_orchestrator.co_types import (
    AgentRequestEvent,
    ErrorResponse,
    EventType,
    InvokeResponse,
    PartialResponse,
    new_event_response,
)
from collab_orchestrator.team_handler.conversation import Conversation


class TaskExecutor:
    def __init__(self, agents: list[TaskAgent]):
        self.agents: dict[str, TaskAgent] = {}
        for agent in agents:
            self.agents[f"{agent.agent.name}:{agent.agent.version}"] = agent
        self.t = get_telemetry()

    async def execute_task_sse(
        self,
        task_id: str,
        instructions: str,
        agent_name: str,
        conversation: Conversation,
        session_id: str | None = None,
        source: str | None = None,
        request_id: str | None = None,
    ) -> AsyncIterable[str]:
        with (
            self.t.tracer.start_as_current_span(
                name="execute-task",
                attributes={"instructions": instructions, "agent_name": agent_name},
            )
            if self.t.telemetry_enabled()
            else nullcontext()
        ):
            task_agent = self.agents[agent_name]
            if not task_agent:
                raise ValueError(f"Task agent {agent_name} not found.")

            yield new_event_response(
                EventType.AGENT_REQUEST,
                AgentRequestEvent(
                    session_id=session_id,
                    source=source,
                    request_id=request_id,
                    task_id=task_id,
                    agent_name=agent_name,
                    task_goal=instructions,
                ),
            )

            # Define a proper keepalive coroutine that can be run as a task
            async def keepalive_coroutine():
                try:
                    while True:
                        await asyncio.sleep(30)
                        # Use a custom event type instead of 'comment' so browsers won't filter it
                        keepalive_queue.put_nowait(
                            f"event: keepalive\ndata: connection alive\n\n"
                        )
                        logging.info("Keepalive message sent to client")
                except (CancelledError, asyncio.CancelledError):
                    # Task was cancelled, which is expected when main task completes
                    pass
                except Exception as e:
                    logging.error(f"Error in keepalive task: {e}")

            task_result = ""
            pre_reqs = conversation.to_pre_requisites()

            # Create a queue for the keepalive messages
            keepalive_queue = asyncio.Queue()

            # Start the keepalive task
            keepalive_task = asyncio.create_task(keepalive_coroutine())

            try:
                # Create a task for the main operation
                perform_task_coro = task_agent.perform_task(
                    session_id, instructions, pre_reqs
                )
                perform_task = asyncio.create_task(perform_task_coro)

                # Continue until the main task is done
                while not perform_task.done():
                    # Wait for either the main task to complete or a keepalive message
                    # with a small timeout to check the main task frequently
                    try:
                        # Wait for a keepalive message for up to 1 second
                        message = await asyncio.wait_for(keepalive_queue.get(), 1)
                        yield message
                    except asyncio.TimeoutError:
                        # No keepalive message yet, just continue checking the main task
                        pass

                # Get the result from the main task
                response = await perform_task

                # Cancel keepalive task
                keepalive_task.cancel()

                i_response = InvokeResponse.model_validate(response)
                task_result = i_response.output_raw
                yield new_event_response(EventType.FINAL_RESPONSE, i_response)
                # async for content in task_agent.perform_task_sse(
                #     session_id, instructions, pre_reqs
                # ):
                #     if isinstance(content, PartialResponse):
                #         yield new_event_response(EventType.PARTIAL_RESPONSE, content)
                #     elif isinstance(content, InvokeResponse):
                #         task_result = content.output_raw
                #         yield new_event_response(EventType.FINAL_RESPONSE, content)
                #     elif isinstance(content, ServerSentEvent):
                #         yield f"event: {content.event}\ndata: {content.data}\n\n"
                #     else:
                #         yield new_event_response(
                #             EventType.ERROR,
                #             ErrorResponse(
                #                 session_id=session_id,
                #                 source=source,
                #                 request_id=request_id,
                #                 status_code=500,
                #                 detail=f"Unknown response type - {str(content)}",
                #             ),
                #         )
            except Exception as e:
                # Cancel keepalive task if main task fails
                if keepalive_task and not keepalive_task.done():
                    keepalive_task.cancel()

                print(e)
                logging.error(str(e))
                yield new_event_response(
                    EventType.ERROR,
                    ErrorResponse(
                        session_id=session_id,
                        source=source,
                        request_id=request_id,
                        status_code=500,
                        detail=f"Unexpected error occurred: {e}",
                    ),
                )
            finally:
                # Ensure keepalive task is always cancelled
                if keepalive_task and not keepalive_task.done():
                    keepalive_task.cancel()
                    try:
                        await asyncio.wait_for(keepalive_task, 1)
                    except (
                        CancelledError,
                        asyncio.CancelledError,
                        asyncio.TimeoutError,
                    ):
                        pass

            conversation.add_item(task_id, agent_name, instructions, task_result)
