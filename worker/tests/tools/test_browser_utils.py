from unittest.mock import MagicMock


def _no_match() -> MagicMock:
    loc = MagicMock()
    loc.count.return_value = 0
    return loc


def test_navigates_to_href_when_apply_link_found():
    """Navigates to the Apply link href directly when an anchor with href is matched."""
    from worker.tools.browser_utils import click_through_to_form

    page = MagicMock()
    page.url = "https://remoterocketship.com/jobs/123"

    apply_link = MagicMock()
    apply_link.count.return_value = 1
    apply_link.first.get_attribute.return_value = (
        "https://boards.greenhouse.io/company/jobs/456"
    )

    def locator_side_effect(selector: str) -> MagicMock:
        if "Apply for this job online" in selector:
            return apply_link
        return _no_match()

    page.locator.side_effect = locator_side_effect
    click_through_to_form(page)

    page.goto.assert_called_once_with(
        "https://boards.greenhouse.io/company/jobs/456",
        wait_until="networkidle",
        timeout=30_000,
    )


def test_resolves_relative_href():
    """Resolves a relative href against the current page URL."""
    from worker.tools.browser_utils import click_through_to_form

    page = MagicMock()
    page.url = "https://example.com/jobs/123"

    apply_link = MagicMock()
    apply_link.count.return_value = 1
    apply_link.first.get_attribute.return_value = "/apply/456"

    def locator_side_effect(selector: str) -> MagicMock:
        if "Apply for this job online" in selector:
            return apply_link
        return _no_match()

    page.locator.side_effect = locator_side_effect
    click_through_to_form(page)

    page.goto.assert_called_once_with(
        "https://example.com/apply/456",
        wait_until="networkidle",
        timeout=30_000,
    )


def test_clicks_button_and_waits_when_no_href():
    """Clicks the element and waits for networkidle when no href attribute."""
    from worker.tools.browser_utils import click_through_to_form

    page = MagicMock()
    page.url = "https://example.com/jobs/123"

    apply_button = MagicMock()
    apply_button.count.return_value = 1
    apply_button.first.get_attribute.return_value = None  # no href

    def locator_side_effect(selector: str) -> MagicMock:
        if "Apply for this job online" in selector:
            return apply_button
        return _no_match()

    page.locator.side_effect = locator_side_effect
    click_through_to_form(page)

    apply_button.first.click.assert_called_once()
    page.wait_for_load_state.assert_called_once_with("networkidle", timeout=15_000)


def test_falls_back_to_wait_on_click_navigation_error():
    """Falls back to wait_for_timeout when wait_for_load_state raises."""
    from worker.tools.browser_utils import click_through_to_form

    page = MagicMock()
    page.url = "https://example.com/jobs/123"
    page.wait_for_load_state.side_effect = Exception("timeout")

    apply_button = MagicMock()
    apply_button.count.return_value = 1
    apply_button.first.get_attribute.return_value = None

    def locator_side_effect(selector: str) -> MagicMock:
        if "Apply for this job online" in selector:
            return apply_button
        return _no_match()

    page.locator.side_effect = locator_side_effect
    click_through_to_form(page)  # must not raise

    page.wait_for_timeout.assert_called_once_with(3000)


def test_does_nothing_when_no_apply_button():
    """No navigation when the page has no Apply button (already on the form)."""
    from worker.tools.browser_utils import click_through_to_form

    page = MagicMock()
    page.locator.return_value = _no_match()

    click_through_to_form(page)

    page.goto.assert_not_called()
    page.wait_for_load_state.assert_not_called()


def test_stops_after_first_matching_selector():
    """Clicks through only once even when multiple selectors would match."""
    from worker.tools.browser_utils import click_through_to_form

    page = MagicMock()
    page.url = "https://example.com"

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        loc.count.return_value = 1
        loc.first.get_attribute.return_value = f"https://example.com/{selector}"
        return loc

    page.locator.side_effect = locator_side_effect
    click_through_to_form(page)

    assert page.goto.call_count == 1
