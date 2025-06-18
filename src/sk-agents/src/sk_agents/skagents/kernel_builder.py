from semantic_kernel.kernel import Kernel
from ska_utils import AppConfig

from sk_agents.extra_data_collector import ExtraDataCollector
from sk_agents.mcp_integration import SimplifiedMCPIntegration
from sk_agents.plugin_loader import get_plugin_loader
from sk_agents.ska_types import ModelType
from sk_agents.skagents.chat_completion_builder import ChatCompletionBuilder
from sk_agents.skagents.remote_plugin_loader import RemotePluginLoader


class KernelBuilder:
    def __init__(
        self,
        chat_completion_builder: ChatCompletionBuilder,
        remote_plugin_loader: RemotePluginLoader,
        app_config: AppConfig,
        authorization: str | None = None,
    ):
        self.chat_completion_builder: ChatCompletionBuilder = chat_completion_builder
        self.remote_plugin_loader = remote_plugin_loader
        self.app_config: AppConfig = app_config
        self.authorization = authorization

    def build_kernel(
        self,
        model_name: str,
        service_id: str,
        plugins: list[str],
        remote_plugins: list[str],
        authorization: str | None = None,
        extra_data_collector: ExtraDataCollector | None = None,
        mcp_servers: list[dict] | None = None,
    ) -> Kernel:
        kernel = self._create_base_kernel(model_name, service_id)
        kernel = self._parse_plugins(plugins, kernel, authorization, extra_data_collector)
        kernel = self._load_remote_plugins(remote_plugins, kernel)
        return self._load_mcp_plugins(mcp_servers, kernel)

    def get_model_type_for_name(self, model_name: str) -> ModelType:
        return self.chat_completion_builder.get_model_type_for_name(model_name)

    def model_supports_structured_output(self, model_name: str) -> bool:
        return self.chat_completion_builder.model_supports_structured_output(model_name)

    def _create_base_kernel(self, model_name: str, service_id: str) -> Kernel:
        chat_completion = self.chat_completion_builder.get_chat_completion_for_model(
            service_id=service_id,
            model_name=model_name,
        )

        kernel = Kernel()
        kernel.add_service(chat_completion)

        return kernel

    def _load_remote_plugins(self, remote_plugins: list[str], kernel: Kernel) -> Kernel:
        if remote_plugins is None or len(remote_plugins) < 1:
            return kernel
        self.remote_plugin_loader.load_remote_plugins(kernel, remote_plugins)
        return kernel

    @staticmethod
    def _parse_plugins(
        plugin_names: list[str],
        kernel: Kernel,
        authorization: str | None = None,
        extra_data_collector: ExtraDataCollector | None = None,
    ) -> Kernel:
        if plugin_names is None or len(plugin_names) < 1:
            return kernel

        plugin_loader = get_plugin_loader()
        plugins = plugin_loader.get_plugins(plugin_names)
        for k, v in plugins.items():
            kernel.add_plugin(v(authorization, extra_data_collector), k)
        return kernel

    def _load_mcp_plugins(self, mcp_servers: list[dict] | None, kernel: Kernel) -> Kernel:
        """Load MCP servers as Semantic Kernel plugins with Microsoft-style simplified integration."""
        if not mcp_servers or len(mcp_servers) < 1:
            return kernel

        try:
            # Use Microsoft-style simplified integration (only mode supported)
            return self._load_simplified_mcp_plugins(mcp_servers, kernel)
                
        except Exception as e:
            # Log the error but don't fail the kernel build
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not load MCP plugins: {e}")
            return kernel

    def _load_simplified_mcp_plugins(self, mcp_servers: list[dict], kernel: Kernel) -> Kernel:
        """Load MCP servers using Microsoft-style simplified integration."""
        import asyncio
        import logging
        import concurrent.futures
        import threading
        logger = logging.getLogger(__name__)
        
        try:
            # Check if we're already in an event loop
            try:
                current_loop = asyncio.get_running_loop()
                # We're in a running loop, use thread-based execution
                logger.info("Detected running event loop, using thread-based MCP initialization")
                
                def run_mcp_integration():
                    """Run MCP integration in a separate thread with its own event loop."""
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            SimplifiedMCPIntegration.add_mcp_tools_to_kernel(kernel, mcp_servers)
                        )
                    finally:
                        new_loop.close()
                
                # Run in thread pool to avoid event loop conflicts
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_mcp_integration)
                    future.result(timeout=30)  # 30 second timeout
                    
            except RuntimeError:
                # No event loop running, safe to create one
                logger.info("No running event loop detected, creating new loop for MCP initialization")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        SimplifiedMCPIntegration.add_mcp_tools_to_kernel(kernel, mcp_servers)
                    )
                finally:
                    loop.close()
            
            logger.info(f"Successfully loaded simplified MCP integration (Microsoft-style) for {len(mcp_servers)} servers")
            
        except Exception as e:
            logger.error(f"Failed to load simplified MCP plugins: {e}")
            import traceback
            logger.debug(f"MCP integration error details: {traceback.format_exc()}")
            
        return kernel
