# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- `CONTEXT.md` at the repo root.
- `CONTEXT-MAP.md` at the repo root if it exists; it points at one `CONTEXT.md` per context.
- `docs/adr/` for architectural decisions that touch the area being changed.

If any of these files do not exist, proceed silently.

## File Structure

This is a single-context repo: one root `CONTEXT.md`, with ADRs under `docs/adr/` when needed.

## Use The Glossary

When naming domain concepts in issues, specs, tests, or code, use the terms defined in `CONTEXT.md`. Avoid synonyms that the glossary explicitly rejects.
