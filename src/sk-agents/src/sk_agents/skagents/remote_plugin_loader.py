import httpx
from typing import Any

from pydantic import BaseModel, field_validator
from pydantic_yaml import parse_yaml_file_as
from semantic_kernel import Kernel
from semantic_kernel.connectors.openapi_plugin.openapi_function_execution_parameters import (
    OpenAPIFunctionExecutionParameters,
)
from semantic_kernel.connectors.mcp import MCPStdioPlugin, MCPSsePlugin
from ska_utils import AppConfig

from sk_agents.configs import TA_REMOTE_PLUGIN_PATH


class RemotePlugin(BaseModel):
    plugin_name: str
    openapi_json_path: str | None = None
    server_url: str | None = None
    mcp_plugin_type: str | None = None
    mcp_command: str | None = None
    mcp_args: list[str] | None = None
    mcp_env: dict[str, str] | None = None
    mcp_url: str | None = None

    @field_validator("mcp_plugin_type")
    def validate_mcp_plugin_type(cls, value: str | None) -> str | None:
        if value and value not in ("stdio", "sse"):
            raise ValueError('mcp_plugin_type must be "stdio" or "sse"')
        return value

    @field_validator("mcp_command")
    def validate_mcp_command(cls, value: str | None, values: Any) -> str | None:
        if values.data.get("mcp_plugin_type") == "stdio" and not value:
            raise ValueError("mcp_command must be set if mcp_plugin_type is 'stdio'")
        return value

    @field_validator("mcp_url")
    def validate_mcp_url(cls, value: str | None, values: Any) -> str | None:
        if values.data.get("mcp_plugin_type") == "sse" and not value:
            raise ValueError("mcp_url must be set if mcp_plugin_type is 'sse'")
        return value

    @field_validator("openapi_json_path")
    def validate_openapi_json_path(cls, value: str | None, values: Any) -> str | None:
        if values.data.get("mcp_plugin_type") and value:
            raise ValueError(
                "openapi_json_path should not be set if mcp_plugin_type is set"
            )
        if not values.data.get("mcp_plugin_type") and not value:
            raise ValueError(
                "openapi_json_path must be set if mcp_plugin_type is not set"
            )
        return value


class RemotePlugins(BaseModel):
    remote_plugins: list[RemotePlugin]

    def get(self, plugin_name: str) -> RemotePlugin | None:
        for remote_plugin in self.remote_plugins:
            if remote_plugin.plugin_name == plugin_name:
                return remote_plugin
        return None


class RemotePluginCatalog:
    def __init__(self, app_config: AppConfig) -> None:
        plugin_path = app_config.get(TA_REMOTE_PLUGIN_PATH.env_name)
        if plugin_path is None:
            self.catalog = None
        else:
            self.catalog: RemotePlugins = parse_yaml_file_as(RemotePlugins, plugin_path)

    def get_remote_plugin(self, plugin_name: str) -> RemotePlugin | None:
        return self.catalog.get(plugin_name)


class RemotePluginLoader:
    def __init__(self, catalog: RemotePluginCatalog) -> None:
        self.catalog = catalog
        self._mcp_plugins: list[MCPStdioPlugin | MCPSsePlugin] = []

    async def _load_mcp_plugin(self, kernel: Kernel, remote_plugin: RemotePlugin):
        if remote_plugin.mcp_plugin_type == "stdio":
            if not remote_plugin.mcp_command:
                # This should ideally be caught by Pydantic validation, but good to double check
                raise ValueError(
                    "mcp_command is required for stdio MCP plugin"
                )
            plugin = MCPStdioPlugin(
                name=remote_plugin.plugin_name,
                command=remote_plugin.mcp_command,
                args=remote_plugin.mcp_args,
                env=remote_plugin.mcp_env,
            )
        elif remote_plugin.mcp_plugin_type == "sse":
            if not remote_plugin.mcp_url:
                # This should ideally be caught by Pydantic validation
                raise ValueError("mcp_url is required for sse MCP plugin")
            plugin = MCPSsePlugin(
                name=remote_plugin.plugin_name, url=remote_plugin.mcp_url
            )
        else:
            # This case should also be prevented by Pydantic validation
            raise ValueError(
                f"Unsupported MCP plugin type: {remote_plugin.mcp_plugin_type}"
            )

        # According to the task description, we add the plugin to the kernel.
        # The lifecycle (connect/close) might be an issue.
        # For now, we'll add to a list for potential later management.
        # await plugin.connect() # Not calling connect as per simplified approach
        kernel.add_plugin(plugin)
        self._mcp_plugins.append(plugin)

    async def load_remote_plugins(self, kernel: Kernel, remote_plugins: list[str]):
        for remote_plugin_name in remote_plugins:
            remote_plugin = self.catalog.get_remote_plugin(remote_plugin_name)
            if not remote_plugin:
                raise ValueError(f"Remote plugin {remote_plugin_name} not found in catalog")

            if remote_plugin.mcp_plugin_type:
                await self._load_mcp_plugin(kernel, remote_plugin)
            elif remote_plugin.openapi_json_path: # Ensure openapi_json_path exists
                client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
                # add_plugin_from_openapi is synchronous
                kernel.add_plugin_from_openapi(
                    plugin_name=remote_plugin.plugin_name,
                    openapi_document_path=remote_plugin.openapi_json_path,
                    execution_settings=OpenAPIFunctionExecutionParameters(
                        http_client=client,
                        server_url_override=remote_plugin.server_url,
                        enable_payload_namespacing=True,
                    ),
                )
            else:
                # This case should be prevented by Pydantic validation (one of them must be set)
                raise ValueError(
                    f"Remote plugin {remote_plugin_name} has neither MCP nor OpenAPI config"
                )
