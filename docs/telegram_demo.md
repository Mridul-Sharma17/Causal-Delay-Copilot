# Telegram demo

This is a short, standalone Telegram presentation layer for the hero scenario. It uses the same scripted cases, evidence chain, manager decisions, and draft email as the website demo, but it does not connect to the backend, persist decisions, or send email.

## Run it

Open PowerShell at the repository root:

```powershell
cd 'C:\Users\Mridul Sharma\Desktop\Kaya AI Hackathon\Causal-Delay-Copilot'
$env:TELEGRAM_BOT_TOKEN = '<your token>'
uv run --locked --no-sync python scripts/telegram_demo_bot.py
```

The token is read only from the current PowerShell environment. Never commit it or put it in a source file.

## Demo path

In Telegram, open the bot and send `/start`.

1. Tap **Open switchgear case**.
2. Tap **View evidence chain**.
3. Tap **Open decision options**.
4. Tap **Request recovery plan** to show the prepared email draft.

The other two staged cases are available from the inbox as well. Stop the local bot with `Ctrl+C`.

## Offline content check

This prints the inbox, hero case, evidence, decisions, and email draft without contacting Telegram:

```powershell
uv run --locked --no-sync python scripts/telegram_demo_bot.py --dry-run
```
