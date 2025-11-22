# Teal Agents CLI

The Teal Agents CLI is a developer tool designed to accelerate the creation and management of agents and orchestrators within the `teal-agents` repository.

## Why use this CLI?

### 1. Standardization & V3 Compliance
The codebase is moving towards the `tealagents/v1alpha1` (V3) API standard. Manually creating configuration files often leads to version mismatches (e.g., accidentally using `skagents/v1`). This CLI automatically generates configurations that are compliant with the latest architecture.

### 2. Rapid Scaffolding
Instead of copy-pasting existing directories and manually finding/replacing names and descriptions, the CLI generates the complete file structure for you instantly.

### 3. Reduced Boilerplate
It handles the creation of:
- YAML Configurations with correct `apiVersion` and `kind`.
- Python boilerplate for Workflows (Dapr).
- Standard directory layouts.

## Usage

Run the CLI from the repository root:

```bash
python3 devtools/cli/src/main.py [COMMAND] [NAME] [OPTIONS]
```

### Commands

#### Create an Agent
Generates a standard V3 Agent configuration.

```bash
python3 devtools/cli/src/main.py create-agent MyAgent --model gpt-4o --description "Handles user queries"
```

#### Create an Assistant Orchestrator
Generates an Assistant Orchestrator configuration, pre-wired with the default fallback and chooser agents.

```bash
python3 devtools/cli/src/main.py create-ao MyAssistant --description "Main routing assistant"
```

#### Create a Collab Orchestrator
Generates a Team Orchestrator configuration. **Note**: This tool automatically handles the V3 compatibility layer for Collab Orchestrators.

```bash
python3 devtools/cli/src/main.py create-co MyTeam --description "Collaborative planning team"
```

#### Create a Workflow Orchestrator
Generates a Dapr-based workflow configuration and a starter Python script.

```bash
python3 devtools/cli/src/main.py create-wo MyWorkflow --description "Data processing pipeline"
```
