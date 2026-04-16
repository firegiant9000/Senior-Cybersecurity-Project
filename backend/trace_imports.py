"""Trace imports to detect circular dependencies."""
import sys
import importlib.util

def trace_import(module_name, visited=None):
    if visited is None:
        visited = set()
    
    if module_name in visited:
        return f"CYCLE DETECTED: {module_name}"
    
    visited.add(module_name)
    
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            return f"NOT FOUND: {module_name}"
        
        if spec.origin is None:
            return f"NO ORIGIN: {module_name}"
        
        with open(spec.origin, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all imports in this module
        imports = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('from app'):
                # Extract the module name
                parts = line.split()
                if len(parts) >= 2:
                    imports.append(parts[1])
            elif line.startswith('import app'):
                parts = line.split()
                if len(parts) >= 2:
                    imports.append(parts[1])
        
        return {"module": module_name, "imports": imports}
    except Exception as e:
        return f"ERROR: {module_name} - {e}"

# Check critical imports
modules = [
    "app.main",
    "app.workers.scheduler",
    "app.api.routes.v1.ingest",
]

for m in modules:
    result = trace_import(m)
    print(f"{m}: {result}")
