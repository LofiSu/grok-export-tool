# History rewrite plan

This file is a review note. It does not rewrite history, and it does not force-push.

Merging it does not remove anything from existing commits. Close it after an approved rewrite, or leave it unmerged. The exact contact strings are listed only in the pull request description, so this file does not put them back into the tree.

## Current tree

The contact-removal commit on `cursor/remove-contact-links-3f8b` deletes the X profile, both blog URLs, and the coffee-sponsor link from the working tree.

Left in place:

- GitHub `https://github.com/LofiSu`
- Email `lofisuchat@gmail.com`
- GitHub Sponsors `https://github.com/sponsors/LofiSu`
- Connect and donate wording, including “a coffee chat”

## Commit messages

`git log --all --format='%B'` does not contain the X handle, either blog host, or the coffee-sponsor name. No commit-message rewrite is required for those strings.

The contact-removal subject was worded so it does not reintroduce them.

## What `git log -p` still shows

Git stores trees, and `git log -p` rebuilds patches. These commits still have the old contact lines in their trees.

### `main`

| Commit | Subject | Role |
| --- | --- | --- |
| `3b20c702b5c3267b2b386d7789f83b1e846060f3` | refactor: move skill to standards-compliant Agent Skills format | Parent of the packaging commit. Tree does not contain the contacts. |
| `1ad0a9aa87972692abdd282c38b4b533de23119d` | Package the public release: guides, Pages site, and contact (#2) | Current `main` tip before the scrub. This is the only `main` commit whose tree contains the contacts. |

Files in `1ad0a9a`: `CHANGELOG.md`, `README.md`, `README.zh-CN.md`, `REPO_META.md`, `docs/guide.html`, `docs/guide.md`, `docs/guide.zh-CN.html`, `docs/guide.zh-CN.md`, `docs/index.html`, `docs/index.zh-CN.html`, `llms.txt`.

After the scrub merges, `git log -p` on `main` will still show the contacts: once as additions in `1ad0a9a`, and once as deletions in the scrub commit.

### `origin/cursor/public-release-packaging-34f5`

Not an ancestor of `main`. These commits still show up in `git log --all -p` while that remote branch exists. `20b42d7` introduced the contacts. Later commits on that branch kept them.

| Commit | Subject |
| --- | --- |
| `20b42d739e1decab83ed62847bc1bfb337492296` | Add bilingual guides and a GitHub Pages site for the public release. |
| `477e89d07d125ac360b577f474a3a09f6c7bdc3a` | Harden export and MCP against cookie leaks and crash paths. |
| `8207c4746801466ceb36388634d9aa567eb9d6fd` | Delete the cookie-database copy before decryption and reserve the avatar slot. |
| `5c51feac217d5038014262574bee44c7c253a878` | Merge main and add the approved logo, poster, and release copy. |

`5c51fea` is the first of these whose tree also includes `CHANGELOG.md` and `REPO_META.md`.

## Do not run this until

1. The tree-scrub pull request is merged, so the desired tip tree is on `main`.
2. Any in-flight rewrite that strips `Co-authored-by: Cursor Agent` has landed. Rebase this plan onto that `main` before rewriting, so the two force-pushes are not racing.
3. The owner explicitly approves a force-push. This branch does not force-push.

## Rewrite `main` without a text filter

A blob replace is a poor fit. It would leave broken “Blog:” and donate lines behind. The scrub commit already has the right tree. Rebuild one packaging commit with that tree and drop both the dirty commit and the scrub commit.

```bash
git fetch origin main
# S = scrub commit (clean tree). P = 3b20c702b5c3267b2b386d7789f83b1e846060f3
TREE=$(git rev-parse origin/main^{tree})
NEW=$(git commit-tree "$TREE" -p 3b20c702b5c3267b2b386d7789f83b1e846060f3 \
  -m "Package the public release: guides, Pages site, and contact (#2)")
git push --force-with-lease=main:1ad0a9aa87972692abdd282c38b4b533de23119d origin "$NEW:main"
```

Use the lease ref that is actually current after the co-author rewrite. If that rewrite already replaced `1ad0a9a`, stop and redo this plan against the new tip. Do not force-push over an unexpected tip.

Preserve the original author and date if the owner wants that:

```bash
git -c user.name='LofiSu' -c user.email='163713803+LofiSu@users.noreply.github.com' \
  commit-tree "$TREE" -p 3b20c702b5c3267b2b386d7789f83b1e846060f3 \
  --date='<author-date of the packaging commit>' \
  -m "Package the public release: guides, Pages site, and contact (#2)"
```

Check the result before the force-push:

```bash
git diff "$TREE" origin/main
# NEEDLE is the alternation from the pull request description. Do not copy it into this file.
git log --format='%B' "$NEW" | grep -E "$NEEDLE" && exit 1
git log -p "$NEW" -1 | grep -E "$NEEDLE" && exit 1
git grep -E "$NEEDLE" "$NEW" && exit 1
```

The `git log -p` check must be empty. The new commit’s patch is against `3b20c70`, whose tree never had the contacts, and the new tree is the scrubbed tree, so the contacts are not added and not deleted.

## Packaging branch

`main` does not contain `20b42d7` or its children. A `main` rewrite leaves `origin/cursor/public-release-packaging-34f5` in `git log --all`.

That branch is the pre-squash history of the already-merged packaging pull request. Preferred follow-up, still only after approval:

- Delete the remote branch, which drops those four commits from fresh clones, or
- Rebuild the same four commits with the contact lines removed and force-push that branch only.

Deleting is enough if nobody needs that branch. Do not force-push it from this pull request.

## What a git rewrite does not clear

GitHub still keeps the old patch on the merged packaging pull request, its review comments, and any cached pages. Those are not git objects. Editing or deleting that pull request is separate from rewriting `main`.

## Verify after the rewrite

```bash
git fetch origin
# NEEDLE is the alternation from the pull request description.
git grep -E "$NEEDLE" $(git rev-list origin/main)
git log origin/main --format='%B' | grep -E "$NEEDLE"
git log origin/main -p | grep -E "$NEEDLE"
```

All three commands should print nothing. Repeat with `--all` only after the packaging branch is deleted or rewritten. `https://github.com/LofiSu`, `lofisuchat@gmail.com`, and `https://github.com/sponsors/LofiSu` must still be present.
