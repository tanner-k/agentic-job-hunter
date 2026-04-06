"""Tests for the browser stealth helpers."""

from unittest.mock import MagicMock

from worker.tools.stealth import get_context_options, get_launch_args, random_delay


def test_get_launch_args_includes_automation_flag():
    args = get_launch_args()
    assert "--disable-blink-features=AutomationControlled" in args


def test_get_launch_args_returns_list_of_strings():
    args = get_launch_args()
    assert isinstance(args, list)
    assert all(isinstance(a, str) for a in args)


def test_get_context_options_has_required_keys():
    opts = get_context_options()
    assert "viewport" in opts
    assert "user_agent" in opts
    assert "locale" in opts
    assert "timezone_id" in opts


def test_get_context_options_viewport_has_width_and_height():
    opts = get_context_options()
    assert "width" in opts["viewport"]
    assert "height" in opts["viewport"]


def test_random_delay_calls_page_wait_for_timeout():
    page = MagicMock()
    random_delay(page, min_ms=100, max_ms=200)
    page.wait_for_timeout.assert_called_once()
    called_with = page.wait_for_timeout.call_args[0][0]
    assert 100 <= called_with <= 200


def test_user_agent_rotates():
    """Calling get_context_options 20 times should yield at least 2 distinct user-agents."""
    agents = {get_context_options()["user_agent"] for _ in range(20)}
    assert len(agents) >= 2
