import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SENTRY_AUTH_TOKEN = os.getenv("SENTRY_AUTH_TOKEN")
SENTRY_ORG = os.getenv("SENTRY_ORG")
SENTRY_PROJECT = os.getenv("SENTRY_PROJECT", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SENTRY_API_BASE = "https://sentry.io/api/0"


def fetch_top_issues(limit=10):
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


def pick_top_3(issues):
    scored = []
    for issue in issues:
        freq = issue.get("count", 0)
        users = issue.get("userCount", 0)
        priority = freq + users * 10
        scored.append((priority, issue))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:3]]


def build_slack_message(top_issues):
    today = datetime.now().strftime("%m/%d/%y")
    lines = [f"*Sentry Error Report for {today}*\n"]
    for issue in top_issues:
        link = issue.get("permalink", "")
        title = issue.get("title", "Unknown error")
        count = issue.get("count", 0)
        users = issue.get("userCount", 0)
        summary = f"{title} — {count} events, {users} users affected"
        lines.append(f"{link}: {summary}")
    return "\n\n".join(lines)


def post_to_slack(message):
    payload = {"text": message}
    resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()
    print("Slack message posted successfully.")


def main():
    if not SENTRY_AUTH_TOKEN or not SENTRY_ORG or not SLACK_WEBHOOK_URL:
        print("Missing required env vars: SENTRY_AUTH_TOKEN, SENTRY_ORG, SLACK_WEBHOOK_URL")
        return

    issues = fetch_top_issues(limit=10)
    if not issues:
        print("No unresolved Sentry issues found.")
        return

    top_3 = pick_top_3(issues)
    message = build_slack_message(top_3)
    print("Generated message:\n")
    print(message)
    post_to_slack(message)


if __name__ == "__main__":
    main()
