# YAML-Configured MCP Agent

This example demonstrates how to configure MCP servers directly in YAML configuration files, eliminating the need for Python code to set up MCP integration.

## Features

- **YAML-based MCP Configuration**: Define MCP servers directly in agent config files
- **Global and Agent-specific Servers**: Support for both global and per-agent MCP server configuration
- **Automatic Merging**: Global MCP servers are automatically merged with agent-specific ones
- **Simplified Integration**: Uses Microsoft-style simplified MCP integration by default
- **Production Ready**: Uses the same underlying infrastructure as programmatic configuration

## Configuration Structure

```yaml
apiVersion: skagents/v1
kind: Sequential
description: "YAML-configured agent with MCP integration"
service_name: YamlMcpAgent
version: 0.1
input_type: BaseInput

spec:
  # Global MCP servers - available to all agents
  mcp_servers:
    - name: GlobalFileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/tmp"]
      timeout: 30

  agents:
    - name: filesystem_agent
      model: gpt-4o-mini
      system_prompt: |
        You have access to filesystem tools via MCP:
        - GlobalFileSystem.list_directory(path) - List directory contents
        - GlobalFileSystem.read_file(path) - Read file contents
        - AgentFileSystem.write_file(path, content) - Write to file
      
      # Agent-specific MCP servers - merged with global ones
      mcp_servers:
        - name: AgentFileSystem
          command: npx
          args: ["@modelcontextprotocol/server-filesystem", "."]
          timeout: 30

  tasks:
    - name: filesystem_operations
      task_no: 1
      description: "Filesystem operations task"
      instructions: "Task instructions here..."
      agent: filesystem_agent
```

## Prerequisites

### 1. Install MCP Filesystem Server
```bash
npm install @modelcontextprotocol/server-filesystem
```

### 2. Set Environment Variables
```bash
export TA_API_KEY="your-openai-api-key"
export TA_SERVICE_CONFIG="examples/mcp-yaml-config-agent/config.yaml"
```

## Running the Agent

### 1. Start the Agent Server
```bash
cd src/sk-agents
uv run -- fastapi run src/sk_agents/app.py
```

### 2. Test the Configuration
```bash
# Verify YAML config parsing
uv run python test_yaml_mcp_config.py

# Expected output:
# 🎉 ALL YAML MCP CONFIGURATION TESTS PASSED!
```

### 3. Access the Agent API
- **OpenAPI Docs**: http://localhost:8000/YamlMcpAgent/0.1/docs
- **REST Endpoint**: http://localhost:8000/YamlMcpAgent/0.1/invoke
- **WebSocket**: ws://localhost:8000/YamlMcpAgent/0.1/stream

## MCP Server Configuration Options

### Global MCP Servers
Defined at the `spec.mcp_servers` level and available to all agents:

```yaml
spec:
  mcp_servers:
    - name: shared_filesystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/shared"]
      integration_mode: wrapper
      timeout: 30
```

### Agent-Specific MCP Servers
Defined at the agent level and merged with global servers:

```yaml
agents:
  - name: my_agent
    mcp_servers:
      - name: private_filesystem
        command: npx
        args: ["@modelcontextprotocol/server-filesystem", "/private"]
        integration_mode: direct
        plugin_name: PrivateFS
```

### Integration Modes

#### Wrapper Mode
```yaml
- name: filesystem_wrapper
  command: npx
  args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
  integration_mode: wrapper
  timeout: 30
```

**Agent Usage:**
```python
# Generic MCP function calls
result = await call_mcp_tool('filesystem_wrapper', 'list_directory', '{"path": "/workspace"}')
tools = await list_mcp_tools()
```

#### Direct Mode
```yaml
- name: filesystem_direct
  command: npx
  args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
  integration_mode: direct
  plugin_name: FileSystem
  timeout: 30
```

**Agent Usage:**
```python
# Native Semantic Kernel functions
result = await FileSystem.list_directory(path="/workspace")
content = await FileSystem.read_file(path="README.md")
```

## Example Agent Interactions

### Request
```json
{
  "input": "List all files in the current directory and show me the content of any README file you find"
}
```

### Agent Process
1. **Tool Discovery**: Agent discovers both global and agent-specific MCP tools
2. **Directory Listing**: Uses `agent_filesystem` (direct mode) to list current directory
3. **File Reading**: Uses `FileSystem.read_file()` to read README.md
4. **Response**: Provides structured output with directory contents and README content

### Response
```json
{
  "output": "I found 15 files in the current directory including:\n\n**Directories:**\n- src/\n- tests/\n- examples/\n\n**Files:**\n- README.md\n- pyproject.toml\n- config.yaml\n\n**README.md Content:**\n# Teal Agents Platform\nThis is the core agent framework...",
  "status": "success"
}
```

## Advanced Configuration

### Environment Variables in MCP Config
```yaml
mcp_servers:
  - name: github
    command: npx
    args: ["@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    integration_mode: direct
    plugin_name: GitHub
```

### Multiple MCP Servers with Different Modes
```yaml
mcp_servers:
  # Filesystem operations
  - name: filesystem
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
    integration_mode: direct
    plugin_name: FileSystem
    
  # Database operations
  - name: database
    command: python
    args: ["run_sqlite_mcp_server.py", "/data/app.db"]
    integration_mode: direct
    plugin_name: Database
    
  # Web search (wrapper mode for flexibility)
  - name: search
    command: npx
    args: ["@modelcontextprotocol/server-brave-search"]
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"
    integration_mode: wrapper
    timeout: 45
```

## Troubleshooting

### Configuration Parsing Errors
```bash
# Test YAML config parsing
uv run python test_yaml_mcp_config.py
```

### MCP Server Connection Issues
```bash
# Test MCP server manually
npx @modelcontextprotocol/server-filesystem /tmp
```

### Agent Runtime Errors
Check FastAPI logs for MCP-related errors:
```bash
# Look for MCP initialization logs
tail -f /var/log/agent.log | grep -i mcp
```

## Benefits of YAML Configuration

### 1. **Declarative Configuration**
- No Python code required for MCP setup
- Version-controlled agent configurations
- Easy to modify and deploy

### 2. **Flexible Server Management**
- Global servers shared across agents
- Agent-specific servers for specialized tasks
- Automatic merging with conflict resolution

### 3. **Production Deployment**
- Environment variable substitution
- Configurable timeouts and settings
- Easy to scale and manage

### 4. **Developer Experience**
- Clear, readable configuration
- IDE support for YAML editing
- Validation and error checking

## Related Examples

- `examples/mcp-real-filesystem-agent/` - Programmatic MCP configuration
- `examples/mcp-enhanced-agent/` - Multiple MCP servers and modes
- See `test_yaml_mcp_config.py` for comprehensive configuration testing

## Further Reading

- [Teal Agents MCP Integration Guide](../../CLAUDE.md#enhanced-mcp-integration)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Available MCP Servers](https://github.com/modelcontextprotocol/servers)