"""CO2 Calculator Backend Application."""

__version__ = "0.1.0"


# Eagerly import every sub-package under app.modules so that feature modules
# register their routers/services at startup.  We resolve paths through the
# package itself (app.modules.__path__), which is always absolute and
# independent of the process working directory.  Registering under the full
# dotted name (e.g. "app.modules.buildings") avoids shadowing any unrelated
# top-level package.
import importlib
import pkgutil

import app.modules as _modules_pkg

all_modules: dict = {}
for _module_info in pkgutil.walk_packages(_modules_pkg.__path__, prefix="app.modules."):
    if not _module_info.ispkg:
        continue
    _mod = importlib.import_module(_module_info.name)
    all_modules[_module_info.name] = _mod
