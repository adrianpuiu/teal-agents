from copy import deepcopy

from sk_agents.extra_data_collector import ExtraDataCollector
from sk_agents.skagents.v1.agent_builder import AgentBuilder
from sk_agents.skagents.v1.sequential.config import AgentConfig, Config, TaskConfig
from sk_agents.skagents.v1.sequential.task import Task
from sk_agents.skagents.v1.sk_agent import SKAgent


class TaskBuilder:
    def __init__(self, agent_builder: AgentBuilder):
        self.agent_builder = agent_builder

    @staticmethod
    def _get_agent_config_by_name(agent_name: str, agent_configs: list[AgentConfig]) -> AgentConfig:
        for agent_config in agent_configs:
            if agent_config.name == agent_name:
                return agent_config
        raise ValueError(f"Agent {agent_name} not found")

    def _get_agent_for_task(
        self,
        task_config: TaskConfig,
        agent_configs: list[AgentConfig],
        extra_data_collector: ExtraDataCollector,
        config: Config | None = None,
        output_type: str | None = None,
    ) -> SKAgent:
        agent_config = TaskBuilder._get_agent_config_by_name(task_config.agent, agent_configs)

        # Create a copy of the agent config to avoid modifying the original
        agent_config_copy = deepcopy(agent_config)

        # Merge MCP servers if config is provided
        if config:
            merged_mcp_servers = config.get_agent_mcp_servers(agent_config.name)
            if merged_mcp_servers:
                agent_config_copy.mcp_servers = merged_mcp_servers

        agent = self.agent_builder.build_agent(agent_config_copy, extra_data_collector, output_type)
        return agent

    def build_task(
        self,
        task_config: TaskConfig,
        agent_configs: list[AgentConfig],
        config: Config | None = None,
        output_type: str | None = None,
    ) -> Task:
        extra_data_collector = ExtraDataCollector()
        agent = self._get_agent_for_task(
            task_config, agent_configs, extra_data_collector, config, output_type
        )
        return Task(
            name=task_config.name,
            description=task_config.description,
            instructions=task_config.instructions,
            agent=agent,
            extra_data_collector=extra_data_collector,
        )
