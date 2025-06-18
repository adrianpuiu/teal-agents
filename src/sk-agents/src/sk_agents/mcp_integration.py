"""MCP (Model Context Protocol) integration for Teal Agents platform.

This module provides MCP client capabilities that can be used as Semantic Kernel plugins,
allowing Teal Agents to connect to and interact with MCP servers.
"""

import asyncio
import json
import logging
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field
from semantic_kernel.functions import kernel_function
from semantic_kernel.functions.kernel_function import KernelFunction
from semantic_kernel.kernel import Kernel

logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection."""

    name: str = Field(description="Name identifier for the MCP server")
    command: str = Field(description="Command to start the MCP server")
    args: list[str] = Field(
        default_factory=list, description="Arguments for the MCP server command"
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the MCP server"
    )
    timeout: int = Field(default=30, description="Connection timeout in seconds")
    integration_mode: str = Field(
        default="wrapper", description="Integration mode: 'wrapper' or 'direct'"
    )
    plugin_name: str | None = Field(default=None, description="Custom plugin name for direct mode")


class MCPToolResult(BaseModel):
    """Result from an MCP tool call."""

    success: bool
    content: str
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MCPPlugin:
    """Semantic Kernel plugin that provides MCP server connectivity."""

    def __init__(self, server_configs: list[MCPServerConfig]):
        """Initialize MCP plugin with server configurations.

        Args:
            server_configs: List of MCP server configurations to connect to
        """
        self.server_configs = {config.name: config for config in server_configs}
        self.sessions: dict[str, ClientSession] = {}
        self.connections: dict[str, Any] = {}
        self._initialized = False

    async def initialize(self):
        """Initialize connections to all configured MCP servers."""
        if self._initialized:
            return

        for server_name, config in self.server_configs.items():
            try:
                await self._connect_to_server(server_name, config)
                logger.info(f"Connected to MCP server: {server_name}")
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {server_name}: {e}")

        self._initialized = True

    async def _connect_to_server(self, server_name: str, config: MCPServerConfig):
        """Connect to a single MCP server."""
        try:
            server_params = StdioServerParameters(
                command=config.command, args=config.args, env=config.env
            )

            # Establish connection with timeout
            stdio_context = stdio_client(server_params)
            read, write = await asyncio.wait_for(stdio_context.__aenter__(), timeout=config.timeout)

            session_context = ClientSession(read, write)
            session = await asyncio.wait_for(session_context.__aenter__(), timeout=config.timeout)

            await asyncio.wait_for(session.initialize(), timeout=config.timeout)

            # Store connection details
            self.connections[server_name] = (stdio_context, session_context)
            self.sessions[server_name] = session

        except TimeoutError:
            logger.error(f"Timeout connecting to MCP server {server_name} after {config.timeout}s")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {server_name}: {e}")
            raise

    async def cleanup(self):
        """Clean up all MCP server connections."""
        for server_name in list(self.sessions.keys()):
            try:
                # Clean up session
                if server_name in self.sessions:
                    session = self.sessions[server_name]
                    if hasattr(session, "__aexit__"):
                        await session.__aexit__(None, None, None)

                # Clean up connection contexts
                if server_name in self.connections:
                    stdio_context, session_context = self.connections[server_name]
                    if hasattr(session_context, "__aexit__"):
                        await session_context.__aexit__(None, None, None)
                    if hasattr(stdio_context, "__aexit__"):
                        await stdio_context.__aexit__(None, None, None)

                logger.info(f"Disconnected from MCP server: {server_name}")
            except Exception as e:
                logger.error(f"Error disconnecting from MCP server {server_name}: {e}")

        self.sessions.clear()
        self.connections.clear()
        self._initialized = False

    @kernel_function(
        name="list_mcp_tools", description="List all available tools from connected MCP servers"
    )
    async def list_mcp_tools(self) -> str:
        """List all available MCP tools from connected servers."""
        if not self._initialized:
            await self.initialize()

        all_tools = {}

        for server_name, session in self.sessions.items():
            try:
                tools_response = await session.list_tools()
                server_tools = []

                for tool in tools_response.tools:
                    server_tools.append(
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema,
                        }
                    )

                all_tools[server_name] = server_tools
            except Exception as e:
                logger.error(f"Error listing tools from {server_name}: {e}")
                all_tools[server_name] = [{"error": str(e)}]

        return json.dumps(all_tools, indent=2)

    @kernel_function(name="call_mcp_tool", description="Call a specific tool on an MCP server")
    async def call_mcp_tool(self, server_name: str, tool_name: str, arguments: str = "{}") -> str:
        """Call a specific MCP tool with given arguments.

        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: JSON string of tool arguments

        Returns:
            JSON string containing the tool result
        """
        if not self._initialized:
            await self.initialize()

        if server_name not in self.sessions:
            return json.dumps(
                {
                    "success": False,
                    "error": f"MCP server '{server_name}' not found or not connected",
                }
            )

        try:
            # Parse arguments
            args_dict = json.loads(arguments) if arguments else {}

            # Call the tool
            session = self.sessions[server_name]
            result = await session.call_tool(tool_name, arguments=args_dict)

            # Format response
            content_parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    content_parts.append(content.text)
                else:
                    content_parts.append(str(content))

            response = MCPToolResult(
                success=True,
                content="\n".join(content_parts),
                metadata={
                    "server": server_name,
                    "tool": tool_name,
                    "is_error": result.isError if hasattr(result, "isError") else False,
                },
            )

        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name} on {server_name}: {e}")
            response = MCPToolResult(
                success=False,
                content="",
                error=str(e),
                metadata={"server": server_name, "tool": tool_name},
            )

        return response.model_dump_json()

    @kernel_function(name="read_mcp_resource", description="Read a resource from an MCP server")
    async def read_mcp_resource(self, server_name: str, resource_uri: str) -> str:
        """Read a resource from an MCP server.

        Args:
            server_name: Name of the MCP server
            resource_uri: URI of the resource to read

        Returns:
            JSON string containing the resource content
        """
        if not self._initialized:
            await self.initialize()

        if server_name not in self.sessions:
            return json.dumps(
                {
                    "success": False,
                    "error": f"MCP server '{server_name}' not found or not connected",
                }
            )

        try:
            session = self.sessions[server_name]
            result = await session.read_resource(resource_uri)

            content_parts = []
            for content in result.contents:
                if hasattr(content, "text"):
                    content_parts.append(content.text)
                else:
                    content_parts.append(str(content))

            response = {
                "success": True,
                "content": "\n".join(content_parts),
                "uri": resource_uri,
                "server": server_name,
            }

        except Exception as e:
            logger.error(f"Error reading resource {resource_uri} from {server_name}: {e}")
            response = {
                "success": False,
                "error": str(e),
                "uri": resource_uri,
                "server": server_name,
            }

        return json.dumps(response, indent=2)

    @kernel_function(name="get_mcp_prompt", description="Get a prompt template from an MCP server")
    async def get_mcp_prompt(
        self, server_name: str, prompt_name: str, arguments: str = "{}"
    ) -> str:
        """Get a prompt template from an MCP server.

        Args:
            server_name: Name of the MCP server
            prompt_name: Name of the prompt to get
            arguments: JSON string of prompt arguments

        Returns:
            JSON string containing the prompt content
        """
        if not self._initialized:
            await self.initialize()

        if server_name not in self.sessions:
            return json.dumps(
                {
                    "success": False,
                    "error": f"MCP server '{server_name}' not found or not connected",
                }
            )

        try:
            args_dict = json.loads(arguments) if arguments else {}

            session = self.sessions[server_name]
            result = await session.get_prompt(prompt_name, arguments=args_dict)

            response = {
                "success": True,
                "name": prompt_name,
                "description": result.description,
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content.text
                        if hasattr(msg.content, "text")
                        else str(msg.content),
                    }
                    for msg in result.messages
                ],
                "server": server_name,
            }

        except Exception as e:
            logger.error(f"Error getting prompt {prompt_name} from {server_name}: {e}")
            response = {
                "success": False,
                "error": str(e),
                "name": prompt_name,
                "server": server_name,
            }

        return json.dumps(response, indent=2)


class MCPPluginFactory:
    """Factory for creating MCP plugins from configuration."""

    @staticmethod
    def create_from_config(mcp_configs: list[dict[str, Any]]) -> MCPPlugin:
        """Create MCP plugin from configuration dictionaries.

        Args:
            mcp_configs: List of MCP server configuration dictionaries

        Returns:
            Configured MCPPlugin instance
        """
        server_configs = [MCPServerConfig(**config) for config in mcp_configs]
        return MCPPlugin(server_configs)

    @staticmethod
    def create_filesystem_plugin(workspace_path: str = "/workspace") -> MCPPlugin:
        """Create MCP plugin with filesystem server.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            MCPPlugin configured with filesystem server
        """
        config = MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", workspace_path],
            env={},
        )
        return MCPPlugin([config])

    @staticmethod
    def create_sqlite_plugin(db_path: str) -> MCPPlugin:
        """Create MCP plugin with SQLite server.

        Args:
            db_path: Path to SQLite database file

        Returns:
            MCPPlugin configured with SQLite server
        """
        import os

        script_dir = os.path.dirname(os.path.abspath(__file__))
        wrapper_script = os.path.join(script_dir, "..", "..", "run_sqlite_mcp_server.py")

        config = MCPServerConfig(
            name="sqlite", command="python", args=[wrapper_script, db_path], env={}
        )
        return MCPPlugin([config])


class MCPDirectToolFunction:
    """A Semantic Kernel function that directly calls an MCP tool."""

    def __init__(
        self,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any],
        session: ClientSession,
        server_name: str,
    ):
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.tool_schema = tool_schema
        self.session = session
        self.server_name = server_name

    async def __call__(self, **kwargs) -> str:
        """Execute the MCP tool with given arguments."""
        try:
            # Convert kwargs to the format expected by MCP
            arguments = {k: v for k, v in kwargs.items() if v is not None}

            # Call the tool
            result = await self.session.call_tool(self.tool_name, arguments=arguments)

            # Format response
            response = {
                "success": True,
                "content": [],
                "server": self.server_name,
                "tool": self.tool_name,
            }

            # Handle different content types
            from typing import cast

            content_list = cast(list[dict[str, Any]], response["content"])
            for content in result.content:
                if hasattr(content, "text"):
                    content_list.append({"type": "text", "text": content.text})
                elif hasattr(content, "data"):
                    content_list.append(
                        {
                            "type": "resource",
                            "resource": {
                                "uri": getattr(content, "uri", ""),
                                "mimeType": getattr(
                                    content, "mimeType", "application/octet-stream"
                                ),
                            },
                            "data": content.data,
                        }
                    )
                else:
                    content_list.append({"type": "unknown", "data": str(content)})

            return json.dumps(response, indent=2)

        except Exception as e:
            logger.error(f"Error calling MCP tool {self.tool_name} on {self.server_name}: {e}")
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "server": self.server_name,
                    "tool": self.tool_name,
                }
            )


class EnhancedMCPPlugin(MCPPlugin):
    """Enhanced MCP plugin supporting both wrapper and direct tool integration modes."""

    def __init__(self, server_configs: list[MCPServerConfig]):
        super().__init__(server_configs)
        self.direct_tools: dict[str, list[KernelFunction]] = {}

    async def register_direct_tools_to_kernel(self, kernel: Kernel) -> None:
        """Register MCP tools directly as individual Semantic Kernel functions."""
        if not self._initialized:
            await self.initialize()

        for server_name, session in self.sessions.items():
            server_config = self.server_configs[server_name]

            # Skip if not in direct mode
            if server_config.integration_mode != "direct":
                continue

            try:
                # Get tools from server
                tools_response = await session.list_tools()
                server_tools = []

                # Create individual kernel functions for each tool
                for tool in tools_response.tools:
                    # Create the direct tool function
                    direct_func = MCPDirectToolFunction(
                        tool_name=tool.name,
                        tool_description=tool.description,
                        tool_schema=tool.inputSchema,
                        session=session,
                        server_name=server_name,
                    )

                    # Convert to Semantic Kernel function with proper metadata
                    kernel_func = self._create_kernel_function_from_tool(tool, direct_func)
                    server_tools.append(kernel_func)

                    # Add to kernel with appropriate plugin name
                    plugin_name = server_config.plugin_name or f"{server_name}_tools"
                    kernel.add_function(plugin_name=plugin_name, function=kernel_func)

                    logger.info(f"Registered direct MCP tool: {plugin_name}.{tool.name}")

                self.direct_tools[server_name] = server_tools

            except Exception as e:
                logger.error(f"Error registering direct tools from {server_name}: {e}")

    def _create_kernel_function_from_tool(
        self, tool, direct_func: MCPDirectToolFunction
    ) -> KernelFunction:
        """Create a Semantic Kernel function from an MCP tool."""
        from semantic_kernel.functions.kernel_function_from_method import KernelFunctionFromMethod
        from semantic_kernel.functions.kernel_function_metadata import KernelFunctionMetadata
        from semantic_kernel.functions.kernel_parameter_metadata import KernelParameterMetadata

        # Extract parameters from tool schema
        parameters = []
        if tool.inputSchema and "properties" in tool.inputSchema:
            for param_name, param_info in tool.inputSchema["properties"].items():
                param_metadata = KernelParameterMetadata(
                    name=param_name,
                    description=param_info.get("description", ""),
                    default_value=param_info.get("default"),
                    type_=param_info.get("type", "string"),
                    required=param_name in tool.inputSchema.get("required", []),
                )
                parameters.append(param_metadata)

        # Create function metadata
        metadata = KernelFunctionMetadata(
            name=tool.name,
            plugin_name="",  # Will be set when added to kernel
            description=tool.description,
            parameters=parameters,
            is_prompt=False,
            is_asynchronous=True,
        )

        # Create kernel function
        return KernelFunctionFromMethod(method=direct_func, metadata=metadata)


class EnhancedMCPPluginFactory(MCPPluginFactory):
    """Enhanced factory for creating MCP plugins with dual integration modes."""

    @staticmethod
    def create_from_config(mcp_configs: list[dict[str, Any]]) -> EnhancedMCPPlugin:
        """Create enhanced MCP plugin from configuration dictionaries.

        Args:
            mcp_configs: List of MCP server configuration dictionaries

        Returns:
            Configured EnhancedMCPPlugin instance
        """
        server_configs = [MCPServerConfig(**config) for config in mcp_configs]
        return EnhancedMCPPlugin(server_configs)

    @staticmethod
    def create_filesystem_plugin(
        workspace_path: str = "/workspace",
        integration_mode: str = "wrapper",
        plugin_name: str | None = None,
    ) -> EnhancedMCPPlugin:
        """Create enhanced MCP plugin with filesystem server.

        Args:
            workspace_path: Path to workspace directory
            integration_mode: 'wrapper' or 'direct'
            plugin_name: Custom plugin name for direct mode

        Returns:
            EnhancedMCPPlugin configured with filesystem server
        """
        config = MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", workspace_path],
            env={},
            integration_mode=integration_mode,
            plugin_name=plugin_name or "FileSystem",
        )
        return EnhancedMCPPlugin([config])

    @staticmethod
    def create_multi_server_plugin(
        servers: list[dict[str, Any]], default_integration_mode: str = "wrapper"
    ) -> EnhancedMCPPlugin:
        """Create enhanced MCP plugin with multiple servers.

        Args:
            servers: List of server configurations
            default_integration_mode: Default integration mode if not specified

        Returns:
            EnhancedMCPPlugin configured with multiple servers
        """
        configs = []
        for server in servers:
            server_config = server.copy()
            if "integration_mode" not in server_config:
                server_config["integration_mode"] = default_integration_mode
            configs.append(MCPServerConfig(**server_config))

        return EnhancedMCPPlugin(configs)
