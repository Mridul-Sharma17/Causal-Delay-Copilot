# Project Instructions

- Use the `main` branch only; do not create or work on separate branches.
- When implementing a ticket, fulfill every acceptance criterion before claiming completion.

## CLI-first tooling

- Prefer an official, capable CLI over a web UI or MCP for project operations.
- Use `gh` for GitHub, the repository-local Playwright CLI for browser automation, the Vercel CLI for Vercel, and the Railway CLI for Railway.
- Use web UI or MCP only when the required capability is unavailable or inadequate in the CLI; state the reason and verify through CLI when possible.
- Batch related surgical mutations, then independently read back the resulting state through CLI.
 If any of these is not installed or not setup/login then do the setup first and ask the user to login by telling it steps, rather than shifting to non-cli paths

## Git workflow - mandatory

- Work directly on `main` only. Never create, checkout, or use issue/feature branches or detached worktrees.
- Before editing, verify `git branch --show-current` is `main`. If the worktree is dirty or on another branch, stop and report it; never discard, stash, rebase, or reset user work without approval.
- Commit and push completed work to `origin/main`. A task is not complete until the remote `main` commit is independently verified.
- Do not claim work is pushed or resolve an issue if the commit exists only on a non-main branch.
