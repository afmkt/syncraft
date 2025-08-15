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

# Commit and tag
git add pyproject.toml
git commit -m "$COMMIT_MSG"
git tag "v$NEW_VERSION"

# Push commit and tag
git push origin main
git push origin "v$NEW_VERSION"

echo "Release $NEW_VERSION committed, tagged, and pushed."