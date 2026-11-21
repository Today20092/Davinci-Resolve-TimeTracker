# Git workflow

`main` is the only long-lived branch. Each task gets its own branch and pull request into `main`; there is no integration branch and no stacked PRs.

## Work on a task

1. Work in a worktree the host manages, based on current `origin/main`. A T3 Code thread on the main checkout moves itself with `t3_worktree_handoff` before editing; the project's worktree script runs `uv sync --dev` and `pnpm --dir frontend install --frozen-lockfile`. Without host worktree tools, use `git worktree add` and run `uv sync --dev` and `pnpm --dir frontend install --frozen-lockfile`.
2. Commit work in progress instead of using `git stash`: stashes are shared by every worktree.
3. Make the change and run the [complete checks](development.md#run-checks). Source merges do not update installed or built applications.
4. End every code task with a commit and a pull request to `main`, without being asked. Opening a PR is safe; only a merge changes `main`; nothing deploys.
5. CI runs on the PR (Ubuntu and Windows). Watch it and fix failures until it passes. To merge without waiting, queue it with `gh pr merge --auto --merge`; GitHub merges once the required checks pass.
6. Merge only when the user asks, with a merge commit.

Fetch before choosing a base. Use `git pull --ff-only` to advance a local `main`; inspect divergent histories and merge deliberately. Never force-push `main`.

## What runs where

| Event | Effect |
| --- | --- |
| Pull request, push to `main`, any tag | [CI](../.github/workflows/ci.yml): Python format, lint and pytest; frontend tests, lint and build, on Windows and Ubuntu |
| `v*` tag | [Release automation](../.github/workflows/release.yml) creates draft notes |
| Monthly | [Dependabot](../.github/dependabot.yml) opens one grouped minor-and-patch PR per ecosystem; majors one PR each. [Auto-merge](../.github/workflows/dependabot-auto-merge.yml) queues minor and patch PRs; majors wait for a person |

Follow the [release policy](releasing.md) for versions and publication. A merge and a published release are separate actions.

## Repository controls

`main` requires a pull request, both `test` checks and resolved conversations; rules apply to administrators, and force pushes and deletion are blocked. It does not require branches to be up to date, since nothing deploys from `main`. Auto-merge is allowed and merged branches are deleted automatically. The `development` branch is retired.

## Cleanup

GitHub deletes a merged PR's branch. Remove the task's worktree through the host (or `git worktree remove`) once it has no uncommitted or unmerged work.
