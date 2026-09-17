import requests
from html import unescape
import re


def strip_html(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)

    return re.sub(r"\s+", " ", text).strip()


def fetch_greenhouse(company):
    name = company["name"]
    slug = company["slug"]

    url = (
        f"https://boards-api.greenhouse.io/v1/boards/"
        f"{slug}/jobs?content=true"
    )

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()

    except Exception as exc:
        print(f"[Greenhouse:{name}] ERROR: {exc}")
        return []

    jobs = []

    for job in data.get("jobs", []):

        jobs.append({
            "id": f"greenhouse:{slug}:{job.get('id')}",
            "title": job.get("title", "").strip(),
            "company": name,
            "location": (
                job.get("location") or {}
            ).get("name", "Not specified"),
            "url": job.get("absolute_url", ""),
            "career_url": company.get("careers_url", ""),
            "source": "Greenhouse",
            "source_type": "official_ats",
            "authenticity": "🟢 Official company careers",
            "posted": job.get("updated_at", ""),
            "description": strip_html(job.get("content", "")),
        })

    return jobs