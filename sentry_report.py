import os
import sys
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

SENTRY_AUTH_TOKEN = os.getenv("SENTRY_AUTH_TOKEN")
SENTRY_ORG = os.getenv("SENTRY_ORG")
SENTRY_PROJECT = os.getenv("SENTRY_PROJECT", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SENTRY_API_BASE = "https://sentry.io/api/0"

LEVEL_WEIGHTS = {
    "fatal": 5000,
    "error": 1000,
    "warning": 100,
    "info": 10,
    "debug": 1,
}


def fetch_top_issues(limit=20):
    headers = {"Authorization": f"Bearer {SENTRY_AUTH_TOKEN}"}
    params = {
        "query": "is:unresolved",
        "sort": "freq",
        "limit": limit,
    }
    if SENTRY_PROJECT:
        params["project"] = SENTRY_PROJECT

    url = f"{SENTRY_API_BASE}/organizations/{SENTRY_ORG}/issues/"
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def score_issue(issue):
    count = int(issue.get("count", 0) or 0)
    users = int(issue.get("userCount", 0) or 0)
    level = issue.get("level", "error")
    level_score = LEVEL_WEIGHTS.get(level, LEVEL_WEIGHTS["error"])
    last_seen = issue.get("lastSeen", "")
    recency_bonus = 200 if last_seen and last_seen[:10] == datetime.now(timezone.utc).strftime("%Y-%m-%d") else 0
    return level_score + count + users * 10 + recency_bonus


def pick_top_3(issues):
    scored = [(score_issue(issue), issue) for issue in issues]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [issue for _, issue in scored[:3]]


def shorten(text, max_len=120):
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def build_slack_message(top_issues):
    today = datetime.now().strftime("%m/%y/%d")
    lines = [f"*Sentry Error Report for {today}*", "", ""]

    for issue in top_issues:
        link = issue.get("permalink", "")
        title = shorten(issue.get("title", "Unknown error"))
        count = issue.get("count", "0")
        users = issue.get("userCount", "0")
        level = issue.get("level", "error")
        summary = f"{title} — {count} events, {users} users affected (level: {level})"
        lines.append(f"{link}: {summary}")
        lines.append("")

    while len(lines) > 0 and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def post_to_slack(message):
    payload = {"text": message}
    resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()
    print("Slack message posted successfully.")


def main():
    if not SENTRY_AUTH_TOKEN or not SENTRY_ORG or not SLACK_WEBHOOK_URL:
        print("Missing required env vars: SENTRY_AUTH_TOKEN, SENTRY_ORG, SLACK_WEBHOOK_URL")
        sys.exit(1)

    issues = fetch_top_issues(limit=20)
    if not issues:
        print("No unresolved Sentry issues found.")
        return

    top_3 = pick_top_3(issues)
    message = build_slack_message(top_3)
    print("Generated message:\n")
    print(message)
    print()
    post_to_slack(message)


if __name__ == "__main__":
    main()
