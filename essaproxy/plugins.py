import importlib.util
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugins_dir: str):
        self.plugins_dir = plugins_dir
        self.plugins = []
        
    def load_plugins(self):
        self.plugins = []
        # Support absolute or relative paths
        target_dir = self.plugins_dir
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Could not create plugins directory {target_dir}: {e}")
                return
            
        for filename in os.listdir(target_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                filepath = os.path.join(target_dir, filename)
                module_name = filename[:-3]
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        self.plugins.append(module)
                        logger.info(f"Loaded Edge Plugin: {module_name}")
                except Exception as e:
                    logger.error(f"Failed to load Edge Plugin {module_name}: {e}")

    async def execute_request_plugins(self, client_ip: str, header_data: bytes) -> dict:
        """
        Executes request hooks. Plugins can return a dict with modifications 
        or return a 'response' key to short-circuit the request.
        """
        context = {
            "client_ip": client_ip,
            "header_data": header_data,
            "drop": False,
            "short_circuit_response": None
        }
        
        for plugin in self.plugins:
            if hasattr(plugin, 'on_request'):
                try:
                    if asyncio.iscoroutinefunction(plugin.on_request):
                        await plugin.on_request(context)
                    else:
                        plugin.on_request(context)
                except Exception as e:
                    logger.error(f"Plugin {plugin.__name__} crashed during on_request: {e}")
                    
        return context
