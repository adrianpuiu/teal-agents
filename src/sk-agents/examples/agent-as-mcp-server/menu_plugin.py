"""
Menu Plugin for the Agent as MCP Server example.

This is equivalent to Microsoft's MenuPlugin in their agent_mcp_server.py sample.
"""

from typing import Annotated

from semantic_kernel.functions import kernel_function


class MenuPlugin:
    """A sample Menu Plugin used for the MCP server example."""

    @kernel_function(description="Provides a list of specials from the menu.")
    def get_specials(self) -> Annotated[str, "Returns the specials from the menu."]:
        return """
        Special Soup: Clam Chowder
        Special Salad: Cobb Salad
        Special Drink: Chai Tea
        """

    @kernel_function(description="Provides the price of the requested menu item.")
    def get_item_price(
        self, menu_item: Annotated[str, "The name of the menu item."]
    ) -> Annotated[str, "Returns the price of the menu item."]:
        return "$9.99"