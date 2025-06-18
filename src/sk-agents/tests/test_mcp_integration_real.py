#!/usr/bin/env python3
"""
Real MCP filesystem server integration tests for pytest.
Tests the enhanced MCP integration with actual @modelcontextprotocol/server-filesystem.
"""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

import pytest

from sk_agents.mcp_integration import EnhancedMCPPluginFactory, MCPServerConfig

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_mcp_prerequisites():
    """Check if MCP prerequisites are available."""
    try:
        # Check Node.js
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "Node.js not available"
        
        # Check NPX
        result = subprocess.run(['npx', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "NPX not available"
        
        # Check if MCP filesystem server is available
        result = subprocess.run([
            'npx', '@modelcontextprotocol/server-filesystem', '--version'
        ], capture_output=True, text=True, timeout=10)
        
        # The server doesn't have --version, so we check if it's installed
        # by seeing if npx can resolve it (even if it errors on --version)
        if 'Error accessing directory --version' in result.stderr:
            return True, "MCP filesystem server available"
        
        return False, "MCP filesystem server not available"
        
    except Exception as e:
        return False, f"Prerequisites check failed: {e}"


# Skip these tests if MCP prerequisites are not met
mcp_available, mcp_reason = check_mcp_prerequisites()
skip_mcp_tests = pytest.mark.skipif(
    not mcp_available, 
    reason=f"MCP prerequisites not met: {mcp_reason}. Install with: npm install @modelcontextprotocol/server-filesystem"
)


class TestRealMCPIntegration:
    """Test suite for real MCP filesystem server integration."""

    @skip_mcp_tests
    @pytest.mark.asyncio
    async def test_real_mcp_server_connection(self):
        """Test connection to real MCP filesystem server."""
        current_dir = os.getcwd()
        
        config = MCPServerConfig(
            name="test_real_fs",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", current_dir],
            integration_mode="wrapper",
            timeout=30
        )
        
        plugin = EnhancedMCPPluginFactory.create_from_config([config.model_dump()])
        
        try:
            await plugin.initialize()
            
            # Test tool discovery
            tools_result = await plugin.list_mcp_tools()
            tools_data = json.loads(tools_result)
            
            assert "test_real_fs" in tools_data
            tools = tools_data["test_real_fs"]
            assert len(tools) > 0
            
            # Verify essential tools are available
            tool_names = [tool['name'] for tool in tools]
            assert 'list_directory' in tool_names
            assert 'read_file' in tool_names
            
        finally:
            await plugin.cleanup()

    @skip_mcp_tests
    @pytest.mark.asyncio
    async def test_real_directory_listing(self):
        """Test directory listing with real MCP filesystem server."""
        current_dir = os.getcwd()
        
        config = MCPServerConfig(
            name="test_dir_listing",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", current_dir],
            integration_mode="wrapper",
            timeout=30
        )
        
        plugin = EnhancedMCPPluginFactory.create_from_config([config.model_dump()])
        
        try:
            await plugin.initialize()
            
            # List directory contents
            list_result = await plugin.call_mcp_tool(
                server_name="test_dir_listing",
                tool_name="list_directory",
                arguments=json.dumps({"path": current_dir})
            )
            
            result_data = json.loads(list_result)
            
            assert result_data.get("success") is True
            content = result_data.get('content', '')
            assert len(content) > 0
            
            # Check for expected project files/directories
            expected_items = ["src", "tests", "pyproject.toml"]
            found_items = [item for item in expected_items if item in content]
            assert len(found_items) >= 2, f"Expected items not found. Content: {content[:200]}"
            
            # Verify file/directory classification
            assert '[FILE]' in content or '[DIR]' in content
            
        finally:
            await plugin.cleanup()

    @skip_mcp_tests
    @pytest.mark.asyncio
    async def test_real_file_reading(self):
        """Test file reading with real MCP filesystem server."""
        current_dir = os.getcwd()
        
        # Find a readable file
        test_file = None
        for candidate in ["pyproject.toml", "README.md", ".gitignore"]:
            file_path = Path(current_dir) / candidate
            if file_path.exists() and file_path.is_file():
                test_file = str(file_path)
                break
        
        if not test_file:
            pytest.skip("No suitable test file found for reading test")
        
        config = MCPServerConfig(
            name="test_file_reading",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", current_dir],
            integration_mode="wrapper",
            timeout=30
        )
        
        plugin = EnhancedMCPPluginFactory.create_from_config([config.model_dump()])
        
        try:
            await plugin.initialize()
            
            # Read file contents
            read_result = await plugin.call_mcp_tool(
                server_name="test_file_reading",
                tool_name="read_file",
                arguments=json.dumps({"path": test_file})
            )
            
            result_data = json.loads(read_result)
            
            assert result_data.get("success") is True
            content = result_data.get('content', '')
            assert len(content) > 0
            
            # Verify we got actual file content
            if test_file.endswith("pyproject.toml"):
                assert 'name' in content or '[tool' in content
            elif test_file.endswith("README.md"):
                assert '#' in content or 'README' in content
            
        finally:
            await plugin.cleanup()

    @skip_mcp_tests
    @pytest.mark.asyncio
    async def test_multiple_mcp_operations(self):
        """Test multiple operations with real MCP server."""
        current_dir = os.getcwd()
        
        config = MCPServerConfig(
            name="test_multiple_ops",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", current_dir],
            integration_mode="wrapper",
            timeout=30
        )
        
        plugin = EnhancedMCPPluginFactory.create_from_config([config.model_dump()])
        
        try:
            await plugin.initialize()
            
            # Operation 1: List tools
            tools_result = await plugin.list_mcp_tools()
            tools_data = json.loads(tools_result)
            assert "test_multiple_ops" in tools_data
            
            # Operation 2: List directory
            list_result = await plugin.call_mcp_tool(
                server_name="test_multiple_ops",
                tool_name="list_directory",
                arguments=json.dumps({"path": current_dir})
            )
            list_data = json.loads(list_result)
            assert list_data.get("success") is True
            
            # Operation 3: Get file info (if available)
            tools = tools_data["test_multiple_ops"]
            tool_names = [tool['name'] for tool in tools]
            
            if 'get_file_info' in tool_names:
                # Find a file to get info for
                pyproject_path = Path(current_dir) / "pyproject.toml"
                if pyproject_path.exists():
                    info_result = await plugin.call_mcp_tool(
                        server_name="test_multiple_ops",
                        tool_name="get_file_info",
                        arguments=json.dumps({"path": str(pyproject_path)})
                    )
                    info_data = json.loads(info_result)
                    assert info_data.get("success") is True
            
        finally:
            await plugin.cleanup()

    @skip_mcp_tests
    @pytest.mark.asyncio
    async def test_mcp_error_handling(self):
        """Test error handling with real MCP server."""
        current_dir = os.getcwd()
        
        config = MCPServerConfig(
            name="test_error_handling",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", current_dir],
            integration_mode="wrapper",
            timeout=30
        )
        
        plugin = EnhancedMCPPluginFactory.create_from_config([config.model_dump()])
        
        try:
            await plugin.initialize()
            
            # Test with non-existent directory
            list_result = await plugin.call_mcp_tool(
                server_name="test_error_handling",
                tool_name="list_directory",
                arguments=json.dumps({"path": "/nonexistent/directory/path"})
            )
            
            result_data = json.loads(list_result)
            # Should handle error gracefully
            assert "success" in result_data
            
            # Test with non-existent file
            read_result = await plugin.call_mcp_tool(
                server_name="test_error_handling",
                tool_name="read_file",
                arguments=json.dumps({"path": "/nonexistent/file.txt"})
            )
            
            result_data = json.loads(read_result)
            # Should handle error gracefully
            assert "success" in result_data
            
        finally:
            await plugin.cleanup()


class TestMCPConfiguration:
    """Test MCP configuration and setup."""

    def test_mcp_server_config_creation(self):
        """Test MCP server configuration creation."""
        config = MCPServerConfig(
            name="test_config",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", "/test"],
            integration_mode="wrapper",
            timeout=30
        )
        
        assert config.name == "test_config"
        assert config.command == "npx"
        assert config.integration_mode == "wrapper"
        assert config.timeout == 30

    def test_enhanced_mcp_plugin_factory(self):
        """Test enhanced MCP plugin factory."""
        config_data = {
            'name': 'test_factory',
            'command': 'echo',
            'args': ['test'],
            'integration_mode': 'wrapper'
        }
        
        plugin = EnhancedMCPPluginFactory.create_from_config([config_data])
        
        assert plugin is not None
        assert "test_factory" in plugin.server_configs
        assert plugin.server_configs["test_factory"].integration_mode == "wrapper"

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """Test plugin initialization and cleanup lifecycle."""
        config_data = {
            'name': 'test_lifecycle',
            'command': 'echo',
            'args': ['test'],
            'integration_mode': 'wrapper',
            'timeout': 5
        }
        
        plugin = EnhancedMCPPluginFactory.create_from_config([config_data])
        
        # Test that cleanup works even without initialization
        await plugin.cleanup()
        
        # Test normal lifecycle would work
        # (We don't initialize with 'echo' as it's not a real MCP server)
        assert plugin is not None


# Mark all real MCP tests for easy identification
pytestmark = [
    pytest.mark.integration,
    pytest.mark.mcp,
    pytest.mark.slow
]