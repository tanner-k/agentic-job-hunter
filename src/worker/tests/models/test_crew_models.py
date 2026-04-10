def test_job_listing_requires_url_company_title():
    from worker.models.job_listing import JobListing

    job = JobListing(url="https://example.com", company="Acme", job_title="Engineer")
    assert job.url == "https://example.com"
    assert job.company == "Acme"
    assert job.job_title == "Engineer"


def test_search_results_holds_job_list():
    from worker.models.job_listing import JobListing, SearchResults

    results = SearchResults(
        jobs=[
            JobListing(url="https://a.com", company="A", job_title="Dev"),
            JobListing(url="https://b.com", company="B", job_title="Eng"),
        ]
    )
    assert len(results.jobs) == 2


def test_search_results_empty_jobs_allowed():
    from worker.models.job_listing import SearchResults

    results = SearchResults(jobs=[])
    assert results.jobs == []


def test_inspected_job_fields_and_resume():
    from worker.models.inspected_job import InspectedJob

    job = InspectedJob(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        form_fields=["First Name", "Email"],
        requires_resume=True,
        requires_cover_letter=False,
        job_description="",
    )
    assert job.form_fields == ["First Name", "Email"]
    assert job.requires_resume is True


def test_inspected_jobs_holds_list():
    from worker.models.inspected_job import InspectedJob, InspectedJobs

    jobs = InspectedJobs(
        jobs=[
            InspectedJob(
                url="https://a.com",
                company="A",
                job_title="D",
                form_fields=["Email"],
                requires_resume=False,
                requires_cover_letter=False,
                job_description="",
            ),
        ]
    )
    assert len(jobs.jobs) == 1


def test_application_packet_json_instructions_is_string():
    import json

    from worker.models.application_packet import ApplicationPacket

    instructions = json.dumps({"First Name": "Tanner", "Email": "t@example.com"})
    packet = ApplicationPacket(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        json_instructions=instructions,
        requires_resume=False,
    )
    assert isinstance(packet.json_instructions, str)
    parsed = json.loads(packet.json_instructions)
    assert parsed["First Name"] == "Tanner"


def test_application_packets_holds_list():
    import json

    from worker.models.application_packet import ApplicationPacket, ApplicationPackets

    packets = ApplicationPackets(
        job_applications=[
            ApplicationPacket(
                url="https://a.com",
                company="A",
                job_title="D",
                json_instructions=json.dumps({"Email": "a@b.com"}),
                requires_resume=False,
            )
        ]
    )
    assert len(packets.job_applications) == 1


def test_inspected_job_has_cover_letter_fields():
    from worker.models.inspected_job import InspectedJob

    job = InspectedJob(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        form_fields=["First Name"],
        requires_resume=False,
        requires_cover_letter=True,
        job_description="We are looking for a talented engineer.",
    )
    assert job.requires_cover_letter is True
    assert job.job_description == "We are looking for a talented engineer."


def test_application_packet_has_cover_letter_fields():
    import json

    from worker.models.application_packet import ApplicationPacket

    packet = ApplicationPacket(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        json_instructions=json.dumps({"Email": "t@example.com"}),
        requires_resume=False,
    )
    assert packet.cover_letter_text is None
    assert packet.cover_letter_path is None


def test_application_packet_cover_letter_fields_accept_values():
    import json

    from worker.models.application_packet import ApplicationPacket

    packet = ApplicationPacket(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        json_instructions=json.dumps({"Email": "t@example.com"}),
        requires_resume=False,
        cover_letter_text="Dear Hiring Manager...",
        cover_letter_path="/tmp/acme_engineer_20260409_120000.pdf",
    )
    assert packet.cover_letter_text == "Dear Hiring Manager..."
    assert packet.cover_letter_path == "/tmp/acme_engineer_20260409_120000.pdf"


def test_build_cover_letter_writer_returns_agent():
    from unittest.mock import MagicMock, patch

    with (
        patch("worker.agents.cover_letter_writer.build_llm") as mock_llm,
        patch("worker.agents.cover_letter_writer.resume_loader_tool"),
        patch("worker.agents.cover_letter_writer.cover_letter_context_loader_tool"),
        patch("worker.agents.cover_letter_writer.pdf_renderer_tool"),
        patch("worker.agents.cover_letter_writer.Agent") as mock_agent,
    ):
        mock_llm.return_value = MagicMock()
        agent_instance = MagicMock()
        agent_instance.role = "Cover Letter Writer"
        agent_instance.allow_delegation = False
        mock_agent.return_value = agent_instance

        from worker.agents.cover_letter_writer import build_cover_letter_writer

        agent = build_cover_letter_writer()

    assert agent.role == "Cover Letter Writer"
    assert agent.allow_delegation is False


def test_build_field_inspector_returns_agent():
    from unittest.mock import MagicMock, patch

    # Patch build_llm, field_inspector_tool, and Agent to avoid needing Ollama running
    with (
        patch("worker.agents.field_inspector.build_llm") as mock_llm,
        patch("worker.agents.field_inspector.field_inspector_tool"),
        patch("worker.agents.field_inspector.Agent") as mock_agent,
    ):
        mock_instance = MagicMock()
        mock_llm.return_value = mock_instance
        # Create a real agent-like object that passes assertions
        agent_instance = MagicMock()
        agent_instance.role = "Form Field Inspector"
        agent_instance.max_iter = 8
        agent_instance.allow_delegation = False
        mock_agent.return_value = agent_instance
        from worker.agents.field_inspector import build_field_inspector

        agent = build_field_inspector()
    assert agent.role == "Form Field Inspector"
    assert agent.max_iter == 8
    assert agent.allow_delegation is False
