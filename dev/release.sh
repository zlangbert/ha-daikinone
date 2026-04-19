#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"

if [ -z "$VERSION" ]; then
    echo "VERSION required (usage: task release -- 0.9.7)" >&2
    exit 1
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "VERSION must be semver without a v prefix (e.g. 0.9.7), got: $VERSION" >&2
    exit 1
fi

if ! git rev-parse --verify main > /dev/null 2>&1; then
    echo "main branch not found" >&2
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "working directory is not clean (has changes or untracked files)" >&2
    exit 1
fi

git checkout -b "release-prep-$VERSION"
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" custom_components/daikinone/manifest.json
git commit -am "release: prepare release $VERSION"
git push -u origin "release-prep-$VERSION"
gh pr create --title "release: prepare $VERSION" --body "Prepare release $VERSION" --base main
gh pr merge --auto --squash --delete-branch

while [ "$(gh pr view --json state -q .state)" != "MERGED" ]; do
    sleep 3
done

gh release create "v$VERSION" --generate-notes
git checkout main
git branch -D "release-prep-$VERSION"
