#!/usr/bin/env bash
set -e


# Choose bump type: patch, minor, major
BUMP_TYPE="${1:-patch}"

# Check clean working tree
if ! git diff-index --quiet HEAD --; then
  echo "❌ Working tree is dirty. Commit or stash changes first."
  exit 1
fi

echo "🔖 Releasing a new $BUMP_TYPE version..."
bump-my-version bump --config-file bumpversion.cfg "$BUMP_TYPE"

git push
git push --tags
