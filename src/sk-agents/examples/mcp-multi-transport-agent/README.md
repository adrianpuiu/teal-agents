# Multi-Transport MCP Integration

This example demonstrates **Microsoft-style MCP integration with multiple transport types**, including the new **Streamable HTTP transport** introduced in Microsoft Semantic Kernel Python (MCP 1.8).

## Supported Transport Types

### 🔌 **Stdio Transport** (Default - Local)
```yaml
- name: GitHub
  transport: stdio  # Default
  command: docker
  args: ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server"]
```
- **Use for**: Local MCP servers, development tools
- **Benefits**: Fast, reliable, no network dependencies
- **Examples**: Filesystem, GitHub CLI, local databases

### 🌐 **Streamable HTTP Transport** (New - Remote)
```yaml
- name: RemoteAI
  transport: streamable_http
  url: "http://localhost:8000/mcp"
  headers:
    Authorization: "Bearer ${API_TOKEN}"
```
- **Use for**: Modern remote MCP services
- **Benefits**: Better error handling, HTTP standards, replaces SSE
- **Examples**: Cloud AI services, remote APIs, distributed tools

### 📡 **SSE Transport** (Legacy - Remote)
```yaml
- name: LegacyRemote
  transport: sse
  url: "http://localhost:8001/sse"
```
- **Use for**: Existing SSE-based MCP servers
- **Benefits**: Server-sent events, one-way streaming
- **Status**: Being replaced by Streamable HTTP

### ⚡ **WebSocket Transport** (Real-time)
```yaml
- name: RealtimeTools
  transport: websocket
  url: "ws://localhost:8002/ws"
```
- **Use for**: Real-time bidirectional communication
- **Benefits**: Live streaming, instant updates
- **Examples**: Chat systems, live monitoring, collaborative tools

## Microsoft Alignment

Our implementation perfectly aligns with Microsoft's latest patterns:

### **Microsoft's Approach**
```python
# Microsoft Semantic Kernel Python - multiple transports
async with MCPStdioPlugin(name="GitHub", command="docker", args=["run", "github-mcp"]) as stdio_plugin:
    pass
    
async with MCPStreamableHttpPlugin(name="RemoteAI", url="http://localhost:8000/mcp") as http_plugin:
    pass
```

### **Teal-Agents YAML Equivalent**
```yaml
mcp_servers:
  - name: GitHub
    transport: stdio
    command: docker
    args: ["run", "github-mcp"]
  
  - name: RemoteAI
    transport: streamable_http
    url: "http://localhost:8000/mcp"
```

**Result**: Identical function calling - `GitHub.search_repositories()`, `RemoteAI.generate_text()`

## Configuration Examples

### Basic Multi-Transport Setup
```yaml
mcp_servers:
  # Local GitHub tools
  - name: GitHub
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
  
  # Remote AI service  
  - name: CloudAI
    transport: streamable_http
    url: "https://api.example.com/mcp"
    headers:
      Authorization: "Bearer ${API_KEY}"
      Content-Type: "application/json"
  
  # Real-time monitoring
  - name: Monitoring
    transport: websocket
    url: "wss://monitor.example.com/ws"
```

### Environment Variable Support
```yaml
mcp_servers:
  - name: SecureService
    transport: streamable_http
    url: "${MCP_SERVICE_URL}"
    headers:
      Authorization: "Bearer ${MCP_API_TOKEN}"
      X-Client-ID: "${CLIENT_ID}"
    timeout: 60
```

### Legacy Compatibility
```yaml
mcp_servers:
  # Modern simplified mode (default)
  - name: ModernService
    transport: streamable_http
    url: "http://localhost:8000/mcp"
  
  # Legacy wrapper mode
  - name: LegacyService
    transport: stdio
    command: legacy-server
    integration_mode: wrapper  # Triggers legacy mode
```

## Transport Selection Guide

| Transport | Use When | Benefits | Drawbacks |
|-----------|----------|----------|-----------|
| **stdio** | Local tools, development | Fast, reliable, no network | Local only |
| **streamable_http** | Modern remote services | HTTP standards, error handling | Network dependency |
| **sse** | Legacy remote servers | Streaming events | Being deprecated |
| **websocket** | Real-time communication | Bidirectional, low latency | Connection complexity |

## Function Calling Examples

All transports result in clean function calls:

```python
# Stdio transport - local tools
await GitHub.search_repositories(query="semantic-kernel")
await FileSystem.read_file(path="README.md")

# Streamable HTTP - remote AI
await RemoteAI.generate_text(prompt="Write a summary", model="gpt-4")
await RemoteAI.analyze_data(data=dataset, analysis_type="classification")

# WebSocket - real-time
await RealtimeTools.stream_data(query="live-metrics")
await RealtimeTools.live_updates(subscription="alerts")

# Legacy wrapper mode (backward compatibility)
await call_mcp_tool("legacy_server", "process", '{"data": "example"}')
```

## Prerequisites

### For Streamable HTTP Transport
```bash
# Requires MCP 1.8+
pip install "mcp>=1.8"
```

### For Stdio Transport
```bash
# Install MCP servers
npm install -g @modelcontextprotocol/server-github
npm install -g @modelcontextprotocol/server-filesystem
```

### For Remote Transports
- Remote MCP server running with appropriate transport
- Network connectivity to server URL
- Valid authentication tokens/headers

## Testing

```bash
# Set environment variables
export TA_SERVICE_CONFIG="examples/mcp-multi-transport-agent/config.yaml"
export TA_API_KEY="your-openai-api-key"
export GITHUB_TOKEN="your-github-token"
export API_TOKEN="your-api-token"

# Start agent
uv run -- fastapi run src/sk_agents/app.py

# Test different transports
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "List files using stdio transport"}'

curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Generate text using streamable HTTP transport"}'
```

## Migration from Legacy

### From SSE to Streamable HTTP
```yaml
# Old SSE configuration
- name: RemoteService
  transport: sse
  url: "http://localhost:8000/sse"

# New Streamable HTTP configuration  
- name: RemoteService
  transport: streamable_http
  url: "http://localhost:8000/mcp"
```

### From Legacy Wrapper to Simplified
```yaml
# Old wrapper mode
- name: filesystem
  command: npx
  args: ["filesystem-server", "/workspace"]
  integration_mode: wrapper

# New simplified mode
- name: FileSystem
  transport: stdio
  command: npx
  args: ["filesystem-server", "/workspace"]
```

This multi-transport approach provides maximum flexibility while maintaining Microsoft compatibility and backward compatibility with existing teal-agents deployments.