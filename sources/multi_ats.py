import json
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


TIMEOUT = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/json;q=0.9,*/*;q=0.8"
    ),
}


# ============================================================
# HELPERS
# ============================================================

def strip_html(value):
    if not value:
        return ""

    soup = BeautifulSoup(
        str(value),
        "html.parser"
    )

    return re.sub(
        r"\s+",
        " ",
        soup.get_text(" ", strip=True)
    ).strip()


def get_company_name(company):
    return company.get(
        "name",
        "Unknown"
    )


def get_career_url(company):
    return company.get(
        "careers_url",
        ""
    )


def normalize_job(
    company,
    source,
    raw_id,
    title,
    location,
    url,
    description="",
    posted=""
):

    return {

        "id": (
            f"{source.lower()}:"
            f"{company.get('name', 'unknown')}:"
            f"{raw_id or 'unknown'}"
        ),

        "title": (
            title or ""
        ).strip(),

        "company": get_company_name(
            company
        ),

        "location": (
            location or "Not specified"
        ).strip(),

        "url": url or get_career_url(
            company
        ),

        "career_url": get_career_url(
            company
        ),

        "source": source,

        "authenticity": (
            "🟢 Official company careers"
        ),

        "posted": posted or "",

        "description": strip_html(
            description
        )
    }


def request_get(url, **kwargs):

    headers = dict(
        HEADERS
    )

    headers.update(
        kwargs.pop(
            "headers",
            {}
        )
    )

    return requests.get(
        url,
        headers=headers,
        timeout=TIMEOUT,
        **kwargs
    )


# ============================================================
# GREENHOUSE
# ============================================================

def fetch_greenhouse(company):

    slug = company["slug"]
    name = get_company_name(
        company
    )

    api_url = (
        "https://boards-api.greenhouse.io/"
        f"v1/boards/{slug}/jobs"
    )

    print(
        f"[Greenhouse] Checking {name}..."
    )

    try:

        response = request_get(
            api_url,
            params={
                "content": "true"
            }
        )

        if response.status_code == 404:

            print(
                f"[Greenhouse:{name}] "
                "API 404 - trying public board"
            )

            return fetch_greenhouse_public(
                company
            )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"[Greenhouse:{name}] ERROR: "
            f"{exc}"
        )

        return []

    jobs = []

    for job in data.get(
        "jobs",
        []
    ):

        location = (
            job.get("location")
            or {}
        ).get(
            "name",
            "Not specified"
        )

        jobs.append(
            normalize_job(

                company,

                "Greenhouse",

                job.get(
                    "id"
                ),

                job.get(
                    "title"
                ),

                location,

                job.get(
                    "absolute_url"
                ),

                job.get(
                    "content"
                ),

                job.get(
                    "updated_at"
                )
            )
        )

    print(
        f"[Greenhouse] {name}: "
        f"{len(jobs)} jobs"
    )

    return jobs


def fetch_greenhouse_public(company):

    slug = company["slug"]
    name = get_company_name(
        company
    )

    board_url = (
        f"https://job-boards.greenhouse.io/"
        f"{slug}"
    )

    try:

        response = request_get(
            board_url
        )

        response.raise_for_status()

    except Exception as exc:

        print(
            f"[Greenhouse:{name}] "
            f"public board ERROR: {exc}"
        )

        return []

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    jobs = []

    pattern = re.compile(
        rf"/{re.escape(slug)}/jobs/(\d+)",
        re.I
    )

    links_seen = set()

    for anchor in soup.find_all(
        "a",
        href=True
    ):

        href = urljoin(
            board_url,
            anchor["href"]
        )

        match = pattern.search(
            href
        )

        if not match:
            continue

        if href in links_seen:
            continue

        links_seen.add(
            href
        )

        title = anchor.get_text(
            " ",
            strip=True
        )

        if not title:
            continue

        jobs.append(
            normalize_job(

                company,

                "Greenhouse",

                match.group(1),

                title,

                "Not specified",

                href,

                ""
            )
        )

    print(
        f"[Greenhouse] {name}: "
        f"{len(jobs)} jobs via public board"
    )

    return jobs


# ============================================================
# LEVER
# ============================================================

def fetch_lever(company):

    slug = company["slug"]
    name = get_company_name(
        company
    )

    url = (
        f"https://api.lever.co/"
        f"v0/postings/{slug}?mode=json"
    )

    print(
        f"[Lever] Checking {name}..."
    )

    try:

        response = request_get(
            url
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"[Lever:{name}] ERROR: "
            f"{exc}"
        )

        return []

    jobs = []

    for job in data:

        categories = (
            job.get(
                "categories"
            )
            or {}
        )

        description = (
            job.get(
                "descriptionPlain"
            )
            or job.get(
                "description"
            )
            or ""
        )

        jobs.append(
            normalize_job(

                company,

                "Lever",

                job.get(
                    "id"
                ),

                job.get(
                    "text"
                ),

                categories.get(
                    "location",
                    "Not specified"
                ),

                job.get(
                    "hostedUrl"
                ),

                description,

                job.get(
                    "createdAt"
                )
            )
        )

    print(
        f"[Lever] {name}: "
        f"{len(jobs)} jobs"
    )

    return jobs


# ============================================================
# ASHBY
# ============================================================

def fetch_ashby(company):

    slug = company["slug"]
    name = get_company_name(
        company
    )

    url = (
        "https://api.ashbyhq.com/"
        f"posting-api/job-board/{slug}"
    )

    print(
        f"[Ashby] Checking {name}..."
    )

    try:

        response = request_get(
            url
        )

        response.raise_for_status()

        data = response.json()

        jobs = data.get(
            "jobs",
            []
        )

    except Exception as exc:

        print(
            f"[Ashby:{name}] ERROR: "
            f"{exc}"
        )

        return []

    result = []

    for job in jobs:

        if job.get(
            "isListed"
        ) is False:

            continue

        location = (
            job.get(
                "location"
            )
            or job.get(
                "locationName"
            )
            or "Not specified"
        )

        result.append(
            normalize_job(

                company,

                "Ashby",

                job.get(
                    "id"
                ),

                job.get(
                    "title"
                ),

                location,

                (
                    job.get(
                        "jobUrl"
                    )
                    or job.get(
                        "applyUrl"
                    )
                ),

                (
                    job.get(
                        "descriptionHtml"
                    )
                    or job.get(
                        "description"
                    )
                ),

                (
                    job.get(
                        "publishedAt"
                    )
                    or job.get(
                        "updatedAt"
                    )
                )
            )
        )

    print(
        f"[Ashby] {name}: "
        f"{len(result)} jobs"
    )

    return result


# ============================================================
# SMARTRECRUITERS
# ============================================================

def fetch_smartrecruiters(company):

    slug = company["slug"]
    name = get_company_name(
        company
    )

    url = (
        "https://api.smartrecruiters.com/"
        f"v1/companies/{slug}/postings"
    )

    print(
        f"[SmartRecruiters] "
        f"Checking {name}..."
    )

    try:

        response = request_get(
            url,
            params={
                "limit": 100,
                "offset": 0
            }
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"[SmartRecruiters:{name}] "
            f"ERROR: {exc}"
        )

        return []

    result = []

    for job in data.get(
        "content",
        []
    ):

        location_data = (
            job.get(
                "location"
            )
            or {}
        )

        location = (
            location_data.get(
                "fullLocation"
            )
            or location_data.get(
                "city"
            )
            or "Not specified"
        )

        result.append(
            normalize_job(

                company,

                "SmartRecruiters",

                (
                    job.get(
                        "id"
                    )
                    or job.get(
                        "refNumber"
                    )
                ),

                job.get(
                    "name"
                ),

                location,

                job.get(
                    "ref"
                )
                or job.get(
                    "url"
                ),

                "",

                job.get(
                    "releasedDate"
                )
            )
        )

    print(
        f"[SmartRecruiters] "
        f"{name}: {len(result)} jobs"
    )

    return result


# ============================================================
# WORKDAY
# ============================================================

def get_workday_config(company):

    config = company.get(
        "workday"
    )

    if config:

        return (
            config["host"],
            config["tenant"],
            config["site"]
        )

    careers_url = company[
        "careers_url"
    ]

    parsed = urlparse(
        careers_url
    )

    host = parsed.netloc

    parts = parsed.path.strip(
        "/"
    ).split("/")

    site = (
        parts[0]
        if parts
        else ""
    )

    tenant_match = re.match(
        r"([^.]+)\.wd\d+\.myworkdayjobs\.com",
        host,
        re.I
    )

    if tenant_match:

        tenant = (
            tenant_match.group(1)
        )

    else:

        tenant = host.split(
            "."
        )[0]

    return (
        host,
        tenant,
        site
    )


def fetch_workday(company):

    name = get_company_name(
        company
    )

    print(
        f"[Workday] Checking {name}..."
    )

    try:

        host, tenant, site = (
            get_workday_config(
                company
            )
        )

        endpoint = (
            f"https://{host}/wday/cxs/"
            f"{tenant}/{site}/jobs"
        )

        payload = {

            "appliedFacets": {},

            "limit": 100,

            "offset": 0,

            "searchText": ""
        }

        response = requests.post(

            endpoint,

            headers={
                **HEADERS,
                "Content-Type":
                    "application/json",
                "Accept":
                    "application/json"
            },

            json=payload,

            timeout=TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"[Workday:{name}] ERROR: "
            f"{exc}"
        )

        return []

    result = []

    for job in data.get(
        "jobPostings",
        []
    ):

        external_path = (
            job.get(
                "externalPath"
            )
            or ""
        )

        if external_path.startswith(
            "http"
        ):

            job_url = (
                external_path
            )

        else:

            job_url = urljoin(
                f"https://{host}",
                external_path
            )

        location = (
            job.get(
                "locationsText"
            )
            or job.get(
                "location"
            )
            or "Not specified"
        )

        result.append(
            normalize_job(

                company,

                "Workday",

                (
                    job.get(
                        "jobPostingId"
                    )
                    or job.get(
                        "id"
                    )
                    or external_path
                ),

                job.get(
                    "title"
                ),

                location,

                job_url,

                " ".join(
                    job.get(
                        "bulletFields",
                        []
                    )
                ),

                (
                    job.get(
                        "postedOn"
                    )
                    or job.get(
                        "postedDate"
                    )
                )
            )
        )

    print(
        f"[Workday] {name}: "
        f"{len(result)} jobs"
    )

    return result


# ============================================================
# JSON-LD COMPANY NATIVE
# ============================================================

def extract_json_ld_jobs(
    html
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    results = []

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        raw = (
            script.string
            or script.get_text()
        )

        if not raw:
            continue

        try:

            data = json.loads(
                raw
            )

        except Exception:

            continue

        objects = (
            data
            if isinstance(
                data,
                list
            )
            else [data]
        )

        for obj in objects:

            if not isinstance(
                obj,
                dict
            ):
                continue

            if obj.get(
                "@type"
            ) == "JobPosting":

                results.append(
                    obj
                )

            graph = obj.get(
                "@graph"
            )

            if isinstance(
                graph,
                list
            ):

                for item in graph:

                    if (
                        isinstance(
                            item,
                            dict
                        )
                        and item.get(
                            "@type"
                        ) == "JobPosting"
                    ):

                        results.append(
                            item
                        )

    return results


def fetch_company_native(
    company,
    response=None
):

    name = get_company_name(
        company
    )

    print(
        f"[Native] Checking {name}..."
    )

    try:

        if response is None:

            response = request_get(
                company[
                    "careers_url"
                ]
            )

        response.raise_for_status()

    except Exception as exc:

        print(
            f"[Native:{name}] ERROR: "
            f"{exc}"
        )

        return []

    postings = extract_json_ld_jobs(
        response.text
    )

    result = []

    for index, posting in enumerate(
        postings,
        start=1
    ):

        location = (
            posting.get(
                "jobLocation"
            )
            or {}
        )

        if isinstance(
            location,
            list
        ):

            location = (
                location[0]
                if location
                else {}
            )

        if isinstance(
            location,
            dict
        ):

            address = (
                location.get(
                    "address"
                )
                or location
            )

            if isinstance(
                address,
                dict
            ):

                location = (
                    address.get(
                        "addressLocality"
                    )
                    or address.get(
                        "addressRegion"
                    )
                    or "Not specified"
                )

        if not isinstance(
            location,
            str
        ):

            location = (
                posting.get(
                    "jobLocationType"
                )
                or "Not specified"
            )

        identifier = (
            posting.get(
                "identifier"
            )
        )

        if isinstance(
            identifier,
            dict
        ):

            identifier = (
                identifier.get(
                    "value"
                )
            )

        result.append(
            normalize_job(

                company,

                "Company Native",

                identifier
                or index,

                posting.get(
                    "title"
                ),

                location,

                posting.get(
                    "url"
                )
                or company[
                    "careers_url"
                ],

                posting.get(
                    "description"
                ),

                posting.get(
                    "datePosted"
                )
                or posting.get(
                    "dateModified"
                )
            )
        )

    print(
        f"[Native] {name}: "
        f"{len(result)} jobs"
    )

    return result


# ============================================================
# AUTOMATIC SOURCE DETECTION
# ============================================================

def detect_source(
    company
):

    configured = (
        company.get(
            "source",
            "auto"
        )
        .lower()
    )

    if configured not in (
        "auto",
        "native"
    ):

        return configured

    url = company.get(
        "careers_url",
        ""
    ).lower()

    if "greenhouse.io" in url:
        return "greenhouse"

    if "lever.co" in url:
        return "lever"

    if "ashbyhq.com" in url:
        return "ashby"

    if "smartrecruiters.com" in url:
        return "smartrecruiters"

    if "myworkdayjobs.com" in url:
        return "workday"

    return "native"


# ============================================================
# COMPANY FETCH
# ============================================================

def fetch_company(
    company
):

    source = detect_source(
        company
    )

    name = get_company_name(
        company
    )

    print(
        f"[{name}] "
        f"Source: {source}"
    )

    if source == "greenhouse":
        return fetch_greenhouse(
            company
        )

    if source == "lever":
        return fetch_lever(
            company
        )

    if source == "ashby":
        return fetch_ashby(
            company
        )

    if source == "smartrecruiters":
        return fetch_smartrecruiters(
            company
        )

    if source == "workday":
        return fetch_workday(
            company
        )

    return fetch_company_native(
        company
    )


# ============================================================
# FETCH EVERYTHING
# ============================================================

def fetch_all(
    companies
):

    jobs = []

    for company in companies:

        if company.get(
            "enabled",
            True
        ) is False:

            continue

        try:

            result = fetch_company(
                company
            )

            jobs.extend(
                result
            )

        except Exception as exc:

            print(
                f"[{company.get('name')}] "
                f"FAILED: {exc}"
            )

    return jobs