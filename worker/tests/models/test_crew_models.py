

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
        packets=[
            ApplicationPacket(
                url="https://a.com",
                company="A",
                job_title="D",
                json_instructions=json.dumps({"Email": "a@b.com"}),
                requires_resume=False,
            )
        ]
    )
    assert len(packets.packets) == 1
