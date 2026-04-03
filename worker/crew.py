from crewai import Crew, Process, Task

from worker.agents.browser import build_browser
from worker.agents.evaluator import build_evaluator
from worker.agents.searcher import build_searcher
from worker.logging_config import get_logger
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
    "Find up to 5 highly relevant job listings. For each listing you MUST include:\n"
    "1. The direct application URL (the actual page with the Apply button, not a search result page)\n"
    "2. The company name\n"
    "3. The job title\n"
    "4. Whether a resume upload is required"
)

_TASK_EVALUATE_DESCRIPTION = (
    "Review the jobs found by the Searcher.\n"
    "1. Discard any jobs that do not meet the ${min_salary} requirement or lack the keywords: {job_keywords}.\n"
    "2. For each approved job, output a Browser Instruction Packet with these EXACT fields:\n"
    "   - url: the direct application URL from the Searcher (do not change it)\n"
    "   - json_instructions: a JSON dict mapping form field labels to values. "
    "Example: {{\"First Name\": \"Jane\", \"Last Name\": \"Doe\", \"Email\": \"jane@email.com\", \"Phone\": \"555-1234\"}}\n"
    "   - requires_resume: true or false\n"
    "3. Output one packet per approved job. Do not skip any approved jobs."
)

_TASK_APPLY_DESCRIPTION = (
    "You have a list of Browser Instruction Packets from the Evaluator. "
    "For EACH packet, immediately call the Browser Form Fitter tool with:\n"
    "- url: the exact URL from the packet\n"
    "- json_instructions: the exact JSON string from the packet\n"
    "- requires_resume: the boolean value from the packet\n"
    "Do NOT search the web. Do NOT skip any packets. Call the Browser Form Fitter tool once per job."
)


def run_crew(criteria: SearchCriteria, task_id: str | None = None) -> str:
    """Build a fresh crew and run it for the given search criteria.

    A new crew is built per run to prevent context bleed between tasks.
    """
    searcher = build_searcher()
    evaluator = build_evaluator()
    browser_agent = build_browser()

    task_search = Task(
        description=_TASK_SEARCH_DESCRIPTION,
        expected_output="A structured list of job listings that strictly match the provided criteria.",
        agent=searcher,
    )
    task_evaluate = Task(
        description=_TASK_EVALUATE_DESCRIPTION,
        expected_output="Instruction packet with URL, JSON form data, and requires_resume flag.",
        agent=evaluator,
    )
    task_apply = Task(
        description=_TASK_APPLY_DESCRIPTION,
        expected_output="Final report of all successfully submitted applications.",
        agent=browser_agent,
    )

    crew = Crew(
        agents=[searcher, evaluator, browser_agent],
        tasks=[task_search, task_evaluate, task_apply],
        process=Process.sequential,
        verbose=True,
    )

    inputs = {
        "job_title": criteria.job_title,
        "location": criteria.location,
        "min_salary": criteria.min_salary,
        "job_keywords": ", ".join(criteria.job_keywords),
        "company": criteria.company,
        "job_website": criteria.job_website,
    }

    set_current_task_id(task_id)
    logger.info("crew_kickoff", task_id=task_id, job_title=criteria.job_title)
    try:
        result = crew.kickoff(inputs=inputs)
    finally:
        set_current_task_id(None)
    logger.info("crew_complete", task_id=task_id)
    return str(result)
