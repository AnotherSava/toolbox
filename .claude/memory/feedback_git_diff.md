---
name: git diff against HEAD
description: Always diff against HEAD (not staged vs unstaged) to understand what a commit will contain
type: feedback
---

When reviewing changes for a commit, always compare against HEAD (`git diff HEAD`) to see the actual content that will be committed. Do not compare staged vs unstaged diffs — that shows intermediate editing states, not the final result.

**Why:** Comparing staged vs unstaged led to a wrong commit message that described "cleaning up" entries that never existed in the repo — the staged state was just an intermediate edit, and the unstaged diff was a further edit on top. The real change (vs HEAD) was simply adding a new file.

**How to apply:** During `/commit`, use `git diff HEAD` (or `git show HEAD:<file>` for individual files) as the primary source of truth. Use `git status` to see which files changed, but always check the total diff against the repo to understand what the commit actually does.
