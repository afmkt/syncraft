#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
  echo "Usage: scripts/release.sh <new-version>"
  exit 1
fi

VERSION="$1"

# Check clean working tree
if ! git diff-index --quiet HEAD --; then
  echo "❌ Working tree is dirty. Commit or stash changes first."
  exit 1
fi

bump-my-version "$VERSION"
git push
git push --tags
