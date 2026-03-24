from __future__ import annotations
from pathlib import Path
from importlib.resources import files
from platformdirs import user_cache_dir
import sys


# Detection flag for Pyodide/Emscripten
IS_WEB = sys.platform == "emscripten"


def builtin_cache_path() -> Path:
    """Return the path to the built-in cache."""
    # files() returns a Traversable; converting to Path is right, 
    # but in Pyodide we ensure it's actually writeable if needed.
    p = files('syncraft').joinpath('cache')
    
    # In some Pyodide environments, the package might be in a 
    # read-only site-packages. We cast to string then Path.
    lang_path = Path(str(p))
    
    try:
        lang_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fallback for read-only virtual filesystems in Pyodide
        if IS_WEB:
            lang_path = Path("/tmp/syncraft/builtin_cache")
            lang_path.mkdir(parents=True, exist_ok=True)
        else:
            raise
    return lang_path

def user_cache_path(base: None | str | Path) -> Path:
    """Return the path to the user-specific cache for a given grammar."""
    base_path = Path(base) if base is not None else Path(user_cache_dir("syncraft")) / "cache"
    base_path.mkdir(parents=True, exist_ok=True)
    
    return base_path


