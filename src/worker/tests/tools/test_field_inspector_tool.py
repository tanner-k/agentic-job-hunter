import json
from unittest.mock import MagicMock, patch


def _make_page(labels=None, inputs=None, textareas=None, selects=None, file_inputs=0):
    """Build a minimal mock Playwright Page object."""
    page = MagicMock()

    def mock_locator(selector):
        loc = MagicMock()
        if (
            "label" in selector
            and "input" not in selector
            and "textarea" not in selector
            and "select" not in selector
        ):
            items = [_mock_element(text=t) for t in (labels or [])]
            loc.all.return_value = items
        elif "input[type=file]" in selector:
            loc.count.return_value = file_inputs
        elif selector.startswith("input"):
            items = [_mock_element(attrs=a) for a in (inputs or [])]
            loc.all.return_value = items
        elif selector.startswith("textarea"):
            items = [_mock_element(attrs=a) for a in (textareas or [])]
            loc.all.return_value = items
        elif selector.startswith("select"):
            items = [_mock_element(attrs=a) for a in (selects or [])]
            loc.all.return_value = items
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = mock_locator
    return page


def _mock_element(text=None, attrs=None):
    el = MagicMock()
    el.inner_text.return_value = text or ""
    attrs = attrs or {}
    el.get_attribute.side_effect = lambda a: attrs.get(a, "")
    return el


def test_extracts_label_text():
    from worker.tools.field_inspector_tool import _extract_fields

    page = _make_page(labels=["First Name", "Email Address"])
    fields = _extract_fields(page)
    assert "First Name" in fields
    assert "Email Address" in fields


def test_strips_trailing_colon_and_asterisk():
    from worker.tools.field_inspector_tool import _extract_fields

    page = _make_page(labels=["First Name*", "Email:"])
    fields = _extract_fields(page)
    assert "First Name" in fields
    assert "Email" in fields


def test_deduplicates_fields():
    from worker.tools.field_inspector_tool import _extract_fields

    page = _make_page(labels=["Email", "Email"])
    fields = _extract_fields(page)
    assert fields.count("Email") == 1


def test_extracts_input_placeholder():
    from worker.tools.field_inspector_tool import _extract_fields

    page = _make_page(inputs=[{"placeholder": "Your phone number"}])
    fields = _extract_fields(page)
    assert "Your phone number" in fields


def test_skips_empty_labels():
    from worker.tools.field_inspector_tool import _extract_fields

    page = _make_page(labels=["", "  ", "Valid Field"])
    fields = _extract_fields(page)
    assert "" not in fields
    assert "  " not in fields
    assert "Valid Field" in fields


def test_tool_returns_json_with_form_fields():
    from worker.tools.field_inspector_tool import field_inspector_tool

    mock_page = _make_page(labels=["First Name", "Email"], file_inputs=1)

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert "First Name" in data["form_fields"]
    assert "Email" in data["form_fields"]
    assert data["requires_resume"] is True
    assert data["url"] == "https://example.com"


def test_tool_returns_empty_on_playwright_error():
    from worker.tools.field_inspector_tool import field_inspector_tool

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_pw.return_value.__enter__.side_effect = Exception("browser crashed")
        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert data["form_fields"] == []
    assert data["requires_resume"] is False
    assert "error" in data


def test_get_input_label_via_label_for():
    """Returns label text when <label for="id"> matches the element's id."""
    from unittest.mock import MagicMock

    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    element.get_attribute.side_effect = lambda attr: (
        "email-field" if attr == "id" else None
    )
    label_loc = MagicMock()
    label_loc.inner_text.return_value = "Email Address"
    page.locator.return_value = label_loc

    result = _get_input_label(page, element)
    assert result == "Email Address"
    page.locator.assert_called_with('label[for="email-field"]')


def test_get_input_label_via_wrapping_label():
    """Falls back to wrapping ancestor label when label-for lookup fails."""
    from unittest.mock import MagicMock

    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    element.get_attribute.return_value = None
    page.locator.side_effect = Exception("no label[for]")
    ancestor = MagicMock()
    ancestor.inner_text.return_value = "Upload Cover Letter"
    element.locator.return_value = ancestor

    result = _get_input_label(page, element)
    assert result == "Upload Cover Letter"
    element.locator.assert_called_with("xpath=ancestor::label[1]")


def test_get_input_label_via_aria_label():
    """Falls back to aria-label attribute."""
    from unittest.mock import MagicMock

    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    page.locator.side_effect = Exception("no label[for]")
    ancestor = MagicMock()
    ancestor.inner_text.side_effect = Exception("no ancestor")
    element.locator.return_value = ancestor
    element.get_attribute.side_effect = lambda attr: (
        "Cover Letter File" if attr == "aria-label" else None
    )

    result = _get_input_label(page, element)
    assert result == "Cover Letter File"


def test_get_input_label_via_name():
    """Falls back to name attribute when aria-label is absent."""
    from unittest.mock import MagicMock

    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    page.locator.side_effect = Exception("no label[for]")
    ancestor = MagicMock()
    ancestor.inner_text.side_effect = Exception("no ancestor")
    element.locator.return_value = ancestor
    element.get_attribute.side_effect = lambda attr: (
        "cover_letter_upload" if attr == "name" else None
    )

    result = _get_input_label(page, element)
    assert result == "cover_letter_upload"


def test_get_input_label_returns_empty_when_nothing_found():
    """Returns empty string when no label source is available."""
    from unittest.mock import MagicMock

    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    page.locator.side_effect = Exception("no label[for]")
    element.locator.side_effect = Exception("no ancestor")
    element.get_attribute.return_value = None

    result = _get_input_label(page, element)
    assert result == ""


def test_tool_falls_back_to_domcontentloaded_on_networkidle_timeout():
    from worker.tools.field_inspector_tool import field_inspector_tool

    mock_page = _make_page(labels=["Email"], file_inputs=0)

    call_count = 0

    def goto_side_effect(url, wait_until, timeout):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("networkidle timeout")
        # second call succeeds silently

    mock_page.goto = goto_side_effect

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert call_count == 2
    assert "Email" in data["form_fields"]
