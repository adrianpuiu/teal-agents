# Agent as MCP Server - Microsoft Sample Equivalent

This example demonstrates how to expose a **teal-agents agent as an MCP server** that other tools can consume, equivalent to Microsoft's `agent_mcp_server.py` sample.

## Microsoft Sample Reference

This is the teal-agents equivalent of Microsoft's agent-as-server sample:
- **Source**: [agent_mcp_server.py](https://github.com/microsoft/semantic-kernel/blob/main/python/samples/demos/mcp_server/agent_mcp_server.py)
- **Functionality**: Expose agent functions as MCP tools for external consumption
- **Use Case**: Let other tools (Claude Desktop, VSCode Copilot, etc.) use your agent

## Direction Comparison

### **MCP Client vs MCP Server**

**What we've built so far (MCP Client)**:
```
External MCP Server → Teal-Agents Agent
(GitHub MCP Server) → (Our ChatBot consumes GitHub tools)
```

**This example (MCP Server)**:
```
Teal-Agents Agent → External MCP Client  
(Our Menu Agent) → (Claude Desktop consumes our menu tools)
```

## Configuration Comparison

### Microsoft's Azure AI Agent Approach
```python
agent = AzureAIAgent(
    client=client,
    definition=await client.agents.create_agent(
        model="gpt-4o",
        name="Host",
        instructions="Answer questions about the menu.",
    ),
    plugins=[MenuPlugin()],
)
server = agent.as_mcp_server()
```

### Teal-Agents YAML Equivalent
```yaml
agents:
  - name: host
    role: "Menu Assistant"
    model: gpt-4o-mini
    system_prompt: "Answer questions about the menu."
    plugins:
      - MenuPlugin

# Python equivalent:
# agent = handle(config, app_config)
# server = agent.as_mcp_server()  # To be implemented
```

## MenuPlugin Functionality

Both implementations expose the same menu functions via MCP:

```python
class MenuPlugin:
    @kernel_function(description="Provides a list of specials from the menu.")
    def get_specials(self) -> str:
        return """
        Special Soup: Clam Chowder
        Special Salad: Cobb Salad
        Special Drink: Chai Tea
        """

    @kernel_function(description="Provides the price of the requested menu item.")
    def get_item_price(self, menu_item: str) -> str:
        return "$9.99"
```

**External tools would see these as MCP tools**:
- `get_specials()` - Get daily menu specials
- `get_item_price(menu_item)` - Get price for specific item

## MCP Client Configuration

To consume this agent from external tools:

### Claude Desktop Configuration
```json
{
    "mcpServers": {
        "teal-menu-agent": {
            "command": "uv",
            "args": [
                "--directory=/path/to/teal-agents/src/sk-agents/examples/agent-as-mcp-server",
                "run",
                "agent_mcp_server.py"
            ],
            "env": {
                "TA_API_KEY": "<your openai api key>",
                "TA_SERVICE_CONFIG": "config.yaml"
            }
        }
    }
}
```

### VSCode GitHub Copilot Agents
```json
{
    "mcp": {
        "servers": {
            "teal-menu": {
                "command": "uv",
                "args": ["run", "agent_mcp_server.py"],
                "cwd": "/path/to/agent-as-mcp-server"
            }
        }
    }
}
```

## Transport Options

### Stdio Transport (Default)
```bash
export TA_API_KEY="your_openai_api_key"
export TA_SERVICE_CONFIG="config.yaml"
uv run agent_mcp_server.py --transport stdio
```

### SSE Transport (Web Server)
```bash
export TA_API_KEY="your_openai_api_key"
export TA_SERVICE_CONFIG="config.yaml"
uv run agent_mcp_server.py --transport sse --port 8000
```

## Implementation Status

### ✅ **Completed (MCP Client Capabilities)**
- **GitHub MCP Integration**: Consume external MCP servers
- **Multi-Transport Support**: stdio, SSE, streamable_http, websocket
- **Microsoft Sample Equivalence**: Interactive ChatBot, Issues Agent
- **YAML Configuration**: Enterprise-grade config management

### 🚧 **In Progress (MCP Server Capabilities)**
- **Agent as MCP Server**: Expose teal-agents as MCP servers
- **Tool Registration**: Convert agent functions to MCP tools
- **Transport Layer**: Support stdio and SSE for external clients

### 📋 **Required Implementation**

To complete the MCP server functionality, we need:

#### 1. **Add MCP Server Interface to Teal-Agents**
```python
# Extend BaseHandler to support MCP server capabilities
class BaseHandler:
    async def as_mcp_server(self):
        """Convert agent to MCP server."""
        # Implementation needed
```

#### 2. **Tool Registration from Agent Functions**
```python
# Extract functions from agent plugins and expose as MCP tools
def extract_agent_tools(agent):
    tools = []
    for plugin in agent.plugins:
        for function in plugin.functions:
            tools.append(convert_to_mcp_tool(function))
    return tools
```

#### 3. **MCP Protocol Implementation**
```python
# Implement MCP server protocol
class TealAgentsMCPServer:
    async def handle_list_tools(self):
        # Return available tools from agent
    
    async def handle_call_tool(self, name, arguments):
        # Execute agent function and return result
```

## Use Cases

Once implemented, this would enable:

### **External Tool Integration**
- **Claude Desktop**: Use your teal-agents as tools
- **VSCode Copilot**: Integrate custom agents into development workflow
- **Custom Applications**: Any MCP client can consume your agents

### **Agent Composition**
```
External MCP Client → Teal-Agents MCP Server → Internal MCP Clients
(Claude Desktop) → (Menu Agent) → (GitHub MCP Server)
```

### **Enterprise Scenarios**
- **Internal Tool Exposure**: Make company agents available across tools
- **API Standardization**: MCP as standard interface for all agents
- **Multi-Tool Workflows**: Compose agents across different platforms

## Testing the Current Implementation

```bash
# Run the current implementation (shows limitations)
cd examples/agent-as-mcp-server
export TA_API_KEY="your_openai_api_key"
uv run python agent_mcp_server.py

# Will show:
# ✅ Configuration loading works
# ✅ Agent creation works
# ❌ MCP server creation not yet implemented
```

## Benefits vs Microsoft Approach

| Feature | Microsoft Azure AI Agent | Teal-Agents Equivalent | Advantage |
|---------|-------------------------|----------------------|-----------|
| **Agent Definition** | Programmatic creation | YAML configuration | 🎯 **Config-driven** |
| **Plugin Management** | Hard-coded plugins | Plugin system | 🎯 **Extensible** |
| **Environment Variables** | Azure-specific | Generic env vars | 🎯 **Platform agnostic** |
| **Transport Support** | stdio, SSE | stdio, SSE (planned) | ✅ **Same capability** |
| **MCP Protocol** | Built-in `as_mcp_server()` | To be implemented | 🚧 **In progress** |

## Next Steps

1. **Implement MCP Server Interface**: Add `agent.as_mcp_server()` equivalent
2. **Tool Registration**: Extract agent functions as MCP tools
3. **Protocol Handling**: Implement MCP server protocol
4. **Testing**: Test with Claude Desktop and other MCP clients
5. **Documentation**: Complete usage examples and deployment guides

Once completed, this will provide **full bidirectional MCP support**:
- ✅ **MCP Client**: Consume external MCP servers (GitHub, filesystem, etc.)
- 🚧 **MCP Server**: Expose teal-agents as MCP servers for external consumption

**Result**: Complete MCP ecosystem integration with both consumption and exposure capabilities.