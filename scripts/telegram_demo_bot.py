"""Standalone Telegram demo for the Causal Delay Copilot hero scenario.

This script is intentionally independent from the application backend. It uses
the Telegram Bot API directly and renders the same scripted cases, evidence
chain, decision options, and email draft used by the frontend demo.

The bot never sends an email and never stores a decision. Keep the token in the
TELEGRAM_BOT_TOKEN environment variable; do not put it in source control.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_TIMEOUT_SECONDS = 35
POLL_TIMEOUT_SECONDS = 25


CASES = {
    "switchgear": {
        "title": "Switchgear handoff risk",
        "priority": "URGENT",
        "project": "Project Alpha",
        "detail": "120 units · Electrical package",
        "due": "Decision due today",
    },
    "concrete": {
        "title": "Concrete enclosure delay",
        "priority": "NEEDS EVIDENCE",
        "project": "Project Alpha",
        "detail": "Substructure · Activity 3.2",
        "due": "Review due tomorrow",
    },
    "hvac": {
        "title": "HVAC unit long-lead risk",
        "priority": "MONITORING",
        "project": "Project Beta",
        "detail": "Mechanical · Activity 6.1",
        "due": "Next review in 2 days",
    },
}


HERO = {
    "score": "91%",
    "source": "Amber risk signal",
    "supplier": "PowerGrid Systems",
    "order": "120 high-complexity switchgear units",
    "package": "Project Alpha · Electrical package",
    "promise": "Feb 15, 2026",
    "revision": "Feb 20, 2026",
    "exposure": "$185,000 order exposure",
    "recommendation": "Request supplier recovery plan",
    "headline": "The supplier handoff is the decision point.",
    "language": (
        "High-load exposure is estimated to increase Supplier Milestone "
        "Slippage by 1.5 calendar days (95% interval 0.2 to 2.8), under "
        "the stated assumptions."
    ),
    "recipient": "recovery@powergrid-systems.com",
    "subject": "Project Alpha: recovery plan for switchgear handoff",
    "body": (
        "Hi Priya,\n\n"
        "We are reviewing the revised February 20 handoff for Project Alpha's "
        "switchgear package. Please share a dated recovery plan covering the "
        "remaining 120 units, the next confirmed milestone, and any action "
        "needed from our team.\n\n"
        "Please send the plan by 3:00 PM today so we can protect the downstream "
        "installation sequence.\n\n"
        "Best,\nAlex Morgan"
    ),
}


EVIDENCE = [
    (
        "SIGNAL",
        "The risk signal crossed the review threshold at 91%. It starts an "
        "investigation; it is not a causal conclusion.",
    ),
    (
        "ELIGIBILITY",
        "The switchgear order line is in scope: the supplier handoff, promised "
        "date, revised date, and downstream activity are all bound to the same case.",
    ),
    (
        "CAUSAL READOUT",
        "The evidence supports a supplier recovery conversation for this handoff. "
        "The recommendation stays bounded to the current evidence chain.",
    ),
    (
        "MANAGER VERDICT",
        "Request a dated recovery plan from the supplier. The manager reviews and "
        "sends the message; the copilot does not execute the action.",
    ),
]


DECISIONS = {
    "recovery": {
        "label": "Request supplier recovery plan",
        "rationale": "Protect the switchgear handoff with a dated supplier commitment.",
        "subject": HERO["subject"],
        "body": HERO["body"],
    },
    "monitor": {
        "label": "Accept and monitor",
        "rationale": "Keep the case open and verify the next supplier milestone before escalating.",
        "subject": "Project Alpha: monitor switchgear handoff",
        "body": (
            "Hi Priya,\n\n"
            "Please confirm the next production milestone for Project Alpha's switchgear "
            "handoff and let us know if the February 20 date is still achievable. We will "
            "keep the case under review and follow up at the next checkpoint.\n\n"
            "Best,\nAlex Morgan"
        ),
    },
    "escalate": {
        "label": "Escalate to project controls",
        "rationale": "Bring the schedule owner into the decision before the downstream sequence is affected.",
        "subject": "Project Alpha: switchgear handoff needs schedule review",
        "body": (
            "Hi team,\n\n"
            "The Project Alpha switchgear handoff has moved from February 15 to February 20. "
            "Please review the downstream installation sequence and confirm the mitigation "
            "path for the 120-unit package.\n\n"
            "Best,\nAlex Morgan"
        ),
    },
}


def inline_keyboard(*rows: tuple[str, str]) -> dict[str, list[list[dict[str, str]]]]:
    """Build Telegram's inline keyboard shape from (label, callback) pairs."""

    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": callback}] for label, callback in rows
        ]
    }


def inbox_message() -> str:
    return (
        "CAUSAL DELAY COPILOT\n"
        "Manager attention inbox\n\n"
        "3 cases need a decision or review today. Choose a case to open its path.\n\n"
        "URGENT  ·  Switchgear handoff risk\n"
        "Project Alpha · 120 units · Electrical package\n"
        "Decision due today\n\n"
        "NEEDS EVIDENCE  ·  Concrete enclosure delay\n"
        "Project Alpha · Substructure · Activity 3.2\n"
        "Review due tomorrow\n\n"
        "MONITORING  ·  HVAC unit long-lead risk\n"
        "Project Beta · Mechanical · Activity 6.1\n"
        "Next review in 2 days"
    )


def case_message(case_id: str) -> str:
    case = CASES[case_id]
    if case_id != "switchgear":
        return (
            f"{case['title'].upper()}\n"
            f"{case['project']} · {case['detail']}\n"
            f"{case['priority']} · {case['due']}\n\n"
            "This case is staged for manager review in the Copilot. The next "
            "step is to open the web workbench and attach the supporting evidence."
        )

    return (
        "SWITCHGEAR HANDOFF RISK\n"
        "Project Alpha · Electrical package\n"
        "URGENT · Decision due today\n\n"
        f"{HERO['score']} risk signal\n"
        f"{HERO['supplier']} · {HERO['order']}\n"
        f"Promised {HERO['promise']} → revised {HERO['revision']}\n"
        f"Exposure: {HERO['exposure']}\n\n"
        "COPILOT RECOMMENDATION\n"
        f"{HERO['recommendation']}\n\n"
        f"{HERO['headline']}\n"
        f"{HERO['language']}"
    )


def evidence_message() -> str:
    blocks = ["EVIDENCE CHAIN\n", "The signal is the start of the investigation — not the conclusion.\n"]
    for index, (label, detail) in enumerate(EVIDENCE, start=1):
        blocks.append(f"{index}. {label}\n{detail}\n")
    return "\n".join(blocks).strip()


def decision_message() -> str:
    return (
        "DECISION BRIEF\n"
        "Project Alpha · Switchgear handoff\n\n"
        f"Recommended action: {HERO['recommendation']}\n"
        f"Why: Protect the switchgear handoff with a dated supplier commitment.\n\n"
        "Choose the manager's next action. The copilot prepares the work; the manager approves it."
    )


def draft_message(choice: str) -> str:
    decision = DECISIONS[choice]
    return (
        "DRAFT READY FOR MANAGER APPROVAL\n\n"
        f"Action: {decision['label']}\n"
        f"To: {HERO['recipient']}\n"
        f"Subject: {decision['subject']}\n\n"
        f"{decision['body']}\n\n"
        "This is a demo draft. Telegram does not send the email."
    )


def api_request(token: str, method: str, payload: dict[str, Any] | None = None) -> Any:
    """Call Telegram without ever including the bot token in an error message."""

    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(payload or {}).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Telegram API {method} returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"Telegram API {method} network error: {error.reason}") from error

    if not result.get("ok"):
        description = result.get("description", "unknown Telegram API error")
        raise RuntimeError(f"Telegram API {method} failed: {description}")
    return result.get("result")


def send_message(token: str, chat_id: int | str, text: str, keyboard: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = keyboard
    api_request(token, "sendMessage", payload)


def show_inbox(token: str, chat_id: int | str) -> None:
    send_message(
        token,
        chat_id,
        inbox_message(),
        inline_keyboard(
            ("Open switchgear case", "case:switchgear"),
            ("Open concrete case", "case:concrete"),
            ("Open HVAC case", "case:hvac"),
        ),
    )


def show_case(token: str, chat_id: int | str, case_id: str) -> None:
    if case_id == "switchgear":
        keyboard = inline_keyboard(
            ("View evidence chain", "view:evidence"),
            ("Decision options", "view:decisions"),
            ("Back to inbox", "menu:inbox"),
        )
    else:
        keyboard = inline_keyboard(("Back to inbox", "menu:inbox"))
    send_message(token, chat_id, case_message(case_id), keyboard)


def show_evidence(token: str, chat_id: int | str) -> None:
    send_message(
        token,
        chat_id,
        evidence_message(),
        inline_keyboard(
            ("Open decision options", "view:decisions"),
            ("Back to case", "case:switchgear"),
        ),
    )


def show_decisions(token: str, chat_id: int | str) -> None:
    send_message(
        token,
        chat_id,
        decision_message(),
        inline_keyboard(
            ("Request recovery plan", "draft:recovery"),
            ("Accept and monitor", "draft:monitor"),
            ("Escalate to controls", "draft:escalate"),
            ("Back to evidence", "view:evidence"),
        ),
    )


def show_draft(token: str, chat_id: int | str, choice: str) -> None:
    send_message(
        token,
        chat_id,
        draft_message(choice),
        inline_keyboard(
            ("View other options", "view:decisions"),
            ("Back to inbox", "menu:inbox"),
        ),
    )


def handle_callback(token: str, callback_query: dict[str, Any]) -> None:
    callback_id = callback_query.get("id")
    if callback_id:
        api_request(token, "answerCallbackQuery", {"callback_query_id": callback_id})

    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    data = callback_query.get("data", "")
    if data == "menu:inbox":
        show_inbox(token, chat_id)
    elif data.startswith("case:") and data[5:] in CASES:
        show_case(token, chat_id, data[5:])
    elif data == "view:evidence":
        show_evidence(token, chat_id)
    elif data == "view:decisions":
        show_decisions(token, chat_id)
    elif data.startswith("draft:") and data[6:] in DECISIONS:
        show_draft(token, chat_id, data[6:])


def handle_message(token: str, message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    text = (message.get("text") or "").strip().lower()
    if text.startswith("/start") or text in {"/list", "list", "inbox", "cases"}:
        show_inbox(token, chat_id)
        return

    send_message(
        token,
        chat_id,
        "Use /list to open the manager attention inbox.",
        inline_keyboard(("Open attention inbox", "menu:inbox")),
    )


def process_update(token: str, update: dict[str, Any]) -> None:
    if "callback_query" in update:
        handle_callback(token, update["callback_query"])
    elif "message" in update:
        handle_message(token, update["message"])


def dry_run() -> None:
    """Print every demo state so the scripted content can be checked offline."""

    for label, content in (
        ("INBOX", inbox_message()),
        ("HERO CASE", case_message("switchgear")),
        ("EVIDENCE", evidence_message()),
        ("DECISIONS", decision_message()),
        ("EMAIL DRAFT", draft_message("recovery")),
    ):
        print(f"\n--- {label} ---\n{content}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the standalone Telegram Copilot demo.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the scripted Telegram states without contacting Telegram.",
    )
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=POLL_TIMEOUT_SECONDS,
        help="Telegram long-poll timeout in seconds (default: 25).",
    )
    return parser.parse_args()


def run() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    if args.dry_run:
        dry_run()
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print(
            "TELEGRAM_BOT_TOKEN is not set. Set it in this PowerShell window before running the bot.",
            file=sys.stderr,
        )
        return 2

    try:
        bot = api_request(token, "getMe")
        api_request(token, "deleteWebhook", {"drop_pending_updates": False})
        api_request(
            token,
            "setMyCommands",
            {
                "commands": [
                    {"command": "start", "description": "Open the attention inbox"},
                    {"command": "list", "description": "List cases needing attention"},
                    {"command": "help", "description": "Show demo commands"},
                ]
            },
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    username = bot.get("username", "the bot") if isinstance(bot, dict) else "the bot"
    print(f"Telegram demo bot @{username} is running. Press Ctrl+C to stop.")
    print("Demo path: /start → Switchgear handoff risk → View evidence chain → Decision options")

    offset: int | None = None
    try:
        while True:
            payload: dict[str, Any] = {
                "timeout": max(1, args.poll_timeout),
                "allowed_updates": ["message", "callback_query"],
            }
            if offset is not None:
                payload["offset"] = offset
            try:
                updates = api_request(token, "getUpdates", payload) or []
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    process_update(token, update)
            except RuntimeError as error:
                print(str(error), file=sys.stderr)
                time.sleep(3)
    except KeyboardInterrupt:
        print("\nTelegram demo bot stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(run())
