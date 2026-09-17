import requests


def fetch_adzuna(app_id, app_key, query, country="in", max_results=50):

    if not app_id or not app_key:
        return []

    url = (
        f"https://api.adzuna.com/v1/api/jobs/"
        f"{country}/search/1"
    )

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": max_results,
        "what": query,
        "content-type": "application/json"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()
        data = response.json()

    except Exception as exc:
        print(f"[Adzuna] ERROR: {exc}")
        return []

    jobs = []

    for job in data.get("results", []):

        company = (
            job.get("company") or {}
        ).get("display_name", "Unknown")

        location = (
            job.get("location") or {}
        ).get("display_name", "Not specified")

        jobs.append({
            "id": f"adzuna:{job.get('id')}",
            "title": job.get("title", "").strip(),
            "company": company,
            "location": location,
            "url": job.get("redirect_url", ""),
            "career_url": "",
            "source": "Adzuna",
            "source_type": "aggregator",
            "authenticity": "🟡 Aggregator — verify employer listing",
            "posted": job.get("created", ""),
            "description": job.get("description", ""),
        })

    return jobs