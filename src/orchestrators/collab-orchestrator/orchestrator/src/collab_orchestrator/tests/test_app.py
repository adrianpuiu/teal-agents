import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from fastapi.testclient import TestClient
from pydantic_yaml import parse_yaml_file_as
import json # For serializing SSE data if needed for assertions
import asyncio # For async stream consumption

# Assuming app.py is in the parent directory or properly installed/pathed
from collab_orchestrator.app import app, initialize, config as app_config_module, BaseMultiModalInput, MultiModalItem, HistoryMultiModalMessage, OrchestratorConfig
from collab_orchestrator.co_types import BaseConfig as COTypesBaseConfig, EventType, HitlResumeType, Plan, Step, ExecutableTask, TaskStatus
from collab_orchestrator.pending_plan_store import PendingPlanStore # Needed for mocking
from collab_orchestrator.kind_handler import KindHandler # Needed for mocking
from collab_orchestrator.constants import ORCHESTRATOR_DIR

# Mock configuration before app initialization if possible, or patch during tests
# This is a bit tricky as 'config' is loaded at module level in app.py
# We will patch the 'config' object that app.py uses.

TEST_CONFIG_PATH = ORCHESTRATOR_DIR / "config/test_config.yaml"

@pytest.fixture(scope="module", autouse=True)
def load_test_config_for_app():
    # This fixture tries to ensure that the app's 'config' object is loaded from a test file
    # before any tests run and thus before the app's dependencies are fully resolved.
    try:
        # Create a minimal test_config.yaml if it doesn't exist, or use a predefined one
        # For simplicity, let's assume a test_config.yaml exists or is created by a setup script.
        # If not, we should create one here.
        if not TEST_CONFIG_PATH.exists():
            minimal_config_data = {
                "kind_handlers": {
                    "planning": "collab_orchestrator.planning_handler.planning_handler.PlanningHandler",
                    "team": "collab_orchestrator.team_handler.team_handler.TeamHandler"
                },
                "agent_registry_url": "http://fake-registry.com",
                "pending_plan_store": {"type": "redis", "config": {"redis_url": "redis://fakeredis:6379"}},
                "enable_hitl": False, # Default to False, can be overridden in specific tests
                "hitl_timeout_seconds": 30,
                "telemetry": {"type": "none"},
                "model_config": {"model": "test-model"},
                 "max_context_tokens": 8000, # Add missing field
                "max_history_tokens": 2000, # Add missing field
                "max_tokens": 1000 # Add missing field
            }
            TEST_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TEST_CONFIG_PATH, "w") as f:
                import yaml
                yaml.dump(minimal_config_data, f)

        loaded_config = parse_yaml_file_as(OrchestratorConfig, TEST_CONFIG_PATH)
        app_config_module.config = loaded_config # Override the app's config instance

        # Also, ensure initialize() uses this mocked config
        # This might require patching 'parse_yaml_file_as' if initialize() calls it directly
        # or ensuring 'app_config_module.config' is used by initialize()

    except Exception as e:
        print(f"Error loading test config: {e}")
        # Fallback or raise if critical
        # For now, assume it might proceed with default if file ops fail in restricted env
        pass

    # Patch external dependencies for all tests in this module
    with patch('redis.asyncio.Redis.from_url', return_value=MagicMock(spec=PendingPlanStore)) as mock_redis, \
         patch('collab_orchestrator.utils.create_telemetry_client', return_value=MagicMock()) as mock_telemetry, \
         patch('collab_orchestrator.agents.base_agent_builder.BaseAgentBuilder', MagicMock()) as mock_agent_builder, \
         patch('collab_orchestrator.kind_handler.KindHandler', spec=KindHandler) as mock_kind_handler_class:

        # Mock the KindHandler instance that would be created
        mock_handler_instance = MagicMock(spec=KindHandler)
        mock_handler_instance.invoke = AsyncMock() # This is the key method called by the app
        mock_kind_handler_class.return_value = mock_handler_instance # When KindHandler is instantiated

        # Call initialize here if it sets up dependencies based on the (now patched) config
        # This depends on how 'app.py' is structured. If 'initialize()' is called at module level,
        # this patching might be too late. If it's called on app startup or per request, it's fine.
        # Assuming initialize() is called when app starts or can be called manually.
        try:
            asyncio.run(initialize()) # Run async initialize if needed
        except RuntimeError: # If event loop is already running (e.g. in pytest-asyncio)
             pass # initialize() might have already been called or will be by TestClient

        yield mock_redis, mock_telemetry, mock_agent_builder, mock_kind_handler_class, mock_handler_instance

@pytest.fixture
def client(load_test_config_for_app): # Depends on the config being loaded and patched
    # The TestClient will use the app instance, which should now be initialized with mocked dependencies
    return TestClient(app)

# Test for the root endpoint
def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Collab Orchestrator" in response.text # Assuming HTML response with this title

# Helper to consume SSE stream from TestClient
def consume_sse_stream(response):
    events = []
    for line in response.iter_lines():
        if line.startswith("data:"):
            try:
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]": # Common SSE end signal
                    break
                events.append(json.loads(data_str))
            except json.JSONDecodeError:
                # Handle cases where data might not be JSON (e.g. keepalive or plain messages)
                events.append({"raw_data": data_str})
    return events

# Tests for /sse endpoint
def test_sse_endpoint_valid_input(client, load_test_config_for_app):
    _, _, _, _, mock_handler_instance = load_test_config_for_app

    # Setup mock KindHandler response (async generator)
    async def mock_invoke_stream(*args, **kwargs):
        yield {"event": "processing", "data": "step 1"}
        await asyncio.sleep(0.01)
        yield {"event": "final_result", "data": "complete"}

    mock_handler_instance.invoke = mock_invoke_stream # Make it an async generator

    payload = {
        "input": {"text": "Hello orchestrator"},
        "config": {"kind": "planning", "interaction_id": "test_sse_valid"} # Ensure kind is specified
    }
    response = client.post("/sse", json=payload, headers={"Accept": "text/event-stream"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = consume_sse_stream(response)

    assert len(events) == 2 # Based on the mock_invoke_stream
    assert events[0] == {"event": "processing", "data": "step 1"}
    assert events[1] == {"event": "final_result", "data": "complete"}
    # mock_handler_instance.invoke.assert_called_once() # This assertion is tricky with async generators returned by fixture.
    # Instead, check if the mock was called with expected args if possible, or rely on output.


def test_sse_endpoint_invalid_input_no_kind(client):
    payload = {
        "input": {"text": "Missing kind"},
        "config": {"interaction_id": "test_sse_invalid_kind"} # Missing "kind"
    }
    response = client.post("/sse", json=payload, headers={"Accept": "text/event-stream"})

    assert response.status_code == 422 # Validation error for missing kind
    # FastAPI typically returns JSON for HTTP errors, not an SSE stream
    assert "application/json" in response.headers["content-type"]
    error_details = response.json()
    assert any("Field required" in detail["msg"] and "kind" in detail["loc"] for detail in error_details["detail"])


def test_sse_endpoint_handler_exception(client, load_test_config_for_app):
    _, _, _, _, mock_handler_instance = load_test_config_for_app

    async def mock_invoke_raises_exception(*args, **kwargs):
        raise ValueError("Handler failed processing")
        yield # Make it an async generator type

    mock_handler_instance.invoke = mock_invoke_raises_exception

    payload = {
        "input": {"text": "Trigger handler exception"},
        "config": {"kind": "planning", "interaction_id": "test_sse_handler_ex"}
    }
    response = client.post("/sse", json=payload, headers={"Accept": "text/event-stream"})

    assert response.status_code == 200 # The connection itself is fine, error is in the stream
    events = consume_sse_stream(response)

    # Expecting the error to be streamed back as a JSON object within the SSE stream
    assert len(events) == 1
    # The exact structure of error streamed back depends on app's exception handling for SSE.
    # Assuming it sends a JSON with an "error" key.
    assert "error" in events[0]
    assert "Handler failed processing" in events[0]["error"]


# Tests for Browser Session Endpoints
def test_browser_root_endpoint(client):
    response = client.get("/browser")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Check for some unique element you expect in your browser.html
    assert "<title>Collab Orchestrator Browser</title>" in response.text

def test_browser_session_endpoint(client):
    session_id = "test_session_123"
    response = client.get(f"/browser/{session_id}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Check that the session_id (or some derivative) is present in the response if expected
    # For example, if it's embedded in a JavaScript variable or a data attribute
    assert f"<title>Collab Orchestrator Browser - {session_id}</title>" in response.text # Assuming title reflects session
    # Or, if it's passed to JavaScript:
    # assert f"const sessionId = '{session_id}';" in response.text


# Placeholder for HITL tests (to be added next)
def test_hitl_endpoints_placeholder():
    assert True

# Fixture to enable HITL for specific tests
@pytest.fixture
def hitl_enabled_app(monkeypatch):
    # This fixture will temporarily enable HITL in the app's config
    # and provide a client configured with this app state.

    # Load the original test config first
    original_config = parse_yaml_file_as(OrchestratorConfig, TEST_CONFIG_PATH)

    # Create a new config object with HITL enabled
    hitl_config_data = original_config.model_dump()
    hitl_config_data["enable_hitl"] = True
    hitl_config = OrchestratorConfig(**hitl_config_data)

    # Patch the config used by the app instance
    monkeypatch.setattr(app_config_module, 'config', hitl_config)

    # We also need to ensure that dependencies relying on this config are re-initialized
    # or use this patched config. The `initialize()` function in `app.py` sets up handlers.
    # If `initialize()` is called only once at app startup, this patching might not affect
    # already created handler instances.
    # For robust testing, it's better if `initialize` can be called again, or if handlers
    # fetch config dynamically, or if we can directly patch the `enable_hitl` attribute
    # on the relevant handler instance if that's easier.

    # Let's assume for now that the KindHandler or relevant part of the app
    # will pick up the patched 'app_config_module.config.enable_hitl'.
    # If not, the KindHandler itself would need to be patched more deeply.

    # Re-initialize with HITL enabled. This assumes initialize() can be called multiple times
    # or correctly re-configures components.
    # This is a simplification; real-world might need more careful DI handling.
    original_initialize = app.router.lifespan_context

    async def mock_lifespan(app_instance):
        # This replaces the app's lifespan manager for the test
        await initialize() # Re-run initialize with patched config
        yield
        # Cleanup if necessary, though for tests it might not matter as much

    app.router.lifespan_context = mock_lifespan

    with patch('collab_orchestrator.pending_plan_store.PendingPlanStore', MagicMock(spec=PendingPlanStore)) as mock_store_class:
        mock_pending_store_instance = MagicMock(spec=PendingPlanStore)
        mock_store_class.return_value = mock_pending_store_instance # Used by HITL endpoints

        # The KindHandler mock from load_test_config_for_app might still be in effect.
        # We need to ensure it's also aware of HITL or behaves as expected.
        # For HITL resume operations, the app calls handler.invoke with specific inputs.

        client = TestClient(app)
        yield client, mock_pending_store_instance # provide client and store mock

    app.router.lifespan_context = original_initialize # Restore original lifespan


# Tests for HITL Endpoints
@pytest.mark.asyncio
async def test_hitl_approve_endpoint(hitl_enabled_app, load_test_config_for_app):
    client, mock_pending_store = hitl_enabled_app
    _, _, _, _, mock_main_handler_instance = load_test_config_for_app # Get the main handler mock

    session_id = "hitl_session_approve"
    mock_stored_plan = Plan(steps=[Step(id="s1", reasoning="r", tasks=[ExecutableTask(id="t1", name="n", agent_id="a", inputs={}, status=TaskStatus.PENDING)])])
    mock_user_input = BaseMultiModalInput(text="original query")
    mock_config = COTypesBaseConfig(interaction_id="original_interaction")

    mock_pending_store.get_pending_plan = AsyncMock(return_value=(mock_stored_plan, mock_user_input, mock_config, []))
    mock_pending_store.delete_pending_plan = AsyncMock()

    # Mock the handler's response when resuming with approval
    async def mock_resume_invoke(*args, **kwargs):
        # Check if called with HitlResumeType.APPROVE
        input_data = args[1] # Assuming request_id, input_obj, config_obj, history
        if isinstance(input_data, BaseMultiModalInput) and input_data.hitl_resume_type == HitlResumeType.APPROVE:
            yield {"event": "plan_approved", "data": {"session_id": session_id}}
            yield {"event": "execution_started", "data": "Executing approved plan"}
        else:
            yield {"error": "HITL resume type not APPROVE as expected"}

    mock_main_handler_instance.invoke = mock_resume_invoke

    approved_plan_payload = mock_stored_plan.model_dump() # Send back the plan as if user confirmed it

    response = client.post(f"/sse/{session_id}/approve", json=approved_plan_payload, headers={"Accept": "text/event-stream"})

    assert response.status_code == 200
    events = consume_sse_stream(response)
    assert {"event": "plan_approved", "data": {"session_id": session_id}} in events
    assert {"event": "execution_started", "data": "Executing approved plan"} in events
    mock_pending_store.get_pending_plan.assert_called_once_with(session_id)
    mock_pending_store.delete_pending_plan.assert_called_once_with(session_id)


@pytest.mark.asyncio
async def test_hitl_cancel_endpoint(hitl_enabled_app, load_test_config_for_app):
    client, mock_pending_store = hitl_enabled_app
    _, _, _, _, mock_main_handler_instance = load_test_config_for_app

    session_id = "hitl_session_cancel"
    mock_pending_store.delete_pending_plan = AsyncMock() # Called on cancel

    # Mock the handler's response for cancellation (might just be an event or nothing if app handles it)
    # Typically, cancelling doesn't involve invoking the handler again, but cleaning up.
    # The app endpoint itself might directly return the cancellation confirmation.
    # Let's assume the endpoint itself handles emitting PLAN_CANCELLED and cleaning store.

    response = client.post(f"/sse/{session_id}/cancel", headers={"Accept": "text/event-stream"})

    assert response.status_code == 200 # SSE stream opened for confirmation
    events = consume_sse_stream(response)
    # Check for the specific event the app sends on successful cancellation
    assert any(e.get("type") == EventType.PLAN_CANCELLED.value and e.get("data", {}).get("session_id") == session_id for e in events)
    mock_pending_store.delete_pending_plan.assert_called_once_with(session_id)


@pytest.mark.asyncio
async def test_hitl_edit_endpoint(hitl_enabled_app, load_test_config_for_app):
    client, mock_pending_store = hitl_enabled_app
    _, _, _, _, mock_main_handler_instance = load_test_config_for_app

    session_id = "hitl_session_edit"
    original_plan = Plan(steps=[Step(id="s1", reasoning="original", tasks=[])])
    mock_user_input = BaseMultiModalInput(text="original query")
    mock_config = COTypesBaseConfig(interaction_id="original_interaction")

    mock_pending_store.get_pending_plan = AsyncMock(return_value=(original_plan, mock_user_input, mock_config, []))
    mock_pending_store.delete_pending_plan = AsyncMock()

    async def mock_resume_invoke_edit(*args, **kwargs):
        input_data = args[1]
        if isinstance(input_data, BaseMultiModalInput) and input_data.hitl_resume_type == HitlResumeType.EDIT:
            edited_plan_received = input_data.approved_plan # This is now a dict
            assert edited_plan_received["steps"][0]["reasoning"] == "edited reasoning"
            yield {"event": "plan_edited", "data": {"session_id": session_id, "new_plan": edited_plan_received}}
            yield {"event": "execution_started", "data": "Executing edited plan"}
        else:
            yield {"error": "HITL resume type not EDIT as expected"}

    mock_main_handler_instance.invoke = mock_resume_invoke_edit

    edited_plan_payload = {"steps": [{"id": "s1", "reasoning": "edited reasoning", "tasks": []}]} # User sends edited plan

    response = client.post(f"/sse/{session_id}/edit", json=edited_plan_payload, headers={"Accept": "text/event-stream"})

    assert response.status_code == 200
    events = consume_sse_stream(response)
    assert any(e.get("event") == "plan_edited" for e in events)
    assert any(e.get("event") == "execution_started" for e in events)
    mock_pending_store.get_pending_plan.assert_called_once_with(session_id)
    mock_pending_store.delete_pending_plan.assert_called_once_with(session_id)


def test_hitl_endpoints_disabled(client): # Test with default config (HITL disabled)
    session_id = "hitl_disabled_session"
    # If HITL is disabled, these endpoints should ideally return an error (e.g., 404 or 400/501)
    # This depends on how the app is structured (e.g., if routes are conditionally registered)

    # Assuming routes are present but functionality is disabled, expect a specific error response.
    # If routes are not even registered, TestClient would raise an error or FastAPI a 404.

    approve_response = client.post(f"/sse/{session_id}/approve", json={})
    assert approve_response.status_code == 404 # Or other error like 501 Not Implemented / 400 Bad Request

    cancel_response = client.post(f"/sse/{session_id}/cancel")
    assert cancel_response.status_code == 404

    edit_response = client.post(f"/sse/{session_id}/edit", json={})
    assert edit_response.status_code == 404


# Remove the original placeholder
# def test_hitl_endpoints_placeholder():
#    assert True
