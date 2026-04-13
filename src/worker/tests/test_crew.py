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
        patch.object(
            crew_module, "build_cover_letter_writer", return_value=MagicMock()
        ),
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


def test_crew_has_five_tasks_in_normal_mode(tmp_path):
    """Non-dry-run crew must include exactly 5 tasks (including Cover Letter Writer)."""
    import worker.crew as crew_module
    from worker.models.search_criteria import SearchCriteria

    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text('{"First Name": "Tanner"}')

    tasks_passed = []

    def capture_crew(**kwargs):
        tasks_passed.extend(kwargs.get("tasks", []))
        instance = MagicMock()
        instance.kickoff.return_value = MagicMock(__str__=lambda self: "done")
        return instance

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
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
        criteria = SearchCriteria(
            job_title="Engineer",
            location="Remote",
            min_salary=100000,
            job_keywords=["Python"],
        )
        crew_module.run_crew(criteria)

    assert len(tasks_passed) == 5


def test_crew_dry_run_has_three_tasks_and_excludes_cover_letter_writer(tmp_path):
    """dry_run=True crew must have exactly 3 tasks (no CL writer, no Browser)."""
    import worker.crew as crew_module
    from worker.models.search_criteria import SearchCriteria

    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text('{"First Name": "Tanner"}')

    tasks_passed = []

    def capture_crew(**kwargs):
        tasks_passed.extend(kwargs.get("tasks", []))
        mock_task_eval = MagicMock()
        mock_task_eval.output.pydantic = MagicMock()
        instance = MagicMock()
        instance.kickoff.return_value = MagicMock()
        return instance

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
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
        criteria = SearchCriteria(
            job_title="Engineer",
            location="Remote",
            min_salary=100000,
            job_keywords=["Python"],
        )
        crew_module.run_crew(criteria, dry_run=True)

    assert len(tasks_passed) == 3


def test_failure_logger_called_when_inspect_step_fails(tmp_path):
    """FailureLogger.log must be called when task_inspect.output.pydantic has failed=True."""
    import worker.crew as crew_module
    from worker.models.inspected_job import InspectedJobs
    from worker.models.search_criteria import SearchCriteria

    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text('{"First Name": "Tanner"}')

    # Build a failed InspectedJobs pydantic output
    failed_inspect = InspectedJobs(
        jobs=[], failed=True, failed_reason="no fields found"
    )

    # Task mock whose .output.pydantic returns the failed inspect object
    mock_task_inspect = MagicMock()
    mock_task_inspect.output.pydantic = failed_inspect

    task_call_count = 0

    def make_task(*args, **kwargs):
        nonlocal task_call_count
        task_call_count += 1
        # Return mock_task_inspect for the second Task() call (inspect step)
        if task_call_count == 2:
            return mock_task_inspect
        return MagicMock()

    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
        patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
        patch.object(
            crew_module, "build_cover_letter_writer", return_value=MagicMock()
        ),
        patch.object(crew_module, "build_browser", return_value=MagicMock()),
        patch.object(crew_module, "Task", side_effect=make_task),
        patch.object(crew_module, "Crew", return_value=mock_crew_instance),
        patch.object(crew_module, "set_current_task_id"),
        patch.object(crew_module, "_failure_logger") as mock_failure_logger,
    ):
        mock_settings.personal_data_path = personal_file
        criteria = SearchCriteria(
            job_title="Engineer",
            location="Remote",
            min_salary=100000,
            job_keywords=["Python"],
        )
        crew_module.run_crew(criteria)

    mock_failure_logger.log.assert_called_once()
    call_args = mock_failure_logger.log.call_args[0][0]
    assert call_args.step == "field_inspector"
    assert call_args.failed is True
    assert call_args.failed_reason == "no fields found"
