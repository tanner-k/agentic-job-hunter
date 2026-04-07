"""Email monitoring agent.

Runs on a schedule (every 2 hours). Fetches unread recruiter emails,
classifies them with the reasoning LLM, drafts replies for interviews,
and syncs summaries to Supabase.

Gmail OAuth setup (one-time, run manually):
    uv run python -m worker.agents.email_agent --setup
"""

import base64
import json
import pickle
from datetime import UTC, datetime

from crewai import LLM
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from worker.config import settings
from worker.db.repository import insert_email_log
from worker.logging_config import get_logger
from worker.models.email_log import EmailLog

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def _get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    creds = None
    token_path = settings.gmail_token_path
    credentials_path = settings.gmail_credentials_path

    if token_path.exists():
        with token_path.open("rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {credentials_path}. "
                    "Download credentials.json from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with token_path.open("wb") as f:
            pickle.dump(creds, f)

    return build("gmail", "v1", credentials=creds)


def _get_email_body(msg: dict) -> str:
    """Extract plain text body from a Gmail message."""
    payload = msg.get("payload", {})
    parts = payload.get("parts", [])

    if not parts:
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    return ""


def _classify_email(subject: str, body: str) -> tuple[str, str]:
    """Use reasoning LLM to classify email and return (sentiment, summary).

    Returns sentiment: 'interest' | 'rejection' | 'spam'
    """
    llm = LLM(model=settings.reasoning_model, base_url=settings.ollama_base_url)

    prompt = (
        "You are classifying job application-related emails. "
        "Analyze the following email and respond with ONLY a JSON object with two fields:\n"
        '- "sentiment": one of "interest", "rejection", or "spam"\n'
        '- "summary": a one-sentence summary (max 100 chars)\n\n'
        f"Subject: {subject}\n\n"
        f"Body:\n{body[:2000]}\n\n"
        "Respond with only valid JSON, no other text."
    )

    try:
        response = llm.call([{"role": "user", "content": prompt}])
        # Extract text from response
        response_text = response if isinstance(response, str) else str(response)
        # Find JSON in response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(response_text[start:end])
            return result.get("sentiment", "spam"), result.get("summary", "No summary")
    except Exception as exc:
        logger.error("classification_failed", error=str(exc))

    return "spam", "Failed to classify"


def _create_draft_reply(service, thread_id: str, to: str, subject: str) -> str | None:
    """Create a Gmail draft reply for an interview request. Returns draft URL or None."""
    reply_body = (
        "Thank you for reaching out! I'm very interested in this opportunity "
        "and would love to discuss further. Please let me know your availability "
        "for a call this week or next.\n\nBest regards"
    )

    message_text = (
        f"To: {to}\n"
        f"Subject: Re: {subject}\n"
        f"Content-Type: text/plain; charset=utf-8\n\n"
        f"{reply_body}"
    )

    encoded = base64.urlsafe_b64encode(message_text.encode("utf-8")).decode("utf-8")

    try:
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": encoded, "threadId": thread_id}},
        ).execute()
        draft_id = draft.get("id", "")
        logger.info("draft_created", draft_id=draft_id, to=to)
        # Return a usable link to the draft (opens Gmail web)
        return f"https://mail.google.com/mail/u/0/#drafts/{draft_id}"
    except HttpError as exc:
        logger.error("draft_creation_failed", error=str(exc))
        return None


def run() -> None:
    """Fetch unread emails, classify them, create drafts for interest emails, sync to Supabase."""
    logger.info("email_agent_starting")

    try:
        service = _get_gmail_service()
    except FileNotFoundError as exc:
        logger.error("gmail_auth_failed", error=str(exc))
        return

    try:
        results = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=20,
        ).execute()
    except HttpError as exc:
        logger.error("gmail_fetch_failed", error=str(exc))
        return

    messages = results.get("messages", [])
    logger.info("emails_fetched", count=len(messages))

    for msg_ref in messages:
        msg_id = msg_ref["id"]
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except HttpError as exc:
            logger.error("message_fetch_failed", msg_id=msg_id, error=str(exc))
            continue

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "unknown")
        thread_id = msg.get("threadId", "")
        date_str = headers.get("Date", "")

        try:
            received_at = datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            received_at = datetime.now(tz=UTC)

        body = _get_email_body(msg)
        sentiment, summary = _classify_email(subject, body)

        draft_link = None
        if sentiment == "interest":
            draft_link = _create_draft_reply(service, thread_id, sender, subject)

        log = EmailLog(
            subject=subject,
            sender=sender,
            sentiment=sentiment,
            summary=summary,
            received_at=received_at,
            draft_link=draft_link,
        )
        insert_email_log(log)

        # Mark as read
        try:
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
        except HttpError as exc:
            logger.warning("mark_read_failed", msg_id=msg_id, error=str(exc))

    logger.info("email_agent_complete", processed=len(messages))


if __name__ == "__main__":
    import sys

    if "--setup" in sys.argv:
        # One-time OAuth setup — run manually: uv run python -m worker.agents.email_agent --setup
        print("Starting Gmail OAuth setup...")
        _get_gmail_service()
        print("Setup complete. token.json saved.")
    else:
        run()
