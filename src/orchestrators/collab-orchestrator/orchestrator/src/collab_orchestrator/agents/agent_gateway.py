import asyncio
import logging
from collections.abc import AsyncIterable
from typing import Any

import httpx
import websockets
from httpx_sse import ServerSentEvent, aconnect_sse
from opentelemetry.propagate import inject
from pydantic import BaseModel

from collab_orchestrator.co_types import InvokeResponse, PartialResponse


class AgentGateway(BaseModel):
    host: str
    secure: bool
    agw_key: str

    def _get_endpoint_for_agent(self, agent_name: str, agent_version: str) -> str:
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.host}/{agent_name}/{agent_version}"

    def _get_sse_endpoint_for_agent(self, agent_name: str, agent_version: str) -> str:
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.host}/{agent_name}/{agent_version}/sse"

    def _get_ws_endpoint_for_agent(self, agent_name: str, agent_version: str) -> str:
        protocol = "wss" if self.secure else "ws"
        return f"{protocol}://{self.host}/{agent_name}/{agent_version}/stream"

    async def invoke_agent(
        self,
        agent_name: str,
        agent_version: str,
        agent_input: BaseModel,
    ) -> Any:
        payload = agent_input.model_dump_json()

        headers = {
            "taAgwKey": self.agw_key,
            "Content-Type": "application/json",
        }
        inject(headers)
        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    logging.info(f"Invoking agent {agent_name} version {agent_version}")
                    response = await client.post(
                        self._get_endpoint_for_agent(agent_name, agent_version),
                        content=payload,
                        headers=headers,
                    )
                    logging.info(
                        f"Response from agent {agent_name} version {agent_version}"
                    )
                    response.raise_for_status()
                    return response.json()
            except Exception as e:
                print(e)
                logging.warn(f"Error invoking agent {agent_name}: {e}")
                attempt += 1
        raise TimeoutError()

    async def invoke_agent_sse(
        self, agent_name: str, agent_version: str, agent_input: BaseModel
    ) -> AsyncIterable[PartialResponse | InvokeResponse | ServerSentEvent]:
        json_input = agent_input.model_dump(mode="json")
        headers = {
            "taAgwKey": self.agw_key,
        }
        inject(headers)
        endpoint = self._get_sse_endpoint_for_agent(agent_name, agent_version)
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with aconnect_sse(
                client,
                "POST",
                endpoint,
                json=json_input,
                headers=headers,
            ) as event_source:
                async for sse in event_source.aiter_sse():
                    match sse.event:
                        case "partial-response":
                            yield PartialResponse.model_validate_json(sse.data)
                        case "final-response":
                            yield InvokeResponse.model_validate_json(sse.data)
                        case _:
                            yield sse

    async def invoke_agent_stream(
        self, agent_name: str, agent_version: str, agent_input: BaseModel
    ) -> AsyncIterable[str]:
        payload = agent_input.model_dump_json()

        headers = {
            "taAgwKey": self.agw_key,
        }
        inject(headers)
        async with websockets.connect(
            self._get_ws_endpoint_for_agent(agent_name, agent_version),
            additional_headers=headers,
        ) as ws:
            await ws.send(payload)
            async for message in ws:
                yield message
