import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SENTRY_AUTH_TOKEN = os.getenv("SENTRY_AUTH_TOKEN", "")
SENTRY_ORG = os.getenv("SENTRY_ORG", "")
SENTRY_PROJECT = os.getenv("SENTRY_PROJECT", "")

SENTRY_API_BASE = "https://sentry.io/api/0"


def fetch_top_errors(hours=168, limit=3):
    if not SENTRY_AUTH_TOKEN or not SENTRY_ORG or not SENTRY_PROJECT:
        print("ERROR: SENTRY_AUTH_TOKEN, SENTRY_ORG, and SENTRY_PROJECT must be set.", file=sys.stderr)
        sys.exit(1)

    headers = {"Authorization": f"Bearer {SENTRY_AUTH_TOKEN}"}
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"

    url = f"{SENTRY_API_BASE}/organizations/{SENTRY_ORG}/projects/{SENTRY_PROJECT}/issues/"
    params = {
        "query": "is:unresolved",
        "sort": "freq",
        "limit": limit,
        "start": since,
        "statsPeriod": f"{hours}h",
    }

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_slack_message(issues):
    today = datetime.utcnow().strftime("%m/%y/%d")
    lines = [f"*Sentry error report for {today}*", ""]

    for issue in issues:
        issue_id = issue.get("id", "")
        title = issue.get("title", "Unknown error")
        count = issue.get("count", "?")
        user_count = issue.get("userCount", "?")
        permalink = issue.get("permalink", f"https://sentry.io/organizations/{SENTRY_ORG}/issues/{issue_id}/")
        project = issue.get("project", {}).get("slug", SENTRY_PROJECT)
        short_title = title if len(title) <= 120 else title[:117] + "..."
        lines.append(f"{permalink}: {short_title} (seen {count}x across {user_count} users)")

    return "\n\n".join(lines)


def main():
    issues = fetch_top_errors()
    if not issues:
        today = datetime.utcnow().strftime("%m/%y/%d")
        print(f"*Sentry error report for {today}*\n\nNo unresolved errors found in the last 7 days.")
        return

    msg = format_slack_message(issues)
    print(msg)


if __name__ == "__main__":
    main()
