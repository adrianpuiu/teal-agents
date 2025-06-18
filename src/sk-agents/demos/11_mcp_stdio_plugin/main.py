import asyncio
import os
from pathlib import Path

from ska_utils.config import AppConfig
from sk_agents.configs import TA_REMOTE_PLUGIN_PATH, TA_OPENAI_API_KEY, TA_OPENAI_ORG_ID, TA_CHAT_MODEL_ID, TA_CHAT_SERVICE_ID
from sk_agents.skagents.chat_completion_builder import ChatCompletionBuilder
from sk_agents.skagents.kernel_builder import KernelBuilder
from sk_agents.skagents.remote_plugin_loader import (
    RemotePluginCatalog,
    RemotePluginLoader,
)


async def main():
    # 1. Set up AppConfig
    # Create a dummy .env file for the demo if it doesn't exist
    # to avoid issues with AppConfig if no other .env is present.
    env_path = Path(".env")
    if not env_path.exists():
        with open(env_path, "w") as f:
            f.write("TA_OPENAI_API_KEY=dummy_key\n") # Required by ChatCompletionBuilder
            f.write("TA_CHAT_MODEL_ID=dummy_model\n") # Required by ChatCompletionBuilder
            f.write("TA_CHAT_SERVICE_ID=dummy_service\n") # Required by ChatCompletionBuilder

    app_config = AppConfig()

    # Point TA_REMOTE_PLUGIN_PATH to the demo's YAML file
    # Construct the absolute path to the YAML file
    current_dir = Path(__file__).parent.resolve()
    yaml_file_path = current_dir / "remote_plugins_mcp_demo.yaml"
    app_config.set(TA_REMOTE_PLUGIN_PATH.env_name, str(yaml_file_path))

    # Set dummy OpenAI values if not already in environment, to satisfy ChatCompletionBuilder
    if not app_config.get(TA_OPENAI_API_KEY.env_name):
        app_config.set(TA_OPENAI_API_KEY.env_name, "dummy_key_not_used")
    if not app_config.get(TA_OPENAI_ORG_ID.env_name):
        app_config.set(TA_OPENAI_ORG_ID.env_name, "dummy_org_not_used")
    if not app_config.get(TA_CHAT_MODEL_ID.env_name):
        app_config.set(TA_CHAT_MODEL_ID.env_name, "dummy_chat_model_not_used")
    if not app_config.get(TA_CHAT_SERVICE_ID.env_name):
        app_config.set(TA_CHAT_SERVICE_ID.env_name, "AIChatCompletion")


    print(f"Using remote plugin config: {app_config.get(TA_REMOTE_PLUGIN_PATH.env_name)}")

    # 2. Instantiate ChatCompletionBuilder
    # This is needed by KernelBuilder, even if we don't use chat completion directly.
    # It will use the dummy values if no real OpenAI config is present.
    chat_completion_builder = ChatCompletionBuilder(app_config)

    # 3. Instantiate RemotePluginCatalog and RemotePluginLoader
    remote_plugin_catalog = RemotePluginCatalog(app_config)
    remote_plugin_loader = RemotePluginLoader(remote_plugin_catalog)

    # 4. Instantiate KernelBuilder
    kernel_builder = KernelBuilder(
        chat_completion_builder=chat_completion_builder,
        remote_plugin_loader=remote_plugin_loader,
        app_config=app_config,
    )

    # 5. Build the kernel, including "EchoMCP" in remote_plugins
    print("Building kernel with EchoMCP remote plugin...")
    # KernelBuilder requires a model_name and service_id for the chat service.
    # We provide the dummy ones set in app_config.
    kernel = await kernel_builder.build_kernel(
        model_name=app_config.get(TA_CHAT_MODEL_ID.env_name),
        service_id=app_config.get(TA_CHAT_SERVICE_ID.env_name),
        plugins=[], # No local plugins for this demo
        remote_plugins=["EchoMCP"],
    )
    print("Kernel built.")

    # 6. Invoke the "echo_input" function from the "EchoMCP" plugin
    plugin_name = "EchoMCP"
    function_name = "echo_input"
    input_text = "Hello MCP Stdio World!"

    print(f"Invoking function '{function_name}' from plugin '{plugin_name}' with input: '{input_text}'")

    try:
        echo_function = kernel.get_function(plugin_name, function_name)
        result = await kernel.invoke(echo_function, input=input_text)
        # The MCP plugins currently wrap results in a dict, e.g. {"output": "actual_output"}
        # This might change based on MCP connector evolution.
        # For now, let's print the whole result object.
        print(f"\nResult from {plugin_name}.{function_name}:")
        print(str(result))

        # Try to access common output patterns
        if hasattr(result, 'value'): # SK's FunctionResult typical structure
             print(f"\nFunctionResult.value: {result.value}")
        elif isinstance(result, dict) and "output" in result: # A common dict pattern
             print(f"\nResult dictionary ['output']: {result['output']}")


    except Exception as e:
        print(f"Error invoking plugin: {e}")
    finally:
        # Clean up the dummy .env file if we created it
        # if env_path.exists() and "dummy_key" in env_path.read_text():
        #     try:
        #         os.remove(env_path)
        #         print(f"Cleaned up dummy .env file: {env_path}")
        #     except Exception as e_clean:
        #         print(f"Error cleaning up dummy .env file: {e_clean}")

        # Important for MCP Stdio: The subprocess might keep main.py running.
        # We need to ensure the MCP plugins are closed if they have a close method.
        # The RemotePluginLoader stores them in _mcp_plugins.
        # This is a simplified shutdown; proper lifecycle management might be more complex.
        print("\nShutting down MCP plugins...")
        for mcp_plugin in remote_plugin_loader._mcp_plugins:
            if hasattr(mcp_plugin, "close") and asyncio.iscoroutinefunction(mcp_plugin.close):
                try:
                    await mcp_plugin.close()
                    print(f"Closed MCP plugin: {mcp_plugin.name}")
                except Exception as e_close:
                    print(f"Error closing MCP plugin {mcp_plugin.name}: {e_close}")
            elif hasattr(mcp_plugin, "_process") and mcp_plugin._process is not None:
                # For MCPStdioPlugin, ensure the process is terminated.
                if mcp_plugin._process.poll() is None: # Check if process is still running
                    mcp_plugin._process.terminate()
                    try:
                        await asyncio.wait_for(mcp_plugin._process.wait(), timeout=5.0)
                        print(f"Terminated MCP plugin process for: {mcp_plugin.name}")
                    except asyncio.TimeoutError:
                        print(f"Timeout waiting for MCP plugin process {mcp_plugin.name} to terminate. Killing.")
                        mcp_plugin._process.kill()
                    except Exception as e_term:
                         print(f"Error terminating MCP plugin process {mcp_plugin.name}: {e_term}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
