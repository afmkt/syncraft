from __future__ import annotations
from pathlib import Path
from importlib.resources import files
from platformdirs import user_cache_dir


def builtin_regex_cache_path() -> Path:
    """Return the path to the built-in regex cache."""
    p = files('syncraft').joinpath('grammars').joinpath('regex')
    return Path(str(p))
    


def user_cache_path(language: str, base: None | str = None) -> Path:
    """Return the path to the user-specific cache for a given language."""
    base_path = Path(base) if base is not None else Path(user_cache_dir("syncraft")) / "grammars"
    lang_path = base_path / language
    lang_path.mkdir(parents=True, exist_ok=True)
    return lang_path