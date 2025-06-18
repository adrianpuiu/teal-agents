# Teal Agents Platform

A comprehensive Python-based framework for creating and orchestrating AI-powered agents, built on Microsoft's Semantic Kernel with enhanced MCP (Model Context Protocol) integration.

## Overview

The Teal Agents Platform provides two major sets of functionality:
1. **Core Agent Framework** - Config-first approach to creating individual agents with MCP integration
2. **Orchestrators** - Patterns for composing multiple agents for complex use cases

## Key Features

- **Config-First Development** - Create agents primarily through YAML configuration
- **MCP Integration** - Connect to external tools via Model Context Protocol servers
- **Microsoft Semantic Kernel** - Built on proven, enterprise-ready foundations
- **Multi-Modal Support** - Handle text, images, and other content types
- **Plugin Architecture** - Extend capabilities with custom or remote plugins
- **Production Ready** - Enterprise deployment with Docker and orchestration

## Core Agent Framework
The core framework can be found in the src/sk-agents directory. For more 
information, see its [README.md](src/sk-agents/README.md).

## Orchestrators
Orchestrators provide the patterns in which agents are grouped and interact with
both each other and the applications which leverage them. For more information
on orchestrators, see [README.md](src/orchestrators/README.md).

## Getting Started
Some of the demos and examples in this repository require docker images to be
built locally on your machine. To do this, once cloning this repository locally,
from the root directory
run:
```bash
$ git clone https://github.com/MSDLLCpapers/teal-agents.git
$ cd teal-agents
$ make all
```