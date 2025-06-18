# Teal Agents Documentation

Welcome to the Teal Agents Platform documentation. This directory contains comprehensive guides for building and deploying AI-powered agents with Model Context Protocol (MCP) integration.

## Quick Start

New to Teal Agents? Start here:

1. **[Core Framework README](../README.md)** - Getting started with Teal Agents
2. **[MCP Quick Start](../README.md#mcp-integration-quick-start)** - 5-minute MCP setup
3. **[Simplified MCP Example](../examples/mcp-simplified-agent/)** - Working example

## Documentation Sections

### 📚 Core Documentation

- **[Platform Overview](../../CLAUDE.md)** - Complete platform documentation
- **[MCP Integration Guide](mcp-integration.md)** - Comprehensive MCP documentation
- **[Chat Completion Factory](chat-completion-factory.md)** - Customizing LLM interactions

### 🚀 Getting Started

- **[Basic Agent](../demos/01_getting_started/)** - Create your first agent
- **[Input/Output Types](../demos/02_input_output/)** - Custom data types
- **[Custom Plugins](../demos/03_plugins/)** - Extend agent capabilities
- **[Remote Plugins](../demos/04_remote_plugins/)** - OpenAPI integrations

### 🔧 MCP Integration

#### Quick Examples
- **[Simplified MCP Agent](../examples/mcp-simplified-agent/)** - Microsoft-style integration
- **[YAML MCP Configuration](../examples/mcp-yaml-config-agent/)** - Configuration-driven setup
- **[Real Filesystem Agent](../examples/mcp-real-filesystem-agent/)** - Production filesystem operations

#### Transport Options
- **[Multi-Transport Agent](../examples/mcp-multi-transport-agent/)** - HTTP, WebSocket, stdio
- **[GitHub CLI Agent](../examples/mcp-github-cli-agent/)** - GitHub integration
- **[API Agent](../examples/mcp-api-agent/)** - Custom API servers

### 🏭 Production Deployment

- **[Production Guide](mcp-production-guide.md)** - Enterprise deployment best practices
- **[Migration Guide](mcp-migration-guide.md)** - Upgrade from legacy implementations
- **[Docker Deployment](../demos/05_deployment/)** - Container deployment
- **[GitHub Deployment](../demos/06_deployment_github/)** - GitHub-based deployment

### 🎯 Advanced Topics

- **[Multi-Modal Input](../demos/08_multi_modal/)** - Images and rich content
- **[Task Output](../demos/07_task_output/)** - Custom response formats
- **[Chat Agents](../demos/09_chat_simple/)** - Conversational interfaces
- **[Chat with Plugins](../demos/10_chat_plugins/)** - Plugin-enabled chat

## MCP Feature Matrix

| Feature | Basic | YAML Config | Multi-Transport | Production |
|---------|-------|-------------|-----------------|------------|
| Filesystem Tools | ✅ | ✅ | ✅ | ✅ |
| GitHub Integration | ✅ | ✅ | ✅ | ✅ |
| Database Access | ✅ | ✅ | ✅ | ✅ |
| HTTP Transport | ❌ | ❌ | ✅ | ✅ |
| WebSocket Transport | ❌ | ❌ | ✅ | ✅ |
| Environment Variables | ✅ | ✅ | ✅ | ✅ |
| Global MCP Servers | ❌ | ✅ | ✅ | ✅ |
| Agent-Specific Servers | ❌ | ✅ | ✅ | ✅ |
| Load Balancing | ❌ | ❌ | ❌ | ✅ |
| Monitoring | ❌ | ❌ | ❌ | ✅ |

## Common Use Cases

### 🗂️ File Management
**Best Example:** [Real Filesystem Agent](../examples/mcp-real-filesystem-agent/)
- List directories and files
- Read and write file contents
- Create and manage directory structures
- Search for files and content

### 🐙 GitHub Operations
**Best Example:** [GitHub CLI Agent](../examples/mcp-github-cli-agent/)
- Search repositories
- Create and manage issues
- Read repository contents
- Manage pull requests

### 🗄️ Database Access
**Best Example:** [Enhanced MCP Agent](../examples/mcp-enhanced-agent/)
- Execute SQL queries
- Manage database schemas
- Data analysis and reporting
- Multi-database operations

### 🌐 Web Services
**Best Example:** [API Agent](../examples/mcp-api-agent/)
- REST API integrations
- Custom MCP server development
- External service connections
- Real-time data access

### 🔄 Multi-Agent Workflows
**Best Example:** [YAML MCP Configuration](../examples/mcp-yaml-config-agent/)
- Global tool sharing
- Agent-specific tools
- Coordinated operations
- State management

## Configuration Patterns

### Minimal Configuration
```yaml
spec:
  mcp_servers:
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
```

### Production Configuration
```yaml
spec:
  mcp_servers:
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      timeout: 30
      env:
        DEBUG: "false"
    
    - name: GitHub
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
      timeout: 60
    
    - name: RemoteAPI
      transport: sse
      url: "https://api.example.com/mcp"
      headers:
        Authorization: "Bearer ${API_TOKEN}"
```

### Multi-Transport Configuration
```yaml
spec:
  mcp_servers:
    # Standard stdio
    - name: LocalFileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/local"]
    
    # HTTP Server-Sent Events
    - name: RemoteAPI
      transport: sse
      url: "http://api.example.com/sse"
    
    # WebSocket for real-time
    - name: RealtimeData
      transport: websocket
      url: "ws://realtime.example.com/ws"
```

## Troubleshooting

### Common Issues

#### MCP Server Not Found
```bash
npm install -g @modelcontextprotocol/server-filesystem
```

#### Connection Timeout
```yaml
mcp_servers:
  - name: SlowServer
    command: npx
    args: ["slow-mcp-server"]
    timeout: 120  # Increase timeout
```

#### Permission Denied
```bash
# Check directory permissions
ls -la /workspace
chmod 755 /workspace
```

### Debug Tools
```bash
# Test MCP configuration
uv run python test_final_mcp_validation.py

# Validate examples
uv run python test_examples_validation.py

# Test YAML parsing
uv run python test_yaml_mcp_config.py
```

## Getting Help

### Documentation
- **[Platform Overview](../../CLAUDE.md)** - Complete reference
- **[MCP Integration Guide](mcp-integration.md)** - Detailed MCP documentation
- **[Production Guide](mcp-production-guide.md)** - Enterprise deployment

### Examples
- **[examples/](../examples/)** - Working configurations
- **[demos/](../demos/)** - Step-by-step tutorials

### Community
- **[GitHub Issues](https://github.com/MSDLLCpapers/teal-agents/issues)** - Bug reports and feature requests
- **[Contributing Guide](../../CONTRIBUTING.md)** - How to contribute

## What's Next?

1. **Try Examples** - Start with [Simplified MCP Agent](../examples/mcp-simplified-agent/)
2. **Customize Configuration** - Adapt to your use case
3. **Add Custom Tools** - Create domain-specific MCP servers
4. **Deploy to Production** - Follow [Production Guide](mcp-production-guide.md)
5. **Join Community** - Share your experience and help others

The Teal Agents platform provides a powerful foundation for building sophisticated AI agent systems with seamless external tool integration through MCP.