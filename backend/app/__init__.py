"""CO2 Calculator Backend Application."""

__version__ = "0.1.0"


# Modules registration
import importlib.util
import sys
from pathlib import Path


def load_all_modules(modules_dir: str) -> dict:
    modules = {}
    base_path = Path(modules_dir)

    for module_path in base_path.iterdir():
        if module_path.is_dir() and (module_path / "__init__.py").exists():
            name = module_path.name
            init_file = module_path / "__init__.py"

            spec = importlib.util.spec_from_file_location(name, init_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                modules[name] = module

    return modules


# Load everything under app/modules/
all_modules = load_all_modules("app/modules")

# for name, mod in all_modules.items():
#     print(f"Loaded: {name}")
