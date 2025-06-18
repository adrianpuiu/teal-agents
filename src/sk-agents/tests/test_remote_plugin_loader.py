import pytest
from pydantic import ValidationError
import asyncio

from semantic_kernel import Kernel
from unittest.mock import AsyncMock, MagicMock, patch

from sk_agents.skagents.remote_plugin_loader import (
    RemotePlugin,
    RemotePlugins,
    RemotePluginLoader,
    RemotePluginCatalog,
)
# Placeholder for semantic_kernel.connectors.mcp.MCPStdioPlugin, MCPSsePlugin if needed for type hinting mocks
# For now, direct patching will avoid needing the actual classes in the test file itself for mock setup.


# Test data for RemotePlugin model
VALID_OPENAPI_CONFIG = {
    "plugin_name": "OpenAPIPlugin",
    "openapi_json_path": "/path/to/openapi.json",
    "server_url": "http://localhost:8080",
}

VALID_MCP_STDIO_CONFIG = {
    "plugin_name": "MCPStdioPlugin",
    "mcp_plugin_type": "stdio",
    "mcp_command": "python server.py",
    "mcp_args": ["--port", "1234"],
    "mcp_env": {"MY_VAR": "my_value"},
}

VALID_MCP_SSE_CONFIG = {
    "plugin_name": "MCPSSEPlugin",
    "mcp_plugin_type": "sse",
    "mcp_url": "http://localhost:5000/sse",
}


class TestRemotePluginModel:
    def test_valid_openapi_plugin(self):
        plugin = RemotePlugin(**VALID_OPENAPI_CONFIG)
        assert plugin.plugin_name == VALID_OPENAPI_CONFIG["plugin_name"]
        assert plugin.openapi_json_path == VALID_OPENAPI_CONFIG["openapi_json_path"]
        assert plugin.server_url == VALID_OPENAPI_CONFIG["server_url"]
        assert plugin.mcp_plugin_type is None

    def test_valid_mcp_stdio_plugin(self):
        plugin = RemotePlugin(**VALID_MCP_STDIO_CONFIG)
        assert plugin.plugin_name == VALID_MCP_STDIO_CONFIG["plugin_name"]
        assert plugin.mcp_plugin_type == "stdio"
        assert plugin.mcp_command == VALID_MCP_STDIO_CONFIG["mcp_command"]
        assert plugin.mcp_args == VALID_MCP_STDIO_CONFIG["mcp_args"]
        assert plugin.mcp_env == VALID_MCP_STDIO_CONFIG["mcp_env"]
        assert plugin.openapi_json_path is None

    def test_valid_mcp_sse_plugin(self):
        plugin = RemotePlugin(**VALID_MCP_SSE_CONFIG)
        assert plugin.plugin_name == VALID_MCP_SSE_CONFIG["plugin_name"]
        assert plugin.mcp_plugin_type == "sse"
        assert plugin.mcp_url == VALID_MCP_SSE_CONFIG["mcp_url"]
        assert plugin.openapi_json_path is None

    def test_invalid_stdio_missing_command(self):
        config = VALID_MCP_STDIO_CONFIG.copy()
        del config["mcp_command"]
        with pytest.raises(ValidationError) as excinfo:
            RemotePlugin(**config)
        assert "mcp_command must be set if mcp_plugin_type is 'stdio'" in str(excinfo.value)

    def test_invalid_sse_missing_url(self):
        config = VALID_MCP_SSE_CONFIG.copy()
        del config["mcp_url"]
        with pytest.raises(ValidationError) as excinfo:
            RemotePlugin(**config)
        assert "mcp_url must be set if mcp_plugin_type is 'sse'" in str(excinfo.value)

    def test_invalid_mcp_and_openapi_set(self):
        config = {
            **VALID_MCP_STDIO_CONFIG,
            "openapi_json_path": "/path/to/openapi.json",
        }
        with pytest.raises(ValidationError) as excinfo:
            RemotePlugin(**config)
        assert "openapi_json_path should not be set if mcp_plugin_type is set" in str(excinfo.value)

    def test_invalid_neither_mcp_nor_openapi_set(self):
        config = {"plugin_name": "TestPlugin"} # Only plugin_name
        with pytest.raises(ValidationError) as excinfo:
            RemotePlugin(**config)
        assert "openapi_json_path must be set if mcp_plugin_type is not set" in str(excinfo.value)

    def test_invalid_mcp_plugin_type(self):
        config = VALID_MCP_STDIO_CONFIG.copy()
        config["mcp_plugin_type"] = "invalid_type"
        with pytest.raises(ValidationError) as excinfo:
            RemotePlugin(**config)
        assert 'mcp_plugin_type must be "stdio" or "sse"' in str(excinfo.value)


class TestRemotePluginsModel:
    def test_get_plugin(self):
        plugin1_data = VALID_OPENAPI_CONFIG
        plugin2_data = VALID_MCP_STDIO_CONFIG
        plugins_model = RemotePlugins(remote_plugins=[plugin1_data, plugin2_data])

        plugin1 = plugins_model.get("OpenAPIPlugin")
        assert plugin1 is not None
        assert plugin1.plugin_name == "OpenAPIPlugin"

        plugin2 = plugins_model.get("MCPStdioPlugin")
        assert plugin2 is not None
        assert plugin2.plugin_name == "MCPStdioPlugin"

        assert plugins_model.get("NonExistentPlugin") is None


@pytest.fixture
def mock_kernel() -> AsyncMock:
    kernel = AsyncMock(spec=Kernel)
    kernel.add_plugin = MagicMock() # Synchronous mock for add_plugin
    kernel.add_plugin_from_openapi = MagicMock() # Synchronous mock
    return kernel

@pytest.fixture
def mock_remote_plugin_catalog() -> MagicMock:
    return MagicMock(spec=RemotePluginCatalog)


class TestRemotePluginLoader:
    @pytest.mark.asyncio
    @patch("sk_agents.skagents.remote_plugin_loader.MCPStdioPlugin")
    async def test_load_mcp_stdio_plugin(self, MockMCPStdioPlugin, mock_kernel):
        loader = RemotePluginLoader(catalog=MagicMock()) # Catalog not used in _load_mcp_plugin
        mock_stdio_instance = MockMCPStdioPlugin.return_value

        plugin_config = RemotePlugin(**VALID_MCP_STDIO_CONFIG)

        await loader._load_mcp_plugin(mock_kernel, plugin_config)

        MockMCPStdioPlugin.assert_called_once_with(
            name=plugin_config.plugin_name,
            command=plugin_config.mcp_command,
            args=plugin_config.mcp_args,
            env=plugin_config.mcp_env,
        )
        mock_kernel.add_plugin.assert_called_once_with(mock_stdio_instance)
        assert mock_stdio_instance in loader._mcp_plugins

    @pytest.mark.asyncio
    @patch("sk_agents.skagents.remote_plugin_loader.MCPSsePlugin")
    async def test_load_mcp_sse_plugin(self, MockMCPSsePlugin, mock_kernel):
        loader = RemotePluginLoader(catalog=MagicMock()) # Catalog not used in _load_mcp_plugin
        mock_sse_instance = MockMCPSsePlugin.return_value

        plugin_config = RemotePlugin(**VALID_MCP_SSE_CONFIG)

        await loader._load_mcp_plugin(mock_kernel, plugin_config)

        MockMCPSsePlugin.assert_called_once_with(
            name=plugin_config.plugin_name,
            url=plugin_config.mcp_url,
        )
        mock_kernel.add_plugin.assert_called_once_with(mock_sse_instance)
        assert mock_sse_instance in loader._mcp_plugins

    @pytest.mark.asyncio
    async def test_load_remote_plugins_happy_path(self, mock_kernel, mock_remote_plugin_catalog):
        openapi_plugin = RemotePlugin(**VALID_OPENAPI_CONFIG)
        stdio_plugin = RemotePlugin(**VALID_MCP_STDIO_CONFIG)
        sse_plugin = RemotePlugin(**VALID_MCP_SSE_CONFIG)

        mock_remote_plugin_catalog.get_remote_plugin.side_effect = [
            openapi_plugin,
            stdio_plugin,
            sse_plugin,
        ]

        loader = RemotePluginLoader(catalog=mock_remote_plugin_catalog)

        # Patch _load_mcp_plugin for this test, as it's tested separately
        loader._load_mcp_plugin = AsyncMock()

        plugin_names_to_load = [
            openapi_plugin.plugin_name,
            stdio_plugin.plugin_name,
            sse_plugin.plugin_name,
        ]
        await loader.load_remote_plugins(mock_kernel, plugin_names_to_load)

        # Check openapi call
        mock_kernel.add_plugin_from_openapi.assert_called_once()
        call_args = mock_kernel.add_plugin_from_openapi.call_args
        assert call_args[1]["plugin_name"] == openapi_plugin.plugin_name
        assert call_args[1]["openapi_document_path"] == openapi_plugin.openapi_json_path
        assert call_args[1]["execution_settings"].server_url_override == openapi_plugin.server_url

        # Check _load_mcp_plugin calls
        assert loader._load_mcp_plugin.call_count == 2
        loader._load_mcp_plugin.assert_any_call(mock_kernel, stdio_plugin)
        loader._load_mcp_plugin.assert_any_call(mock_kernel, sse_plugin)

        # Verify get_remote_plugin calls
        assert mock_remote_plugin_catalog.get_remote_plugin.call_count == 3

    @pytest.mark.asyncio
    async def test_load_remote_plugins_empty_list(self, mock_kernel, mock_remote_plugin_catalog):
        loader = RemotePluginLoader(catalog=mock_remote_plugin_catalog)
        loader._load_mcp_plugin = AsyncMock() # Mock this out

        await loader.load_remote_plugins(mock_kernel, [])

        mock_kernel.add_plugin_from_openapi.assert_not_called()
        loader._load_mcp_plugin.assert_not_called()
        mock_remote_plugin_catalog.get_remote_plugin.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_remote_plugins_plugin_not_found(self, mock_kernel, mock_remote_plugin_catalog):
        mock_remote_plugin_catalog.get_remote_plugin.return_value = None
        loader = RemotePluginLoader(catalog=mock_remote_plugin_catalog)

        with pytest.raises(ValueError) as excinfo:
            await loader.load_remote_plugins(mock_kernel, ["NonExistentPlugin"])
        assert "Remote plugin NonExistentPlugin not found in catalog" in str(excinfo.value)
        mock_remote_plugin_catalog.get_remote_plugin.assert_called_once_with("NonExistentPlugin")

    # Test for RemotePluginLoader._load_mcp_plugin with invalid mcp_plugin_type (should not happen due to Pydantic)
    # but good for defense.
    @pytest.mark.asyncio
    async def test_load_mcp_plugin_invalid_type_defense(self, mock_kernel):
        loader = RemotePluginLoader(catalog=MagicMock())
        plugin_config = RemotePlugin(plugin_name="Test", mcp_plugin_type="invalid", mcp_command="cmd")
        # Manually bypass Pydantic validation for this specific test scenario if RemotePlugin direct init is used
        # Or, if constructing RemotePlugin always validates, this test might be for internal logic robustness
        # For now, assuming RemotePlugin ensures valid mcp_plugin_type, this test is more about _load_mcp_plugin's internal else branch.
        # To properly test this, we might need to mock RemotePlugin or construct it carefully.
        # Let's assume pydantic caught it, but if _load_mcp_plugin was called with bad data:

        # To force this, let's create a mock RemotePlugin object that bypasses Pydantic validation
        mock_plugin_config = MagicMock(spec=RemotePlugin)
        mock_plugin_config.plugin_name = "BadTypePlugin"
        mock_plugin_config.mcp_plugin_type = "unknown_type"
        # Ensure other fields that might be checked before mcp_plugin_type are present or None
        mock_plugin_config.mcp_command = None
        mock_plugin_config.mcp_url = None
        mock_plugin_config.openapi_json_path = None # Make it an MCP type conceptually

        with pytest.raises(ValueError) as excinfo:
            await loader._load_mcp_plugin(mock_kernel, mock_plugin_config)
        assert "Unsupported MCP plugin type: unknown_type" in str(excinfo.value)

```

**Explanation of the initial structure and tests:**

1.  **Imports**: All necessary modules like `pytest`, `ValidationError`, `asyncio`, `Kernel`, mocks, and the classes from `remote_plugin_loader` are imported.
2.  **Test Data**: Defined valid configurations for OpenAPI, MCP Stdio, and MCP SSE plugins as dictionaries. This makes tests cleaner.
3.  **`TestRemotePluginModel`**:
    *   Tests for successful instantiation with valid OpenAPI, MCP Stdio, and MCP SSE configurations.
    *   Uses `pytest.raises(ValidationError)` to check for expected validation errors:
        *   Missing `mcp_command` for stdio.
        *   Missing `mcp_url` for sse.
        *   Both `mcp_plugin_type` and `openapi_json_path` are set.
        *   Neither `mcp_plugin_type` nor `openapi_json_path` is set.
        *   Invalid `mcp_plugin_type` value.
4.  **`TestRemotePluginsModel`**:
    *   Simple test for the `get()` method of the `RemotePlugins` collection class.
5.  **Fixtures**:
    *   `mock_kernel`: Provides an `AsyncMock` for the `Kernel` with its `add_plugin` and `add_plugin_from_openapi` methods mocked synchronously for easier assertion.
    *   `mock_remote_plugin_catalog`: Provides a `MagicMock` for `RemotePluginCatalog`.
6.  **`TestRemotePluginLoader`**:
    *   **`test_load_mcp_stdio_plugin`**:
        *   Patches `MCPStdioPlugin` to assert it's called correctly.
        *   Verifies `kernel.add_plugin` is called with the plugin instance.
        *   Checks that the plugin instance is added to `loader._mcp_plugins`.
    *   **`test_load_mcp_sse_plugin`**: Similar to the stdio test, but for `MCPSsePlugin`.
    *   **`test_load_remote_plugins_happy_path`**:
        *   Mocks `RemotePluginCatalog.get_remote_plugin` to return a sequence of different plugin types.
        *   Patches `loader._load_mcp_plugin` with an `AsyncMock` because its internal logic is tested separately. This simplifies this test to focus on the dispatching logic of `load_remote_plugins`.
        *   Asserts `kernel.add_plugin_from_openapi` is called for the OpenAPI plugin.
        *   Asserts `_load_mcp_plugin` is called for both MCP plugins with the correct `RemotePlugin` objects.
    *   **`test_load_remote_plugins_empty_list`**: Ensures no plugin loading methods are called if an empty list of plugin names is provided.
    *   **`test_load_remote_plugins_plugin_not_found`**: Checks that a `ValueError` is raised if `catalog.get_remote_plugin` returns `None` (meaning the plugin name isn't in the catalog).
    *   **`test_load_mcp_plugin_invalid_type_defense`**: This tests the defensive `else` branch in `_load_mcp_plugin`. Since Pydantic should prevent this, a `MagicMock` is used to create a `RemotePlugin` object with an invalid `mcp_plugin_type` to specifically target that code path.

This structure covers all the points mentioned in the subtask description. I will now use the tool to create this file.
