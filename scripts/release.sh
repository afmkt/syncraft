#!/bin/bash
set -e

BUMP=${1:-patch}

# Read current version robustly
CURRENT_VERSION=$(sed -nE 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*"([0-9]+)\.([0-9]+)\.([0-9]+)".*/\1.\2.\3/p' pyproject.toml)

if [ -z "$CURRENT_VERSION" ]; then
  echo "Error: Could not find current version in pyproject.toml"
  exit 1
fi

echo "Current version: $CURRENT_VERSION"

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

case "$BUMP" in
  major)
    ((MAJOR+=1))
    MINOR=0
    PATCH=0
    ;;
  minor)
    ((MINOR+=1))
    PATCH=0
    ;;
  patch)
    ((PATCH+=1))
    ;;
  *)
    echo "Unknown bump type: $BUMP. Use major, minor, or patch."
    exit 1
    ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "New version: $NEW_VERSION"

# Update pyproject.toml in place
sed -i.bak -E "s/^([[:space:]]*version[[:space:]]*=[[:space:]]*\")[0-9]+\.[0-9]+\.[0-9]+(\".*)/\1$NEW_VERSION\2/" pyproject.toml
rm pyproject.toml.bak

echo "Version updated in pyproject.toml"

# Ask for commit message
read -p "Enter commit message [default: Bump version to $NEW_VERSION]: " COMMIT_MSG
COMMIT_MSG=${COMMIT_MSG:-"Bump version to $NEW_VERSION"}

# Optional: Build docs locally to verify they work
read -p "Build documentation locally to verify? (y/N): " BUILD_DOCS
if [[ "$BUILD_DOCS" =~ ^[Yy]$ ]]; then
  echo "Building documentation locally..."
  if command -v mkdocs >/dev/null 2>&1; then
    mkdocs build --clean --site-dir ./site
    echo "✅ Documentation built successfully"
    echo "📄 Version in docs: $(grep -o 'Current version: [0-9.]*' site/index.html | cut -d' ' -f3)"
  else
    echo "⚠️  mkdocs not found. Install with: pip install mkdocs mkdocs-material mkdocstrings mkdocstrings-python mkdocs-macros-plugin"
  fi
fi

# Commit and tag
git add pyproject.toml uv.lock
git commit -m "$COMMIT_MSG"
git tag "v$NEW_VERSION"

# Push commit and tag
git push origin main
git push origin "v$NEW_VERSION"

echo "Release $NEW_VERSION committed, tagged, and pushed."

# Wait a moment and check if the tag triggered the docs workflow
echo "Waiting for documentation deployment to trigger..."
sleep 3

echo ""
echo "✅ Release $NEW_VERSION completed successfully!"
echo ""
echo "Next steps:"
echo "1. The documentation will be automatically updated via GitHub Actions"
echo "2. Check the deployment status at: https://github.com/afmkt/syncraft/actions"
echo "3. Once deployed, verify the docs at: https://afmkt.github.io/syncraft/"
echo "4. Create a GitHub release if needed: https://github.com/afmkt/syncraft/releases/new?tag=v$NEW_VERSION"