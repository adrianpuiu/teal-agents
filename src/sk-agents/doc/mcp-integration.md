# MCP Integration Guide

This guide provides comprehensive documentation for Model Context Protocol (MCP) integration in the Teal Agents platform.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Available MCP Servers](#available-mcp-servers)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Topics](#advanced-topics)

## Overview

Model Context Protocol (MCP) enables agents to connect to external tools and services through standardized interfaces. The Teal Agents platform implements Microsoft's official Semantic Kernel MCP pattern for optimal reliability and ease of use.

### Key Benefits

- **Standardized Tool Access** - Connect to any MCP-compatible server
- **Microsoft Alignment** - Follows official Semantic Kernel patterns
- **Clean Function Names** - Tools appear as native functions (e.g., `FileSystem.read_file()`)
- **Multiple Transports** - Support for stdio, HTTP, WebSocket connections
- **Production Ready** - Enterprise-grade error handling and lifecycle management

### Architecture

```
Agent Configuration (YAML)
    ↓
MCP Server Definitions
    ↓
SimplifiedMCPIntegration
    ↓
Semantic Kernel Functions
    ↓
Agent Function Calls
```

## Quick Start

### 1. Install Prerequisites

```bash
# Install Node.js (required for most MCP servers)
# Ubuntu/Debian: sudo apt install nodejs npm
# macOS: brew install node
# Windows: Download from nodejs.org

# Install popular MCP server
npm install -g @modelcontextprotocol/server-filesystem
```

### 2. Configure Agent

Create an agent configuration with MCP servers:

```yaml
apiVersion: skagents/v1
kind: Sequential
description: "My first MCP-enabled agent"
service_name: McpAgent
version: 0.1

spec:
  mcp_servers:
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
  
  agents:
    - name: default
      model: gpt-4o-mini
      system_prompt: |
        You have access to filesystem tools:
        - FileSystem.list_directory(path) - List directory contents
        - FileSystem.read_file(path) - Read file contents
        - FileSystem.write_file(path, content) - Write to file
```

### 3. Start Agent

```bash
export TA_SERVICE_CONFIG="path/to/your/config.yaml"
export TA_API_KEY="your-openai-api-key"

cd src/sk-agents
uv run -- fastapi run src/sk_agents/app.py
```

### 4. Test Functionality

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "List files in the current directory"}'
```

## Configuration

### Basic Configuration

The simplest MCP server configuration:

```yaml
spec:
  mcp_servers:
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
```

### Advanced Configuration

With environment variables, timeouts, and custom settings:

```yaml
spec:
  mcp_servers:
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      timeout: 30
      env:
        DEBUG: "true"
    
    - name: GitHub
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
      timeout: 60
```

### Multi-Transport Configuration

Support for different connection types:

```yaml
spec:
  mcp_servers:
    # Standard stdio connection
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
    
    # HTTP Server-Sent Events
    - name: RemoteAPI
      transport: sse
      url: "http://localhost:8000/sse"
      headers:
        Authorization: "Bearer ${API_TOKEN}"
    
    # WebSocket connection
    - name: RealtimeTools
      transport: websocket
      url: "ws://localhost:8000/ws"
```

### Global vs Agent-Specific Servers

**Global MCP Servers** (available to all agents):
```yaml
spec:
  mcp_servers:
    - name: SharedFileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/shared"]
  
  agents:
    - name: agent1
      # Inherits SharedFileSystem
    - name: agent2
      # Also inherits SharedFileSystem
```

**Agent-Specific MCP Servers** (private to one agent):
```yaml
spec:
  agents:
    - name: specialized_agent
      mcp_servers:
        - name: PrivateTools
          command: npx
          args: ["@modelcontextprotocol/server-filesystem", "/private"]
```

**Mixed Configuration** (global + agent-specific):
```yaml
spec:
  # Global servers
  mcp_servers:
    - name: SharedFileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/shared"]
  
  agents:
    - name: specialized_agent
      # Agent-specific servers (merged with global)
      mcp_servers:
        - name: PrivateTools
          command: npx
          args: ["@modelcontextprotocol/server-filesystem", "/private"]
      # This agent has access to both SharedFileSystem and PrivateTools
```

## Available MCP Servers

### Official MCP Servers

#### Filesystem Server
```bash
npm install -g @modelcontextprotocol/server-filesystem
```

**Configuration:**
```yaml
- name: FileSystem
  command: npx
  args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
```

**Available Tools:**
- `FileSystem.list_directory(path)` - List directory contents
- `FileSystem.read_file(path)` - Read file contents
- `FileSystem.write_file(path, content)` - Write to file
- `FileSystem.edit_file(path, edits)` - Edit existing file
- `FileSystem.create_directory(path)` - Create directory
- `FileSystem.move_file(source, destination)` - Move/rename files

#### GitHub Server
```bash
npm install -g @modelcontextprotocol/server-github
```

**Configuration:**
```yaml
- name: GitHub
  command: npx
  args: ["-y", "@modelcontextprotocol/server-github"]
  env:
    GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

**Available Tools:**
- `GitHub.search_repositories(query)` - Search repositories
- `GitHub.create_repository(name, description)` - Create repository
- `GitHub.get_file_contents(owner, repo, path)` - Get file contents
- `GitHub.create_issue(owner, repo, title, body)` - Create issue

#### SQLite Server
```bash
npm install -g @modelcontextprotocol/server-sqlite
```

**Configuration:**
```yaml
- name: Database
  command: npx
  args: ["@modelcontextprotocol/server-sqlite", "/path/to/database.db"]
```

**Available Tools:**
- `Database.query(sql)` - Execute SQL query
- `Database.schema()` - Get database schema
- `Database.tables()` - List tables

### Community MCP Servers

Many community-created MCP servers are available. See the [MCP Server Registry](https://github.com/modelcontextprotocol/servers) for a complete list.

## Best Practices

### Configuration

1. **Use Descriptive Names**
   ```yaml
   # Good
   - name: ProjectFileSystem
     command: npx
     args: ["@modelcontextprotocol/server-filesystem", "/project"]
   
   # Avoid
   - name: fs1
     command: npx
     args: ["@modelcontextprotocol/server-filesystem", "/project"]
   ```

2. **Set Appropriate Timeouts**
   ```yaml
   - name: FileSystem
     command: npx
     args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
     timeout: 30  # 30 seconds for filesystem operations
   
   - name: SlowAPI
     command: python
     args: ["slow_api_server.py"]
     timeout: 120  # 2 minutes for slow operations
   ```

3. **Use Environment Variables for Secrets**
   ```yaml
   - name: GitHub
     command: npx
     args: ["-y", "@modelcontextprotocol/server-github"]
     env:
       GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"  # From environment
   ```

### System Prompts

1. **Document Available Tools**
   ```yaml
   system_prompt: |
     You have access to the following tools via MCP:
     
     FileSystem tools:
     - FileSystem.list_directory(path) - List directory contents
     - FileSystem.read_file(path) - Read file contents
     - FileSystem.write_file(path, content) - Write to file
     
     Always explain what filesystem operations you're performing.
   ```

2. **Provide Usage Examples**
   ```yaml
   system_prompt: |
     Example usage:
     - To list files: "Show me all Python files in the src directory"
     - To read content: "What's in the README.md file?"
     - To create files: "Create a config file with these settings"
   ```

### Error Handling

1. **Graceful Degradation**
   - Configure fallback options when MCP servers are unavailable
   - Provide helpful error messages to users
   - Use appropriate timeouts to prevent hanging

2. **Monitoring**
   - Monitor MCP server health and connection status
   - Log MCP tool usage for debugging and optimization
   - Set up alerts for MCP server failures

## Troubleshooting

### Common Issues

#### MCP Server Not Found
```
Error: Command 'npx @modelcontextprotocol/server-filesystem' not found
```

**Solution:**
```bash
# Install the MCP server
npm install -g @modelcontextprotocol/server-filesystem

# Verify installation
npx @modelcontextprotocol/server-filesystem --version
```

#### Connection Timeout
```
Error: MCP client connection timeout
```

**Solutions:**
1. Increase timeout in configuration:
   ```yaml
   - name: FileSystem
     command: npx
     args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
     timeout: 60  # Increase from default 30 seconds
   ```

2. Check server responsiveness:
   ```bash
   # Test server manually
   npx @modelcontextprotocol/server-filesystem /workspace
   ```

#### Permission Denied
```
Error: EACCES: permission denied, open '/restricted/file.txt'
```

**Solutions:**
1. Check directory permissions
2. Use appropriate workspace paths
3. Configure server with accessible directories

### Debugging Tools

#### Test MCP Configuration
```bash
cd src/sk-agents
uv run python test_final_mcp_validation.py
```

#### Validate YAML Configuration
```bash
uv run python test_yaml_mcp_config.py
```

#### Test Real MCP Server
```bash
uv run python test_real_mcp_simplified.py
```

### Log Analysis

Look for MCP-related log entries:
```bash
# During agent startup
grep -i "mcp" /var/log/agent.log

# MCP connection issues
grep -i "simplified mcp client" /var/log/agent.log

# Tool execution errors
grep -i "mcp tool" /var/log/agent.log
```

## Advanced Topics

### Custom MCP Servers

You can create custom MCP servers for domain-specific tools:

```python
# custom_mcp_server.py
from mcp import create_server, types

app = create_server("my-custom-server")

@app.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="custom_function",
            description="My custom tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                }
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "custom_function":
        return [types.TextContent(type="text", text=f"Result: {arguments['input']}")]
```

### Transport Selection

Choose the appropriate transport based on your use case:

- **stdio** - Best for local servers, simple setup
- **sse** - Good for remote servers, HTTP-based
- **streamable_http** - Modern HTTP streaming, best performance
- **websocket** - Real-time bidirectional communication

### Performance Optimization

1. **Connection Pooling**
   - Reuse MCP client connections when possible
   - Configure appropriate connection timeouts

2. **Caching**
   - Cache MCP tool responses when appropriate
   - Use agent memory for frequently accessed data

3. **Concurrent Operations**
   - MCP clients support concurrent tool calls
   - Design agents to leverage parallelism

### Security Considerations

1. **Access Control**
   - Limit MCP server directory access
   - Use environment variables for sensitive configuration
   - Validate user inputs before passing to MCP tools

2. **Network Security**
   - Use HTTPS for remote MCP servers
   - Implement proper authentication for remote connections
   - Monitor MCP traffic for anomalies

3. **Resource Limits**
   - Set appropriate timeouts to prevent resource exhaustion
   - Limit file sizes and operation scope
   - Monitor resource usage

## Related Documentation

- [Examples](../examples/) - Working MCP configuration examples
- [CLAUDE.md](../../CLAUDE.md) - Complete platform documentation
- [MCP Specification](https://spec.modelcontextprotocol.io/) - Official MCP documentation
- [Semantic Kernel MCP](https://devblogs.microsoft.com/semantic-kernel/) - Microsoft's MCP integration