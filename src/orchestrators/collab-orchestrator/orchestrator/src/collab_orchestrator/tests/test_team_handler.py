import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY

from collab_orchestrator.team_handler.team_handler import TeamHandler
from collab_orchestrator.team_handler.conversation import Conversation, ConversationItem, Role
from collab_orchestrator.team_handler.manager_agent import ManagerAgent, ManagerOutput, Action, AssignTaskOutput, ResultOutput, AbortOutput, ConversationMessage, TeamBaseAgent, ManagerInput
from collab_orchestrator.team_handler.task_executor import TaskExecutor
from collab_orchestrator.co_types import BaseMultiModalInput, BaseConfig, EventType, AbortResult, ErrorResponse, TokenUsage, InvokeResponse, MultiModalItem, HistoryMultiModalMessage, KeepaliveMessage, PreRequisite
from collab_orchestrator.agents import AgentGateway, BaseAgentBuilder, TaskAgent, BaseAgent, InvokableAgent
from ska_utils import Telemetry
import asyncio

# Tests for Conversation
def test_conversation_add_and_get_messages():
    convo = Conversation()
    item1 = ConversationItem(task_id="task1", round_id=1, role=Role.MANAGER, content="Assigning task 1", action_type=Action.ASSIGN_NEW_TASK)
    item2 = ConversationItem(task_id="task1", round_id=1, role=Role.AGENT, content="Result for task 1", action_type=Action.PROVIDE_RESULT, agent_id="agent1", agent_name="TestAgent")
    item3 = ConversationItem(task_id="task2", round_id=2, role=Role.MANAGER, content="Assigning task 2", action_type=Action.ASSIGN_NEW_TASK)

    convo.add_item(item1)
    convo.add_item(item2)
    convo.add_item(item3)

    assert len(convo.get_messages_for_task("task1")) == 2
    assert convo.get_messages_for_task("task1")[0].content == "Assigning task 1"
    assert convo.get_messages_for_task("task1")[1].content == "Result for task 1"
    assert len(convo.get_messages_for_task("task2")) == 1
    assert convo.get_messages_for_task("task2")[0].content == "Assigning task 2"
    assert len(convo.get_messages_for_task("task_nonexistent")) == 0

    assert len(convo.items) == 3


def test_conversation_to_prerequisites():
    convo = Conversation()
    # Manager assigns task1 to agent1
    manager_assign_item = ConversationItem(
        task_id="task1", round_id=1, role=Role.MANAGER, content="Do work for task1",
        action_type=Action.ASSIGN_NEW_TASK, agent_id="agent1", agent_name="SearchAgent"
    )
    convo.add_item(manager_assign_item)

    # agent1 provides result for task1
    agent_result_item = ConversationItem(
        task_id="task1", round_id=1, role=Role.AGENT, content="Search results for task1",
        action_type=Action.PROVIDE_RESULT, agent_id="agent1", agent_name="SearchAgent"
    )
    convo.add_item(agent_result_item)

    # Manager assigns task2 to agent2, dependent on task1
    manager_assign_item_2 = ConversationItem(
        task_id="task2", round_id=2, role=Role.MANAGER, content="Do work for task2 based on task1",
        action_type=Action.ASSIGN_NEW_TASK, agent_id="agent2", agent_name="SummaryAgent",
        prerequisites=[PreRequisite(task_id="task1", content="Search results for task1")] # This would be filled by manager normally
    )
    convo.add_item(manager_assign_item_2)


    prerequisites_for_task2 = convo.get_prerequisites_for_task("task2", ["task1"])
    assert len(prerequisites_for_task2) == 1
    assert prerequisites_for_task2[0].task_id == "task1"
    assert prerequisites_for_task2[0].content == "Search results for task1"

    # Test asking for a prerequisite that doesn't exist in the dependency list
    prerequisites_for_task2_wrong_dep = convo.get_prerequisites_for_task("task2", ["task_nonexistent"])
    assert len(prerequisites_for_task2_wrong_dep) == 0

    # Test for a task that has no agent results yet (should be empty)
    # Manager assigns task3
    manager_assign_item_3 = ConversationItem(
        task_id="task3", round_id=3, role=Role.MANAGER, content="Do work for task3",
        action_type=Action.ASSIGN_NEW_TASK, agent_id="agent1", agent_name="SearchAgent"
    )
    convo.add_item(manager_assign_item_3)
    prerequisites_for_task3 = convo.get_prerequisites_for_task("task3", ["task1"]) # Depends on task1
    # Even if task1 has a result, if task3's assignment didn't list it as a prereq for content,
    # or if task1's agent result is not what's needed, it might be empty or different.
    # The current logic of get_prerequisites_for_task is to fetch AGENT results for listed parent_task_ids.
    assert len(prerequisites_for_task3) == 1
    assert prerequisites_for_task3[0].task_id == "task1"
    assert prerequisites_for_task3[0].content == "Search results for task1"

    # Test for a task that has no parent dependencies listed
    prerequisites_for_task3_no_deps = convo.get_prerequisites_for_task("task3", [])
    assert len(prerequisites_for_task3_no_deps) == 0


# Fixtures for ManagerAgent and TeamHandler
@pytest.fixture
def mock_invokable_agent_gateway():
    # This gateway is used by ManagerAgent to call the underlying LLM model
    gateway = MagicMock(spec=AgentGateway)
    # Simulate the LLM call within ManagerAgent
    async def mock_invoke_llm(*args, **kwargs):
        # Based on input, decide what the manager "LLM" would say
        input_json = kwargs.get("json", {})
        if "Assign a new task" in input_json.get("objective", ""):
            return InvokeResponse(
                response={
                    "action": {
                        "type": Action.ASSIGN_NEW_TASK.value,
                        "task_id": "task_llm_generated_1",
                        "agent_id": "search_agent_id",
                        "agent_name": "SearchAgent",
                        "inputs": {"query": "What is AI?"},
                        "reasoning": "Need to find info about AI."
                    }
                },
                token_usage=TokenUsage(total_tokens=50)
            )
        elif "Provide the final result" in input_json.get("objective", ""):
            return InvokeResponse(
                response={
                    "action": {
                        "type": Action.PROVIDE_RESULT.value,
                        "content": "Final answer is AI is complex.",
                        "reasoning": "Summarized all findings."
                    }
                },
                token_usage=TokenUsage(total_tokens=30)
            )
        return InvokeResponse(response={}, token_usage=TokenUsage(total_tokens=10)) # Default fallback

    gateway.invoke_agent = AsyncMock(side_effect=mock_invoke_llm)
    return gateway

@pytest.fixture
def manager_agent(mock_invokable_agent_gateway): # Renamed from mock_agent_gateway to be specific
    # This is the "LLM" agent config that ManagerAgent itself uses
    llm_agent_config = BaseAgent(
        id="manager_llm_agent",
        name="ManagerLLMAgent",
        description="LLM used by Manager",
        base_url="http://fakellm.com",
        input_schema={},
        output_schema={},
        routes=[], # Simplified, ManagerAgent uses a direct invoke
        token_cost_str="unknown" # Add this missing field
    )
    return ManagerAgent(
        agent_id="manager_llm_agent", # This is the ID of the LLM agent *used by* the ManagerAgent
        agent_gateway=mock_invokable_agent_gateway, # Gateway to call the above LLM
        model_config=None, # Assuming ManagerAgent handles this or it's not critical for these tests
        instance_id="test_manager_instance",
        parent_request_id="test_parent_req",
        base_agent=llm_agent_config # Pass the BaseAgent model for the LLM
    )

# Tests for ManagerAgent
@pytest.mark.asyncio
async def test_manager_agent_determine_next_action_assign(manager_agent):
    user_input = BaseMultiModalInput(text="Assign a new task about AI")
    conversation_history = []
    available_agents = [TeamBaseAgent(id="search_agent_id", name="SearchAgent", description="Searches web")]

    manager_input = ManagerInput(
        objective="Assign a new task about AI",
        conversation_history=conversation_history,
        agents=available_agents,
        user_input=user_input.text # Pass only text as per ManagerInput model
    )

    action_response = await manager_agent.determine_next_action(
        manager_input=manager_input,
        request_id="req1",
        session_id="sess1",
        interaction_id="inter1"
    )

    assert isinstance(action_response, ManagerOutput)
    assert isinstance(action_response.action, AssignTaskOutput)
    assert action_response.action.type == Action.ASSIGN_NEW_TASK
    assert action_response.action.agent_id == "search_agent_id"
    assert action_response.action.inputs == {"query": "What is AI?"}
    assert action_response.token_usage.total_tokens == 50


@pytest.mark.asyncio
async def test_manager_agent_determine_next_action_result(manager_agent):
    user_input = BaseMultiModalInput(text="Provide the final result based on findings.")
    # Simulate a conversation item where an agent provided some data
    previous_agent_response = ConversationMessage(
        role="AGENT",
        name="SearchAgent",
        content="AI is a field of computer science.",
        task_id="task_llm_generated_1" # Matches the task ID from the mocked LLM response
    )
    conversation_history = [previous_agent_response]
    available_agents = [TeamBaseAgent(id="search_agent_id", name="SearchAgent", description="Searches web")]

    manager_input = ManagerInput(
        objective="Provide the final result based on findings.",
        conversation_history=conversation_history,
        agents=available_agents,
        user_input=user_input.text
    )

    action_response = await manager_agent.determine_next_action(
        manager_input=manager_input,
        request_id="req2",
        session_id="sess2",
        interaction_id="inter2"
    )

    assert isinstance(action_response, ManagerOutput)
    assert isinstance(action_response.action, ResultOutput)
    assert action_response.action.type == Action.PROVIDE_RESULT
    assert action_response.action.content == "Final answer is AI is complex."
    assert action_response.token_usage.total_tokens == 30


# Fixtures for TeamHandler (continuing from ManagerAgent fixtures)
@pytest.fixture
def mock_task_executor():
    executor = MagicMock(spec=TaskExecutor)
    # Simulate execute_task_sse to yield InvokeResponse for non-streamed, and stream for streamed
    async def mock_execute_task_logic(task, request_id, session_id, interaction_id, config, conversation, event_callback, token_callback, stream_tokens):
        event_callback(type=EventType.AGENT_TASK_START, data={"task_id": task.id, "agent_id": task.agent_id, "inputs": task.inputs})
        await asyncio.sleep(0.01) # simulate async work
        result_content = f"Result for {task.id} by {task.agent_id}"
        token_usage = TokenUsage(total_tokens=20, prompt_tokens=10, completion_tokens=10)

        if stream_tokens:
            yield KeepaliveMessage()
            yield InvokeResponse(response={"partial_output": result_content[:10]}, token_usage=None) # Simulate partial
            await asyncio.sleep(0.01)
            yield InvokeResponse(response={"final_output": result_content}, token_usage=token_usage) # Simulate final
        else:
            yield InvokeResponse(response={"full_output": result_content}, token_usage=token_usage)

        event_callback(type=EventType.AGENT_TASK_END, data={"task_id": task.id, "result": {"full_output": result_content}}) # Assume full result for event
        token_callback(token_usage) # Ensure token callback is made

    executor.execute_task_sse = mock_execute_task_logic # Use for both stream/non-stream for simplicity in mock
    # For non-SSE execute_task (if ever directly called, though handler uses SSE version)
    executor.execute_task = AsyncMock(return_value=(InvokeResponse(response={"full_output": "non_sse_result"}, token_usage=TokenUsage(total_tokens=15)), "non_sse_result"))
    return executor

@pytest.fixture
def mock_base_agent_builder(): # This is for the TeamHandler to build the ManagerAgent
    builder = MagicMock(spec=BaseAgentBuilder)
    # It doesn't directly build TaskAgents, TaskExecutor does, but ManagerAgent needs its LLM agent
    # So this mock is primarily for ManagerAgent's LLM dependency if TeamHandler were to build it directly.
    # However, manager_agent fixture already creates a ManagerAgent with its own gateway.
    # Let's assume TeamHandler gets a factory or direct instance of ManagerAgent.
    # For this test structure, TeamHandler will receive an already configured manager_agent.
    return builder


@pytest.fixture
def mock_telemetry():
    telemetry = MagicMock(spec=Telemetry)
    telemetry.emit_event = MagicMock()
    telemetry.emit_error_event = MagicMock()
    return telemetry

@pytest.fixture
def team_handler(manager_agent, mock_task_executor, mock_base_agent_builder, mock_telemetry): # Removed mock_agent_gateway as it's not directly used by TeamHandler if manager_agent is pre-configured
    # Assume ManagerAgent is passed pre-configured or via a factory that uses its own gateway
    return TeamHandler(
        manager_agent=manager_agent, # Pass the already configured manager_agent
        task_executor=mock_task_executor,
        agent_builder=mock_base_agent_builder, # For resolving TaskAgent details if needed by TaskExecutor, though TaskExecutor mock handles it now
        telemetry=mock_telemetry,
        max_rounds=5
    )

async def collect_events_from_handler(async_gen):
    return [event async for event in async_gen]

# Tests for TeamHandler
@pytest.mark.asyncio
async def test_team_handler_invoke_success_assign_result(team_handler, manager_agent, mock_task_executor):
    user_input = BaseMultiModalInput(text="Solve a complex problem.")
    config = BaseConfig(interaction_id="th_i1", available_agents=[ # Pass available agents in config
        TeamBaseAgent(id="search_agent_id", name="SearchAgent", description="Searches web"),
        TeamBaseAgent(id="summary_agent_id", name="SummaryAgent", description="Summarizes text")
    ])
    request_id = "th_r1"

    # Mock ManagerAgent sequence: Assign -> Result
    assign_action = AssignTaskOutput(
        type=Action.ASSIGN_NEW_TASK, task_id="task1", agent_id="search_agent_id", agent_name="SearchAgent",
        inputs={"query": "info"}, reasoning="search first", prerequisites=[]
    )
    result_action = ResultOutput(
        type=Action.PROVIDE_RESULT, content="Final solution", reasoning="all done"
    )
    manager_agent.determine_next_action = AsyncMock(side_effect=[
        ManagerOutput(action=assign_action, token_usage=TokenUsage(total_tokens=50)),
        ManagerOutput(action=result_action, token_usage=TokenUsage(total_tokens=30))
    ])

    events = await collect_events_from_handler(team_handler.invoke(request_id, user_input, config, []))

    assert any(e.type == EventType.TEAM_EXECUTION_START for e in events)
    assert any(e.type == EventType.MANAGER_ACTION_START and e.data["action_type"] == Action.ASSIGN_NEW_TASK for e in events)
    assert any(e.type == EventType.AGENT_TASK_START and e.data["task_id"] == "task1" for e in events)
    assert any(e.type == EventType.AGENT_TASK_END and e.data["task_id"] == "task1" for e in events)
    assert any(e.type == EventType.MANAGER_ACTION_END and e.data["action_type"] == Action.ASSIGN_NEW_TASK for e in events)
    assert any(e.type == EventType.MANAGER_ACTION_START and e.data["action_type"] == Action.PROVIDE_RESULT for e in events)
    assert any(e.type == EventType.MANAGER_ACTION_END and e.data["action_type"] == Action.PROVIDE_RESULT for e in events)
    final_result_events = [e for e in events if isinstance(e, InvokeResponse) and e.response.get("full_output") == "Final solution"] # Check if ResultOutput content is passed as final InvokeResponse
    # The final InvokeResponse should be the content from ResultOutput
    final_invoke_response = next(e for e in events if isinstance(e, InvokeResponse) and e.is_final)
    assert final_invoke_response.response == "Final solution"

    assert any(e.type == EventType.TEAM_EXECUTION_END for e in events)
    team_handler.telemetry.emit_event.assert_any_call(event_name="TeamExecutionStart", event_data=ANY)
    team_handler.telemetry.emit_event.assert_any_call(event_name="TeamExecutionEnd", event_data=ANY)
    assert manager_agent.determine_next_action.call_count == 2
    # mock_task_executor.execute_task_sse was called once by the handler for the single ASSIGN_NEW_TASK
    # To assert this, we need to inspect the mock's calls. The current mock_execute_task_logic doesn't lend itself to easy call count per task.
    # A more robust way would be to have execute_task_sse be an AsyncMock itself, and then check its call_args_list or call_count.
    # For now, we'll rely on the event sequence.


@pytest.mark.asyncio
async def test_team_handler_invoke_abort(team_handler, manager_agent):
    user_input = BaseMultiModalInput(text="This should be aborted.")
    config = BaseConfig(interaction_id="th_i2", available_agents=[TeamBaseAgent(id="a1", name="A1", description="d1")])
    request_id = "th_r2"

    abort_action = AbortOutput(type=Action.ABORT, reason="User request cannot be fulfilled.")
    manager_agent.determine_next_action = AsyncMock(return_value=ManagerOutput(action=abort_action, token_usage=TokenUsage(total_tokens=20)))

    events = await collect_events_from_handler(team_handler.invoke(request_id, user_input, config, []))

    assert any(e.type == EventType.MANAGER_ACTION_START and e.data["action_type"] == Action.ABORT for e in events)
    assert any(e.type == EventType.MANAGER_ACTION_END and e.data["action_type"] == Action.ABORT for e in events)
    final_abort_event = next(e for e in events if isinstance(e, AbortResult))
    assert final_abort_event.reason == "User request cannot be fulfilled."
    assert any(e.type == EventType.TEAM_EXECUTION_END for e in events) # Still ends gracefully
    team_handler.telemetry.emit_event.assert_any_call(event_name="TeamExecutionAbort", event_data=ANY)


@pytest.mark.asyncio
async def test_team_handler_invoke_max_rounds_exceeded(team_handler, manager_agent):
    team_handler.max_rounds = 1 # Set low for test
    user_input = BaseMultiModalInput(text="This will exceed max rounds.")
    config = BaseConfig(interaction_id="th_i3", available_agents=[TeamBaseAgent(id="a1", name="A1", description="d1")])
    request_id = "th_r3"

    # Manager keeps assigning tasks
    assign_action = AssignTaskOutput(type=Action.ASSIGN_NEW_TASK, task_id="task_loop", agent_id="a1", agent_name="A1", inputs={}, reasoning="loop", prerequisites=[])
    manager_agent.determine_next_action = AsyncMock(return_value=ManagerOutput(action=assign_action, token_usage=TokenUsage(total_tokens=10)))

    events = await collect_events_from_handler(team_handler.invoke(request_id, user_input, config, []))

    # Should have one assign action, then error
    assert any(e.type == EventType.MANAGER_ACTION_START and e.data["action_type"] == Action.ASSIGN_NEW_TASK for e in events)
    final_error_event = next(e for e in events if isinstance(e, ErrorResponse))
    assert "Maximum team execution rounds (1) exceeded." in final_error_event.error
    team_handler.telemetry.emit_error_event.assert_called_once_with(event_name="TeamExecutionMaxRoundsExceeded", error_message=ANY, event_data=ANY)


@pytest.mark.asyncio
async def test_team_handler_invoke_manager_exception(team_handler, manager_agent):
    user_input = BaseMultiModalInput(text="Manager will fail.")
    config = BaseConfig(interaction_id="th_i4", available_agents=[])
    request_id = "th_r4"

    manager_agent.determine_next_action = AsyncMock(side_effect=Exception("Manager LLM exploded"))

    events = await collect_events_from_handler(team_handler.invoke(request_id, user_input, config, []))

    final_error_event = next(e for e in events if isinstance(e, ErrorResponse))
    assert "An unexpected error occurred in Manager Agent: Manager LLM exploded" in final_error_event.error
    team_handler.telemetry.emit_error_event.assert_called_once_with(event_name="TeamExecutionManagerError", error_message=ANY, event_data=ANY)


@pytest.mark.asyncio
async def test_team_handler_invoke_task_executor_exception(team_handler, manager_agent, mock_task_executor):
    user_input = BaseMultiModalInput(text="Task executor will fail.")
    config = BaseConfig(interaction_id="th_i5", available_agents=[TeamBaseAgent(id="a1", name="A1", description="d1")])
    request_id = "th_r5"

    assign_action = AssignTaskOutput(type=Action.ASSIGN_NEW_TASK, task_id="task_fail", agent_id="a1", agent_name="A1", inputs={}, reasoning="fail this", prerequisites=[])
    manager_agent.determine_next_action = AsyncMock(return_value=ManagerOutput(action=assign_action, token_usage=TokenUsage(total_tokens=10)))

    # Make the mock_task_executor's relevant method raise an error
    mock_task_executor.execute_task_sse = AsyncMock(side_effect=Exception("Task execution failed badly"))
    # If execute_task_sse is an async generator, the exception needs to be raised when it's iterated
    async def failing_generator(*args, **kwargs):
        raise Exception("Task execution failed badly from generator")
        yield # to make it a generator
    mock_task_executor.execute_task_sse = failing_generator


    events = await collect_events_from_handler(team_handler.invoke(request_id, user_input, config, []))

    final_error_event = next(e for e in events if isinstance(e, ErrorResponse))
    assert "An unexpected error occurred during task execution (task_fail): Task execution failed badly from generator" in final_error_event.error
    team_handler.telemetry.emit_error_event.assert_called_once_with(event_name="TeamExecutionTaskError", error_message=ANY, event_data=ANY)


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_tokens_enabled", [True, False])
async def test_team_handler_invoke_stream_tokens_toggle(team_handler, manager_agent, mock_task_executor, stream_tokens_enabled):
    user_input = BaseMultiModalInput(text="Test streaming.")
    config = BaseConfig(interaction_id="th_i6", stream_tokens=stream_tokens_enabled, available_agents=[TeamBaseAgent(id="search_agent_id", name="SA", description="d")])
    request_id = "th_r6"

    assign_action = AssignTaskOutput(
        type=Action.ASSIGN_NEW_TASK, task_id="task_stream", agent_id="search_agent_id", agent_name="SA",
        inputs={"query": "stream test"}, reasoning="test streaming", prerequisites=[]
    )
    result_action = ResultOutput(type=Action.PROVIDE_RESULT, content="Streamed result", reasoning="done streaming")

    manager_agent.determine_next_action = AsyncMock(side_effect=[
        ManagerOutput(action=assign_action, token_usage=TokenUsage(total_tokens=50)),
        ManagerOutput(action=result_action, token_usage=TokenUsage(total_tokens=30))
    ])

    # We need to ensure the mock_task_executor.execute_task_sse behaves as expected for streaming
    # The current mock_execute_task_logic in the fixture already differentiates.

    events = await collect_events_from_handler(team_handler.invoke(request_id, user_input, config, []))

    if stream_tokens_enabled:
        assert any(isinstance(e, KeepaliveMessage) for e in events)
        # Check for partial InvokeResponse (which would not have is_final=True if it's truly partial)
        # The mock sends one partial then one final.
        partial_responses = [e for e in events if isinstance(e, InvokeResponse) and e.response.get("partial_output") and not e.is_final]
        final_task_responses = [e for e in events if isinstance(e, InvokeResponse) and e.response.get("final_output") and e.is_final]
        assert len(partial_responses) > 0 or len(final_task_responses) > 0 # Depending on how mock is structured for final part of stream
    else: # Not streaming
        assert not any(isinstance(e, KeepaliveMessage) for e in events)
        # Expect a single InvokeResponse from the task which is final
        task_responses = [e for e in events if isinstance(e, InvokeResponse) and e.response.get("full_output") and e.is_final]
        assert len(task_responses) > 0

    final_result_event = next(e for e in events if isinstance(e, InvokeResponse) and e.is_final and e.response == "Streamed result")
    assert final_result_event is not None
