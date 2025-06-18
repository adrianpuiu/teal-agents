# Quick Start: AI Agent with MCP File Listing

## 🚀 Complete Implementation Guide

### Prerequisites
- Node.js 16+ and npm
- Python 3.11+
- UV package manager
- OpenAI API key

### Quick Setup (5 minutes)

```bash
# 1. Install MCP server
npm install -g @modelcontextprotocol/server-filesystem

# 2. Clone and setup
git clone https://github.com/MSDLLCpapers/teal-agents.git
cd teal-agents/src/sk-agents
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env and add your OpenAI API key

# 4. Test MCP setup
uv run python test_mcp_setup.py

# 5. Start agent
export TA_SERVICE_CONFIG="$(pwd)/my-file-agent-config.yaml"
uv run -- fastapi run src/sk_agents/app.py

# 6. Test in another terminal
uv run python test_agent_requests.py
```

### Example Queries

Send POST requests to `http://localhost:8000/MyFileAgent/0.1/chat`:

```bash
# List files
curl -X POST "http://localhost:8000/MyFileAgent/0.1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "List all files in the current directory"}'

# Count Python files
curl -X POST "http://localhost:8000/MyFileAgent/0.1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "How many Python files are here?"}'

# Find specific files
curl -X POST "http://localhost:8000/MyFileAgent/0.1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Are there any YAML configuration files?"}'
```

### Common Issues

**Problem: MCP server not found**
```bash
# Solution: Install MCP server globally
npm install -g @modelcontextprotocol/server-filesystem
npx @modelcontextprotocol/server-filesystem --help
```

**Problem: Permission denied**
```bash
# Solution: Check directory permissions
ls -la .
chmod 755 .  # If needed
```

**Problem: Agent endpoint not found**
```bash
# Solution: Check if agent is running and endpoint URL
# Visit: http://localhost:8000/MyFileAgent/0.1/docs
```

**Problem: API key error**
```bash
# Solution: Set proper environment variable
export TA_API_KEY="your-openai-api-key"
```

### Configuration Files

The agent uses `my-file-agent-config.yaml` which configures:
- Agent role and capabilities
- MCP filesystem server connection
- Available tools and functions
- System prompts for AI behavior

### Next Steps

1. **Customize the directory**: Change the `args` in the config to point to different directories
2. **Add more tools**: Include additional MCP servers (GitHub, database, etc.)
3. **Enhance prompts**: Modify system prompts for specific use cases
4. **Add authentication**: Implement API keys or authentication for production use

### Architecture

```
User Request → FastAPI → Teal Agent → MCP Server → Filesystem → Response
```

The agent translates natural language requests into MCP tool calls, executes them, and returns human-readable responses.