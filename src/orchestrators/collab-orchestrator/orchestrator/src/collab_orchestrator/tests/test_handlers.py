import pytest
from unittest.mock import MagicMock, patch

from collab_orchestrator.handler_factory import HandlerFactory
from collab_orchestrator.planning_handler.planning_handler import PlanningHandler
from collab_orchestrator.team_handler.team_handler import TeamHandler
from collab_orchestrator.co_types import BaseConfig, OrchestratorConfig
from collab_orchestrator.agents import AgentGateway, BaseAgentBuilder # Removed TaskAgent, BaseAgent as they are not direct dependencies of factory/handlers here
from collab_orchestrator.pending_plan_store import PendingPlanStore # Needed for PlanningHandler
from collab_orchestrator.step_executor import StepExecutor # Needed for PlanningHandler
from collab_orchestrator.team_handler.manager_agent import ManagerAgent # Needed for TeamHandler
from collab_orchestrator.team_handler.task_executor import TaskExecutor as TeamTaskExecutor # Needed for TeamHandler

from ska_utils import Telemetry

# Mock configuration for the handlers
@pytest.fixture
def mock_orchestrator_config():
    config = MagicMock(spec=OrchestratorConfig)
    config.agent_registry_url = "http://fake-registry.com"
    config.enable_hitl = False
    config.hitl_timeout_seconds = 30
    config.pending_plan_store_config = {"type": "memory"} # Example, not directly used if PendingPlanStore is mocked
    config.model_config = {"model": "test-model"} # Example
    config.max_rounds = 5 # For TeamHandler
    # Add other fields that might be accessed by handlers if not mocked out
    config.telemetry_config = {"type": "none"}
    config.max_context_tokens = 8000
    config.max_history_tokens = 2000
    config.max_tokens = 1000


    # Mock nested structures if handlers expect them
    # For PlanningHandler, it might expect specific structures for its components
    # For TeamHandler, it might expect specific structures for ManagerAgent/TaskExecutor
    return config

@pytest.fixture
def mock_telemetry_client():
    return MagicMock(spec=Telemetry)

@pytest.fixture
def mock_agent_gateway():
    return MagicMock(spec=AgentGateway)

@pytest.fixture
def mock_base_agent_builder(mock_agent_gateway, mock_orchestrator_config): # Added dependencies
    # BaseAgentBuilder itself takes agent_registry_url
    # If handlers create it, this needs to be accurate.
    # If it's passed to handlers, then this mock is fine.
    # Let's assume it's passed to handlers or created by them using the config.
    builder = BaseAgentBuilder(agent_registry_url=mock_orchestrator_config.agent_registry_url, agent_gateway=mock_agent_gateway)
    # Mock methods if handlers call them during init (unlikely for simple init)
    builder.build_agent = MagicMock()
    return builder

# Mocks for specific handler dependencies
@pytest.fixture
def mock_pending_plan_store():
    return MagicMock(spec=PendingPlanStore)

@pytest.fixture
def mock_step_executor():
    return MagicMock(spec=StepExecutor)

@pytest.fixture
def mock_manager_agent():
    return MagicMock(spec=ManagerAgent)

@pytest.fixture
def mock_team_task_executor():
    return MagicMock(spec=TeamTaskExecutor)


@pytest.fixture
def handler_factory(
    mock_orchestrator_config,
    mock_telemetry_client,
    mock_base_agent_builder, # Used by handlers
    mock_agent_gateway, # Used by handlers or their components
    mock_pending_plan_store, # For PlanningHandler
    mock_step_executor, # For PlanningHandler
    mock_manager_agent, # For TeamHandler
    mock_team_task_executor # For TeamHandler
):
    # Patch the constructors of the handlers within the factory's scope
    # This way, when the factory tries to create them, our mocks are used for their dependencies.

    # This is a bit complex because the factory instantiates handlers internally.
    # We need to ensure that when HandlerFactory calls PlanningHandler(...),
    # it gets a PlanningHandler that was initialized with our mocks if we want to test
    # that the factory correctly passes *its own* arguments (like telemetry, builder) to them.

    # Alternative: Instead of patching constructors here, we can patch the modules
    # where these dependencies are imported by the handlers, or ensure the factory
    # passes these exact mock instances. The latter is cleaner if factory's design allows.

    # Let's assume HandlerFactory is responsible for creating/passing these.
    # The factory itself needs some of these mocks to pass them down.

    # We need to mock what the factory *creates* or *uses to create* handlers.
    # The factory's job is to instantiate PlanningHandler and TeamHandler.
    # It will need to create/fetch their specific dependencies.

    # For this test, we are testing the factory's logic of "which handler to create"
    # and "does it create it with the shared components (telemetry, builder, gateway, config)".
    # The specific components like PendingPlanStore for PlanningHandler are secondary
    # to testing the factory logic itself, but if their creation fails in the handler's __init__,
    # the factory test would fail. So, we mock them too.

    with patch('collab_orchestrator.planning_handler.planning_handler.PendingPlanStore', return_value=mock_pending_plan_store), \
         patch('collab_orchestrator.planning_handler.planning_handler.StepExecutor', return_value=mock_step_executor), \
         patch('collab_orchestrator.team_handler.team_handler.ManagerAgent', return_value=mock_manager_agent), \
         patch('collab_orchestrator.team_handler.team_handler.TaskExecutor', return_value=mock_team_task_executor), \
         patch('collab_orchestrator.planning_handler.planning_handler.BaseAgentBuilder', return_value=mock_base_agent_builder), \
         patch('collab_orchestrator.team_handler.team_handler.BaseAgentBuilder', return_value=mock_base_agent_builder), \
         patch('collab_orchestrator.planning_handler.planning_handler.AgentGateway', return_value=mock_agent_gateway), \
         patch('collab_orchestrator.team_handler.team_handler.AgentGateway', return_value=mock_agent_gateway): # Also for manager agent if it creates one

        factory = HandlerFactory(
            config=mock_orchestrator_config,
            telemetry_client=mock_telemetry_client,
            # The factory will create these or be passed factories for these:
            # For simplicity, assume it can create them or they are passed as already instantiated.
            # The key is what the factory passes to the HANDLERS it creates.
            agent_builder=mock_base_agent_builder,
            agent_gateway=mock_agent_gateway,
            # Pass mocks for components that handlers would try to create if not passed:
            # This depends on handler constructor signatures.
            # Assuming HandlerFactory is responsible for providing these to handlers:
            pending_plan_store=mock_pending_plan_store,
            step_executor=mock_step_executor,
            manager_agent=mock_manager_agent, # This implies factory creates/gets this for TeamHandler
            team_task_executor=mock_team_task_executor # Implies factory creates/gets this for TeamHandler
        )
        return factory

# Tests for HandlerFactory

def test_create_planning_handler(handler_factory, mock_orchestrator_config, mock_telemetry_client, mock_base_agent_builder):
    request_config = BaseConfig(kind="planning", interaction_id="test1")
    handler = handler_factory.get_handler(request_config, "req1", "sess1")

    assert isinstance(handler, PlanningHandler)
    # Check if the handler was initialized with the correct shared components from the factory
    assert handler.telemetry == mock_telemetry_client
    assert handler.agent_builder == mock_base_agent_builder
    # Add more checks if factory passes more common things, e.g. config
    assert handler.config == mock_orchestrator_config


def test_create_team_handler(handler_factory, mock_orchestrator_config, mock_telemetry_client, mock_base_agent_builder):
    request_config = BaseConfig(kind="team", interaction_id="test2")
    handler = handler_factory.get_handler(request_config, "req2", "sess2")

    assert isinstance(handler, TeamHandler)
    assert handler.telemetry == mock_telemetry_client
    assert handler.agent_builder == mock_base_agent_builder
    assert handler.config == mock_orchestrator_config


def test_get_handler_singleton_behavior(handler_factory):
    request_config1 = BaseConfig(kind="planning", interaction_id="test_single1")
    handler1 = handler_factory.get_handler(request_config1, "r1", "s1")

    request_config2 = BaseConfig(kind="planning", interaction_id="test_single2") # Different interaction ID
    handler2 = handler_factory.get_handler(request_config2, "r2", "s2") # Should be same handler instance for "planning"

    assert handler1 is handler2 # Check for instance equality for same kind

    request_config_team = BaseConfig(kind="team", interaction_id="test_single_team")
    team_handler1 = handler_factory.get_handler(request_config_team, "rt1", "st1")
    team_handler2 = handler_factory.get_handler(request_config_team, "rt2", "st2")
    assert team_handler1 is team_handler2

    assert handler1 is not team_handler1 # Ensure different kinds are different instances

def test_get_handler_unknown_type(handler_factory):
    request_config = BaseConfig(kind="unknown_handler", interaction_id="test3")
    with pytest.raises(ValueError) as excinfo:
        handler_factory.get_handler(request_config, "req3", "sess3")
    assert "Unknown handler kind: unknown_handler" in str(excinfo.value)

def test_is_valid_handler(handler_factory):
    assert handler_factory.is_valid_handler("planning") is True
    assert handler_factory.is_valid_handler("team") is True
    assert handler_factory.is_valid_handler("non_existent_handler") is False
    assert handler_factory.is_valid_handler("") is False
    assert handler_factory.is_valid_handler(None) is False
