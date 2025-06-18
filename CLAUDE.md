# Teal Agents Platform - Claude Code Assistant Guide

## Project Overview

Teal Agents Platform is a comprehensive Python-based framework for creating and orchestrating AI-powered agents. The platform provides two main functionalities:

1. **Core Agent Framework** - A config-first approach to creating individual agents built on Microsoft's Semantic Kernel
2. **Orchestrators** - Multiple patterns for composing and coordinating multiple agents for complex use cases

### Key Technologies
- **Language**: Python 3.11+ (3.13 for core agents)
- **Framework**: Built on Microsoft Semantic Kernel
- **Web Framework**: FastAPI for REST APIs and WebSocket support
- **Package Manager**: UV (modern Python package manager)
- **Containerization**: Docker with multi-stage builds
- **Configuration**: YAML-based configuration files
- **Testing**: pytest with async support
- **Code Quality**: ruff (linting/formatting), mypy (type checking)

## Project Structure

```
/home/agp/teal-agents/
├── shared/ska_utils/           # Shared utilities library
├── src/
│   ├── sk-agents/             # Core agent framework
│   └── orchestrators/         # Agent orchestration patterns
│       ├── assistant-orchestrator/    # Chat-style orchestration
│       ├── collab-orchestrator/       # Collaborative agent orchestration
│       └── workflow-orchestrator/     # Workflow-based orchestration
├── assets/                    # Documentation images and diagrams
├── *.Dockerfile              # Container definitions
└── Makefile                   # Build automation
```

### Core Components

#### 1. Shared Utilities (`/home/agp/teal-agents/shared/ska_utils/`)
Common utilities used across all components:
- **Configuration management** (`app_config.py`)
- **Redis streams integration** (event handling/publishing)
- **Telemetry and monitoring** (`telemetry.py`)
- **Standardized date handling** (`standardized_dates.py`)
- **Keepalive executor** for long-running processes

#### 2. Core Agent Framework (`/home/agp/teal-agents/src/sk-agents/`)
The main agent creation framework with:
- **Config-driven agent creation** using YAML files
- **Plugin system** for extending agent capabilities
- **Multi-modal support** (text, images)
- **Remote plugin integration** via OpenAPI specs
- **Enhanced MCP integration** with dual modes (wrapper + direct)
- **State management** (in-memory and Redis)
- **Chat completion factories** with customization points

Key files:
- `src/sk_agents/app.py` - Main FastAPI application
- `src/sk_agents/ska_types.py` - Core type definitions
- `src/sk_agents/configs.py` - Configuration loading
- `src/sk_agents/skagents/` - Agent implementation classes

#### 3. Assistant Orchestrator (`/home/agp/teal-agents/src/orchestrators/assistant-orchestrator/`)
Chat-style multi-agent orchestration with:
- **Orchestrator** - Main coordination service
- **Services** - Authentication and persistence layer
- **WebSocket support** for real-time chat
- **Agent selection** via dedicated selector agents
- **Chat history persistence** using DynamoDB
- **User context management**

Key files:
- `orchestrator/jose.py` - Main orchestrator application
- `orchestrator/conversation_manager.py` - Chat session management
- `services/ska_services.py` - Supporting services

#### 4. Other Orchestrators
- **Collab Orchestrator** - Team-based agent collaboration
- **Workflow Orchestrator** - Sequential workflow execution

## Development Setup

### Prerequisites
- Python 3.11+ (3.13 recommended for core agents)
- Docker and Docker Compose
- UV package manager
- Git

### Local Development

1. **Clone and build**:
```bash
git clone https://github.com/MSDLLCpapers/teal-agents.git
cd teal-agents
make all  # Builds all Docker images
```

2. **Core Agent Development**:
```bash
cd src/sk-agents
uv sync  # Install dependencies
cp .env.example .env  # Configure environment
# Edit .env with your API keys and config path
uv run -- fastapi run src/sk_agents/app.py
```

3. **Assistant Orchestrator Development**:
```bash
cd src/orchestrators/assistant-orchestrator/orchestrator
uv sync
# Configure environment variables (see README.md)
uv run -- fastapi run jose.py --port 8000
```

### Environment Configuration

#### Core Agents
- `TA_API_KEY` - LLM API key (OpenAI, Anthropic, etc.)
- `TA_SERVICE_CONFIG` - Path to agent config YAML
- `TA_AGENT_NAME` - Agent name for deployment
- `TA_GITHUB` - Enable GitHub-based agent loading

#### Assistant Orchestrator
- `TA_AGW_HOST` - Agent catalog host:port
- `TA_AGW_SECURE` - Use HTTPS for agent catalog
- `TA_AUTH_ENABLED` - Enable client authentication
- `TA_SERVICES_TYPE` - Authentication type (internal/external)
- `TA_TELEMETRY_ENABLED` - Enable OpenTelemetry

## Configuration Files

### Agent Configuration (`config.yaml`)
```yaml
apiVersion: skagents/v1
kind: Sequential  # or Chat
description: "Agent description"
service_name: AgentName
version: 0.1
input_type: BaseInput
spec:
  agents:
    - name: default
      role: "Agent Role"
      model: gpt-4o-mini
      system_prompt: "System instructions"
  tasks:
    - name: task_name
      task_no: 1
      description: "Task description"
      instructions: "Detailed instructions"
      agent: default
```

### Orchestrator Configuration
```yaml
apiVersion: skagents/v1
kind: AssistantOrchestrator
description: "Orchestrator description"
service_name: OrchestratorName
version: 0.1
spec:
  fallback_agent: GeneralAgent:0.1
  agent_chooser: AgentSelectorAgent:0.1
  agents:
    - MathAgent:0.1
    - WeatherAgent:0.1
```

## MCP Integration

The Teal Agents platform includes comprehensive support for Model Context Protocol (MCP) servers, providing agents with powerful external tool capabilities. Our implementation follows Microsoft's official Semantic Kernel MCP pattern for optimal reliability and ease of use.

### MCP Overview

Model Context Protocol (MCP) enables agents to interact with external systems through standardized tools. Common MCP servers include:
- **Filesystem** - File and directory operations
- **Database** - SQL queries and data management  
- **GitHub** - Repository and issue management
- **Web Search** - Internet search capabilities
- **Custom** - Domain-specific tools

### How MCP Works

MCP tools are registered directly as Semantic Kernel functions, providing clean, LLM-friendly interfaces:

```python
# Agent function calls - Microsoft Semantic Kernel pattern
result = await GitHub.search_repositories(query="semantic-kernel")
content = await FileSystem.read_file(path="README.md")
await FileSystem.write_file(path="output.txt", content="Hello World")
```

For backward compatibility, legacy wrapper mode is still available:
```python
# Legacy wrapper functions (backward compatibility)
result = await call_mcp_tool('filesystem', 'list_directory', '{"path": "/workspace"}')
tools = await list_mcp_tools()
```

### MCP Server Configuration

Add MCP servers to your agent configuration using the simplified approach:

```yaml
apiVersion: skagents/v1
kind: Sequential
description: "Agent with filesystem and GitHub capabilities"
service_name: McpAgent
version: 0.1
spec:
  agents:
    - name: default
      role: "Helpful assistant with MCP capabilities"
      model: gpt-4o-mini
      system_prompt: |
        You have access to external tools through MCP:
        
        FileSystem tools:
        - FileSystem.list_directory(path) - List directory contents
        - FileSystem.read_file(path) - Read file contents
        - FileSystem.write_file(path, content) - Write to file
        
        GitHub tools:
        - GitHub.search_repositories(query) - Search repositories
        - GitHub.create_repository(name, description) - Create repository
        - GitHub.get_file_contents(owner, repo, path) - Get file contents
        
  # MCP Server Configuration - Simplified Microsoft-style approach
  mcp_servers:
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
    
    - name: GitHub
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

### MCP Server Setup

#### Prerequisites
```bash
# Install Node.js and npm (required for most MCP servers)
# Ubuntu/Debian: sudo apt install nodejs npm
# macOS: brew install node
# Windows: Download from nodejs.org

# Verify installation
node --version
npm --version
```

#### Popular MCP Servers
```bash
# Filesystem operations (most commonly used)
npm install -g @modelcontextprotocol/server-filesystem

# GitHub integration  
npm install -g @modelcontextprotocol/server-github

# SQLite database
npm install -g @modelcontextprotocol/server-sqlite

# Web search
npm install -g @modelcontextprotocol/server-brave-search
```

### YAML Configuration Options

#### Basic Configuration
The simplest way to add MCP servers to your agent:

```yaml
spec:
  # MCP servers available to all agents  
  mcp_servers:
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
    
    - name: GitHub
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
```

#### Advanced Configuration
With environment variables, timeouts, and multiple transports:

```yaml
spec:
  # Global MCP servers - available to all agents
  mcp_servers:
    - name: FileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      timeout: 30
    
    - name: GitHub
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
      timeout: 60
    
    # Remote MCP server via HTTP
    - name: RemoteAPI
      transport: sse
      url: "http://localhost:8000/sse"
      headers:
        Authorization: "Bearer ${API_TOKEN}"

  agents:
    - name: default
      model: gpt-4o-mini
      system_prompt: |
        You have access to external tools via MCP:
        - FileSystem.list_directory(path) - List directory contents
        - FileSystem.read_file(path) - Read file contents
        - FileSystem.write_file(path, content) - Write to file
        - GitHub.search_repositories(query) - Search repositories
      
      # Agent-specific MCP servers (optional)
      mcp_servers:
        - name: TempFiles
          command: npx
          args: ["@modelcontextprotocol/server-filesystem", "/tmp"]
          timeout: 15
```

#### Running YAML-Configured Agents
```bash
# Set environment variables
export TA_SERVICE_CONFIG="path/to/your/config.yaml"
export TA_API_KEY="your-openai-api-key"

# Start the agent
uv run -- fastapi run src/sk_agents/app.py

# Agent automatically loads MCP servers from YAML
```

#### Global vs Agent-Specific MCP Servers

**Global MCP Servers** (defined at `spec.mcp_servers`):
- Available to all agents in the configuration
- Useful for shared resources like common filesystems or databases
- Automatically merged with agent-specific servers

**Agent-Specific MCP Servers** (defined at `agents[].mcp_servers`):
- Only available to that specific agent
- Useful for specialized tools or private resources
- Takes priority over global servers with the same name

#### YAML Configuration Benefits
- ✅ **No Python Code Required** - Pure configuration approach
- ✅ **Version Control Friendly** - Easy to track changes
- ✅ **Environment Variable Support** - Secure credential handling
- ✅ **Automatic Merging** - Global and agent-specific servers combined
- ✅ **Both Integration Modes** - Wrapper and direct modes supported
- ✅ **Production Ready** - Deploy configs without code changes

### Real Working Example

Here's a complete working example that lists files in the current directory:

```python
from sk_agents.mcp_integration import EnhancedMCPPluginFactory, MCPServerConfig

# Configure real MCP filesystem server
config = MCPServerConfig(
    name="filesystem",
    command="npx", 
    args=["@modelcontextprotocol/server-filesystem", "/current/directory"],
    integration_mode="wrapper",  # or "direct"
    timeout=30
)

# Create and use MCP plugin
plugin = EnhancedMCPPluginFactory.create_from_config([config.model_dump()])
await plugin.initialize()

# List directory contents
result = await plugin.call_mcp_tool(
    server_name="filesystem",
    tool_name="list_directory", 
    arguments='{"path": "/current/directory"}'
)
```

### MCP Testing

Run comprehensive MCP integration tests:
```bash
cd src/sk-agents

# Test real MCP filesystem server
uv run python test_real_mcp_final.py

# Test enhanced MCP functionality
uv run python test_enhanced_mcp.py

# Test edge cases and error handling
uv run python test_focused_edge_cases.py
```

Expected test output:
```
🎉 REAL MCP FILESYSTEM INTEGRATION SUCCESSFUL!
✅ Successfully demonstrated:
   • Real MCP filesystem server connection  
   • Current working directory listing via MCP
   • Enhanced Teal Agents MCP integration
   • Production-ready MCP filesystem operations
```

### Agent Capabilities with MCP

Agents with MCP integration can perform:

**Filesystem Operations:**
- List directory contents: "Show me all Python files in the src directory"
- Read files: "What's in the README.md file?"
- Write files: "Create a config file with these settings"
- Search files: "Find all files containing 'TODO' comments"

**Database Operations:**
- Query data: "Show me all users created last week"
- Schema inspection: "List all tables in the database"
- Data analysis: "Count records by category"

**GitHub Operations:**
- Search repositories: "Find React projects with TypeScript"
- Create issues: "Report this bug in the main repository"
- Read files: "Show me the package.json from that repo"

### Advanced Configuration

**Multiple MCP Servers:**
```yaml
mcp_servers:
  - name: filesystem
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
    integration_mode: direct
    plugin_name: FileSystem
    
  - name: database
    command: python
    args: ["mcp_sqlite_server.py", "/data/app.db"]
    integration_mode: direct  
    plugin_name: Database
    
  - name: github
    command: npx
    args: ["@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    integration_mode: wrapper
```

**Environment Variables:**
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

### Production Deployment

For production use:
1. **Install MCP servers** on your deployment environment
2. **Configure allowed directories** for filesystem servers
3. **Set environment variables** for API keys and tokens
4. **Use direct mode** for better LLM reliability
5. **Monitor timeouts** and error handling
6. **Test integration** with your specific MCP servers

The enhanced MCP integration provides production-ready capabilities for agents to interact with external systems through standardized protocols.

## Build and Deployment

### Docker Images
- `teal-agents:latest` - Core agent framework
- `ao:latest` - Assistant orchestrator
- `ao-services:latest` - Orchestrator services

### Build Commands
```bash
make all           # Build all images
make teal-agents   # Build core agent image
make orchestrator  # Build orchestrator image
make services      # Build services image
make clean         # Remove all images
```

### Deployment
Each component includes Docker Compose configurations for local deployment:
- `/home/agp/teal-agents/src/orchestrators/assistant-orchestrator/example/compose.yaml`
- Component-specific examples in demo directories

## Testing

### Core Agent Tests
```bash
cd src/sk-agents
uv run -- pytest tests/
uv run -- pytest --cov=src/sk_agents tests/  # With coverage
```

### MCP Integration Tests
```bash
cd src/sk-agents

# Test GitHub CLI MCP server (wrapper + direct modes)
uv run python examples/mcp-github-cli-agent/test_github_cli_server.py

# Test Direct SK function integration specifically
uv run python examples/mcp-github-cli-agent/simple_direct_test.py

# Test API MCP server
uv run python examples/mcp-api-agent/simple_test.py
```

### Assistant Orchestrator Tests
```bash
cd src/orchestrators/assistant-orchestrator/orchestrator
uv run -- pytest tests/
```

### Shared Utils Tests
```bash
cd shared/ska_utils
uv run -- pytest tests/
```

### Enhanced MCP Integration Tests
```bash
cd src/sk-agents

# Test real MCP filesystem server integration
uv run python test_real_mcp_final.py

# Test enhanced MCP functionality 
uv run python test_enhanced_mcp.py

# Test direct tool registration
uv run python test_direct_tool_registration.py

# Test edge cases and error handling
uv run python test_focused_edge_cases.py

# Test YAML MCP configuration
uv run python test_yaml_mcp_config.py

# Prerequisites for real MCP tests
npm install @modelcontextprotocol/server-filesystem
```

## Code Quality Tools

All components use consistent tooling:
- **ruff** - Linting and formatting (line length: 100)
- **mypy** - Type checking (relaxed settings)
- **pytest** - Testing with async support
- **coverage** - Test coverage reporting

Run quality checks:
```bash
uv run -- ruff check .
uv run -- ruff format .
uv run -- mypy .
```

## Key Architectural Patterns

### 1. Config-First Agent Creation
Agents are primarily configured through YAML files with minimal custom code required.

### 2. Plugin Architecture
Extensible through:
- Custom plugins (Python code)
- Remote plugins (OpenAPI specifications)
- Built-in Semantic Kernel plugins

### 3. Multi-Level Orchestration
Different orchestration patterns for different use cases:
- **Assistant**: Chat-style user interactions
- **Collaborative**: Multi-agent team coordination
- **Workflow**: Sequential process automation

### 4. Microservices Architecture
Components are containerized and can be deployed independently with clear service boundaries.

## Common Development Tasks

### Creating a New Agent
1. Create config YAML in appropriate demo directory
2. Add custom plugins if needed (`custom_plugins.py`)
3. Define custom types if needed (`custom_types.py`)
4. Test locally with FastAPI dev server

### Adding Custom Plugins
```python
# custom_plugins.py
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

class MyPlugin:
    @kernel_function(name="my_function", description="Function description")
    def my_function(self, input: str) -> str:
        return f"Processed: {input}"
```

### Extending Orchestrators
1. Implement required agent interfaces (input/output formats)
2. Register agents with Kong-based agent catalog
3. Configure orchestrator with agent references
4. Test integration through orchestrator APIs

## Debugging and Logging

- **OpenTelemetry** integration for distributed tracing
- **FastAPI** automatic OpenAPI documentation at `/docs`
- **WebSocket** debugging through browser dev tools
- **Redis** streams for event monitoring
- **DynamoDB** for persistent data inspection

## MCP Integration Examples

### Available Examples
- **`examples/mcp-yaml-config-agent/`** - Complete YAML-configured MCP agent
- **`examples/mcp-real-filesystem-agent/`** - Programmatic MCP configuration
- **`examples/mcp-enhanced-agent/`** - Multiple MCP servers with different modes

### YAML Configuration Templates
```bash
# Basic MCP filesystem agent
examples/mcp-yaml-config-agent/config.yaml

# Advanced MCP configuration with multiple servers
examples/mcp-real-filesystem-agent/config.yaml
```

### Testing Your MCP Configuration
```bash
# Test YAML parsing and validation
uv run python test_yaml_mcp_config.py

# Test with real MCP servers
uv run python test_real_mcp_final.py

# Run comprehensive test suite
uv run python run_mcp_tests.py
```

## Important Files to Understand

### Core Framework
- `/home/agp/teal-agents/src/sk-agents/src/sk_agents/app.py` - Main agent application
- `/home/agp/teal-agents/src/sk-agents/src/sk_agents/skagents/v1/agent_builder.py` - Agent construction logic
- `/home/agp/teal-agents/src/sk-agents/src/sk_agents/skagents/kernel_builder.py` - Kernel construction with MCP support

### MCP Integration
- `/home/agp/teal-agents/src/sk-agents/src/sk_agents/mcp_integration.py` - Enhanced MCP implementation
- `/home/agp/teal-agents/src/sk-agents/src/sk_agents/skagents/v1/config.py` - Agent configuration with MCP support
- `/home/agp/teal-agents/src/sk-agents/tests/test_mcp_integration_real.py` - Real MCP integration tests

### Orchestrators
- `/home/agp/teal-agents/src/orchestrators/assistant-orchestrator/orchestrator/jose.py` - Orchestrator entry point
- `/home/agp/teal-agents/src/orchestrators/assistant-orchestrator/orchestrator/conversation_manager.py` - Chat management

### Shared Utilities
- `/home/agp/teal-agents/shared/ska_utils/src/ska_utils/` - Shared utility implementations

This platform enables rapid development of sophisticated AI agent systems through configuration-driven development, powerful orchestration capabilities, and seamless MCP integration for external tool access.

### Quick Start with MCP

Get up and running with MCP-enabled agents in 5 minutes:

#### 1. Install Prerequisites
```bash
# Install Node.js (required for MCP servers)
# Ubuntu/Debian: sudo apt install nodejs npm
# macOS: brew install node

# Install MCP filesystem server
npm install -g @modelcontextprotocol/server-filesystem
```

#### 2. Create Agent Configuration
```bash
# Use an existing MCP example
export TA_SERVICE_CONFIG="examples/mcp-simplified-agent/config.yaml"
export TA_API_KEY="your-openai-api-key"
```

#### 3. Start Agent
```bash
cd src/sk-agents
uv run -- fastapi run src/sk_agents/app.py
```

#### 4. Test MCP Functionality
```bash
# Test filesystem operations
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "List files in the current directory"}'

# Test GitHub search (if configured)  
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for Python repositories on GitHub"}'
```

The platform provides production-ready MCP integration following Microsoft's Semantic Kernel patterns.