"""Integration-level tests for the CrewAI pipeline.

These tests wire run_crew() with mocked external boundaries (LLM, Playwright,
Supabase) but exercise the real orchestration logic: task construction, task
ordering, crew inputs, and the browser agent's tool guard.

Run with:
    uv run pytest -m integration -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from worker.models.search_criteria import SearchCriteria


@pytest.mark.integration
class TestRunCrewPipeline:
    """Full pipeline smoke tests — mocked LLM and tools, real orchestration."""

    def _criteria(self) -> SearchCriteria:
        return SearchCriteria(
            job_title="Software Engineer",
            location="Remote",
            min_salary=100_000,
            job_keywords=["Python"],
            company="",
            job_website="",
        )

    def _setup_crew_mock(self, tmp_path, kickoff_side_effect=None):
        """Return a (personal_file, crew_kwargs_capture) pair with patched crew module."""
        personal_data = {"First Name": "Tanner", "Email": "t@example.com"}
        personal_file = tmp_path / "personal_data.json"
        personal_file.write_text(json.dumps(personal_data))
        return personal_file

    def test_run_crew_returns_none_when_no_packets(self, tmp_path):
        """run_crew() returns None when Evaluator produces no packets."""
        import worker.crew as crew_module

        personal_file = self._setup_crew_mock(tmp_path)

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = MagicMock()

        with (
            patch.object(crew_module, "settings") as mock_settings,
            patch.object(crew_module, "build_searcher", return_value=MagicMock()),
            patch.object(
                crew_module, "build_field_inspector", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
            patch.object(
                crew_module, "build_cover_letter_writer", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_browser", return_value=MagicMock()),
            patch.object(crew_module, "Crew", return_value=mock_crew_instance),
            patch.object(crew_module, "set_current_task_id"),
        ):
            mock_settings.personal_data_path = personal_file

            # task_evaluate.output.pydantic returns None (no packets produced)
            tasks = []

            def capture_task(**kwargs):
                t = MagicMock()
                t.description = kwargs.get("description", "")
                t.output = MagicMock()
                t.output.pydantic = None
                tasks.append(t)
                return t

            with patch.object(crew_module, "Task", side_effect=capture_task):
                result = crew_module.run_crew(self._criteria(), task_id="test-1")

        assert result is None

    def test_run_crew_builds_five_tasks_in_correct_order(self, tmp_path):
        """Crew must receive exactly 5 tasks in search → inspect → evaluate → cover_letter → apply order."""
        import worker.crew as crew_module

        personal_file = self._setup_crew_mock(tmp_path)
        tasks_received = []

        def capture_crew(**kwargs):
            tasks_received.extend(kwargs.get("tasks", []))
            crew = MagicMock()
            crew.kickoff.return_value = MagicMock()
            return crew

        with (
            patch.object(crew_module, "settings") as mock_settings,
            patch.object(crew_module, "build_searcher", return_value=MagicMock()),
            patch.object(
                crew_module, "build_field_inspector", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
            patch.object(
                crew_module, "build_cover_letter_writer", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_browser", return_value=MagicMock()),
            patch.object(crew_module, "Task", return_value=MagicMock()),
            patch.object(crew_module, "Crew", side_effect=capture_crew),
            patch.object(crew_module, "set_current_task_id"),
        ):
            mock_settings.personal_data_path = personal_file
            crew_module.run_crew(self._criteria())

        assert len(tasks_received) == 5

    def test_task_apply_description_contains_do_not_search_guard(self, tmp_path):
        """Browser task description must contain the tool-guard instruction."""
        import worker.crew as crew_module

        personal_file = self._setup_crew_mock(tmp_path)
        captured_descriptions = []

        def capture_task(**kwargs):
            captured_descriptions.append(kwargs.get("description", ""))
            t = MagicMock()
            t.description = kwargs.get("description", "")
            t.output = MagicMock()
            t.output.pydantic = None
            return t

        with (
            patch.object(crew_module, "settings") as mock_settings,
            patch.object(crew_module, "build_searcher", return_value=MagicMock()),
            patch.object(
                crew_module, "build_field_inspector", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
            patch.object(
                crew_module, "build_cover_letter_writer", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_browser", return_value=MagicMock()),
            patch.object(crew_module, "Task", side_effect=capture_task),
            patch.object(
                crew_module, "Crew", return_value=MagicMock(kickoff=MagicMock())
            ),
            patch.object(crew_module, "set_current_task_id"),
        ):
            mock_settings.personal_data_path = personal_file
            crew_module.run_crew(self._criteria())

        # Last task description is the Browser task
        apply_description = captured_descriptions[-1]
        assert "Do NOT search the web" in apply_description

    def test_excluded_companies_appear_in_searcher_inputs(self, tmp_path):
        """Excluded company names must be forwarded into crew inputs."""
        import worker.crew as crew_module

        personal_file = self._setup_crew_mock(tmp_path)
        captured_inputs: dict = {}

        def fake_kickoff(inputs):
            captured_inputs.update(inputs)

        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = fake_kickoff

        with (
            patch.object(crew_module, "settings") as mock_settings,
            patch.object(crew_module, "build_searcher", return_value=MagicMock()),
            patch.object(
                crew_module, "build_field_inspector", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
            patch.object(
                crew_module, "build_cover_letter_writer", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_browser", return_value=MagicMock()),
            patch.object(crew_module, "Task", return_value=MagicMock()),
            patch.object(crew_module, "Crew", return_value=mock_crew),
            patch.object(crew_module, "set_current_task_id"),
        ):
            mock_settings.personal_data_path = personal_file
            crew_module.run_crew(
                self._criteria(), excluded_companies=["Acme Corp", "Globex"]
            )

        assert "Acme Corp" in captured_inputs.get("excluded_companies", "")
        assert "Globex" in captured_inputs.get("excluded_companies", "")

    def test_task_id_is_set_and_cleared_around_kickoff(self, tmp_path):
        """set_current_task_id must be called with task_id before kickoff and None after."""
        import worker.crew as crew_module

        personal_file = self._setup_crew_mock(tmp_path)
        calls = []

        with (
            patch.object(crew_module, "settings") as mock_settings,
            patch.object(crew_module, "build_searcher", return_value=MagicMock()),
            patch.object(
                crew_module, "build_field_inspector", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
            patch.object(
                crew_module, "build_cover_letter_writer", return_value=MagicMock()
            ),
            patch.object(crew_module, "build_browser", return_value=MagicMock()),
            patch.object(crew_module, "Task", return_value=MagicMock()),
            patch.object(
                crew_module,
                "Crew",
                return_value=MagicMock(kickoff=MagicMock()),
            ),
            patch.object(
                crew_module,
                "set_current_task_id",
                side_effect=lambda v: calls.append(v),
            ),
        ):
            mock_settings.personal_data_path = personal_file
            crew_module.run_crew(self._criteria(), task_id="abc-123")

        assert calls[0] == "abc-123"
        assert calls[-1] is None


@pytest.mark.integration
class TestBrowserAgentToolGuard:
    """Verify the browser agent is constructed with only the browser_tool."""

    def _capture_agent_kwargs(self) -> dict:
        """Call build_browser() with Agent mocked and return the kwargs passed to it."""
        import worker.agents.browser as browser_module

        captured: dict = {}

        def capture_agent(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with (
            patch.object(browser_module, "build_llm", return_value=MagicMock()),
            patch.object(browser_module, "Agent", side_effect=capture_agent),
        ):
            browser_module.build_browser()

        return captured

    def test_browser_agent_has_exactly_one_tool(self):
        """build_browser() must pass exactly one tool to Agent."""
        kwargs = self._capture_agent_kwargs()
        assert len(kwargs["tools"]) == 1

    def test_browser_agent_tool_is_browser_form_fitter(self):
        """The single tool must be the Browser Form Fitter (not a search tool)."""
        kwargs = self._capture_agent_kwargs()
        assert kwargs["tools"][0].name == "Browser Form Fitter"

    def test_browser_agent_does_not_allow_delegation(self):
        """allow_delegation must be False to prevent the agent spawning sub-agents."""
        kwargs = self._capture_agent_kwargs()
        assert kwargs["allow_delegation"] is False
