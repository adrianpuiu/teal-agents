# Teal Agents Framework

Teal Agent Framework is a (early!) prototype framework meant to accelerate the
creation and deployment of AI-powered agents. The framework is built on top of
Microsoft's
[Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/overview/),
a lightweight, open source, agent framework.

Building upon Semantic Kernel, the Teal Agent Framework takes a config-first
approach to the creation of agents. The majority of setup is performed in an
agent's configuration file and you have the option to add in custom code to
enhance your agent's capability.

## Key Features

- **Config-First Development** - Create agents primarily through YAML configuration
- **MCP Integration** - Connect to external tools via Model Context Protocol servers
- **Microsoft Semantic Kernel** - Built on proven, enterprise-ready foundations
- **Multi-Modal Support** - Handle text, images, and other content types
- **Plugin Architecture** - Extend capabilities with custom or remote plugins

## Prerequisites
- Python 3.11 or higher
- An appropriate API key for the LLM of your choice
- Docker (or comparable equivalent)
- Node.js and npm (for MCP server integration)

## Running a simple demo
Running locally will allow you to test your agent's configuration and code.
First, clone the repository locally and install all dependencies. In this
I'm using `uv` as an environment manager.

```bash
$ git clone https://github.com/MSDLLCpapers/teal-agents
$ cd teal-agents/src/sk-agents
$ uv sync
```

Once cloned, you'll need to set up an environment file which will provide your
LLM API key and point to the correct agent configuration file. Create a `.env`
file in the root of the repository and add the following:

```text
TA_API_KEY=<your-API-key>
TA_SERVICE_CONFIG=demos/01_getting_started/config.yaml
```

Finally, start the agent using fastapi via either using `uv run` or after
activating your environment.

```bash
$ uv run -- fastapi run src/sk_agents/app.py
```
or
```bash
$ source .venv/bin/activate
$ fastapi run src/sk_agents/app.py
```


You can test the agent by visiting http://localhost:8000/docs

![Agent Swagger UI](doc/assets/demo-1.png)

## MCP Integration Quick Start

Model Context Protocol (MCP) allows agents to connect to external tools and services. Here's how to get started:

### 1. Install MCP Server
```bash
# Install Node.js if not already installed
# Then install a popular MCP server
npm install -g @modelcontextprotocol/server-filesystem
```

### 2. Create MCP-Enabled Agent
```bash
# Use the MCP example configuration
export TA_SERVICE_CONFIG="examples/mcp-simplified-agent/config.yaml"
export TA_API_KEY="your-openai-api-key"

# Start the agent
uv run -- fastapi run src/sk_agents/app.py
```

### 3. Test MCP Functionality
```bash
# Test filesystem operations
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "List files in the current directory"}'
```

See the [MCP examples](examples/) for more configurations including GitHub integration, database access, and multi-transport setups.

### Additional Documentation

#### Core Framework
- [Configuring an Agent](/src/sk-agents/demos/01_getting_started/README.md)
- [Working with Input and Output](/src/sk-agents/demos/02_input_output/README.md)
- [Creating Custom Plugins](/src/sk-agents/demos/03_plugins/README.md)
- [Using Remote Plugins](/src/sk-agents/demos/04_remote_plugins/README.md)
- [Docker Deployment (Basic)](/src/sk-agents/demos/05_deployment/README.md)
- [Github Deployment](/src/sk-agents/demos/06_deployment_github/README.md)
- [Task Output](/src/sk-agents/demos/07_task_output/README.md)
- [Multi-Modal Input](/src/sk-agents/demos/08_multi_modal/README.md)

#### MCP Integration
- [Simplified MCP Agent](examples/mcp-simplified-agent/README.md) - Microsoft-style MCP integration
- [YAML MCP Configuration](examples/mcp-yaml-config-agent/README.md) - Configuration-driven MCP setup
- [Multi-Transport MCP](examples/mcp-multi-transport-agent/README.md) - HTTP, WebSocket, and stdio transports
- [Real Filesystem Agent](examples/mcp-real-filesystem-agent/README.md) - Production filesystem operations
