import json
import os
import time
from pathlib import Path

from sources.greenhouse import fetch_greenhouse
from sources.lever import fetch_lever
from sources.adzuna import fetch_adzuna

from filters.profile_filter import ProfileFilter

from notifications.telegram import TelegramBot


BASE_DIR = Path(__file__).resolve().parent

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"

PROFILE_FILE = CONFIG_DIR / "profile.json"
COMPANIES_FILE = CONFIG_DIR / "companies.json"
SEEN_FILE = DATA_DIR / "seen_jobs.json"


TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    ""
)

ADZUNA_APP_ID = os.getenv(
    "ADZUNA_APP_ID",
    ""
)

ADZUNA_APP_KEY = os.getenv(
    "ADZUNA_APP_KEY",
    ""
)


ADZUNA_QUERIES = [
    "java backend developer fresher",
    "java software engineer",
    "sde 1 java",
    "associate software engineer",
    "software engineer fresher",
    "backend engineer java",
    "java spring boot",
    "full stack developer fresher"
]


def load_json(path, default):

    if not path.exists():
        return default

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as exc:

        print(
            f"Could not read {path}: {exc}"
        )

        return default


def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp_path = path.with_suffix(
        ".tmp"
    )

    with open(
        temp_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    temp_path.replace(path)


def load_profile():

    return load_json(
        PROFILE_FILE,
        {}
    )


def load_companies():

    return load_json(
        COMPANIES_FILE,
        {
            "greenhouse": [],
            "lever": [],
            "direct": []
        }
    )


def load_seen():

    data = load_json(
        SEEN_FILE,
        []
    )

    return set(data)


def save_seen(seen):

    save_json(
        SEEN_FILE,
        sorted(list(seen))
    )


def fetch_all_jobs(companies):

    jobs = []

    greenhouse_companies = companies.get(
        "greenhouse",
        []
    )

    lever_companies = companies.get(
        "lever",
        []
    )

    for company in greenhouse_companies:

        print(
            f"Checking Greenhouse: "
            f"{company['name']}"
        )

        jobs.extend(
            fetch_greenhouse(company)
        )

        time.sleep(0.3)

    for company in lever_companies:

        print(
            f"Checking Lever: "
            f"{company['name']}"
        )

        jobs.extend(
            fetch_lever(company)
        )

        time.sleep(0.3)

    if ADZUNA_APP_ID and ADZUNA_APP_KEY:

        for query in ADZUNA_QUERIES:

            print(
                f"Checking Adzuna: "
                f"{query}"
            )

            jobs.extend(
                fetch_adzuna(
                    ADZUNA_APP_ID,
                    ADZUNA_APP_KEY,
                    query=query
                )
            )

            time.sleep(1)

    else:

        print(
            "Adzuna credentials not configured."
        )

    return jobs


def deduplicate_jobs(jobs):

    unique = {}

    for job in jobs:

        job_id = job.get("id")

        if not job_id:
            continue

        unique[job_id] = job

    return list(unique.values())


def main():

    print(
        "================================"
    )

    print(
        "       JOB ALERT BOT v2"
    )

    print(
        "================================"
    )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    profile = load_profile()

    companies = load_companies()

    seen = load_seen()

    print(
        f"Previously seen jobs: {len(seen)}"
    )

    all_jobs = fetch_all_jobs(
        companies
    )

    all_jobs = deduplicate_jobs(
        all_jobs
    )

    print(
        f"Fetched {len(all_jobs)} unique jobs."
    )

    profile_filter = ProfileFilter(
        profile
    )

    matches = []

    for job in all_jobs:

        processed = profile_filter.process(
            job
        )

        if processed is None:
            continue

        if job["id"] in seen:
            continue

        matches.append(
            processed
        )

    matches.sort(
        key=lambda x: x.get(
            "match_score",
            0
        ),
        reverse=True
    )

    print(
        f"New matching jobs: "
        f"{len(matches)}"
    )

    telegram = TelegramBot(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID
    )

    sent_count = 0

    for job in matches:

        print(
            f"[MATCH {job['match_score']}] "
            f"{job['company']} - "
            f"{job['title']}"
        )

        success = telegram.send_job(
            job
        )

        if success:

            seen.add(
                job["id"]
            )

            sent_count += 1

        time.sleep(0.5)

    # Always save state.
    # This is important for GitHub Actions cache.
    save_seen(seen)

    print(
        "--------------------------------"
    )

    print(
        f"Fetched: {len(all_jobs)}"
    )

    print(
        f"New matches: {len(matches)}"
    )

    print(
        f"Telegram alerts sent: "
        f"{sent_count}"
    )

    print(
        f"Seen jobs stored: "
        f"{len(seen)}"
    )

    print(
        "================================"
    )


if __name__ == "__main__":
    main()