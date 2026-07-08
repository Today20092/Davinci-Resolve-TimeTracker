# Issue Tracker: GitHub

Issues and PRDs for this repo live as GitHub issues. Use the `gh` CLI for tracker operations.

## Conventions

- Create an issue: `gh issue create --title "..." --body-file <file> --label "ready-for-agent"`.
- Read an issue: `gh issue view <number> --comments`.
- List issues: `gh issue list --state open --json number,title,body,labels,assignees`.
- Comment on an issue: `gh issue comment <number> --body-file <file>`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`.
- Close an issue: `gh issue close <number> --comment "..."`.

Infer the repo from `git remote -v`; `gh` does this automatically inside the clone.

## Pull Requests As A Triage Surface

PRs as a request surface: no.

## When A Skill Says "Publish To The Issue Tracker"

Create a GitHub issue and apply the configured triage label.

## When A Skill Says "Fetch The Relevant Ticket"

Run `gh issue view <number> --comments`.

## Wayfinding Operations

Used by `/wayfinder`. The map is a single issue with child issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue when available. If sub-issues are unavailable, put `Part of #<map>` at the top of the child body and include a task-list link in the map body.
- **Blocking**: use GitHub native issue dependencies when available. If dependencies are unavailable, use a `Blocked by: #<n>, #<n>` line near the top of the issue body.
- **Frontier**: list the map's open children or linked task-list issues, then drop any with open blockers or an assignee.
- **Claim**: `gh issue edit <n> --add-assignee @me`.
- **Resolve**: comment with the answer, close the issue, then append a context pointer to the map issue.
