"""Unit tests for the email monitoring agent.

All external I/O (Gmail API, LLM, Supabase, filesystem) is mocked.
"""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker.agents.email_agent import (
    _classify_email,
    _create_draft_reply,
    _get_email_body,
    _get_gmail_service,
    run,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encode(text: str) -> str:
    """Return a URL-safe base64 string as Gmail would provide."""
    return base64.urlsafe_b64encode(text.encode()).decode()


def _msg(body_text: str | None = None, parts: list | None = None) -> dict:
    """Build a minimal Gmail message dict."""
    payload: dict = {}
    if parts is not None:
        payload["parts"] = parts
    elif body_text is not None:
        payload["body"] = {"data": _encode(body_text)}
    return {"payload": payload}


def _interest_messages(n: int = 1) -> list[dict]:
    """Return a list of minimal Gmail message references."""
    return [{"id": f"msg-{i}"} for i in range(n)]


# ---------------------------------------------------------------------------
# _get_email_body
# ---------------------------------------------------------------------------


class TestGetEmailBody:
    def test_body_from_simple_payload(self):
        msg = _msg("Hello from recruiter")
        assert _get_email_body(msg) == "Hello from recruiter"

    def test_body_from_text_plain_part(self):
        parts = [
            {"mimeType": "text/html", "body": {"data": _encode("<b>HTML</b>")}},
            {"mimeType": "text/plain", "body": {"data": _encode("Plain text body")}},
        ]
        msg = _msg(parts=parts)
        assert _get_email_body(msg) == "Plain text body"

    def test_body_returns_empty_when_no_data(self):
        msg = {"payload": {}}
        assert _get_email_body(msg) == ""

    def test_body_returns_empty_when_no_text_plain_part(self):
        parts = [
            {"mimeType": "text/html", "body": {"data": _encode("<b>Only HTML</b>")}}
        ]
        msg = _msg(parts=parts)
        assert _get_email_body(msg) == ""


# ---------------------------------------------------------------------------
# _classify_email
# ---------------------------------------------------------------------------


class TestClassifyEmail:
    def _mock_llm(self, response_text: str) -> MagicMock:
        mock = MagicMock()
        mock.return_value.call.return_value = response_text
        return mock

    def test_classify_returns_interest(self):
        llm_response = (
            '{"sentiment": "interest", "summary": "Recruiter wants an interview"}'
        )
        with patch("worker.agents.email_agent.LLM") as mock_llm_cls:
            mock_llm_cls.return_value.call.return_value = llm_response
            sentiment, summary = _classify_email(
                "Interview Request", "We'd love to chat"
            )

        assert sentiment == "interest"
        assert "interview" in summary.lower() or len(summary) > 0

    def test_classify_returns_rejection(self):
        llm_response = '{"sentiment": "rejection", "summary": "Not moving forward"}'
        with patch("worker.agents.email_agent.LLM") as mock_llm_cls:
            mock_llm_cls.return_value.call.return_value = llm_response
            sentiment, summary = _classify_email(
                "Your application", "We regret to inform you"
            )

        assert sentiment == "rejection"

    def test_classify_falls_back_to_spam_on_bad_json(self):
        with patch("worker.agents.email_agent.LLM") as mock_llm_cls:
            mock_llm_cls.return_value.call.return_value = "not valid json at all"
            sentiment, summary = _classify_email("Subject", "Body")

        assert sentiment == "spam"
        assert summary == "Failed to classify"

    def test_classify_falls_back_to_spam_on_llm_exception(self):
        with patch("worker.agents.email_agent.LLM") as mock_llm_cls:
            mock_llm_cls.return_value.call.side_effect = RuntimeError("LLM unreachable")
            sentiment, summary = _classify_email("Subject", "Body")

        assert sentiment == "spam"
        assert summary == "Failed to classify"

    def test_classify_extracts_json_from_noisy_response(self):
        """LLM sometimes wraps JSON in prose — we parse the first {...} block."""
        noisy = 'Sure! Here is the result:\n{"sentiment": "spam", "summary": "Ad email"}\nDone.'
        with patch("worker.agents.email_agent.LLM") as mock_llm_cls:
            mock_llm_cls.return_value.call.return_value = noisy
            sentiment, summary = _classify_email("Ad", "Buy now!")

        assert sentiment == "spam"


# ---------------------------------------------------------------------------
# _create_draft_reply
# ---------------------------------------------------------------------------


class TestCreateDraftReply:
    def _mock_service(self, draft_id: str = "draft-abc") -> MagicMock:
        service = MagicMock()
        service.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
            "id": draft_id
        }
        return service

    def test_create_draft_returns_gmail_url(self):
        service = self._mock_service("draft-xyz")
        url = _create_draft_reply(
            service, "thread-1", "recruiter@example.com", "Job Offer"
        )

        assert url is not None
        assert url.startswith("https://mail.google.com")
        assert "draft-xyz" in url

    def test_create_draft_returns_none_on_http_error(self):
        from googleapiclient.errors import HttpError

        service = MagicMock()
        service.users.return_value.drafts.return_value.create.return_value.execute.side_effect = HttpError(
            MagicMock(status=403), b"Forbidden"
        )
        result = _create_draft_reply(
            service, "thread-1", "recruiter@example.com", "Job Offer"
        )

        assert result is None

    def test_create_draft_calls_correct_user(self):
        service = self._mock_service()
        _create_draft_reply(service, "t-1", "test@test.com", "Subject")

        service.users.return_value.drafts.return_value.create.assert_called_once()
        call_kwargs = service.users.return_value.drafts.return_value.create.call_args[1]
        assert call_kwargs["userId"] == "me"


# ---------------------------------------------------------------------------
# _get_gmail_service
# ---------------------------------------------------------------------------


class TestGetGmailService:
    def test_uses_cached_token_when_valid(self, tmp_path: Path):
        """When a valid token exists, it is loaded and used directly."""
        token_path = tmp_path / "token.json"
        token_path.touch()  # must exist so the exists() check passes

        creds = MagicMock()
        creds.valid = True

        with (
            patch("worker.agents.email_agent.settings") as mock_settings,
            patch("worker.agents.email_agent.pickle.load", return_value=creds),
            patch("builtins.open"),
            patch("worker.agents.email_agent.build") as mock_build,
        ):
            mock_settings.gmail_token_path = token_path
            mock_settings.gmail_credentials_path = tmp_path / "credentials.json"
            _get_gmail_service()

        mock_build.assert_called_once_with("gmail", "v1", credentials=creds)

    def test_refreshes_expired_token(self, tmp_path: Path):
        """When the token is expired with a refresh_token, it is refreshed."""
        token_path = tmp_path / "token.json"
        token_path.touch()

        creds = MagicMock()
        creds.valid = False
        creds.expired = True
        creds.refresh_token = "refresh-token"

        with (
            patch("worker.agents.email_agent.settings") as mock_settings,
            patch("worker.agents.email_agent.pickle.load", return_value=creds),
            patch("worker.agents.email_agent.pickle.dump"),
            patch("builtins.open"),
            patch("worker.agents.email_agent.Request"),
            patch("worker.agents.email_agent.build"),
        ):
            mock_settings.gmail_token_path = token_path
            mock_settings.gmail_credentials_path = tmp_path / "credentials.json"
            _get_gmail_service()

        creds.refresh.assert_called_once()

    def test_raises_when_credentials_missing(self, tmp_path: Path):
        with (
            patch("worker.agents.email_agent.settings") as mock_settings,
        ):
            mock_settings.gmail_token_path = tmp_path / "token.json"  # does not exist
            mock_settings.gmail_credentials_path = (
                tmp_path / "credentials.json"
            )  # does not exist

            with pytest.raises(FileNotFoundError, match="credentials.json"):
                _get_gmail_service()


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


class TestRun:
    def _make_service(self, messages: list[dict]) -> MagicMock:
        """Build a minimal Gmail service mock returning the given message list."""
        service = MagicMock()
        list_result = {"messages": [{"id": m["id"]} for m in messages]}
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = list_result

        def get_message(userId, id, format):  # noqa: A002
            return MagicMock(execute=lambda: next(m for m in messages if m["id"] == id))

        service.users.return_value.messages.return_value.get.side_effect = get_message
        return service

    def _make_msg(
        self, msg_id: str, subject: str = "Test", sender: str = "a@b.com"
    ) -> dict:
        headers = [
            {"name": "Subject", "value": subject},
            {"name": "From", "value": sender},
            {"name": "Date", "value": "2024-01-01T00:00:00+00:00"},
        ]
        return {
            "id": msg_id,
            "threadId": f"thread-{msg_id}",
            "payload": {
                "headers": headers,
                "body": {"data": _encode("body text")},
            },
        }

    def test_run_skips_on_missing_credentials(self):
        with (
            patch(
                "worker.agents.email_agent._get_gmail_service",
                side_effect=FileNotFoundError("no credentials"),
            ),
            patch("worker.agents.email_agent.insert_email_log") as mock_insert,
        ):
            run()

        mock_insert.assert_not_called()

    def test_run_inserts_log_for_each_message(self):
        msgs = [self._make_msg("m1"), self._make_msg("m2")]
        service = self._make_service(msgs)

        with (
            patch("worker.agents.email_agent._get_gmail_service", return_value=service),
            patch(
                "worker.agents.email_agent._classify_email",
                return_value=("rejection", "Not moving forward"),
            ),
            patch("worker.agents.email_agent.insert_email_log") as mock_insert,
        ):
            run()

        assert mock_insert.call_count == 2

    def test_run_creates_draft_only_for_interest(self):
        msgs = [self._make_msg("m1"), self._make_msg("m2")]
        service = self._make_service(msgs)

        classifications = [
            ("interest", "They want to interview"),
            ("rejection", "Not selected"),
        ]

        with (
            patch("worker.agents.email_agent._get_gmail_service", return_value=service),
            patch(
                "worker.agents.email_agent._classify_email",
                side_effect=classifications,
            ),
            patch(
                "worker.agents.email_agent._create_draft_reply",
                return_value="https://mail.google.com/draft-1",
            ) as mock_draft,
            patch("worker.agents.email_agent.insert_email_log"),
        ):
            run()

        assert mock_draft.call_count == 1

    def test_run_handles_gmail_fetch_error_gracefully(self):
        from googleapiclient.errors import HttpError

        service = MagicMock()
        service.users.return_value.messages.return_value.list.return_value.execute.side_effect = HttpError(
            MagicMock(status=500), b"Server Error"
        )

        with (
            patch("worker.agents.email_agent._get_gmail_service", return_value=service),
            patch("worker.agents.email_agent.insert_email_log") as mock_insert,
        ):
            run()

        mock_insert.assert_not_called()
