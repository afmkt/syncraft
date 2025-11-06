from __future__ import annotations
from pathlib import Path
from importlib.resources import files
from platformdirs import user_cache_dir


def builtin_cache_path() -> Path:
    """Return the path to the built-in cache."""
    p = files('syncraft').joinpath('cache')
    lang_path = Path(str(p))
    lang_path.mkdir(parents=True, exist_ok=True)
    return lang_path
    


def user_cache_path(base: None | str | Path) -> Path:
    """Return the path to the user-specific cache for a given grammar."""
    base_path = Path(base) if base is not None else Path(user_cache_dir("syncraft")) / "cache"
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path