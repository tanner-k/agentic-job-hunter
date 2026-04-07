from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchCriteria:
    """Immutable search parameters — maps to search_tasks Supabase table."""

    job_title: str
    location: str
    min_salary: int = 0
    job_keywords: list[str] = field(default_factory=list)
    company: str = ""
    job_website: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "SearchCriteria":
        """Create from a Supabase row or CSV row dict."""
        keywords = data.get("keywords") or data.get("job_keywords") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        return cls(
            job_title=data["job_title"],
            location=data["location"],
            min_salary=int(data.get("min_salary") or 0),
            job_keywords=keywords,
            company=data.get("company") or "",
            job_website=data.get("job_website") or "",
        )
