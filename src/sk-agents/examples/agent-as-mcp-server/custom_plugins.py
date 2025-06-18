"""
Custom plugins for the Agent as MCP Server example.

This loads the MenuPlugin for use in the agent configuration.
"""

# Import the MenuPlugin to make it available for the agent
from .menu_plugin import MenuPlugin

# Make it available for the agent builder
__all__ = ["MenuPlugin"]