# Real MCP Filesystem Agent

This example demonstrates a Teal Agent with real MCP filesystem capabilities using the official `@modelcontextprotocol/server-filesystem` server.

## Features

- **Real MCP Integration**: Uses the official Model Context Protocol filesystem server
- **Dual Integration Modes**: Both wrapper and direct modes for maximum flexibility
- **Comprehensive File Operations**: List, read, write, edit, search, and move files
- **Production Ready**: Tested with real MCP server and actual filesystem operations

## Prerequisites

### 1. Install Node.js and npm
```bash
# Ubuntu/Debian
sudo apt install nodejs npm

# macOS
brew install node

# Windows
# Download from https://nodejs.org/
```

### 2. Install MCP Filesystem Server
```bash
# Install globally
npm install -g @modelcontextprotocol/server-filesystem

# Or install locally in project
npm install @modelcontextprotocol/server-filesystem
```

### 3. Verify Installation
```bash
# Test the MCP server
npx @modelcontextprotocol/server-filesystem /tmp
# Should output: "Secure MCP Filesystem Server running on stdio"
# Press Ctrl+C to exit
```

## Configuration

The agent is configured with two MCP servers demonstrating both integration modes:

### Direct Mode (Recommended)
```yaml
- name: filesystem_direct
  command: npx
  args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
  integration_mode: direct
  plugin_name: FileSystem
```

**Benefits:**
- Tools registered as native Semantic Kernel functions
- Better LLM function calling reliability  
- Type-safe parameters
- IDE support and debugging

**Usage in Agent:**
```python
# Direct function calls
result = await FileSystem.list_directory(path="/workspace")
content = await FileSystem.read_file(path="README.md")
```

### Wrapper Mode (Compatible)
```yaml
- name: filesystem_wrapper
  command: npx
  args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
  integration_mode: wrapper
```

**Benefits:**
- Generic, works with any MCP server
- Full backward compatibility
- Dynamic tool discovery

**Usage in Agent:**
```python
# Generic MCP function calls
result = await call_mcp_tool('filesystem_wrapper', 'list_directory', '{"path": "/workspace"}')
tools = await list_mcp_tools()
```

## Available Tools

The real MCP filesystem server provides these tools:

### Core Operations
- **`list_directory`** - List directory contents with [FILE] and [DIR] prefixes
- **`read_file`** - Read complete file contents with encoding support
- **`write_file`** - Create or completely overwrite files
- **`edit_file`** - Make line-based edits with git-style diffs

### Advanced Operations  
- **`create_directory`** - Create directories including nested paths
- **`move_file`** - Move or rename files and directories
- **`search_files`** - Recursively search for files by pattern
- **`get_file_info`** - Get detailed file metadata (size, dates, permissions)

### Utility Operations
- **`directory_tree`** - Get recursive JSON tree structure
- **`list_allowed_directories`** - Show accessible directory paths

## Running the Agent

### 1. Start the Agent
```bash
cd src/sk-agents
uv run -- fastapi run src/sk_agents/app.py
```

### 2. Set Environment Variables
```bash
export TA_SERVICE_CONFIG="examples/mcp-real-filesystem-agent/config.yaml"
export TA_API_KEY="your-openai-api-key"
```

### 3. Test the Integration
```bash
# Test real MCP functionality
uv run python test_real_mcp_final.py

# Expected output:
# 🎉 REAL MCP FILESYSTEM INTEGRATION SUCCESSFUL!
```

## Example Interactions

### List Directory Contents
**User:** "Show me all files in the current directory"

**Agent Response:**
```
I'll list the contents of the current directory using the filesystem tools.

[Calls FileSystem.list_directory(path=".")]

Here are the contents:

**Directories (3):**
- 📁 src
- 📁 tests  
- 📁 examples

**Files (8):**
- 📄 pyproject.toml (2,297 bytes)
- 📄 README.md (2,318 bytes)
- 📄 .gitignore (3,375 bytes)
- 📄 Makefile (546 bytes)
- 📄 uv.lock (282,328 bytes)
- 📄 test_real_mcp_final.py (4,521 bytes)
- 📄 demo_mcp_agent_capabilities.py (13,045 bytes)
- 📄 sk_agents.sh (1,377 bytes)

Total: 3 directories and 8 files found.
```

### Read File Contents
**User:** "What's in the README.md file?"

**Agent Response:**
```
I'll read the README.md file for you.

[Calls FileSystem.read_file(path="README.md")]

Here's the content of README.md:

# Teal Agents - Core Agent Framework

This is the core agent framework for creating AI-powered agents...

[File content continues...]

The README contains documentation about the Teal Agents platform, including setup instructions, configuration options, and usage examples.
```

### Search for Files
**User:** "Find all Python test files"

**Agent Response:**
```
I'll search for Python test files in the current directory and subdirectories.

[Calls FileSystem.search_files(path=".", pattern="test*.py")]

Found the following Python test files:

1. **test_real_mcp_final.py** - Real MCP filesystem integration test
2. **test_enhanced_mcp.py** - Enhanced MCP functionality tests  
3. **test_direct_tool_registration.py** - Direct tool registration tests
4. **test_focused_edge_cases.py** - Edge case testing suite
5. **tests/test_mcp_integration_real.py** - Pytest integration tests

Total: 5 test files found. These appear to be comprehensive tests for MCP integration functionality.
```

## Directory Security

The MCP filesystem server enforces directory access restrictions:

```bash
# Server started with allowed directory
npx @modelcontextprotocol/server-filesystem /workspace

# Output: "Allowed directories: [ '/workspace' ]"
```

**Security Features:**
- Only operates within specified allowed directories
- Prevents access to system files outside allowed paths
- Validates all file paths before operations
- Provides clear error messages for unauthorized access

## Troubleshooting

### Common Issues

#### 1. MCP Server Not Found
```
Error: Cannot find module '@modelcontextprotocol/server-filesystem'
```
**Solution:** Install the MCP server:
```bash
npm install -g @modelcontextprotocol/server-filesystem
```

#### 2. Permission Denied
```
Error: EACCES: permission denied
```
**Solution:** Check directory permissions or run with appropriate privileges

#### 3. Directory Not Allowed
```
Error: Access denied to directory /restricted
```
**Solution:** Ensure the requested path is within the allowed directories

#### 4. Node.js Version Issues
```
WARN EBADENGINE Unsupported engine
```
**Solution:** MCP servers require Node.js 20 or later:
```bash
# Install newer Node.js version
nvm install 20
nvm use 20
```

### Debugging

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check MCP server connectivity:
```bash
# Test server manually
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | npx @modelcontextprotocol/server-filesystem /workspace
```

## Performance Considerations

- **Timeout Configuration**: Set appropriate timeouts for large directories
- **Directory Size**: Large directories may take longer to list
- **File Size Limits**: Very large files may hit server limits
- **Concurrent Operations**: MCP servers handle one operation at a time

## Production Deployment

For production use:

1. **Install MCP servers** in your deployment environment
2. **Configure allowed directories** appropriately  
3. **Set proper timeouts** for your use case
4. **Monitor server health** and restart if needed
5. **Use direct mode** for better LLM reliability
6. **Implement proper error handling** in your agents

## Related Examples

- `examples/mcp-enhanced-agent/` - Multiple MCP servers with different modes
- `examples/basic-agent/` - Simple agent without MCP
- See `test_real_mcp_final.py` for comprehensive testing examples

## Further Reading

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [MCP Filesystem Server Documentation](https://github.com/modelcontextprotocol/servers)
- [Teal Agents MCP Integration Guide](../../CLAUDE.md#enhanced-mcp-integration)