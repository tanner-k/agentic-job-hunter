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


def _make_labeled_element(aria_label: str) -> MagicMock:
    """Mock Locator whose aria-label attribute returns the given string."""
    el = MagicMock()
    el.get_attribute.side_effect = lambda attr: (
        aria_label if attr == "aria-label" else None
    )
    el.locator.side_effect = Exception("no ancestor")
    return el


def _make_page_with_cl_textarea(submit_count: int = 1) -> tuple[MagicMock, MagicMock]:
    """Page with a cover-letter-labeled textarea. Returns (page, textarea_mock)."""
    page = MagicMock()
    cl_textarea = _make_labeled_element("Cover Letter")

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector.lower() or "apply" in selector.lower():
            loc.count.return_value = submit_count
        elif "textarea" in selector:
            loc.all.return_value = [cl_textarea]
        elif "input[type='file']" in selector or "input[type=file]" in selector:
            loc.all.return_value = []
            loc.count.return_value = 0
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value = MagicMock()
    page.get_by_text.return_value.locator.return_value = MagicMock()
    return page, cl_textarea


def _make_page_with_cl_file_input(
    submit_count: int = 1,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Page with a resume file input and a cover-letter file input."""
    page = MagicMock()
    resume_fi = _make_labeled_element("Resume")
    cl_fi = _make_labeled_element("Cover Letter")

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector.lower() or "apply" in selector.lower():
            loc.count.return_value = submit_count
        elif "textarea" in selector:
            loc.all.return_value = []
        elif "input[type='file']" in selector or "input[type=file]" in selector:
            loc.all.return_value = [resume_fi, cl_fi]
            loc.count.return_value = 2
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value = MagicMock()
    page.get_by_text.return_value.locator.return_value = MagicMock()
    return page, resume_fi, cl_fi


def test_browser_uploads_resume_to_non_cl_file_input_only(tmp_path):
    """Resume is uploaded to the non-cover-letter file input, not the CL one."""
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"dummy")

    page, resume_fi, cl_fi = _make_page_with_cl_file_input()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = resume_file
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work

        _browser_work("https://example.com", "{}", requires_resume=True)

    resume_fi.set_input_files.assert_called_once_with(str(resume_file))
    cl_fi.set_input_files.assert_not_called()


def test_browser_pastes_cover_letter_text_into_textarea(tmp_path):
    """cover_letter_text is pasted into a cover-letter-labeled textarea."""
    page, cl_textarea = _make_page_with_cl_textarea()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = tmp_path / "resume.pdf"
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work

        _browser_work(
            "https://example.com",
            "{}",
            requires_resume=False,
            cover_letter_text="Dear Hiring Manager,\n\nI am excited...",
        )

    cl_textarea.fill.assert_called_once_with("Dear Hiring Manager,\n\nI am excited...")


def test_browser_uploads_cl_file_when_path_set(tmp_path):
    """cover_letter_path is uploaded when a CL file input is present."""
    cl_pdf = tmp_path / "cover_letter.pdf"
    cl_pdf.write_bytes(b"pdf content")

    page, resume_fi, cl_fi = _make_page_with_cl_file_input()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = tmp_path / "resume.pdf"
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work

        _browser_work(
            "https://example.com",
            "{}",
            requires_resume=False,
            cover_letter_path=str(cl_pdf),
        )

    cl_fi.set_input_files.assert_called_once_with(str(cl_pdf))


def test_browser_skips_cl_file_when_path_is_none_and_no_textarea(tmp_path):
    """No action on CL file input when cover_letter_path is None and no text area."""
    page, resume_fi, cl_fi = _make_page_with_cl_file_input()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = tmp_path / "resume.pdf"
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work

        _browser_work(
            "https://example.com",
            "{}",
            requires_resume=False,
            cover_letter_path=None,
            cover_letter_text=None,
        )

    cl_fi.set_input_files.assert_not_called()


def test_browser_uses_file_upload_not_textarea_when_path_set(tmp_path):
    """When both CL file input and textarea exist and path is set, file upload wins."""
    cl_pdf = tmp_path / "cl.pdf"
    cl_pdf.write_bytes(b"pdf")

    page = MagicMock()
    cl_fi = _make_labeled_element("Cover Letter")
    cl_textarea = _make_labeled_element("Cover Letter")

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector.lower() or "apply" in selector.lower():
            loc.count.return_value = 1
        elif "textarea" in selector:
            loc.all.return_value = [cl_textarea]
        elif "input[type='file']" in selector or "input[type=file]" in selector:
            loc.all.return_value = [cl_fi]
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value = MagicMock()
    page.get_by_text.return_value.locator.return_value = MagicMock()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = tmp_path / "resume.pdf"
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work

        _browser_work(
            "https://example.com",
            "{}",
            requires_resume=False,
            cover_letter_path=str(cl_pdf),
            cover_letter_text="Dear Hiring Manager...",
        )

    cl_fi.set_input_files.assert_called_once_with(str(cl_pdf))
    cl_textarea.fill.assert_not_called()
