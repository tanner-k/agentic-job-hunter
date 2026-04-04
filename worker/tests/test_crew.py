import json
from unittest.mock import MagicMock, patch


def test_run_crew_injects_personal_data_into_inputs(tmp_path):
    """personal_data.json contents must appear in the crew inputs dict."""
    import worker.crew as crew_module
    from worker.models.search_criteria import SearchCriteria

    personal_data = {"First Name": "Tanner", "Email": "t@example.com"}
    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text(json.dumps(personal_data))

    captured_inputs = {}

    def fake_kickoff(inputs):
        captured_inputs.update(inputs)
        return MagicMock(__str__=lambda self: "done")

    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.side_effect = fake_kickoff

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
        patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
        patch.object(crew_module, "build_browser", return_value=MagicMock()),
        patch.object(crew_module, "Task", return_value=MagicMock()),
        patch.object(crew_module, "Crew", return_value=mock_crew_instance),
        patch.object(crew_module, "set_current_task_id"),
    ):
        mock_settings.personal_data_path = personal_file
        criteria = SearchCriteria(
            job_title="Engineer",
            location="Remote",
            min_salary=100000,
            job_keywords=["Python"],
            company="",
            job_website="",
        )
        crew_module.run_crew(criteria, task_id="test-123")

    assert "personal_data" in captured_inputs
    loaded = json.loads(captured_inputs["personal_data"])
    assert loaded["First Name"] == "Tanner"


def test_crew_has_four_tasks(tmp_path):
    """Crew must be built with exactly 4 tasks."""
    import worker.crew as crew_module
    from worker.models.search_criteria import SearchCriteria

    personal_data = {"First Name": "Tanner"}
    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text(json.dumps(personal_data))

    tasks_passed = []

    def capture_crew(**kwargs):
        tasks_passed.extend(kwargs.get("tasks", []))
        crew = MagicMock()
        crew.kickoff.return_value = MagicMock(__str__=lambda self: "done")
        return crew

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
        patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
        patch.object(crew_module, "build_browser", return_value=MagicMock()),
        patch.object(crew_module, "Task", return_value=MagicMock()),
        patch.object(crew_module, "Crew", side_effect=capture_crew),
        patch.object(crew_module, "set_current_task_id"),
    ):
        mock_settings.personal_data_path = personal_file
        criteria = SearchCriteria(
            job_title="Engineer",
            location="Remote",
            min_salary=100000,
            job_keywords=["Python"],
            company="",
            job_website="",
        )
        crew_module.run_crew(criteria)

    assert len(tasks_passed) == 4
