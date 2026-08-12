# Project Instructions

- Use the `main` branch only; do not create or work on separate branches.
- When implementing a ticket, fulfill every acceptance criterion before claiming completion.
- When implementing a ticket or issue, mark each acceptance-criteria checkbox `[x]` only after that criterion has been successfully completed; this is bookkeeping for clarification.

## CLI-first tooling

- Prefer an official, capable CLI over a web UI or MCP for project operations.
- Use `gh` for GitHub, the repository-local Playwright CLI for browser automation, the Vercel CLI for Vercel, and the Railway CLI for Railway.
- Use web UI or MCP only when the required capability is unavailable or inadequate in the CLI; state the reason and verify through CLI when possible.
- Batch related surgical mutations, then independently read back the resulting state through CLI.
 If any of these is not installed or not setup/login then do the setup first and ask the user to login by telling it steps, rather than shifting to non-cli paths

## UI and product interface

- For any UI-related work, including UX advice, frontend generation, visual design, layout, components, copy, or interaction flow, use the repository's `DESIGN.md` as the design-system authority and always use the `impeccable` skill. Do not rely on the agent's default UI preferences when they conflict with those sources.

## Git workflow - mandatory

- Work directly on `main` only. Never create, checkout, or use issue/feature branches or detached worktrees.
- Before editing, verify `git branch --show-current` is `main`. If the worktree is dirty or on another branch, stop and report it; never discard, stash, rebase, or reset user work without approval.
- Commit and push completed work to `origin/main`. A task is not complete until the remote `main` commit is independently verified.
- Do not claim work is pushed or resolve an issue if the commit exists only on a non-main branch.
