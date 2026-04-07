import json

from crewai import Crew, Process, Task

from worker.agents.browser import build_browser
from worker.agents.evaluator import build_evaluator
from worker.agents.field_inspector import build_field_inspector
from worker.agents.searcher import build_searcher
from worker.config import settings
from worker.logging_config import get_logger
from worker.models.application_packet import ApplicationPackets
from worker.models.inspected_job import InspectedJobs
from worker.models.search_criteria import SearchCriteria
from worker.tools.browser_tool import set_current_task_id

logger = get_logger(__name__)

_TASK_SEARCH_DESCRIPTION = (
    "Search for open positions using the following mandatory criteria:\n"
    "- Job Title: {job_title}\n"
    "- Location: {location}\n"
    "- Keywords required in description: {job_keywords}\n"
    "- Minimum Salary: ${min_salary}\n\n"
    "OPTIONAL CONSTRAINTS:\n"
    "- Target Company (if provided, only search this company): {company}\n"
    "- Target Website (if provided, use site: operator): {job_website}\n\n"
    "EXCLUDED COMPANIES (do NOT return any job from these): {excluded_companies}\n\n"
    "You MUST search specifically on job boards. Run at least 3 of these queries:\n"
    '  "{job_title} {location} site:indeed.com"\n'
    '  "{job_title} {location} site:greenhouse.io"\n'
    '  "{job_title} {location} site:lever.co"\n'
    "Only keep results whose URL contains one of these patterns:\n"
    "  indeed.com/viewjob, greenhouse.io/jobs/,\n"
    "  lever.co/jobs/, boards.greenhouse.io/, jobs.lever.co/, workday.com/jobs/\n\n"
    "DISCARD any result that looks like a social post, article, hashtag feed, or profile page.\n\n"
    "Find the single best matching job listing.\n\n"
    "Output your finding in EXACTLY this format — one block only, nothing else:\n\n"
    "JOB:\n"
    "URL: <full https:// URL to the application page>\n"
    "Company: <company name>\n"
    "Title: <exact job title>\n"
    "---\n\n"
    "Output EXACTLY ONE job block. Do NOT include any text outside of this block. "
    "The block MUST start with 'JOB:' on its own line and include a full URL."
)

_TASK_INSPECT_DESCRIPTION = (
    "You have a list of job listings from the Searcher. "
    "Each listing is a block starting with 'JOB:' and containing a 'URL:' line.\n\n"
    "IMPORTANT: If the input contains no lines starting with 'URL:', "
    "output an empty InspectedJobs list immediately without calling any tools.\n\n"
    "For EACH job block, call the Field Inspector tool exactly once with its URL.\n"
    "Do NOT skip any job. Do NOT call the tool more than once per URL.\n"
    "Collect all results and output them as an InspectedJobs object with the form_fields "
    "and requires_resume value returned by the tool for each job."
)

_TASK_EVALUATE_DESCRIPTION = (
    "You have a list of inspected jobs from the Field Inspector. "
    "Each job has a list of exact form_fields extracted from its application page.\n\n"
    "Personal data to use when filling fields:\n"
    "{personal_data}\n\n"
    "Steps:\n"
    "1. Discard any jobs that do not meet the ${min_salary} salary requirement "
    "or lack the keywords: {job_keywords}.\n"
    "2. For each approved job, create an ApplicationPacket:\n"
    "   - url: exact URL from the inspector (do not change it)\n"
    "   - company: company name\n"
    "   - job_title: job title\n"
    "   - json_instructions: a JSON-encoded STRING mapping each form_field that matches "
    "personal data to its value. Use ONLY field names from the form_fields list — "
    "do NOT invent field names. "
    'Example: \'{{"First Name": "Tanner", "Email": "tanner@example.com"}}\'\n'
    "   - requires_resume: the requires_resume boolean from the inspector\n"
    "3. Output one ApplicationPacket per approved job. Do not skip any approved job."
)

_TASK_APPLY_DESCRIPTION = (
    "You have a list of ApplicationPackets from the Evaluator. "
    "For EACH packet, immediately call the Browser Form Fitter tool with:\n"
    "- url: the exact URL from the packet\n"
    "- json_instructions: the exact json_instructions string from the packet\n"
    "- requires_resume: the boolean value from the packet\n"
    "Do NOT search the web. Do NOT skip any packets. Call Browser Form Fitter once per job."
)


def _build_crew_inputs(
    criteria: SearchCriteria,
    excluded: list[str],
) -> dict:
    """Build the template variable dict passed to Crew.kickoff()."""
    personal_data = json.loads(settings.personal_data_path.read_text())
    excluded_str = ", ".join(excluded) if excluded else "none"
    return {
        "job_title": criteria.job_title,
        "location": criteria.location,
        "min_salary": criteria.min_salary,
        "job_keywords": ", ".join(criteria.job_keywords),
        "company": criteria.company or "",
        "job_website": criteria.job_website or "",
        "personal_data": json.dumps(personal_data),
        "excluded_companies": excluded_str,
    }


def run_crew(
    criteria: SearchCriteria,
    task_id: str | None = None,
    excluded_companies: list[str] | None = None,
    dry_run: bool = False,
) -> "str | ApplicationPackets | None":
    """Run one search→inspect→evaluate→(apply) cycle for a single job.

    A fresh crew is built each call to prevent context bleed.
    Stages: Searcher -> Field Inspector -> Evaluator -> [Browser if not dry_run].

    Args:
        dry_run: When True, skip the Browser task and return the ApplicationPackets
                 produced by the Evaluator so the caller can preview what would be
                 submitted before any real application is made.

    Returns:
        dry_run=False: company name applied to, or None if no application was made.
        dry_run=True:  ApplicationPackets from the Evaluator, or None on failure.
    """
    excluded = excluded_companies or []

    searcher = build_searcher()
    field_inspector = build_field_inspector()
    evaluator = build_evaluator()

    task_search = Task(
        description=_TASK_SEARCH_DESCRIPTION,
        expected_output=(
            "Exactly one job listing. Format: JOB: / URL: / Company: / Title: / ---"
        ),
        agent=searcher,
    )
    task_inspect = Task(
        description=_TASK_INSPECT_DESCRIPTION,
        expected_output="InspectedJobs JSON with form_fields and requires_resume for the job.",
        agent=field_inspector,
        output_pydantic=InspectedJobs,
    )
    task_evaluate = Task(
        description=_TASK_EVALUATE_DESCRIPTION,
        expected_output="ApplicationPackets JSON with json_instructions and requires_resume for the approved job.",
        agent=evaluator,
        output_pydantic=ApplicationPackets,
    )

    if dry_run:
        agents = [searcher, field_inspector, evaluator]
        tasks = [task_search, task_inspect, task_evaluate]
    else:
        browser_agent = build_browser()
        task_apply = Task(
            description=_TASK_APPLY_DESCRIPTION,
            expected_output="Final report confirming the application was submitted.",
            agent=browser_agent,
        )
        agents = [searcher, field_inspector, evaluator, browser_agent]
        tasks = [task_search, task_inspect, task_evaluate, task_apply]

    crew = Crew(
        agents=agents,  # type: ignore[arg-type]
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

    inputs = _build_crew_inputs(criteria, excluded)

    set_current_task_id(task_id)
    logger.info(
        "crew_kickoff",
        task_id=task_id,
        job_title=criteria.job_title,
        excluded=excluded,
        dry_run=dry_run,
    )
    try:
        crew.kickoff(inputs=inputs)
    finally:
        set_current_task_id(None)

    if dry_run:
        try:
            packets: ApplicationPackets | None = task_evaluate.output.pydantic  # type: ignore[assignment, union-attr]
            logger.info("crew_dry_run_complete", task_id=task_id)
            return packets
        except Exception:
            return None

    # Extract the company that was evaluated so the caller can exclude it next round.
    company: str | None = None
    try:
        packets = task_evaluate.output.pydantic  # type: ignore[assignment, union-attr]
        if packets and packets.job_applications:
            company = packets.job_applications[0].company
    except Exception:
        pass

    logger.info("crew_complete", task_id=task_id, company_applied=company)
    return company
