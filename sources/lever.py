import requests
import re
from html import unescape


def strip_html(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)

    return re.sub(r"\s+", " ", text).strip()


def fetch_lever(company):
    name = company["name"]
    slug = company["slug"]

    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()

    except Exception as exc:
        print(f"[Lever:{name}] ERROR: {exc}")
        return []

    jobs = []

    for job in data:

        categories = job.get("categories") or {}

        description = (
            job.get("descriptionPlain")
            or strip_html(job.get("description", ""))
        )

        jobs.append({
            "id": f"lever:{slug}:{job.get('id')}",
            "title": job.get("text", "").strip(),
            "company": name,
            "location": categories.get(
                "location",
                "Not specified"
            ),
            "url": job.get("hostedUrl", ""),
            "career_url": company.get("careers_url", ""),
            "source": "Lever",
            "source_type": "official_ats",
            "authenticity": "🟢 Official company careers",
            "posted": job.get("createdAt", ""),
            "description": description,
        })

    return jobs