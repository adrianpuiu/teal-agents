import logging
import uuid
from collections.abc import AsyncIterable
from contextlib import nullcontext
import asyncio
from asyncio import Task, CancelledError

from ska_utils import Telemetry

from collab_orchestrator.agents import (
    AgentGateway,
    BaseAgent,
    BaseAgentBuilder,
    TaskAgent,
)
from collab_orchestrator.co_types import (
    AbortResult,
    BaseConfig,
    BaseMultiModalInput,
    ErrorResponse,
    EventType,
    InvokeResponse,
    KindHandler,
    TokenUsage,
    new_event_response,
)
from collab_orchestrator.team_handler.conversation import Conversation
from collab_orchestrator.team_handler.manager_agent import (
    Action,
    ManagerAgent,
)
from collab_orchestrator.team_handler.task_executor import TaskExecutor
from collab_orchestrator.team_handler.types import TeamSpec


class TeamHandler(KindHandler):
    def __init__(
        self,
        t: Telemetry,
        config: BaseConfig,
        agent_gateway: AgentGateway,
        base_agent_builder: BaseAgentBuilder,
        task_agents_bases: list[BaseAgent],
        task_agents: list[TaskAgent],
    ):
        super().__init__(
            t, config, agent_gateway, base_agent_builder, task_agents_bases, task_agents
        )
        self.manager_agent: ManagerAgent | None = None
        self.max_rounds = 0
        self.task_executor: TaskExecutor | None = None

    async def _execute_task(
        self,
        task_id: str,
        instructions: str,
        agent_name: str,
        conversation: Conversation,
        session_id: str | None = None,
        source: str | None = None,
        request_id: str | None = None,
    ) -> AsyncIterable[str]:
        """Executes a single task and streams results."""
        logging.info(f"Executing task for agent {agent_name}")
        try:
            async for result in self.task_executor.execute_task_sse(
                task_id=task_id,
                instructions=instructions,
                agent_name=agent_name,
                conversation=conversation,
                session_id=session_id,
                source=source,
                request_id=request_id,
            ):
                yield result
        except Exception as e:
            print(e)
            logging.error(str(e))
            yield new_event_response(
                EventType.ERROR,
                ErrorResponse(
                    session_id=session_id or "",
                    source=source or "",
                    request_id=request_id or "",
                    status_code=500,
                    detail=str(e),
                ),
            )
            return

    async def initialize(self):
        spec = TeamSpec.model_validate(obj=self.config.spec.model_dump())

        manager_agent_base = await self.base_agent_builder.build_agent(
            spec.manager_agent
        )
        self.manager_agent = ManagerAgent(
            agent=manager_agent_base, gateway=self.agent_gateway
        )
        self.max_rounds = spec.max_rounds
        self.task_executor = TaskExecutor(self.task_agents)

    async def invoke(
        self, chat_history: BaseMultiModalInput, request: str
    ) -> AsyncIterable:
        session_id: str
        if chat_history.session_id:
            session_id = chat_history.session_id
        else:
            session_id = uuid.uuid4().hex
        request_id = uuid.uuid4().hex
        source = f"{self.config.service_name}:{self.config.version}"

        with (
            self.t.tracer.start_as_current_span(
                name="invoke-sse", attributes={"goal": request}
            )
            if self.t.telemetry_enabled()
            else nullcontext()
        ):
            round_no = 0
            conversation = Conversation(messages=[])
            while True:
                logging.info("Begin of round %d", round_no)
                with (
                    self.t.tracer.start_as_current_span(name="determine-next-action")
                    if self.t.telemetry_enabled()
                    else nullcontext()
                ):
                    logging.info("Invoking manager agent to determine next action")

                    # Define a keepalive coroutine for the manager agent call
                    async def manager_keepalive():
                        try:
                            while True:
                                await asyncio.sleep(30)
                                # Send a keepalive event for the manager agent call
                                yield f"event: keepalive\ndata: manager call in progress\n\n"
                                logging.info("Manager keepalive message sent to client")
                        except (CancelledError, asyncio.CancelledError):
                            # Task was cancelled, which is expected when manager call completes
                            pass
                        except Exception as e:
                            logging.error(f"Error in manager keepalive task: {e}")

                    # Create a queue for keepalive messages
                    manager_keepalive_queue = asyncio.Queue()

                    # Start the keepalive task
                    async def run_keepalive():
                        try:
                            while True:
                                await asyncio.sleep(30)
                                manager_keepalive_queue.put_nowait(
                                    f"event: keepalive\ndata: manager call in progress\n\n"
                                )
                                logging.info("Manager keepalive message sent to client")
                        except (CancelledError, asyncio.CancelledError):
                            pass
                        except Exception as e:
                            logging.error(f"Error in manager keepalive task: {e}")

                    manager_keepalive_task = asyncio.create_task(run_keepalive())

                    try:
                        # Create a task for the manager call
                        determine_action_coro = (
                            self.manager_agent.determine_next_action(
                                chat_history,
                                request,
                                self.task_agents_bases,
                                conversation.messages,
                            )
                        )
                        determine_action_task = asyncio.create_task(
                            determine_action_coro
                        )

                        # Continue until the manager task is done
                        while not determine_action_task.done():
                            # Wait for either the task to complete or a keepalive message
                            try:
                                # Wait for a keepalive message for up to 1 second
                                message = await asyncio.wait_for(
                                    manager_keepalive_queue.get(), 1
                                )
                                yield message
                            except asyncio.TimeoutError:
                                # No keepalive message yet, just continue checking the task
                                pass

                        # Get the result from the manager task
                        manager_output = await determine_action_task

                        # Cancel keepalive task
                        manager_keepalive_task.cancel()

                        logging.info("Manager call completed successfully")
                    except Exception as e:
                        # Cancel keepalive task if manager task fails
                        if manager_keepalive_task and not manager_keepalive_task.done():
                            manager_keepalive_task.cancel()

                        print(e)
                        logging.error(str(e))
                        yield new_event_response(
                            EventType.ERROR,
                            ErrorResponse(
                                session_id=session_id,
                                source=source,
                                request_id=request_id,
                                status_code=500,
                                detail=str(e),
                            ),
                        )
                        return
                    finally:
                        # Ensure keepalive task is always cancelled
                        if manager_keepalive_task and not manager_keepalive_task.done():
                            manager_keepalive_task.cancel()
                            try:
                                await asyncio.wait_for(manager_keepalive_task, 1)
                            except (
                                CancelledError,
                                asyncio.CancelledError,
                                asyncio.TimeoutError,
                            ):
                                pass

                    manager_output.session_id = session_id
                    manager_output.source = source
                    manager_output.request_id = request_id
                    yield new_event_response(EventType.MANAGER_RESPONSE, manager_output)

                    logging.info(f"Next Action: {manager_output.next_action}")
                    match manager_output.next_action:
                        case Action.PROVIDE_RESULT:
                            yield new_event_response(
                                EventType.FINAL_RESPONSE,
                                InvokeResponse(
                                    session_id=session_id,
                                    source=source,
                                    request_id=request_id,
                                    token_usage=TokenUsage(
                                        completion_tokens=0,
                                        prompt_tokens=0,
                                        total_tokens=0,
                                    ),
                                    output_raw=conversation.get_message_by_task_id(
                                        manager_output.action_detail.result_task_id
                                    ).result,
                                ),
                            )
                            break
                        case Action.ABORT:
                            yield new_event_response(
                                EventType.ERROR,
                                AbortResult(
                                    session_id=session_id,
                                    source=source,
                                    request_id=request_id,
                                    abort_reason=manager_output.action_detail.abort_reason,
                                ),
                            )
                            break
                        case Action.ASSIGN_NEW_TASK:
                            async for result in self._execute_task(
                                manager_output.action_detail.task_id,
                                manager_output.action_detail.instructions,
                                manager_output.action_detail.agent_name,
                                conversation,
                                session_id,
                                source,
                                request_id,
                            ):
                                yield result
                        case _:
                            yield new_event_response(
                                EventType.ERROR,
                                ErrorResponse(
                                    session_id=session_id,
                                    source=source,
                                    request_id=request_id,
                                    status_code=400,
                                    detail=f"Unknown action: {manager_output.next_action}",
                                ),
                            )
                            break
                    round_no = round_no + 1
                    if round_no >= self.max_rounds:
                        logging.error("Max number of rounds reached")
                        yield new_event_response(
                            EventType.ERROR,
                            AbortResult(
                                session_id=session_id,
                                source=source,
                                request_id=request_id,
                                abort_reason=f"Max rounds surpassed: {self.max_rounds}",
                            ),
                        )
                        break
