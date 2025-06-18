import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel
import httpx
import json
from aconnect_sse import SSEClient, Event as SSEEvent


from collab_orchestrator.agents.agent_gateway import AgentGateway, InvokeResponse, PartialResponse, KeepaliveMessage
from collab_orchestrator.agents.base_agent_builder import BaseAgentBuilder, BaseAgent, OpenApiResponse, OpenApiPath, OpenApiPost


@pytest.fixture
def mock_agent_gateway():
    return AgentGateway(base_url="http://fakeagent.com")

@pytest.mark.asyncio
async def test_invoke_agent_success(mock_agent_gateway):
    mock_response_data = {"key": "value"}
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data

    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        response = await mock_agent_gateway.invoke_agent("test_agent", {"input": "data"})
        assert isinstance(response, InvokeResponse)
        assert response.response == mock_response_data
        mock_post.assert_called_once_with("http://fakeagent.com/test_agent/invoke", json={"input": "data"}, timeout=AgentGateway.DEFAULT_TIMEOUT)

@pytest.mark.asyncio
async def test_invoke_agent_with_retries_on_timeout(mock_agent_gateway):
    mock_response_data = {"key": "value"}
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data

    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [httpx.TimeoutException("timeout"), mock_response]
        response = await mock_agent_gateway.invoke_agent("test_agent", {"input": "data"})
        assert isinstance(response, InvokeResponse)
        assert response.response == mock_response_data
        assert mock_post.call_count == 2

@pytest.mark.asyncio
async def test_invoke_agent_failure_after_max_retries(mock_agent_gateway):
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("timeout")
        with pytest.raises(httpx.TimeoutException):
            await mock_agent_gateway.invoke_agent("test_agent", {"input": "data"})
        assert mock_post.call_count == mock_agent_gateway.max_retries

@pytest.mark.asyncio
async def test_invoke_agent_sse_success(mock_agent_gateway):
    mock_event_data = {"key": "value"}
    mock_sse_event = SSEEvent(data=json.dumps(mock_event_data))

    async def mock_event_stream(*args, **kwargs):
        yield mock_sse_event
        # Simulate final response
        final_response_data = {"type": "final_response", "data": {"final_key": "final_value"}}
        yield SSEEvent(data=json.dumps(final_response_data))


    with patch('aconnect_sse.SSEClient', spec=SSEClient) as mock_sse_client_constructor:
        mock_sse_client_instance = MagicMock(spec=SSEClient)
        mock_sse_client_instance.__aiter__.return_value = mock_event_stream()
        mock_sse_client_constructor.return_value = mock_sse_client_instance

        responses = []
        async for response in mock_agent_gateway.invoke_agent_sse("test_agent_sse", {"input": "data_sse"}):
            responses.append(response)

        assert len(responses) == 2
        assert isinstance(responses[0], PartialResponse)
        assert responses[0].response == mock_event_data
        assert isinstance(responses[1], InvokeResponse) # Assuming final response is an InvokeResponse
        assert responses[1].response == {"final_key": "final_value"}

        mock_sse_client_constructor.assert_called_once_with(
            "http://fakeagent.com/test_agent_sse/invoke_stream",
            json={"input": "data_sse"},
            headers={'Accept': 'text/event-stream'},
            timeout=AgentGateway.DEFAULT_TIMEOUT
        )


@pytest.mark.asyncio
async def test_invoke_agent_sse_with_keepalive_and_partial_final(mock_agent_gateway):
    partial_data = {"content": "partial data"}
    final_data = {"answer": "final answer"}
    keepalive_msg = KeepaliveMessage()

    async def mock_event_stream(*args, **kwargs):
        # Keepalive
        yield SSEEvent(data=json.dumps(keepalive_msg.model_dump()), event="keepalive")
        # Partial
        yield SSEEvent(data=json.dumps({"type": "partial_response", "data": partial_data}))
        # Final
        yield SSEEvent(data=json.dumps({"type": "final_response", "data": final_data}))

    with patch('aconnect_sse.SSEClient', spec=SSEClient) as mock_sse_client_constructor:
        mock_sse_client_instance = MagicMock(spec=SSEClient)
        mock_sse_client_instance.__aiter__.return_value = mock_event_stream()
        mock_sse_client_constructor.return_value = mock_sse_client_instance

        responses = []
        async for response in mock_agent_gateway.invoke_agent_sse("test_agent_sse", {"input": "data_sse"}):
            responses.append(response)

        assert len(responses) == 3
        assert isinstance(responses[0], KeepaliveMessage)
        assert isinstance(responses[1], PartialResponse)
        assert responses[1].response == partial_data
        assert isinstance(responses[2], InvokeResponse)
        assert responses[2].response == final_data


@pytest.fixture
def mock_base_agent_builder():
    return BaseAgentBuilder(agent_registry_url="http://fakeregistry.com")

@pytest.mark.asyncio
async def test_build_agent_success(mock_base_agent_builder):
    agent_id = "test_agent"
    mock_description_response_data = {
        "id": agent_id,
        "name": "Test Agent",
        "description": "An agent for testing",
        "base_url": "http://fakeagent.com",
        "health_check_url": "/health",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "routes": [
            {
                "path": "/invoke",
                "verb": "post",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "name": "invoke"
            }
        ]
    }
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_description_response_data

    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        agent = await mock_base_agent_builder.build_agent(agent_id)

        assert isinstance(agent, BaseAgent)
        assert agent.id == agent_id
        assert agent.name == "Test Agent"
        assert agent.base_url == "http://fakeagent.com"
        assert len(agent.routes) == 1
        assert agent.routes[0].name == "invoke"
        mock_get.assert_called_once_with(f"http://fakeregistry.com/agents/{agent_id}/openapi.json")


@pytest.mark.asyncio
async def test_build_agent_fetch_description_fails(mock_base_agent_builder):
    agent_id = "test_agent_fail"
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock(status_code=404))

        with pytest.raises(httpx.HTTPStatusError):
            await mock_base_agent_builder.build_agent(agent_id)

        mock_get.assert_called_once_with(f"http://fakeregistry.com/agents/{agent_id}/openapi.json")
