from unittest.mock import MagicMock, patch


def _make_page(submit_count: int = 1) -> MagicMock:
    """Return a minimal mock Playwright page that finds a submit button."""
    page = MagicMock()

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector.lower() or "apply" in selector.lower():
            loc.count.return_value = submit_count
        else:
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value = MagicMock()
    page.get_by_text.return_value.locator.return_value = MagicMock()
    return page


def _patch_playwright(page: MagicMock) -> MagicMock:
    """Return a mock for sync_playwright that yields the given page."""
    mock_pw = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = page
    mock_browser.new_context.return_value = mock_context
    mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = (
        mock_browser
    )
    return mock_pw


def _call(url="https://example.com", instructions="{}", resume=False):
    """Call _browser_work directly (the inner Playwright function)."""
    from worker.tools.browser_tool import _browser_work

    return _browser_work(url, instructions, resume)


def test_browser_work_submits_successfully():
    """When a submit button exists, _browser_work returns a success message."""
    page = _make_page(submit_count=1)
    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
    ):
        result = _call()

    assert "Successfully submitted" in result


def test_browser_work_no_submit_button():
    """When no submit button exists, _browser_work reports failure."""
    page = _make_page(submit_count=0)
    page.screenshot = MagicMock()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
    ):
        result = _call()

    assert "Could not find Submit button" in result


def test_browser_work_falls_back_to_domcontentloaded():
    """When networkidle times out, _browser_work retries with domcontentloaded."""
    page = _make_page(submit_count=1)
    call_count = 0

    def goto_side_effect(url, wait_until, timeout):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("networkidle timeout")

    page.goto = goto_side_effect

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
    ):
        result = _call()

    assert call_count == 2
    assert "Successfully submitted" in result


def test_browser_work_invalid_json_instructions():
    """When json_instructions is not valid JSON, returns an error message immediately."""
    from worker.tools.browser_tool import _browser_work

    result = _browser_work("https://example.com", "not-json", False)

    assert "Error" in result
    assert "json_instructions" in result
