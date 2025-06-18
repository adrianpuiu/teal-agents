"""MCP (Model Context Protocol) integration for Teal Agents platform.

This module provides MCP client and server capabilities that can be used as Semantic Kernel plugins,
allowing Teal Agents to connect to and interact with MCP servers, and expose agents as MCP servers.

This is the cleaned-up version with only the Microsoft-compatible simplified implementation.
"""

import asyncio
import logging
import time
from typing import Any, Optional, List, Dict, Union, Annotated
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field
from semantic_kernel.functions.kernel_function_metadata import KernelFunctionMetadata
from semantic_kernel.functions.kernel_parameter_metadata import KernelParameterMetadata
from semantic_kernel.functions.kernel_function_from_method import KernelFunctionFromMethod
from semantic_kernel.kernel import Kernel

logger = logging.getLogger(__name__)


class MCPConnectionError(Exception):
    """Raised when MCP connection fails."""
    pass


class MCPTimeoutError(Exception):
    """Raised when MCP operation times out."""
    pass


class MCPToolError(Exception):
    """Raised when MCP tool execution fails."""
    pass


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection with multiple transport support."""

    name: str = Field(description="Name identifier for the MCP server")
    
    # Transport configuration (stdio, sse, streamable_http, websocket)
    transport: str = Field(default="stdio", description="Transport type: stdio, sse, streamable_http, websocket")
    
    # Stdio transport fields
    command: str | None = Field(default=None, description="Command to start the MCP server (stdio)")
    args: list[str] = Field(
        default_factory=list, description="Arguments for the MCP server command (stdio)"
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the MCP server (stdio)"
    )
    
    # HTTP/SSE/WebSocket transport fields  
    url: str | None = Field(default=None, description="URL for remote MCP server (sse, streamable_http, websocket)")
    headers: dict[str, str] = Field(
        default_factory=dict, description="HTTP headers for remote connection"
    )
    
    # Common fields
    timeout: int = Field(default=30, description="Connection timeout in seconds")
    plugin_name: str | None = Field(default=None, description="Custom plugin name for tool registration")
    max_retries: int = Field(default=3, description="Maximum number of connection retry attempts")
    retry_delay: float = Field(default=1.0, description="Delay between retry attempts in seconds")
    graceful_degradation: bool = Field(default=True, description="Continue without MCP if connection fails")
    
    def model_post_init(self, __context):
        """Validate transport-specific configuration."""
        # Validate transport-specific requirements
        if self.transport == "stdio":
            if not self.command:
                raise ValueError("command is required for stdio transport")
        elif self.transport in ["sse", "streamable_http", "websocket"]:
            if not self.url:
                raise ValueError(f"url is required for {self.transport} transport")
        else:
            raise ValueError(f"Unsupported transport type: {self.transport}")
            
    @property
    def is_remote_transport(self) -> bool:
        """Check if this is a remote transport (not stdio)."""
        return self.transport in ["sse", "streamable_http", "websocket"]


class SimplifiedMCPClient:
    """Microsoft-style simplified MCP client for direct tool registration.
    
    Equivalent to Microsoft's MCPStdioPlugin approach with enhanced multi-transport support.
    """
    
    def __init__(self, server_config: MCPServerConfig):
        self.server_config = server_config
        self.session = None
        self.connection_context = None
        self._initialized = False
        self._connection_attempts = 0
        self._last_error = None
        
    async def __aenter__(self):
        """Context manager entry - Microsoft-style initialization."""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - Microsoft-style cleanup."""
        await self.cleanup()

    async def initialize(self):
        """Initialize connection to MCP server with retry logic and enhanced error handling."""
        if self._initialized:
            return
            
        self._connection_attempts = 0
        last_exception = None
        
        while self._connection_attempts < self.server_config.max_retries:
            self._connection_attempts += 1
            
            try:
                logger.debug(f"MCP connection attempt {self._connection_attempts}/{self.server_config.max_retries} for {self.server_config.name}")
                
                if self.server_config.transport == "stdio":
                    await self._initialize_stdio()
                elif self.server_config.transport == "sse":
                    await self._initialize_sse()
                elif self.server_config.transport == "streamable_http":
                    await self._initialize_streamable_http()
                elif self.server_config.transport == "websocket":
                    await self._initialize_websocket()
                else:
                    raise MCPConnectionError(f"Unsupported transport: {self.server_config.transport}")
                
                self._initialized = True
                self._last_error = None
                logger.info(f"✅ MCP client connected to {self.server_config.name} via {self.server_config.transport} (attempt {self._connection_attempts})")
                return
                
            except asyncio.TimeoutError as e:
                last_exception = MCPTimeoutError(f"Connection timeout after {self.server_config.timeout}s: {e}")
                logger.warning(f"⏱️ MCP connection timeout for {self.server_config.name} (attempt {self._connection_attempts}): {e}")
                
            except Exception as e:
                last_exception = MCPConnectionError(f"Connection failed: {e}")
                logger.warning(f"⚠️ MCP connection failed for {self.server_config.name} (attempt {self._connection_attempts}): {e}")
            
            # Wait before retry (except on last attempt)
            if self._connection_attempts < self.server_config.max_retries:
                retry_delay = self.server_config.retry_delay * (2 ** (self._connection_attempts - 1))  # Exponential backoff
                logger.debug(f"Retrying MCP connection in {retry_delay:.1f}s...")
                await asyncio.sleep(retry_delay)
        
        # All retries exhausted
        self._last_error = last_exception
        error_msg = f"Failed to initialize MCP client {self.server_config.name} after {self.server_config.max_retries} attempts: {last_exception}"
        
        if self.server_config.graceful_degradation:
            logger.warning(f"⚠️ {error_msg} (continuing with graceful degradation)")
            return  # Don't raise, allow graceful degradation
        else:
            logger.error(f"❌ {error_msg}")
            raise last_exception

    async def _initialize_stdio(self):
        """Initialize stdio transport."""
        server_params = StdioServerParameters(
            command=self.server_config.command,
            args=self.server_config.args,
            env=self.server_config.env
        )

        self.connection_context = stdio_client(server_params)
        read, write = await asyncio.wait_for(
            self.connection_context.__aenter__(), 
            timeout=self.server_config.timeout
        )

        session_context = ClientSession(read, write)
        self.session = await asyncio.wait_for(
            session_context.__aenter__(),
            timeout=self.server_config.timeout
        )

        await asyncio.wait_for(
            self.session.initialize(),
            timeout=self.server_config.timeout
        )

    async def _initialize_sse(self):
        """Initialize SSE transport."""
        from mcp.client.sse import sse_client
        
        self.connection_context = sse_client(self.server_config.url)
        read, write = await asyncio.wait_for(
            self.connection_context.__aenter__(),
            timeout=self.server_config.timeout
        )

        session_context = ClientSession(read, write)
        self.session = await asyncio.wait_for(
            session_context.__aenter__(),
            timeout=self.server_config.timeout
        )

        await asyncio.wait_for(
            self.session.initialize(),
            timeout=self.server_config.timeout
        )

    async def _initialize_streamable_http(self):
        """Initialize Streamable HTTP transport (MCP 1.8+)."""
        try:
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError:
            raise ImportError(
                "Streamable HTTP transport requires mcp>=1.8. "
                "Install with: pip install 'mcp>=1.8'"
            )
        
        kwargs = {"url": self.server_config.url}
        if self.server_config.headers:
            kwargs["headers"] = self.server_config.headers
        if self.server_config.timeout:
            kwargs["timeout"] = self.server_config.timeout
            
        self.connection_context = streamablehttp_client(**kwargs)
        read, write, callback = await asyncio.wait_for(
            self.connection_context.__aenter__(),
            timeout=self.server_config.timeout
        )

        session_context = ClientSession(read, write)
        self.session = await asyncio.wait_for(
            session_context.__aenter__(),
            timeout=self.server_config.timeout
        )

        await asyncio.wait_for(
            self.session.initialize(),
            timeout=self.server_config.timeout
        )

    async def _initialize_websocket(self):
        """Initialize WebSocket transport."""
        from mcp.client.websocket import websocket_client
        
        self.connection_context = websocket_client(self.server_config.url)
        read, write = await asyncio.wait_for(
            self.connection_context.__aenter__(),
            timeout=self.server_config.timeout
        )

        session_context = ClientSession(read, write)
        self.session = await asyncio.wait_for(
            session_context.__aenter__(),
            timeout=self.server_config.timeout
        )

        await asyncio.wait_for(
            self.session.initialize(),
            timeout=self.server_config.timeout
        )

    async def list_tools(self):
        """List tools available from the MCP server with enhanced error handling."""
        if not self._initialized:
            await self.initialize()
        
        if not self.session:
            if self.server_config.graceful_degradation:
                logger.warning(f"⚠️ MCP client {self.server_config.name} not initialized - returning empty tools list")
                return type('MockResponse', (), {'tools': []})()  # Mock response with empty tools
            else:
                raise MCPConnectionError(f"MCP client {self.server_config.name} not initialized")
        
        try:
            return await asyncio.wait_for(
                self.session.list_tools(), 
                timeout=self.server_config.timeout
            )
        except asyncio.TimeoutError as e:
            error_msg = f"Timeout listing tools from {self.server_config.name}: {e}"
            if self.server_config.graceful_degradation:
                logger.warning(f"⚠️ {error_msg} - returning empty tools list")
                return type('MockResponse', (), {'tools': []})()
            else:
                raise MCPTimeoutError(error_msg)
        except Exception as e:
            error_msg = f"Failed to list tools from {self.server_config.name}: {e}"
            if self.server_config.graceful_degradation:
                logger.warning(f"⚠️ {error_msg} - returning empty tools list")
                return type('MockResponse', (), {'tools': []})()
            else:
                raise MCPConnectionError(error_msg)

    async def cleanup(self):
        """Clean up MCP client connection with enhanced error handling."""
        cleanup_errors = []
        
        # Cleanup session
        if self.session and hasattr(self.session, "__aexit__"):
            try:
                await asyncio.wait_for(
                    self.session.__aexit__(None, None, None),
                    timeout=5.0  # Quick cleanup timeout
                )
                logger.debug(f"✅ MCP session cleanup successful for {self.server_config.name}")
            except Exception as e:
                cleanup_errors.append(f"session cleanup: {e}")
                logger.warning(f"⚠️ MCP session cleanup failed for {self.server_config.name}: {e}")
        
        # Cleanup connection context
        if self.connection_context and hasattr(self.connection_context, "__aexit__"):
            try:
                await asyncio.wait_for(
                    self.connection_context.__aexit__(None, None, None),
                    timeout=5.0  # Quick cleanup timeout
                )
                logger.debug(f"✅ MCP connection cleanup successful for {self.server_config.name}")
            except Exception as e:
                cleanup_errors.append(f"connection cleanup: {e}")
                logger.warning(f"⚠️ MCP connection cleanup failed for {self.server_config.name}: {e}")
        
        self._initialized = False
        self.session = None
        self.connection_context = None
        
        if cleanup_errors:
            logger.warning(f"⚠️ MCP cleanup completed with {len(cleanup_errors)} errors for {self.server_config.name}")
        else:
            logger.debug(f"✅ MCP cleanup completed successfully for {self.server_config.name}")
    
    def is_healthy(self) -> bool:
        """Check if the MCP client is healthy and ready to use."""
        return self._initialized and self.session is not None and self._last_error is None
    
    def get_status(self) -> dict:
        """Get detailed status information about the MCP client."""
        return {
            "name": self.server_config.name,
            "transport": self.server_config.transport,
            "initialized": self._initialized,
            "healthy": self.is_healthy(),
            "connection_attempts": self._connection_attempts,
            "max_retries": self.server_config.max_retries,
            "last_error": str(self._last_error) if self._last_error else None,
            "graceful_degradation": self.server_config.graceful_degradation
        }


def _extract_parameter_info(tool_schema: dict, tool_name: str) -> List[Dict[str, Any]]:
    """Extract parameter information from MCP tool input schema."""
    parameters = []
    
    if not isinstance(tool_schema, dict):
        logger.debug(f"No valid schema found for tool {tool_name}")
        return parameters
    
    properties = tool_schema.get('properties', {})
    required_fields = tool_schema.get('required', [])
    
    for param_name, param_info in properties.items():
        if not isinstance(param_info, dict):
            continue
            
        param_type = param_info.get('type', 'string')
        param_description = param_info.get('description', f"Parameter {param_name}")
        param_default = param_info.get('default')
        param_enum = param_info.get('enum')
        param_format = param_info.get('format')
        
        # Convert JSON Schema types to Python types
        python_type = _json_schema_to_python_type(param_type, param_info)
        
        parameter_info = {
            'name': param_name,
            'type': python_type,
            'description': param_description,
            'required': param_name in required_fields,
            'default': param_default,
            'enum': param_enum,
            'format': param_format,
            'json_type': param_type,
            'original_schema': param_info
        }
        
        parameters.append(parameter_info)
        logger.debug(f"Extracted parameter {param_name}: {python_type.__name__} ({'required' if parameter_info['required'] else 'optional'})")
    
    return parameters


def _json_schema_to_python_type(json_type: str, schema_info: dict) -> type:
    """Convert JSON Schema type to Python type annotation."""
    from typing import Union, List, Dict, Any
    
    type_mapping = {
        'string': str,
        'integer': int,
        'number': float,
        'boolean': bool,
        'array': List[Any],
        'object': Dict[str, Any],
        'null': type(None)
    }
    
    # Handle arrays with item type specification
    if json_type == 'array':
        items_schema = schema_info.get('items', {})
        if isinstance(items_schema, dict):
            item_type = items_schema.get('type', 'string')
            item_python_type = type_mapping.get(item_type, str)
            return List[item_python_type]
        return List[Any]
    
    # Handle objects with property specification
    if json_type == 'object':
        return Dict[str, Any]
    
    # Handle union types (anyOf, oneOf)
    if 'anyOf' in schema_info or 'oneOf' in schema_info:
        union_schemas = schema_info.get('anyOf', schema_info.get('oneOf', []))
        if union_schemas:
            union_types = []
            for union_schema in union_schemas:
                if isinstance(union_schema, dict):
                    union_type = union_schema.get('type', 'string')
                    union_types.append(type_mapping.get(union_type, str))
            if union_types:
                return Union[tuple(union_types)]
    
    return type_mapping.get(json_type, str)


def _create_dynamic_mcp_function(tool, mcp_client: SimplifiedMCPClient, parameters_info: List[Dict[str, Any]]):
    """Create a dynamic MCP function with proper parameter signature."""
    from semantic_kernel.functions import kernel_function
    from typing import Annotated, get_type_hints
    import inspect
    
    # Prepare the function signature components
    sig_params = []
    sig_annotations = {}
    
    for param_info in parameters_info:
        param_name = param_info['name']
        param_type = param_info['type']
        param_description = param_info['description']
        is_required = param_info['required']
        default_value = param_info['default']
        
        # Create annotated type with description
        annotated_type = Annotated[param_type, param_description]
        sig_annotations[param_name] = annotated_type
        
        # Create parameter for signature
        if is_required and default_value is None:
            param = inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotated_type)
        else:
            default = default_value if default_value is not None else (None if not is_required else inspect.Parameter.empty)
            param = inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotated_type, default=default)
        
        sig_params.append(param)
    
    # Create the function signature
    sig = inspect.Signature(sig_params, return_annotation=str)
    
    # Create the dynamic function
    async def dynamic_mcp_func(**kwargs) -> str:
        f"""Dynamic MCP function for {tool.name} with enhanced parameter handling."""
        try:
            # Check client health
            if not mcp_client.is_healthy():
                await mcp_client.initialize()
                
            if not mcp_client.session:
                if mcp_client.server_config.graceful_degradation:
                    return f"❌ MCP server '{mcp_client.server_config.name}' is unavailable. Please check your configuration and try again."
                else:
                    raise MCPConnectionError(f"MCP client {mcp_client.server_config.name} not initialized")
            
            # Validate and prepare arguments
            validated_args = _validate_and_coerce_parameters(kwargs, parameters_info, tool.name)
            
            # Call the MCP tool with timeout
            result = await asyncio.wait_for(
                mcp_client.session.call_tool(tool.name, arguments=validated_args),
                timeout=mcp_client.server_config.timeout
            )
            
            # Extract content
            content_parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    content_parts.append(content.text)
                else:
                    content_parts.append(str(content))
            
            return "\n".join(content_parts)
            
        except asyncio.TimeoutError as e:
            error_msg = f"⏱️ Timeout calling {tool.name} on {mcp_client.server_config.name}: {e}"
            logger.warning(error_msg)
            if mcp_client.server_config.graceful_degradation:
                return f"❌ {error_msg}. Please try again with simpler parameters."
            else:
                raise MCPTimeoutError(error_msg)
                
        except Exception as e:
            error_msg = f"Error calling MCP tool {tool.name} on {mcp_client.server_config.name}: {e}"
            logger.error(error_msg)
            if mcp_client.server_config.graceful_degradation:
                return f"❌ {error_msg}. Please check your parameters and try again."
            else:
                raise MCPToolError(error_msg)
    
    # Set the function signature and annotations
    dynamic_mcp_func.__signature__ = sig
    dynamic_mcp_func.__annotations__ = sig_annotations
    dynamic_mcp_func.__name__ = f"{tool.name}_dynamic"
    dynamic_mcp_func.__doc__ = f"{tool.description}\n\nDynamically generated function with parameters:\n" + \
                              "\n".join([f"- {p['name']} ({p['type'].__name__}): {p['description']}" for p in parameters_info])
    
    # Apply kernel_function decorator
    decorated_func = kernel_function(
        name=tool.name,
        description=tool.description
    )(dynamic_mcp_func)
    
    logger.info(f"✅ Created dynamic function for {tool.name} with {len(parameters_info)} parameters")
    return decorated_func


def _validate_and_coerce_parameters(kwargs: dict, parameters_info: List[Dict[str, Any]], tool_name: str) -> dict:
    """Validate and coerce parameters according to their schema definitions."""
    validated_args = {}
    
    for param_info in parameters_info:
        param_name = param_info['name']
        param_type = param_info['type']
        is_required = param_info['required']
        param_enum = param_info.get('enum')
        param_format = param_info.get('format')
        json_type = param_info['json_type']
        
        # Check if parameter is provided
        if param_name in kwargs:
            value = kwargs[param_name]
            
            # Handle None values
            if value is None:
                if is_required:
                    raise MCPToolError(f"Required parameter '{param_name}' cannot be None for tool {tool_name}")
                continue
            
            # Type coercion and validation
            try:
                coerced_value = _coerce_parameter_value(value, param_type, json_type, param_format, param_enum, param_name, tool_name)
                validated_args[param_name] = coerced_value
                
            except Exception as e:
                raise MCPToolError(f"Parameter '{param_name}' validation failed for tool {tool_name}: {e}")
                
        elif is_required:
            raise MCPToolError(f"Required parameter '{param_name}' missing for tool {tool_name}")
    
    return validated_args


def _coerce_parameter_value(value: Any, python_type: type, json_type: str, param_format: str, param_enum: list, param_name: str, tool_name: str) -> Any:
    """Coerce a parameter value to the expected type with validation."""
    from typing import get_origin, get_args
    
    # Handle enum validation first
    if param_enum and value not in param_enum:
        raise ValueError(f"Value '{value}' not in allowed values: {param_enum}")
    
    # Handle basic types
    if json_type == 'string':
        if param_format == 'date':
            # Basic date format validation
            import re
            if not re.match(r'\d{4}-\d{2}-\d{2}', str(value)):
                raise ValueError(f"Date format should be YYYY-MM-DD, got: {value}")
        elif param_format == 'email':
            import re
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', str(value)):
                raise ValueError(f"Invalid email format: {value}")
        return str(value)
    
    elif json_type == 'integer':
        if isinstance(value, str) and value.isdigit():
            return int(value)
        elif isinstance(value, (int, float)):
            return int(value)
        else:
            raise ValueError(f"Cannot convert '{value}' to integer")
    
    elif json_type == 'number':
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                raise ValueError(f"Cannot convert '{value}' to number")
        elif isinstance(value, (int, float)):
            return float(value)
        else:
            raise ValueError(f"Cannot convert '{value}' to number")
    
    elif json_type == 'boolean':
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            if value.lower() in ('true', '1', 'yes', 'on'):
                return True
            elif value.lower() in ('false', '0', 'no', 'off'):
                return False
            else:
                raise ValueError(f"Cannot convert '{value}' to boolean")
        elif isinstance(value, (int, float)):
            return bool(value)
        else:
            raise ValueError(f"Cannot convert '{value}' to boolean")
    
    elif json_type == 'array':
        if not isinstance(value, list):
            # Try to convert comma-separated string to list
            if isinstance(value, str):
                return [item.strip() for item in value.split(',') if item.strip()]
            else:
                return [value]  # Single item becomes list
        return value
    
    elif json_type == 'object':
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            # Try to parse as JSON
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError(f"Cannot parse '{value}' as JSON object")
        else:
            raise ValueError(f"Cannot convert '{value}' to object")
    
    # Default: return as-is
    return value


def create_mcp_tool_function(tool, mcp_client: SimplifiedMCPClient):
    """Create a properly decorated MCP tool function for Semantic Kernel with dynamic parameter detection."""
    from semantic_kernel.functions import kernel_function
    from typing import Annotated, Optional, Union, Any, List, Dict
    import inspect
    
    # Extract parameter information from MCP tool schema
    tool_schema = getattr(tool, 'inputSchema', {})
    parameters_info = _extract_parameter_info(tool_schema, tool.name)
    
    # If we have proper parameter schema, create a dynamic function
    if parameters_info and len(parameters_info) > 0:
        return _create_dynamic_mcp_function(tool, mcp_client, parameters_info)
    
    # Fallback: For search_repositories specifically, create a function with explicit parameters
    if tool.name == "search_repositories":
        @kernel_function(
            name=tool.name,
            description=tool.description
        )
        async def search_repositories_func(
            query: Annotated[str, "Search query for repositories"],
            limit: Annotated[int, "Maximum number of results to return"] = 30
        ) -> str:
            """Search for GitHub repositories with enhanced error handling."""
            try:
                # Check client health
                if not mcp_client.is_healthy():
                    await mcp_client.initialize()
                    
                if not mcp_client.session:
                    if mcp_client.server_config.graceful_degradation:
                        return f"❌ MCP server '{mcp_client.server_config.name}' is unavailable. Please check your configuration and try again."
                    else:
                        raise MCPConnectionError(f"MCP client {mcp_client.server_config.name} not initialized")
                
                # Prepare arguments with validation
                arguments = {"query": str(query), "limit": int(limit)}
                
                # Call the MCP tool with timeout
                result = await asyncio.wait_for(
                    mcp_client.session.call_tool(tool.name, arguments=arguments),
                    timeout=mcp_client.server_config.timeout
                )
                
                # Extract content
                content_parts = []
                for content in result.content:
                    if hasattr(content, "text"):
                        content_parts.append(content.text)
                    else:
                        content_parts.append(str(content))
                
                return "\n".join(content_parts)
                
            except asyncio.TimeoutError as e:
                error_msg = f"⏱️ Timeout calling {tool.name} on {mcp_client.server_config.name}: {e}"
                logger.warning(error_msg)
                if mcp_client.server_config.graceful_degradation:
                    return f"❌ {error_msg}. Please try again with a simpler query."
                else:
                    raise MCPTimeoutError(error_msg)
                    
            except Exception as e:
                error_msg = f"Error calling MCP tool {tool.name} on {mcp_client.server_config.name}: {e}"
                logger.error(error_msg)
                if mcp_client.server_config.graceful_degradation:
                    return f"❌ {error_msg}. Please check your configuration and try again."
                else:
                    raise MCPToolError(error_msg)
        
        return search_repositories_func
    
    # For other tools, create a generic function with kwargs
    @kernel_function(
        name=tool.name,
        description=tool.description
    )
    async def mcp_tool_func(
        arguments: Annotated[Optional[str], "JSON string of arguments for the tool"] = None
    ) -> str:
        """Execute MCP tool with enhanced error handling and validation."""
        try:
            # Check client health
            if not mcp_client.is_healthy():
                await mcp_client.initialize()
                
            if not mcp_client.session:
                if mcp_client.server_config.graceful_degradation:
                    return f"❌ MCP server '{mcp_client.server_config.name}' is unavailable. Please check your configuration and try again."
                else:
                    raise MCPConnectionError(f"MCP client {mcp_client.server_config.name} not initialized")
            
            # Parse and validate arguments
            import json
            args_dict = {}
            if arguments:
                try:
                    args_dict = json.loads(arguments)
                    if not isinstance(args_dict, dict):
                        raise ValueError("Arguments must be a JSON object")
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON arguments for {tool.name}: {e}"
                    logger.warning(error_msg)
                    if mcp_client.server_config.graceful_degradation:
                        return f"❌ {error_msg}. Please provide valid JSON arguments."
                    else:
                        raise MCPToolError(error_msg)
                except ValueError as e:
                    error_msg = f"Invalid argument format for {tool.name}: {e}"
                    logger.warning(error_msg)
                    if mcp_client.server_config.graceful_degradation:
                        return f"❌ {error_msg}"
                    else:
                        raise MCPToolError(error_msg)
            
            # Call the MCP tool with timeout
            result = await asyncio.wait_for(
                mcp_client.session.call_tool(tool.name, arguments=args_dict),
                timeout=mcp_client.server_config.timeout
            )
            
            # Extract content
            content_parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    content_parts.append(content.text)
                else:
                    content_parts.append(str(content))
            
            return "\n".join(content_parts)
            
        except asyncio.TimeoutError as e:
            error_msg = f"⏱️ Timeout calling {tool.name} on {mcp_client.server_config.name}: {e}"
            logger.warning(error_msg)
            if mcp_client.server_config.graceful_degradation:
                return f"❌ {error_msg}. Please try again or check the MCP server."
            else:
                raise MCPTimeoutError(error_msg)
                
        except Exception as e:
            error_msg = f"Error calling MCP tool {tool.name} on {mcp_client.server_config.name}: {e}"
            logger.error(error_msg)
            if mcp_client.server_config.graceful_degradation:
                return f"❌ {error_msg}. Please check your configuration and try again."
            else:
                raise MCPToolError(error_msg)
    
    return mcp_tool_func


class SimplifiedMCPIntegration:
    """Microsoft-style simplified MCP integration for Semantic Kernel.
    
    Follows Microsoft's official Semantic Kernel Python MCP patterns:
    - Direct plugin registration like MCPStdioPlugin
    - Clean function names (GitHub.search_repositories vs call_mcp_tool)
    - Context manager lifecycle management
    - Better LLM function calling reliability
    
    Reference: https://devblogs.microsoft.com/semantic-kernel/semantic-kernel-adds-model-context-protocol-mcp-support-for-python/
    """
    
    @staticmethod
    async def add_mcp_tools_to_kernel(kernel: Kernel, mcp_configs: list[dict[str, Any]]):
        """Add MCP tools directly to kernel with enhanced validation and error handling.
        
        Equivalent to Microsoft's approach:
        ```python
        async with MCPStdioPlugin(name="GitHub", command="npx", args=["github-mcp"]) as plugin:
            kernel.add_plugin(plugin, "GitHub")
        ```
        
        But using YAML configuration for enterprise deployment with bulletproof validation.
        """
        if not mcp_configs:
            logger.debug("No MCP servers configured")
            return
        
        # Import validation here to avoid circular imports
        try:
            from sk_agents.mcp_validation import MCPConfigValidator
            
            # Validate configuration before attempting connections
            validator = MCPConfigValidator()
            is_valid, errors, warnings = validator.validate_mcp_config(mcp_configs)
            
            # Log validation results
            if warnings:
                for warning in warnings:
                    logger.warning(f"⚠️ MCP Config Warning: {warning}")
            
            if not is_valid:
                for error in errors:
                    logger.error(f"❌ MCP Config Error: {error}")
                # Continue with graceful degradation if any configs are valid
                logger.warning("⚠️ Some MCP configurations are invalid - attempting to load valid ones")
            
        except ImportError:
            logger.warning("⚠️ MCP validation module not available - proceeding without validation")
        
        successful_integrations = 0
        total_tools_added = 0
        
        for config_dict in mcp_configs:
            try:
                config = MCPServerConfig(**config_dict)
                logger.debug(f"Processing MCP server: {config.name}")
                
                # Use Microsoft-style context manager pattern with enhanced error handling
                async with SimplifiedMCPClient(config) as mcp_client:
                    # Check client health before proceeding
                    if not mcp_client.is_healthy() and not config.graceful_degradation:
                        logger.error(f"❌ MCP client {config.name} is not healthy and graceful degradation is disabled")
                        continue
                    
                    # Get tools from server
                    tools_response = await mcp_client.list_tools()
                    
                    if not tools_response.tools:
                        logger.warning(f"⚠️ No tools available from MCP server {config.name}")
                        continue
                    
                    # Convert each tool to a Semantic Kernel function
                    kernel_functions = []
                    failed_tools = 0
                    
                    for tool in tools_response.tools:
                        try:
                            # Create the properly decorated function
                            tool_func = create_mcp_tool_function(tool, mcp_client)
                            kernel_functions.append(tool_func)
                            logger.debug(f"✅ Created function for tool: {tool.name}")
                        except Exception as e:
                            failed_tools += 1
                            logger.error(f"❌ Failed to create function for tool {tool.name}: {e}")
                    
                    if not kernel_functions:
                        logger.warning(f"⚠️ No valid tools could be created from MCP server {config.name}")
                        continue
                    
                    # Add functions to kernel as a named plugin (like Microsoft's approach)
                    plugin_name = config.plugin_name or config.name
                    
                    # Add each function individually to the kernel
                    for func in kernel_functions:
                        try:
                            kernel.add_function(function=func, plugin_name=plugin_name)
                        except Exception as e:
                            logger.error(f"❌ Failed to add function {func.__name__} to kernel: {e}")
                    
                    successful_integrations += 1
                    total_tools_added += len(kernel_functions)
                    
                    logger.info(f"✅ Added {len(kernel_functions)} MCP tools from {config.name} as '{plugin_name}' plugin")
                    if failed_tools > 0:
                        logger.warning(f"⚠️ {failed_tools} tools failed to load from {config.name}")
                    logger.info(f"🎉 Microsoft-style MCP integration successful for {plugin_name}")
                
            except Exception as e:
                error_msg = f"Failed to add MCP tools from {config_dict.get('name', 'unnamed')}: {e}"
                logger.error(f"❌ {error_msg}")
                
                # Check if graceful degradation is enabled
                config_graceful = config_dict.get('graceful_degradation', True)
                if not config_graceful:
                    logger.error(f"❌ Graceful degradation disabled for {config_dict.get('name', 'unnamed')} - stopping MCP integration")
                    raise MCPConnectionError(error_msg)
                else:
                    logger.warning(f"⚠️ Continuing with graceful degradation for {config_dict.get('name', 'unnamed')}")
        
        # Final summary
        if successful_integrations > 0:
            logger.info(f"🎉 MCP Integration Summary: {successful_integrations}/{len(mcp_configs)} servers connected, {total_tools_added} tools added")
        else:
            logger.warning(f"⚠️ No MCP servers could be connected from {len(mcp_configs)} configured servers")
            if not any(config.get('graceful_degradation', True) for config in mcp_configs):
                raise MCPConnectionError("All MCP servers failed to connect and graceful degradation is disabled")


class TealAgentsMCPServer:
    """MCP Server implementation for exposing teal-agents as MCP servers.
    
    This enables external tools (Claude Desktop, VSCode Copilot, etc.) to consume
    teal-agents as MCP servers, providing bidirectional MCP integration.
    
    Equivalent to Microsoft's agent.as_mcp_server() functionality.
    """
    
    def __init__(self, agent):
        self.agent = agent
        self.tools = []
        self._extract_agent_tools()
        
    def _extract_agent_tools(self):
        """Extract tools from agent's kernel plugins."""
        try:
            # Get all plugins from the agent's kernel
            if hasattr(self.agent, 'kernel') and hasattr(self.agent.kernel, 'plugins'):
                for plugin_name, plugin in self.agent.kernel.plugins.items():
                    if hasattr(plugin, 'functions'):
                        for func_name, func in plugin.functions.items():
                            tool_info = {
                                "name": f"{plugin_name}.{func_name}" if plugin_name != "default" else func_name,
                                "description": getattr(func, 'description', f"Function {func_name} from {plugin_name}"),
                                "plugin_name": plugin_name,
                                "function_name": func_name,
                                "function": func,
                                "input_schema": self._extract_function_schema(func)
                            }
                            self.tools.append(tool_info)
                            
            logger.info(f"✅ Extracted {len(self.tools)} tools from agent")
            
        except Exception as e:
            logger.error(f"❌ Failed to extract agent tools: {e}")
            
    def _extract_function_schema(self, func):
        """Extract JSON schema from function parameters."""
        import inspect
        from typing import get_type_hints
        
        try:
            # Get function signature
            sig = inspect.signature(func.invoke) if hasattr(func, 'invoke') else inspect.signature(func)
            hints = get_type_hints(func.invoke) if hasattr(func, 'invoke') else get_type_hints(func)
            
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'kernel', 'context']:
                    continue
                    
                param_type = hints.get(param_name, str)
                
                # Convert Python types to JSON schema types
                if param_type == str:
                    json_type = "string"
                elif param_type == int:
                    json_type = "integer"
                elif param_type == float:
                    json_type = "number"
                elif param_type == bool:
                    json_type = "boolean"
                else:
                    json_type = "string"
                    
                properties[param_name] = {
                    "type": json_type,
                    "description": f"Parameter {param_name}"
                }
                
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
                    
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
            
        except Exception as e:
            logger.warning(f"Could not extract schema for function: {e}")
            return {"type": "object", "properties": {}}
            
    async def list_tools(self):
        """Return list of available MCP tools."""
        mcp_tools = []
        for tool in self.tools:
            mcp_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"]
            })
        return mcp_tools
        
    async def call_tool(self, name: str, arguments: dict):
        """Execute a tool with given arguments."""
        import inspect
        
        try:
            # Find the tool
            tool = None
            for t in self.tools:
                if t["name"] == name:
                    tool = t
                    break
                    
            if not tool:
                raise ValueError(f"Tool '{name}' not found")
                
            # Execute the function
            func = tool["function"]
            if hasattr(func, 'invoke'):
                # Semantic Kernel function
                try:
                    from semantic_kernel import KernelArguments
                    args = KernelArguments(**arguments)
                    result = await func.invoke(kernel=self.agent.kernel, arguments=args)
                    return str(result.value) if hasattr(result, 'value') else str(result)
                except ImportError:
                    # Fallback for older semantic-kernel versions
                    result = await func.invoke(kernel=self.agent.kernel, **arguments)
                    return str(result.value) if hasattr(result, 'value') else str(result)
            else:
                # Regular function
                result = await func(**arguments) if inspect.iscoroutinefunction(func) else func(**arguments)
                return str(result)
                
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {e}")
            raise
            
    async def create_mcp_server(self, transport: str = "stdio"):
        """Create and return MCP server instance."""
        try:
            from mcp import types
            from mcp.server import Server
            
            # Create MCP server
            server = Server("teal-agents-mcp-server")
            
            # Register list_tools handler
            @server.list_tools()
            async def handle_list_tools() -> list[types.Tool]:
                tools = await self.list_tools()
                return [
                    types.Tool(
                        name=tool["name"],
                        description=tool["description"],
                        inputSchema=tool["inputSchema"]
                    )
                    for tool in tools
                ]
                
            # Register call_tool handler
            @server.call_tool()
            async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
                try:
                    result = await self.call_tool(name, arguments or {})
                    return [types.TextContent(type="text", text=result)]
                except Exception as e:
                    error_msg = f"Error executing tool '{name}': {str(e)}"
                    return [types.TextContent(type="text", text=error_msg)]
                    
            logger.info(f"✅ Created MCP server with {len(self.tools)} tools")
            return server
            
        except ImportError as e:
            logger.error(f"❌ MCP package not available: {e}")
            logger.info("   Install with: uv add mcp")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to create MCP server: {e}")
            return None


# Define the MCP server method
async def as_mcp_server(self, transport: str = "stdio"):
    """Convert agent to MCP server (Microsoft-style)."""
    mcp_server_wrapper = TealAgentsMCPServer(self)
    return await mcp_server_wrapper.create_mcp_server(transport)


# We'll defer adding MCP server support to avoid circular imports
# This will be called when the module is fully loaded