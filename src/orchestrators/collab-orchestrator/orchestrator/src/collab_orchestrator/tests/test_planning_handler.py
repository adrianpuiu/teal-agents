import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from collab_orchestrator.planning_handler.planning_handler import PlanningHandler, PlanningFailedException
from collab_orchestrator.planning_handler.plan import Plan, Step, ExecutableTask, TaskStatus
from collab_orchestrator.planning_handler.plan_manager import PlanManager
from collab_orchestrator.planning_handler.planning_agent import PlanningAgent, GeneratePlanResponse, PlanStep as AgentPlanStep, PlanTask as AgentPlanTask
from collab_orchestrator.co_types import BaseMultiModalInput, BaseConfig, EventType, AbortResult, ErrorResponse, TokenUsage, InvokeResponse, MultiModalItem, HitlResumeType
from collab_orchestrator.agents import AgentGateway, BaseAgentBuilder, TaskAgent, BaseAgent
from collab_orchestrator.step_executor import StepExecutor
from collab_orchestrator.pending_plan_store import PendingPlanStore
from ska_utils import Telemetry
import asyncio


# Fixtures for Plan and PlanManager
@pytest.fixture
def mock_generate_plan_response_dict():
    return {
        "plan": [
            {
                "id": "step1",
                "reasoning": "First step",
                "tasks": [
                    {
                        "id": "task1_1",
                        "name": "agent_search",
                        "reasoning": "Search for information",
                        "agent_id": "search_agent",
                        "inputs": {"query": "Python"},
                        "critique": [],
                        "outputs_to_persist": ["search_results"],
                    }
                ],
            }
        ],
        "can_succeed": True,
        "should_wait_for_user": False,
        "token_usage": {"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50},
    }

@pytest.fixture
def mock_generate_plan_response(mock_generate_plan_response_dict):
    return GeneratePlanResponse(**mock_generate_plan_response_dict)

@pytest.fixture
def mock_planning_agent():
    agent = MagicMock(spec=PlanningAgent)
    agent.generate_plan = AsyncMock()
    return agent

@pytest.fixture
def mock_agent_gateway():
    return MagicMock(spec=AgentGateway)

@pytest.fixture
def mock_base_agent_builder(mock_agent_gateway): # Added mock_agent_gateway dependency
    builder = MagicMock(spec=BaseAgentBuilder)
    # Simulate build_agent returning a mock TaskAgent
    mock_task_agent_instance = MagicMock(spec=TaskAgent)
    mock_task_agent_instance.invoke = AsyncMock(return_value=InvokeResponse(response={"result": "task completed"}))
    builder.build_agent = AsyncMock(return_value=mock_task_agent_instance)
    return builder


@pytest.fixture
def plan_manager(mock_planning_agent, mock_base_agent_builder, mock_agent_gateway):
    return PlanManager(
        planning_agent=mock_planning_agent,
        agent_builder=mock_base_agent_builder,
        agent_gateway=mock_agent_gateway # Pass it here
    )


# Tests for Plan
def test_plan_creation_from_response(mock_generate_plan_response):
    plan = Plan.from_generate_plan_response(mock_generate_plan_response)
    assert len(plan.steps) == 1
    step1 = plan.steps[0]
    assert step1.id == "step1"
    assert step1.reasoning == "First step"
    assert len(step1.tasks) == 1
    task1_1 = step1.tasks[0]
    assert isinstance(task1_1, ExecutableTask)
    assert task1_1.id == "task1_1"
    assert task1_1.name == "agent_search"
    assert task1_1.agent_id == "search_agent"
    assert task1_1.inputs == {"query": "Python"}
    assert task1_1.status == TaskStatus.PENDING

# Tests for PlanManager
@pytest.mark.asyncio
async def test_plan_manager_generate_plan_success(plan_manager, mock_planning_agent, mock_generate_plan_response):
    mock_planning_agent.generate_plan.return_value = mock_generate_plan_response
    request_id = "test_req_id"
    user_input = BaseMultiModalInput(session_id="session1", interaction_id="inter1", text="Generate a plan")
    config = BaseConfig(interaction_id="inter1")

    plan, token_usage, should_wait = await plan_manager.generate_plan(request_id, user_input, config, [])

    assert isinstance(plan, Plan)
    assert len(plan.steps) == 1
    assert token_usage.total_tokens == 100
    assert not should_wait
    mock_planning_agent.generate_plan.assert_called_once()

@pytest.mark.asyncio
async def test_plan_manager_generate_plan_cannot_succeed(plan_manager, mock_planning_agent, mock_generate_plan_response_dict):
    cannot_succeed_response_dict = mock_generate_plan_response_dict.copy()
    cannot_succeed_response_dict["can_succeed"] = False
    cannot_succeed_response = GeneratePlanResponse(**cannot_succeed_response_dict)
    mock_planning_agent.generate_plan.return_value = cannot_succeed_response

    request_id = "test_req_id_fail"
    user_input = BaseMultiModalInput(session_id="session1", interaction_id="inter1", text="Generate a plan that fails")
    config = BaseConfig(interaction_id="inter1")

    with pytest.raises(PlanningFailedException) as excinfo:
        await plan_manager.generate_plan(request_id, user_input, config, [])

    assert "Planning agent indicated that the plan cannot succeed." in str(excinfo.value)
    mock_planning_agent.generate_plan.assert_called_once()


# Fixtures for PlanningHandler
@pytest.fixture
def mock_step_executor():
    executor = MagicMock(spec=StepExecutor)
    # Simulate execute_step_sse to yield some results and then complete
    async def mock_execute_step_sse_logic(step, request_id, config, session_id, interaction_id, user_input, current_plan, event_callback, token_callback, history, tools_results):
        event_callback(type=EventType.STEP_EXECUTION_START, data={"step_id": step.id})
        # Simulate task execution within the step
        for task in step.tasks:
            event_callback(type=EventType.TASK_EXECUTION_START, data={"task_id": task.id, "agent_id": task.agent_id})
            # Mock the actual task invocation (which would be done by TaskAgent via AgentGateway)
            await asyncio.sleep(0.01) # simulate async work
            task_result = {"output": f"result from {task.agent_id} for {task.inputs}"}
            # Yield partial response if agent supports it, then final InvokeResponse
            yield InvokeResponse(response=task_result, token_usage=TokenUsage(total_tokens=10))
            event_callback(type=EventType.TASK_EXECUTION_END, data={"task_id": task.id, "result": task_result})
        event_callback(type=EventType.STEP_EXECUTION_END, data={"step_id": step.id})
        # No explicit return, step executor manages state via callbacks and plan updates.

    executor.execute_step_sse = mock_execute_step_sse_logic
    return executor

@pytest.fixture
def mock_pending_plan_store():
    store = MagicMock(spec=PendingPlanStore)
    store.get_pending_plan = AsyncMock(return_value=None) # Default to no pending plan
    store.save_pending_plan = AsyncMock()
    store.delete_pending_plan = AsyncMock()
    return store

@pytest.fixture
def mock_telemetry():
    telemetry = MagicMock(spec=Telemetry)
    telemetry.emit_event = MagicMock()
    telemetry.emit_error_event = MagicMock()
    return telemetry

@pytest.fixture
def planning_handler(plan_manager, mock_step_executor, mock_pending_plan_store, mock_telemetry):
    return PlanningHandler(
        plan_manager=plan_manager,
        step_executor=mock_step_executor,
        pending_plan_store=mock_pending_plan_store,
        telemetry=mock_telemetry,
        enable_hitl=False # Default to HITL disabled for most tests
    )

@pytest.fixture
def planning_handler_hitl_enabled(plan_manager, mock_step_executor, mock_pending_plan_store, mock_telemetry):
    return PlanningHandler(
        plan_manager=plan_manager,
        step_executor=mock_step_executor,
        pending_plan_store=mock_pending_plan_store,
        telemetry=mock_telemetry,
        enable_hitl=True,
        hitl_timeout_seconds=1 # Use a short timeout for testing
    )


# Helper to collect events from the async generator
async def collect_events(async_gen):
    return [event async for event in async_gen]

# Tests for PlanningHandler
@pytest.mark.asyncio
async def test_planning_handler_invoke_success(planning_handler, plan_manager, mock_generate_plan_response, mock_step_executor):
    plan_manager.generate_plan = AsyncMock(return_value=(
        Plan.from_generate_plan_response(mock_generate_plan_response),
        mock_generate_plan_response.token_usage,
        False
    ))

    request_id = "test_invoke_success"
    user_input = BaseMultiModalInput(session_id="s1", interaction_id="i1", text="Do something")
    config = BaseConfig(interaction_id="i1")

    event_stream = planning_handler.invoke(request_id, user_input, config, [])
    events = await collect_events(event_stream)

    assert any(e.type == EventType.PLAN_GENERATION_END for e in events)
    assert any(e.type == EventType.STEP_EXECUTION_START for e in events)
    assert any(e.type == EventType.TASK_EXECUTION_START for e in events)
    assert any(e.type == EventType.TASK_EXECUTION_END for e in events)
    assert any(e.type == EventType.STEP_EXECUTION_END for e in events)
    assert any(e.type == EventType.PLAN_EXECUTION_END for e in events)
    # Check that telemetry was called for plan generation and execution
    planning_handler.telemetry.emit_event.assert_any_call(event_name="PlanGenerationEnd", event_data=ANY)
    planning_handler.telemetry.emit_event.assert_any_call(event_name="PlanExecutionEnd", event_data=ANY)


@pytest.mark.asyncio
async def test_planning_handler_invoke_plan_generation_fails_planningfailedexception(planning_handler, plan_manager):
    plan_manager.generate_plan = AsyncMock(side_effect=PlanningFailedException("Test planning failure"))

    request_id = "test_plan_fail_pfex"
    user_input = BaseMultiModalInput(session_id="s2", interaction_id="i2", text="Fail this plan")
    config = BaseConfig(interaction_id="i2")

    event_stream = planning_handler.invoke(request_id, user_input, config, [])
    events = await collect_events(event_stream)

    assert len(events) == 1
    assert isinstance(events[0], ErrorResponse)
    assert events[0].error == "Planning failed: Test planning failure"
    planning_handler.telemetry.emit_error_event.assert_called_once()


@pytest.mark.asyncio
async def test_planning_handler_invoke_plan_generation_fails_generic_exception(planning_handler, plan_manager):
    plan_manager.generate_plan = AsyncMock(side_effect=Exception("Generic planning error"))

    request_id = "test_plan_fail_generic"
    user_input = BaseMultiModalInput(session_id="s3", interaction_id="i3", text="Generic fail")
    config = BaseConfig(interaction_id="i3")

    event_stream = planning_handler.invoke(request_id, user_input, config, [])
    events = await collect_events(event_stream)

    assert len(events) == 1
    assert isinstance(events[0], ErrorResponse)
    assert "An unexpected error occurred during planning" in events[0].error
    planning_handler.telemetry.emit_error_event.assert_called_once()


@pytest.mark.asyncio
async def test_planning_handler_invoke_step_execution_fails(planning_handler, plan_manager, mock_generate_plan_response, mock_step_executor):
    plan_manager.generate_plan = AsyncMock(return_value=(
        Plan.from_generate_plan_response(mock_generate_plan_response),
        mock_generate_plan_response.token_usage,
        False
    ))
    mock_step_executor.execute_step_sse = AsyncMock(side_effect=Exception("Step execution error")) # Make it an async mock

    request_id = "test_step_fail"
    user_input = BaseMultiModalInput(session_id="s4", interaction_id="i4", text="Fail step exec")
    config = BaseConfig(interaction_id="i4")

    event_stream = planning_handler.invoke(request_id, user_input, config, [])

    # Need to actually iterate through the generator for the code to run
    final_event = None
    try:
        async for event in event_stream:
            final_event = event
    except Exception as e: # Catch the exception that the handler is supposed to yield as ErrorResponse
         assert isinstance(e, Exception) # Should not happen if handler catches it

    assert final_event is not None
    assert isinstance(final_event, ErrorResponse)
    assert "An unexpected error occurred during step execution" in final_event.error
    planning_handler.telemetry.emit_error_event.assert_called_once()


# HITL Tests
@pytest.mark.asyncio
async def test_planning_handler_hitl_plan_approval(planning_handler_hitl_enabled, plan_manager, mock_generate_plan_response, mock_pending_plan_store):
    hitl_plan_response = mock_generate_plan_response.model_copy(update={"should_wait_for_user": True})
    generated_plan = Plan.from_generate_plan_response(hitl_plan_response)
    plan_manager.generate_plan = AsyncMock(return_value=(
        generated_plan,
        hitl_plan_response.token_usage,
        True # should_wait_for_user
    ))

    request_id = "test_hitl_approve"
    user_input = BaseMultiModalInput(session_id="s_hitl1", interaction_id="i_hitl1", text="Plan for HITL approval")
    config = BaseConfig(interaction_id="i_hitl1", request_id=request_id) # Ensure request_id in config for HITL

    # 1. Initial call to generate plan and get PLAN_APPROVAL_PENDING
    event_stream_initial = planning_handler_hitl_enabled.invoke(request_id, user_input, config, [])
    initial_events = await collect_events(event_stream_initial)

    assert any(e.type == EventType.PLAN_APPROVAL_PENDING for e in initial_events)
    pending_event = next(e for e in initial_events if e.type == EventType.PLAN_APPROVAL_PENDING)
    assert pending_event.data["plan"] is not None
    mock_pending_plan_store.save_pending_plan.assert_called_once()
    original_plan_dict = pending_event.data["plan"]

    # 2. Simulate user approving - by calling invoke again with resume_type=APPROVE
    mock_pending_plan_store.get_pending_plan.return_value = (generated_plan, user_input, config, []) # Simulate plan was stored

    user_input_approve = BaseMultiModalInput(
        session_id="s_hitl1",
        interaction_id="i_hitl1_approve",
        text="Approve", # User text can be anything, resume_type drives it
        hitl_resume_type=HitlResumeType.APPROVE,
        approved_plan=original_plan_dict # Send back the original plan
    )
    config_approve = BaseConfig(interaction_id="i_hitl1_approve", request_id=request_id)

    event_stream_resume = planning_handler_hitl_enabled.invoke(request_id, user_input_approve, config_approve, [])
    resume_events = await collect_events(event_stream_resume)

    assert any(e.type == EventType.PLAN_APPROVED for e in resume_events)
    assert any(e.type == EventType.PLAN_EXECUTION_START for e in resume_events)
    assert any(e.type == EventType.PLAN_EXECUTION_END for e in resume_events)
    mock_pending_plan_store.delete_pending_plan.assert_called_with(request_id)


@pytest.mark.asyncio
async def test_planning_handler_hitl_plan_cancellation(planning_handler_hitl_enabled, plan_manager, mock_generate_plan_response, mock_pending_plan_store):
    hitl_plan_response = mock_generate_plan_response.model_copy(update={"should_wait_for_user": True})
    generated_plan = Plan.from_generate_plan_response(hitl_plan_response)
    plan_manager.generate_plan = AsyncMock(return_value=(generated_plan, hitl_plan_response.token_usage, True))

    request_id = "test_hitl_cancel"
    user_input = BaseMultiModalInput(session_id="s_hitl2", interaction_id="i_hitl2", text="Plan for HITL cancel")
    config = BaseConfig(interaction_id="i_hitl2", request_id=request_id)

    # 1. Initial call
    event_stream_initial = planning_handler_hitl_enabled.invoke(request_id, user_input, config, [])
    await collect_events(event_stream_initial) # Ensure save is called

    # 2. Simulate user cancelling
    mock_pending_plan_store.get_pending_plan.return_value = (generated_plan, user_input, config, [])
    user_input_cancel = BaseMultiModalInput(
        session_id="s_hitl2",
        interaction_id="i_hitl2_cancel",
        hitl_resume_type=HitlResumeType.CANCEL
    )
    config_cancel = BaseConfig(interaction_id="i_hitl2_cancel", request_id=request_id)

    event_stream_resume = planning_handler_hitl_enabled.invoke(request_id, user_input_cancel, config_cancel, [])
    resume_events = await collect_events(event_stream_resume)

    assert any(e.type == EventType.PLAN_CANCELLED for e in resume_events)
    assert not any(e.type == EventType.PLAN_EXECUTION_START for e in resume_events)
    mock_pending_plan_store.delete_pending_plan.assert_called_with(request_id)


@pytest.mark.asyncio
async def test_planning_handler_hitl_plan_edit(planning_handler_hitl_enabled, plan_manager, mock_generate_plan_response, mock_pending_plan_store):
    hitl_plan_response = mock_generate_plan_response.model_copy(update={"should_wait_for_user": True})
    original_plan = Plan.from_generate_plan_response(hitl_plan_response)
    plan_manager.generate_plan = AsyncMock(return_value=(original_plan, hitl_plan_response.token_usage, True))

    request_id = "test_hitl_edit"
    user_input = BaseMultiModalInput(session_id="s_hitl3", interaction_id="i_hitl3", text="Plan for HITL edit")
    config = BaseConfig(interaction_id="i_hitl3", request_id=request_id)

    # 1. Initial call
    initial_stream = planning_handler_hitl_enabled.invoke(request_id, user_input, config, [])
    initial_events = await collect_events(initial_stream)
    pending_event = next(e for e in initial_events if e.type == EventType.PLAN_APPROVAL_PENDING)
    original_plan_dict = pending_event.data["plan"]


    # 2. Simulate user editing - create a modified plan
    mock_pending_plan_store.get_pending_plan.return_value = (original_plan, user_input, config, [])
    edited_plan_dict = original_plan_dict.copy()
    edited_plan_dict["steps"][0]["reasoning"] = "Edited reasoning by user"
    # Ensure the edited plan still has valid structure for Plan.model_validate
    edited_plan_dict["steps"][0]["tasks"][0]["status"] = TaskStatus.PENDING.value # Make sure status is string

    user_input_edit = BaseMultiModalInput(
        session_id="s_hitl3",
        interaction_id="i_hitl3_edit",
        hitl_resume_type=HitlResumeType.EDIT,
        approved_plan=edited_plan_dict
    )
    config_edit = BaseConfig(interaction_id="i_hitl3_edit", request_id=request_id)

    # Mock that the edited plan is considered valid by PlanManager's validate_and_reconstruct_plan
    # For simplicity, we'll assume Plan.model_validate(edited_plan_dict) is enough for this test's scope
    # if PlanManager had more complex validation, that would need more specific mocking.
    # The handler itself calls Plan.model_validate.

    event_stream_resume = planning_handler_hitl_enabled.invoke(request_id, user_input_edit, config_edit, [])
    resume_events = await collect_events(event_stream_resume)

    assert any(e.type == EventType.PLAN_EDITED for e in resume_events)
    assert any(e.type == EventType.PLAN_EXECUTION_START for e in resume_events)
    # Check if the executed plan reflects the edit (e.g., via a new PLAN_EXECUTION_START with the edited plan)
    execution_start_event = next(e for e in resume_events if e.type == EventType.PLAN_EXECUTION_START)
    assert execution_start_event.data["plan"]["steps"][0]["reasoning"] == "Edited reasoning by user"
    mock_pending_plan_store.delete_pending_plan.assert_called_with(request_id)


@pytest.mark.asyncio
async def test_planning_handler_hitl_approval_timeout(planning_handler_hitl_enabled, plan_manager, mock_generate_plan_response, mock_pending_plan_store):
    planning_handler_hitl_enabled.hitl_timeout_seconds = 0.01 # very short for test
    hitl_plan_response = mock_generate_plan_response.model_copy(update={"should_wait_for_user": True})
    plan_manager.generate_plan = AsyncMock(return_value=(
        Plan.from_generate_plan_response(hitl_plan_response),
        hitl_plan_response.token_usage,
        True
    ))

    request_id = "test_hitl_timeout"
    user_input = BaseMultiModalInput(session_id="s_hitl4", interaction_id="i_hitl4", text="Plan for HITL timeout")
    config = BaseConfig(interaction_id="i_hitl4", request_id=request_id)

    event_stream = planning_handler_hitl_enabled.invoke(request_id, user_input, config, [])
    events = await collect_events(event_stream) # This will include the timeout event if logic is correct

    assert any(e.type == EventType.PLAN_APPROVAL_TIMEOUT for e in events)
    assert not any(e.type == EventType.PLAN_EXECUTION_START for e in events)
    mock_pending_plan_store.delete_pending_plan.assert_called_with(request_id)
    planning_handler_hitl_enabled.telemetry.emit_event.assert_any_call(event_name="HitlTimeout", event_data=ANY)

# Need to import ANY from unittest.mock for some assertions
from unittest.mock import ANY
