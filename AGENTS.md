# Project Instructions

- Use the `main` branch only; do not create or work on separate branches.

## CLI-first tooling

- Prefer an official, capable CLI over a web UI or MCP for project operations.
- Use `gh` for GitHub, the repository-local Playwright CLI for browser automation, the Vercel CLI for Vercel, and the Railway CLI for Railway.
- Use web UI or MCP only when the required capability is unavailable or inadequate in the CLI; state the reason and verify through CLI when possible.
- Batch related surgical mutations, then independently read back the resulting state through CLI.
 If any of these is not installed or not setup/login then do the setup first and ask the user to login by telling it steps, rather than shifting to non-cli paths
