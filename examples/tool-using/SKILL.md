---
name: commit
description: Stage and commit the current changes with a conventional message
argument-hint: "[optional commit-message override]"
disable-model-invocation: true
allowed-tools: Bash(git add *), Bash(git commit *), Bash(git status *), Bash(git diff *)
---

Stage and commit the working-tree changes.

1. Run `git status` and `git diff` to see what changed.
2. Draft a conventional-commit message from the diff. If $ARGUMENTS is non-empty, use it as the message instead.
3. Show the user the file list and the message; wait for approval.
4. On approval: `git add` the reviewed files and `git commit`.

Never push — committing is this skill's whole job.
