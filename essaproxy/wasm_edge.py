import logging
import os

logger = logging.getLogger(__name__)

# Try to import wasmtime, fail gracefully if not installed
try:
    from wasmtime import Store, Module, Instance, Engine
    HAS_WASMTIME = True
except ImportError:
    HAS_WASMTIME = False

class WasmEdgeEngine:
    def __init__(self, wasm_dir: str):
        self.wasm_dir = wasm_dir
        self.engine = None
        self.store = None
        self.modules = {}
        
        if HAS_WASMTIME:
            try:
                self.engine = Engine()
                self.store = Store(self.engine)
                self._load_modules()
            except Exception as e:
                logger.error(f"Failed to initialize Wasmtime Engine: {e}")
        else:
            logger.warning("Wasm Edge Engine disabled: 'wasmtime' library not installed. pip install wasmtime")
            
    def _load_modules(self):
        if not os.path.exists(self.wasm_dir):
            os.makedirs(self.wasm_dir)
            
        for filename in os.listdir(self.wasm_dir):
            if filename.endswith(".wasm"):
                try:
                    filepath = os.path.join(self.wasm_dir, filename)
                    module = Module.from_file(self.engine, filepath)
                    self.modules[filename] = module
                    logger.info(f"Loaded WASM Edge Plugin: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load WASM module {filename}: {e}")
                    
    def execute_request_filter(self, path: str) -> bool:
        """
        Executes a WASM function `filter_request` if available.
        Returns False if the WASM module blocks the request (returns 0).
        """
        if not HAS_WASMTIME or not self.modules:
            return True
            
        for name, module in self.modules.items():
            try:
                # Provide an empty import object for sandbox execution
                instance = Instance(self.store, module, [])
                exports = instance.exports(self.store)
                
                # Check if filter_request is exported
                if "filter_request" in exports:
                    filter_fn = exports["filter_request"]
                    # Call the WASM function. Assume it returns 1 (allow) or 0 (block)
                    result = filter_fn(self.store)
                    if result == 0:
                        logger.warning(f"WASM Plugin {name} blocked request for path: {path}")
                        return False
            except Exception as e:
                logger.error(f"WASM Execution Error in {name}: {e}")
                
        return True
