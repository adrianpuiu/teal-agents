from pydantic import BaseModel, ConfigDict

from sk_agents.ska_types import BaseConfig
from sk_agents.skagents.v1.config import AgentConfig


class TaskConfig(BaseModel):
    name: str
    task_no: int
    description: str
    instructions: str
    agent: str


class Spec(BaseModel):
    agents: list[AgentConfig]
    tasks: list[TaskConfig]
    mcp_servers: list[dict] | None = None


class V1Config(BaseConfig):
    model_config = ConfigDict(extra="allow")

    spec: Spec


class Config:
    def __init__(self, config: BaseConfig):
        self.config: V1Config = V1Config(
            apiVersion=config.apiVersion,
            description=config.description,
            service_name=config.service_name,
            version=config.version,
            input_type=config.input_type,
            output_type=config.output_type,
            spec=config.spec,
        )

    def get_agents(self) -> list[AgentConfig]:
        return self.config.spec.agents

    def get_tasks(self) -> list[TaskConfig]:
        return self.config.spec.tasks

    def get_mcp_servers(self) -> list[dict] | None:
        """Get MCP servers from global spec configuration."""
        return self.config.spec.mcp_servers

    def get_agent_mcp_servers(self, agent_name: str) -> list[dict] | None:
        """Get MCP servers for a specific agent, merging global and agent-specific configs."""
        # Get global MCP servers
        global_mcp = self.get_mcp_servers() or []

        # Get agent-specific MCP servers
        agent_mcp = []
        for agent in self.get_agents():
            if agent.name == agent_name and agent.mcp_servers:
                agent_mcp = agent.mcp_servers
                break

        # Merge them (agent-specific overrides global)
        if global_mcp and agent_mcp:
            return global_mcp + agent_mcp
        elif agent_mcp:
            return agent_mcp
        elif global_mcp:
            return global_mcp
        else:
            return None
