# Telegram Bot API integration research

**Status:** research note, verified 2026-08-13  
**Scope:** manager-operated Telegram bot; no application code changes

## Bottom line

Yes: the clean fit for this repository is a Telegram bot that is created in BotFather, runs its logic in the FastAPI backend on Railway, and leaves the Vercel-hosted frontend as the operator UI only. Telegram supports both `getUpdates` (pull/long polling) and `setWebhook` (push). For a deployed backend with a public HTTPS origin, webhook is the better default; keep `getUpdates` only as a local-development or fallback path. [Telegram webhooks](https://core.telegram.org/bots/webhooks), [Telegram FAQ](https://core.telegram.org/bots/faq)

## What the official docs support

- Bot creation starts with `@BotFather` and `/newbot`, which returns a bot token that can later be revoked. [Telegram tutorial](https://core.telegram.org/bots/tutorial)
- Commands are first-class bot UI. Telegram shows `/`-prefixed commands in chat, can surface them in the bot menu, and supports setting them via `setMyCommands` with scope and language control. [Telegram features](https://core.telegram.org/bots/features), [Bot API](https://core.telegram.org/bots/api)
- `sendMessage` is the basic outbound text-message method. It can include `reply_markup` with an `InlineKeyboardMarkup`. [Bot API](https://core.telegram.org/bots/api)
- Inline keyboards are attached next to the message they belong to. Button presses generate `callback_query` updates, and Telegram expects `answerCallbackQuery` to be called after the press. [Bot API](https://core.telegram.org/bots/api)
- `callback_data` is the button payload you receive back in the callback query. That is the normal way to route manager actions such as approve/reject/next-step flows. [Bot API](https://core.telegram.org/bots/api)
- Webhook security supports a `secret_token` value, which Telegram sends back in the `X-Telegram-Bot-Api-Secret-Token` header. Treat that header as the first-line authenticity check for your webhook endpoint. [Bot API](https://core.telegram.org/bots/api)

## Webhook vs. long polling

Telegram's own guidance is straightforward: `getUpdates` is pull, `setWebhook` is push. Webhooks require a reachable server with HTTPS, a valid certificate chain, and an open supported port. Telegram's webhook guide also says it needs a URL on a server it can reach over the public internet. [Telegram webhooks](https://core.telegram.org/bots/webhooks)

Practical implication:

- Use webhook for anything hosted and always on.
- Use `getUpdates` only if you want a local/dev setup without a public inbound URL.

## Can Vercel frontend + Railway FastAPI backend receive the webhook?

Yes, with one important boundary: the webhook must terminate on the Railway backend, not on the Vercel frontend.

Railway's public networking exposes services to the internet over HTTP/HTTPS and provides automatic SSL certificates and public domains. Railway also has a FastAPI deployment guide. That is enough to host the Telegram webhook handler as a public HTTPS endpoint. [Railway public networking](https://docs.railway.com/networking/public-networking), [Railway FastAPI guide](https://docs.railway.com/guides/fastapi)

This repository already matches that split: `README.md` says the Vite frontend proxies `/api` to the backend, and `docs/deployment/hosted-tracer.md` says hosted delivery uses Vercel as the browser origin while rewriting `/api/*` to the one Railway service. So the Telegram bot belongs in the Railway FastAPI service, while the Vercel frontend can remain the manager/operator surface. [`README.md`](../../README.md), [`docs/deployment/hosted-tracer.md`](../deployment/hosted-tracer.md)

## Where Telegram Web Apps fit

Telegram Web Apps are optional here. They matter only if you want a richer in-Telegram UI than commands and inline keyboards. Telegram says Web Apps support custom JavaScript interfaces and can replace a website, but they are not required for a manager-operated bot workflow. [Telegram features](https://core.telegram.org/bots/features), [Telegram Mini Apps](https://core.telegram.org/bots/webapps)

## Recommendation for this repo

Use this shape:

1. Create the bot with BotFather and store the bot token only in Railway secrets.
2. Add a FastAPI webhook endpoint on Railway, protected by `secret_token`.
3. Model manager actions with commands plus inline keyboards/callback queries.
4. Keep the Vercel frontend as a management/status UI only.
5. Use Telegram Web Apps later only if the operator flow needs a full custom UI inside Telegram.

This avoids putting bot ingress on the frontend host and keeps the existing Vercel/Railway split intact.

## Effort estimate

| Track | Estimate | What fits in scope |
|---|---:|---|
| Hackathon demo MVP | 4-8 focused hours | BotFather creation, one webhook endpoint, one or two manager commands, one inline keyboard flow, one `sendMessage` path, and `secret_token` verification. |
| Production-grade integration | 16-40 hours | Retries/idempotency, structured logging, alerting, callback-state handling, command management, secret rotation, deployment health checks, and test coverage for webhook/auth paths. |

The MVP is enough to prove the bot loop. Production work is mostly about making the webhook durable, observable, and safe to operate.
