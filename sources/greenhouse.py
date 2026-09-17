import re
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/140.0 Safari/537.36"
    )
}


def strip_html(text):
    if not text:
        return ""

    soup = BeautifulSoup(text, "html.parser")

    text = soup.get_text(" ", strip=True)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def fetch_greenhouse(company):
    name = company["name"]
    slug = company["slug"]

    api_url = (
        f"https://boards-api.greenhouse.io/"
        f"v1/boards/{slug}/jobs"
    )

    print(f"[Greenhouse] Checking {name}...")
    print(f"[Greenhouse] API: {api_url}")

    try:
        response = requests.get(
            api_url,
            params={"content": "true"},
            headers=HEADERS,
            timeout=20
        )

        # Some boards expose their public Greenhouse
        # pages but return 404 from the board API.
        if response.status_code == 404:
            print(
                f"[Greenhouse:{name}] "
                f"API returned 404."
            )

            print(
                f"[Greenhouse:{name}] "
                f"Using official public board..."
            )

            return fetch_public_greenhouse_board(
                company
            )

        response.raise_for_status()

        data = response.json()

        jobs = normalize_api_jobs(
            data.get("jobs", []),
            company
        )

        print(
            f"[Greenhouse] {name}: "
            f"{len(jobs)} jobs found through API"
        )

        return jobs

    except requests.RequestException as exc:
        print(
            f"[Greenhouse:{name}] "
            f"API ERROR: {exc}"
        )

        return []


def normalize_api_jobs(raw_jobs, company):
    name = company["name"]
    slug = company["slug"]

    jobs = []

    for job in raw_jobs:

        job_id = job.get("id")

        if not job_id:
            continue

        location_data = job.get("location") or {}

        location = location_data.get(
            "name",
            "Not specified"
        )

        description = strip_html(
            job.get("content", "")
        )

        jobs.append({
            "id": (
                f"greenhouse:"
                f"{slug}:"
                f"{job_id}"
            ),

            "title": (
                job.get("title", "")
                .strip()
            ),

            "company": name,

            "location": location,

            "url": (
                job.get("absolute_url")
                or
                f"https://job-boards.greenhouse.io/"
                f"{slug}/jobs/{job_id}"
            ),

            "career_url": (
                company.get("careers_url")
                or
                f"https://job-boards.greenhouse.io/"
                f"{slug}"
            ),

            "source": "Greenhouse",

            "authenticity":
                "🟢 Official company careers",

            "posted": (
                job.get("updated_at", "")
            ),

            "description": description
        })

    return jobs


def fetch_public_greenhouse_board(company):
    """
    Fetch jobs from the official public
    Greenhouse board.

    Example:
    https://job-boards.greenhouse.io/phonepe
    """

    name = company["name"]
    slug = company["slug"]

    board_url = (
        f"https://job-boards.greenhouse.io/"
        f"{slug}"
    )

    print(
        f"[Greenhouse:{name}] "
        f"Fetching public board: {board_url}"
    )

    try:
        response = requests.get(
            board_url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        print(
            f"[Greenhouse:{name}] "
            f"Public board ERROR: {exc}"
        )

        return []

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    jobs = []

    # Greenhouse public boards contain links such as:
    #
    # https://job-boards.greenhouse.io/phonepe/jobs/123456
    #
    # We only accept URLs belonging to the exact
    # Greenhouse board slug.

    pattern = re.compile(
        rf"^https://job-boards\.greenhouse\.io/"
        rf"{re.escape(slug)}/jobs/\d+"
    )

    job_links = []

    for link in soup.find_all("a", href=True):

        href = link["href"].strip()

        if pattern.match(href):

            href = href.split("?")[0]

            if href not in job_links:
                job_links.append(href)

    print(
        f"[Greenhouse:{name}] "
        f"Found {len(job_links)} official job links."
    )

    # Fetch each official job page so we get
    # title + location + description.
    #
    # Limit per company to avoid hammering the ATS.
    for index, job_url in enumerate(job_links, start=1):

        print(
            f"[Greenhouse:{name}] "
            f"Reading job {index}/{len(job_links)}"
        )

        job = fetch_greenhouse_job_page(
            job_url,
            company
        )

        if job:
            jobs.append(job)

        time_sleep()

    print(
        f"[Greenhouse] {name}: "
        f"{len(jobs)} jobs found"
    )

    return jobs


def fetch_greenhouse_job_page(
    job_url,
    company
):
    name = company["name"]
    slug = company["slug"]

    match = re.search(
        rf"/{re.escape(slug)}/jobs/(\d+)",
        job_url
    )

    if not match:
        return None

    job_id = match.group(1)

    try:
        response = requests.get(
            job_url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        print(
            f"[Greenhouse:{name}] "
            f"Job page ERROR: {exc}"
        )

        return None

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    # ---------------------------------------------------------
    # TITLE
    # ---------------------------------------------------------

    title = ""

    h1 = soup.find("h1")

    if h1:
        title = h1.get_text(
            " ",
            strip=True
        )

    if not title:
        meta_title = soup.find(
            "meta",
            property="og:title"
        )

        if meta_title:
            title = meta_title.get(
                "content",
                ""
            ).strip()

    # Remove common "Job Application for"
    # prefix if Greenhouse includes it.
    title = re.sub(
        r"^Job Application for\s+",
        "",
        title,
        flags=re.IGNORECASE
    )

    # ---------------------------------------------------------
    # LOCATION
    # ---------------------------------------------------------

    location = ""

    # Greenhouse commonly exposes location
    # using a div with class "location".
    location_element = soup.select_one(
        ".location"
    )

    if location_element:
        location = location_element.get_text(
            " ",
            strip=True
        )

    # Fallback: search common Greenhouse
    # location elements.
    if not location:

        for selector in [
            "[data-location]",
            ".job__location",
            ".opening-location"
        ]:

            element = soup.select_one(
                selector
            )

            if element:

                location = element.get_text(
                    " ",
                    strip=True
                )

                if location:
                    break

    if not location:
        location = "Not specified"

    # ---------------------------------------------------------
    # DESCRIPTION
    # ---------------------------------------------------------

    description = ""

    # Greenhouse job description containers.
    for selector in [
        "#content",
        ".job__description",
        ".job-description",
        "[data-qa='job-description']"
    ]:

        element = soup.select_one(
            selector
        )

        if element:

            description = element.get_text(
                " ",
                strip=True
            )

            if description:
                break

    # Fallback to page text.
    if not description:

        main = soup.find("main")

        if main:

            description = main.get_text(
                " ",
                strip=True
            )

    description = re.sub(
        r"\s+",
        " ",
        description
    ).strip()

    # ---------------------------------------------------------
    # POSTED / UPDATED
    # ---------------------------------------------------------

    posted = ""

    # Look for structured date information.
    time_element = soup.find(
        "time"
    )

    if time_element:

        posted = (
            time_element.get("datetime")
            or
            time_element.get_text(
                " ",
                strip=True
            )
        )

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    if not title:

        print(
            f"[Greenhouse:{name}] "
            f"Could not extract title: "
            f"{job_url}"
        )

        return None

    return {
        "id": (
            f"greenhouse:"
            f"{slug}:"
            f"{job_id}"
        ),

        "title": title,

        "company": name,

        "location": location,

        "url": job_url,

        "career_url": (
            company.get("careers_url")
            or
            f"https://job-boards.greenhouse.io/"
            f"{slug}"
        ),

        "source": "Greenhouse",

        "authenticity":
            "🟢 Official company careers",

        "posted": posted,

        "description": description
    }


def time_sleep():
    """
    Small delay between requests so we don't
    aggressively hit the ATS.
    """

    import time

    time.sleep(0.25)