"""MkDocs macros for the documentation site.

Exposes the project version as {{ version }}.

Resolution order:
1) Read [project].version from pyproject.toml at the repo root (authoritative)
2) Fallback to importlib.metadata.version("syncraft") if installed
3) Fallback to "0.0.0" if unknown
"""

from __future__ import annotations

from pathlib import Path


def define_env(env):
    # Prefer parsing pyproject.toml to avoid needing an installed package
    try:  # Python 3.11+
        import tomllib as tomli  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - fallback for older interpreters
        try:
            import tomli  # type: ignore
        except Exception:  # pragma: no cover
            tomli = None  # type: ignore

    try:
        import importlib.metadata as ilmd
    except Exception:  # pragma: no cover
        import importlib_metadata as ilmd  # type: ignore

    def get_version() -> str:
        # 1) pyproject.toml at repository root
        try:
            repo_root = Path(__file__).resolve().parents[1]
            pyproject = repo_root / "pyproject.toml"
            if tomli and pyproject.is_file():
                with pyproject.open("rb") as f:
                    data = tomli.load(f)
                version = data.get("project", {}).get("version")
                if isinstance(version, str) and version.strip():
                    return version.strip()
        except Exception:
            pass

        # 2) installed package metadata
        try:
            return ilmd.version("syncraft")
        except ilmd.PackageNotFoundError:
            return "0.0.0"

    env.variables["version"] = get_version()

    def include_code(path: str, language: str = "", start: str | None = None, end: str | None = None) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        file_path = (repo_root / path).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"include_code: file not found: {path}")

        lines = file_path.read_text(encoding="utf-8").splitlines()
        start_index = 0
        end_index = len(lines)

        if start is not None:
            for i, line in enumerate(lines):
                if start in line:
                    start_index = i + 1
                    break
            else:
                raise ValueError(f"include_code: start marker not found: {start}")

        if end is not None:
            for i, line in enumerate(lines[start_index:], start=start_index):
                if end in line:
                    end_index = i
                    break
            else:
                raise ValueError(f"include_code: end marker not found: {end}")

        snippet = "\n".join(lines[start_index:end_index]).rstrip()
        fence = language if language else ""
        return f"```{fence}\n{snippet}\n```"

    env.macro(include_code)
