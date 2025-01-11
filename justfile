release version:
    # Ensuring we are on main branch
    @git rev-parse --verify main > /dev/null 2>&1 || (echo "Not on main branch" && exit 1)

    # Ensuring working directory is clean
    @git status --porcelain | grep -q . && (echo "Working directory is not clean (has changes or untracked files)" && exit 1)

    # Creating and checking out release preparation branch
    @git checkout -b release-prep-{{version}}

    # Updating version in manifest.json
    @sed -i '' 's/"version": "[^"]*"/"version": "{{version}}"/' custom_components/daikinone/manifest.json

    # Comitting version bump
    @git commit -am "release: prepare release {{version}}"

    # Pushing branch and creating PR
    @git push -u origin release-prep-{{version}}
    @gh pr create --title "release: prepare {{version}}" --body "Prepare release {{version}}" --base main

    # Merging PR
    @gh pr merge --auto --delete-branch

    # Creating release
    @gh release create v{{version}} --generate-notes
