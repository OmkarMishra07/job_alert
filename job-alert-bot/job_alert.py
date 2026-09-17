#!/usr/bin/env python3

"""
Personal Job Alert Bot v2
=========================

Official ATS sources only:
    - Greenhouse
    - Lever

Adzuna is intentionally disabled for now.

Features:
    - Fresher / 0-2 YOE filtering
    - Java / Backend / Full Stack targeting
    - SDE / ASE targeting
    - Transparent match scoring
    - Job deduplication
    - Telegram job alerts
    - Direct application links
    - Company careers links

Designed for:
    - GitHub Actions
    - Local execution
"""

import json
import os
import re
import time
from datetime import datetime, timezone

import requests


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    ""
)

TELEGRAM_CHAT_ID = os.environ.get(
    "TELEGRAM_CHAT_ID",
    ""
)

COMPANIES_FILE = "companies.json"
STATE_FILE = "seen_jobs.json"


# ============================================================
# TARGET ROLE KEYWORDS
# ============================================================

INCLUDE_KEYWORDS = [
    "sde",
    "sde-1",
    "sde1",
    "software engineer",
    "software development engineer",
    "software developer",
    "software engineer i",

    "associate software engineer",
    "associate software developer",
    "ase",

    "java developer",
    "java engineer",
    "java backend",

    "backend engineer",
    "backend developer",
    "backend software engineer",

    "full stack engineer",
    "full stack developer",
    "fullstack engineer",
    "fullstack developer",

    "graduate engineer trainee",
    "graduate software engineer",
    "graduate engineer",

    "entry level software engineer",
    "entry-level software engineer",

    "new grad software engineer",
    "new graduate software engineer",

    "software engineer intern",
    "software developer intern",
    "java intern",
    "backend intern"
]


# ============================================================
# ROLES TO EXCLUDE
# ============================================================

EXCLUDE_KEYWORDS = [
    "senior",
    "sr.",
    "staff",
    "principal",
    "lead",
    "manager",
    "director",
    "head of",
    "architect",

    "sde-2",
    "sde2",
    "sde-3",
    "sde3",

    "3+ years",
    "4+ years",
    "5+ years",
    "6+ years",
    "7+ years",
    "8+ years",
    "9+ years",
    "10+ years"
]


# ============================================================
# TECHNICAL SKILLS
# ============================================================

SKILL_KEYWORDS = [
    "java",
    "spring boot",
    "spring",
    "hibernate",

    "sql",
    "postgresql",
    "mysql",
    "mongodb",

    "microservices",
    "rest api",
    "restful api",

    "kafka",
    "redis",

    "docker",
    "kubernetes",

    "aws",
    "azure",
    "gcp",

    "react",
    "javascript",
    "typescript",

    "python",

    "git",
    "github",

    "data structures",
    "algorithms",
    "dsa",

    "system design"
]


# ============================================================
# LOCATION KEYWORDS
# ============================================================

PREFERRED_LOCATIONS = [
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "gurugram",
    "gurgaon",
    "noida",
    "delhi",
    "mumbai",
    "chennai",
    "remote"
]


MAX_YEARS_EXPERIENCE = 2


# ============================================================
# JSON HELPERS
# ============================================================

def load_json(filename, default):

    if not os.path.exists(filename):
        return default

    try:

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as exc:

        print(
            f"Could not read {filename}: {exc}"
        )

        return default


def save_json(filename, data):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# LOAD COMPANIES
# ============================================================

def load_companies():

    default = {
        "greenhouse": [],
        "lever": []
    }

    return load_json(
        COMPANIES_FILE,
        default
    )


# ============================================================
# SEEN JOBS
# ============================================================

def load_seen():

    data = load_json(
        STATE_FILE,
        []
    )

    return set(data)


def save_seen(seen):

    save_json(
        STATE_FILE,
        sorted(list(seen))
    )


# ============================================================
# HTML CLEANER
# ============================================================

def strip_html(text):

    if not text:
        return ""

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# GREENHOUSE
# ============================================================

def fetch_greenhouse(company):

    name = company["name"]
    slug = company["slug"]

    url = (
        f"https://boards-api.greenhouse.io/"
        f"v1/boards/{slug}/jobs?content=true"
    )

    print(
        f"[Greenhouse] Checking {name}..."
    )

    try:

        response = requests.get(
            url,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"[Greenhouse:{name}] ERROR: {exc}"
        )

        return []

    jobs = []

    for job in data.get("jobs", []):

        jobs.append({

            "id": (
                f"greenhouse:"
                f"{slug}:"
                f"{job.get('id')}"
            ),

            "title": job.get(
                "title",
                ""
            ).strip(),

            "company": name,

            "location": (
                job.get("location") or {}
            ).get(
                "name",
                "Not specified"
            ),

            "url": job.get(
                "absolute_url",
                ""
            ),

            "career_url": company.get(
                "careers_url",
                ""
            ),

            "source": "Greenhouse",

            "authenticity": (
                "🟢 Official company careers"
            ),

            "posted": job.get(
                "updated_at",
                ""
            ),

            "description": strip_html(
                job.get(
                    "content",
                    ""
                )
            )
        })

    print(
        f"[Greenhouse] {name}: "
        f"{len(jobs)} jobs found"
    )

    return jobs


# ============================================================
# LEVER
# ============================================================

def fetch_lever(company):

    name = company["name"]
    slug = company["slug"]

    url = (
        f"https://api.lever.co/"
        f"v0/postings/{slug}?mode=json"
    )

    print(
        f"[Lever] Checking {name}..."
    )

    try:

        response = requests.get(
            url,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"[Lever:{name}] ERROR: {exc}"
        )

        return []

    jobs = []

    for job in data:

        categories = (
            job.get("categories")
            or {}
        )

        description = (
            job.get(
                "descriptionPlain"
            )
            or strip_html(
                job.get(
                    "description",
                    ""
                )
            )
        )

        jobs.append({

            "id": (
                f"lever:"
                f"{slug}:"
                f"{job.get('id')}"
            ),

            "title": job.get(
                "text",
                ""
            ).strip(),

            "company": name,

            "location": categories.get(
                "location",
                "Not specified"
            ),

            "url": job.get(
                "hostedUrl",
                ""
            ),

            "career_url": company.get(
                "careers_url",
                ""
            ),

            "source": "Lever",

            "authenticity": (
                "🟢 Official company careers"
            ),

            "posted": job.get(
                "createdAt",
                ""
            ),

            "description": description
        })

    print(
        f"[Lever] {name}: "
        f"{len(jobs)} jobs found"
    )

    return jobs


# ============================================================
# FETCH ALL JOBS
# ============================================================

def fetch_all_jobs(companies):

    jobs = []

    greenhouse = companies.get(
        "greenhouse",
        []
    )

    lever = companies.get(
        "lever",
        []
    )

    print(
        f"Greenhouse companies: "
        f"{len(greenhouse)}"
    )

    print(
        f"Lever companies: "
        f"{len(lever)}"
    )

    # Greenhouse
    for company in greenhouse:

        jobs.extend(
            fetch_greenhouse(company)
        )

        time.sleep(0.5)

    # Lever
    for company in lever:

        jobs.extend(
            fetch_lever(company)
        )

        time.sleep(0.5)

    return jobs


# ============================================================
# REMOVE DUPLICATE JOBS
# ============================================================

def deduplicate_jobs(jobs):

    unique = {}

    for job in jobs:

        job_id = job.get("id")

        if not job_id:
            continue

        unique[job_id] = job

    return list(
        unique.values()
    )


# ============================================================
# JOB TEXT
# ============================================================

def get_job_text(job):

    return (
        f"{job.get('title', '')} "
        f"{job.get('description', '')} "
        f"{job.get('location', '')}"
    ).lower()


# ============================================================
# ROLE MATCH
# ============================================================

def matches_role(job):

    title = job.get(
        "title",
        ""
    ).lower()

    # Must contain target role
    if not any(
        keyword in title
        for keyword in INCLUDE_KEYWORDS
    ):
        return False

    # Must not contain excluded role
    if any(
        keyword in title
        for keyword in EXCLUDE_KEYWORDS
    ):
        return False

    return True


# ============================================================
# EXPERIENCE CHECK
# ============================================================

def extract_max_experience(text):

    # Example:
    # 0-2 years
    match = re.search(
        r"(\d+)\s*-\s*(\d+)\s*years?",
        text
    )

    if match:

        return int(
            match.group(2)
        )

    # Example:
    # 2+ years
    match = re.search(
        r"(\d+)\s*\+\s*years?",
        text
    )

    if match:

        return int(
            match.group(1)
        )

    # Example:
    # 2 years experience
    match = re.search(
        r"(\d+)\s*years?",
        text
    )

    if match:

        return int(
            match.group(1)
        )

    return None


def matches_experience(job):

    text = get_job_text(
        job
    )

    # Explicit fresher/entry-level wording
    if any(
        keyword in text
        for keyword in [
            "fresher",
            "freshers",
            "entry level",
            "entry-level",
            "new grad",
            "new graduate",
            "graduate engineer"
        ]
    ):
        return True

    max_experience = extract_max_experience(
        text
    )

    # If experience isn't mentioned,
    # don't automatically reject it.
    if max_experience is None:
        return True

    return (
        max_experience
        <= MAX_YEARS_EXPERIENCE
    )


# ============================================================
# SKILL DETECTION
# ============================================================

def detect_skills(job):

    text = get_job_text(
        job
    )

    found = []

    for skill in SKILL_KEYWORDS:

        if skill in text:

            if skill not in found:

                found.append(
                    skill
                )

    return found[:8]


# ============================================================
# LOCATION MATCH
# ============================================================

def location_match(job):

    location = job.get(
        "location",
        ""
    ).lower()

    return any(
        location_keyword in location
        for location_keyword
        in PREFERRED_LOCATIONS
    )


# ============================================================
# MATCH SCORE
# ============================================================

def score_job(job, skills):

    title = job.get(
        "title",
        ""
    ).lower()

    text = get_job_text(
        job
    )

    score = 0

    reasons = []

    # Target role
    if any(
        keyword in title
        for keyword in [
            "sde",
            "software engineer",
            "software development engineer",
            "software developer",
            "associate software engineer",
            "ase"
        ]
    ):

        score += 30

        reasons.append(
            "Target software engineering role"
        )

    # Java
    if "java" in text:

        score += 20

        reasons.append(
            "Java mentioned"
        )

    # Spring Boot
    if "spring boot" in text:

        score += 15

        reasons.append(
            "Spring Boot mentioned"
        )

    elif "spring" in text:

        score += 10

        reasons.append(
            "Spring mentioned"
        )

    # Backend/full stack
    if any(
        keyword in text
        for keyword in [
            "backend",
            "back-end",
            "full stack",
            "fullstack"
        ]
    ):

        score += 15

        reasons.append(
            "Backend / Full Stack focus"
        )

    # Fresher
    if any(
        keyword in text
        for keyword in [
            "fresher",
            "freshers",
            "entry level",
            "entry-level",
            "new grad",
            "new graduate",
            "graduate"
        ]
    ):

        score += 15

        reasons.append(
            "Fresher / entry-level"
        )

    # Preferred location
    if location_match(job):

        score += 5

        reasons.append(
            "Preferred location"
        )

    return (
        min(score, 100),
        reasons
    )


# ============================================================
# TIME SINCE POSTING
# ============================================================

def minutes_since(timestamp):

    if not timestamp:
        return None

    try:

        timestamp = timestamp.replace(
            "Z",
            "+00:00"
        )

        posted = datetime.fromisoformat(
            timestamp
        )

        if posted.tzinfo is None:

            posted = posted.replace(
                tzinfo=timezone.utc
            )

        delta = (
            datetime.now(timezone.utc)
            - posted
        )

        return max(
            int(
                delta.total_seconds()
                / 60
            ),
            0
        )

    except Exception:

        return None


# ============================================================
# TELEGRAM MESSAGE
# ============================================================

def format_job_message(job):

    mins = minutes_since(
        job.get("posted")
    )

    if mins is None:

        detected = (
            "Recently detected"
        )

    else:

        detected = (
            f"{mins} minutes after posting"
        )

    skills = job.get(
        "skills",
        []
    )

    if skills:

        skills_text = " • ".join(
            skill.title()
            for skill in skills
        )

    else:

        skills_text = (
            "Not specified"
        )

    reasons = job.get(
        "reasons",
        []
    )

    if reasons:

        reasons_text = "\n".join(
            f"✓ {reason}"
            for reason in reasons
        )

    else:

        reasons_text = (
            "✓ Keyword match"
        )

    return (
        "🚨 <b>NEW JOB MATCH</b>\n\n"

        f"🏢 <b>COMPANY</b>\n"
        f"{job['company']}\n\n"

        f"💼 <b>ROLE</b>\n"
        f"{job['title']}\n\n"

        f"📍 <b>LOCATION</b>\n"
        f"{job['location']}\n\n"

        "🎓 <b>EXPERIENCE</b>\n"
        "Fresher / 0–2 years\n\n"

        f"🛠 <b>SKILLS</b>\n"
        f"{skills_text}\n\n"

        "━━━━━━━━━━━━━━\n"

        f"⭐ <b>MATCH SCORE</b>: "
        f"{job['score']}/100\n"

        f"🔵 <b>SOURCE</b>: "
        f"{job['authenticity']}\n"

        f"🕒 <b>DETECTED</b>: "
        f"{detected}\n\n"

        "<b>WHY IT MATCHES</b>\n"
        f"{reasons_text}"
    )


# ============================================================
# TELEGRAM SEND
# ============================================================

def send_telegram(job):

    if not TELEGRAM_BOT_TOKEN:

        print(
            "ERROR: TELEGRAM_BOT_TOKEN "
            "is missing."
        )

        return False

    if not TELEGRAM_CHAT_ID:

        print(
            "ERROR: TELEGRAM_CHAT_ID "
            "is missing."
        )

        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/"
        f"sendMessage"
    )

    text = format_job_message(
        job
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🚀 APPLY NOW",
                    "url": job["url"]
                }
            ],
            [
                {
                    "text": "🏢 COMPANY CAREERS",
                    "url": (
                        job.get(
                            "career_url"
                        )
                        or job["url"]
                    )
                }
            ]
        ]
    }

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": keyboard
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=20
        )

        response.raise_for_status()

        result = response.json()

        if not result.get("ok"):

            print(
                "Telegram API error:",
                result
            )

            return False

        return True

    except Exception as exc:

        print(
            f"Telegram ERROR: {exc}"
        )

        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=========================================="
    )

    print(
        "        PERSONAL JOB ALERT BOT v2"
    )

    print(
        "=========================================="
    )

    print(
        "Source mode: OFFICIAL ATS ONLY"
    )

    print(
        "Adzuna: DISABLED"
    )

    print()

    # --------------------------------------------------------
    # Load configuration
    # --------------------------------------------------------

    companies = load_companies()

    seen = load_seen()

    print(
        f"Previously seen jobs: "
        f"{len(seen)}"
    )

    print()

    # --------------------------------------------------------
    # Fetch jobs
    # --------------------------------------------------------

    all_jobs = fetch_all_jobs(
        companies
    )

    all_jobs = deduplicate_jobs(
        all_jobs
    )

    print()

    print(
        f"Fetched {len(all_jobs)} "
        f"unique jobs."
    )

    # --------------------------------------------------------
    # Filter
    # --------------------------------------------------------

    matches = []

    for job in all_jobs:

        if not matches_role(job):
            continue

        if not matches_experience(job):
            continue

        if job["id"] in seen:
            continue

        skills = detect_skills(
            job
        )

        score, reasons = score_job(
            job,
            skills
        )

        job["skills"] = skills
        job["score"] = score
        job["reasons"] = reasons

        matches.append(
            job
        )

    # Highest match first
    matches.sort(
        key=lambda job: job["score"],
        reverse=True
    )

    print(
        f"New matching jobs: "
        f"{len(matches)}"
    )

    print()

    # --------------------------------------------------------
    # Telegram
    # --------------------------------------------------------

    sent = 0

    for job in matches:

        print(
            f"[{job['score']}/100] "
            f"{job['company']} - "
            f"{job['title']}"
        )

        success = send_telegram(
            job
        )

        if success:

            seen.add(
                job["id"]
            )

            sent += 1

        time.sleep(0.5)

    # --------------------------------------------------------
    # Save state
    # --------------------------------------------------------

    save_seen(
        seen
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()

    print(
        "=========================================="
    )

    print(
        f"Fetched: {len(all_jobs)}"
    )

    print(
        f"New matches: {len(matches)}"
    )

    print(
        f"Telegram alerts sent: {sent}"
    )

    print(
        f"Seen jobs stored: {len(seen)}"
    )

    print(
        "=========================================="
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()