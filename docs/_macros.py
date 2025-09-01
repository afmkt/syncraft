"""MkDocs macros for the documentation site.

Exposes the installed package version as {{ version }}.
"""

def define_env(env):
    try:
        import importlib.metadata as ilmd
    except Exception:  # pragma: no cover
        import importlib_metadata as ilmd  # type: ignore

    def get_version():
        try:
            return ilmd.version("syncraft")
        except ilmd.PackageNotFoundError:
            return "0.0.0"

    env.variables["version"] = get_version()
