# Build and Release Guide

This guide explains how to build the documentation site and use the release script for the Syncraft project.

## 📚 How to Build the Documentation Site

This project uses **MkDocs** with Material theme for documentation. Here's how to build and serve it:

### **Prerequisites:**
```bash
# Install development dependencies
uv sync --group dev
# OR if using pip:
pip install -e ".[dev]"
```

### **Building the Documentation:**

1. **Serve locally (development):**
   ```bash
   mkdocs serve
   ```
   - Opens at `http://127.0.0.1:8000`
   - Auto-reloads when you edit markdown files
   - Great for development and previewing changes

2. **Build static site:**
   ```bash
   mkdocs build --clean --site-dir ./site
   ```
   - Generates static HTML in the `./site` directory
   - `--clean` removes old build artifacts
   - The built site can be deployed to any web server

3. **Build and serve locally:**
   ```bash
   mkdocs build --clean
   mkdocs serve --dev-addr 127.0.0.1:8001
   ```

### **Documentation Configuration:**
- **Config file:** `mkdocs.yml`
- **Theme:** Material Design
- **Plugins:** 
  - `mkdocstrings` (API documentation from docstrings)
  - `macros` (template variables like `{{ version }}`)
  - `mkdocs-jupyter` (Jupyter notebook support)
- **Content:** Located in `docs/` directory
- **Site URL:** https://afmkt.github.io/syncraft/

### **Automatic Deployment:**
The documentation is automatically built and deployed to GitHub Pages when:
- A version tag (e.g., `v1.2.3`) is pushed
- A GitHub release is published
- Manually triggered via GitHub Actions

---

## 🚀 How to Use the Release Script

The release script (`scripts/release.sh`) automates version bumping, tagging, and publishing. Here's how to use it:

### **Basic Usage:**
```bash
# Patch release (0.2.10 → 0.2.11)
./scripts/release.sh patch

# Minor release (0.2.10 → 0.3.0)
./scripts/release.sh minor

# Major release (0.2.10 → 1.0.0)
./scripts/release.sh major

# Default is patch if no argument provided
./scripts/release.sh
```

### **What the Script Does:**

1. **Reads current version** from `pyproject.toml`
2. **Calculates new version** based on bump type (major/minor/patch)
3. **Updates `pyproject.toml`** with the new version number
4. **Prompts for commit message** (with sensible default)
5. **Commits changes** including `pyproject.toml` and `uv.lock`
6. **Creates git tag** (e.g., `v0.2.11`)
7. **Pushes to origin** (both commit and tag)

### **Example Workflow:**
```bash
$ ./scripts/release.sh minor
Current version: 0.2.10
New version: 0.3.0
Version updated in pyproject.toml
Enter commit message [default: Bump version to 0.3.0]: Add new parsing features
Release 0.3.0 committed, tagged, and pushed.
```

### **What Happens After Release:**

1. **GitHub Actions trigger:**
   - `publish.yml` builds and publishes to PyPI
   - `gh-pages.yml` builds and deploys documentation

2. **Automatic processes:**
   - Package published to PyPI as `syncraft==0.3.0`
   - Documentation updated at https://afmkt.github.io/syncraft/
   - GitHub release created (if configured)

### **Prerequisites for Release Script:**
- Clean git working directory
- Push access to the repository
- Proper git remote setup (`origin`)

---

## 🛠️ Quick Commands Summary

```bash
# Documentation
mkdocs serve                    # Development server
mkdocs build --clean           # Build static site

# Release
./scripts/release.sh patch     # Patch version bump
./scripts/release.sh minor     # Minor version bump  
./scripts/release.sh major     # Major version bump

# Development
uv sync --group dev            # Install all dev dependencies
pytest                         # Run tests
```

