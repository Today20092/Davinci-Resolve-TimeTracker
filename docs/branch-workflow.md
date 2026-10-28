# Git Workflow

## Branches and Integration

`development` is the everyday working and integration branch. `main` is the reviewed release-source branch and remains the preferred remote default. External contributions target `development`.

For sequential work, work directly on `development` and commit useful checkpoints. For parallel work, use scoped `codex/<scope>` branches or worktrees from current `development`; merge completed changes back into `development`. Run the [complete checks](development.md#run-checks) on the combined source. Source merges do not update installed or built applications.

Fetch remote state before synchronization. Use `git pull --ff-only` when the branch can advance without divergence; inspect and deliberately merge divergent histories while preserving local work. Push development checkpoints as backups when authorized.

## Promotion

Promote a tested batch through a `development` to `main` PR using a merge commit to preserve ancestry. Record the source revision and check results in the PR. Bring main-only fixes and release metadata back into `development` through a merge before the next batch. GitHub merge settings and branch protections must be verified before promotion; this policy does not establish that they are configured.

Follow the [release policy](releasing.md) for versions and publication. A source promotion and a published release are separate actions.

## Automation

[CI](../.github/workflows/ci.yml) runs on pushes to `main` and `development`, all tag pushes, and pull requests. It checks Python formatting, lint, and pytest plus frontend tests, lint, and build on Windows and Ubuntu. [Release automation](../.github/workflows/release.yml) creates draft notes for `v*` tags. Neither workflow currently builds downloadable installers.

## Migration and Cleanup

The local `development` branch starts at `692e0cb`, the integrated work from `codex/implement-native-spec` in the “Review open GitHub issues” thread. Existing branches and worktrees are retained. Remote branch publication, protection changes, and promotion require their own authorized operations.

Retire temporary worktrees and branches only after their needed commits are integrated and uncommitted files, ignored artifacts, and test evidence are preserved. Keep active work and the long-lived `development` and `main` branches.
