"""Tests for immutable dataclass models."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from worker.models.application_result import ApplicationResult
from worker.models.job import Job
from worker.models.search_criteria import SearchCriteria


class TestSearchCriteria:
    def test_is_frozen(self) -> None:
        criteria = SearchCriteria(job_title="Engineer", location="Remote")
        with pytest.raises(FrozenInstanceError):
            criteria.job_title = "Manager"  # type: ignore[misc]

    def test_from_dict_parses_keywords_from_comma_string(self) -> None:
        data = {
            "job_title": "Software Engineer",
            "location": "Remote",
            "keywords": "python, crewai, async",
        }
        criteria = SearchCriteria.from_dict(data)
        assert criteria.job_keywords == ["python", "crewai", "async"]

    def test_from_dict_parses_keywords_from_list(self) -> None:
        data = {
            "job_title": "Data Scientist",
            "location": "New York",
            "job_keywords": ["python", "ml", "pytorch"],
        }
        criteria = SearchCriteria.from_dict(data)
        assert criteria.job_keywords == ["python", "ml", "pytorch"]

    def test_from_dict_defaults_min_salary_to_zero_when_missing(self) -> None:
        data = {"job_title": "Backend Developer", "location": "Austin"}
        criteria = SearchCriteria.from_dict(data)
        assert criteria.min_salary == 0

    def test_from_dict_defaults_min_salary_to_zero_when_empty_string(self) -> None:
        data = {"job_title": "Backend Developer", "location": "Austin", "min_salary": ""}
        criteria = SearchCriteria.from_dict(data)
        assert criteria.min_salary == 0

    def test_from_dict_parses_min_salary(self) -> None:
        data = {"job_title": "Staff Engineer", "location": "SF", "min_salary": "150000"}
        criteria = SearchCriteria.from_dict(data)
        assert criteria.min_salary == 150000

    def test_from_dict_defaults_optional_fields(self) -> None:
        data = {"job_title": "Engineer", "location": "Remote"}
        criteria = SearchCriteria.from_dict(data)
        assert criteria.company == ""
        assert criteria.job_website == ""
        assert criteria.job_keywords == []


class TestJob:
    def test_is_frozen(self) -> None:
        job = Job(url="https://example.com/job/1", company="Acme", title="Engineer")
        with pytest.raises(FrozenInstanceError):
            job.title = "Manager"  # type: ignore[misc]

    def test_defaults(self) -> None:
        job = Job(url="https://example.com/job/1", company="Acme", title="Engineer")
        assert job.snippet == ""
        assert job.match_score == 0.0
        assert job.form_fields == {}
        assert job.requires_resume is False

    def test_full_construction(self) -> None:
        job = Job(
            url="https://example.com/job/2",
            company="Globex",
            title="Senior Engineer",
            snippet="Great role",
            match_score=0.85,
            form_fields={"name": "text"},
            requires_resume=True,
        )
        assert job.match_score == 0.85
        assert job.requires_resume is True
        assert job.form_fields == {"name": "text"}


class TestApplicationResult:
    def test_auto_sets_applied_at_when_none(self) -> None:
        before = datetime.now(tz=timezone.utc)
        result = ApplicationResult(
            job_url="https://example.com/job/1",
            company="Acme",
            job_title="Engineer",
            status="applied",
        )
        after = datetime.now(tz=timezone.utc)
        assert result.applied_at is not None
        assert before <= result.applied_at <= after

    def test_preserves_explicit_applied_at(self) -> None:
        ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = ApplicationResult(
            job_url="https://example.com/job/1",
            company="Acme",
            job_title="Engineer",
            status="applied",
            applied_at=ts,
        )
        assert result.applied_at == ts

    def test_is_frozen(self) -> None:
        result = ApplicationResult(
            job_url="https://example.com/job/1",
            company="Acme",
            job_title="Engineer",
            status="applied",
        )
        with pytest.raises(FrozenInstanceError):
            result.status = "failed"  # type: ignore[misc]

    def test_optional_fields_default_to_none(self) -> None:
        result = ApplicationResult(
            job_url="https://example.com/job/1",
            company="Acme",
            job_title="Engineer",
            status="skipped",
        )
        assert result.search_task_id is None
        assert result.error_message is None
        assert result.requires_resume is False
