import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set

import requests

from sources.multi_ats import fetch_all


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"

COMPANIES_FILE = CONFIG_DIR / "companies.json"
STATE_FILE = DATA_DIR / "seen_jobs.json"


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Optional: multiple users
# Example:
# TELEGRAM_CHAT_IDS=123456789,987654321
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")


# ============================================================
# JOB FILTER CONFIG
# ============================================================

MAX_YEARS_EXPERIENCE = 2

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
    "remote",
]

INCLUDE_KEYWORDS = [
    "software engineer",
    "software developer",
    "software development engineer",
    "sde",
    "sde i",
    "sde-1",
    "sde 1",
    "associate software engineer",
    "ase",
    "java developer",
    "java engineer",
    "backend engineer",
    "backend developer",
    "full stack engineer",
    "full stack developer",
    "fullstack engineer",
    "fullstack developer",
    "graduate engineer trainee",
    "graduate software engineer",
    "graduate developer",
    "entry level",
    "entry-level",
    "new grad",
    "software engineer intern",
    "backend intern",
    "developer intern",
]

EXCLUDE_KEYWORDS = [
    "senior",
    "sr.",
    "sr ",
    "staff",
    "principal",
    "lead",
    "manager",
    "director",
    "head of",
    "architect",
    "sde-2",
    "sde 2",
    "sde-3",
    "sde 3",
    "3+ years",
    "4+ years",
    "5+ years",
    "6+ years",
    "7+ years",
    "8+ years",
    "9+ years",
    "10+ years",
    "11+ years",
    "12+ years",
]


SKILL_KEYWORDS = {
    "Java": [
        "java",
    ],
    "Spring Boot": [
        "spring boot",
    ],
    "Spring": [
        "spring",
    ],
    "Hibernate": [
        "hibernate",
    ],
    "SQL": [
        "sql",
    ],
    "PostgreSQL": [
        "postgresql",
        "postgres",
    ],
    "MySQL": [
        "mysql",
    ],
    "MongoDB": [
        "mongodb",
        "mongo",
    ],
    "Microservices": [
        "microservices",
        "microservice",
    ],
    "REST API": [
        "rest api",
        "restful",
        "rest api",
    ],
    "Kafka": [
        "kafka",
    ],
    "Redis": [
        "redis",
    ],
    "Docker": [
        "docker",
    ],
    "Kubernetes": [
        "kubernetes",
        "k8s",
    ],
    "AWS": [
        "aws",
        "amazon web services",
    ],
    "Azure": [
        "azure",
    ],
    "GCP": [
        "gcp",
        "google cloud",
    ],
    "React": [
        "react",
        "react.js",
        "reactjs",
    ],
    "JavaScript": [
        "javascript",
        "js",
    ],
    "TypeScript": [
        "typescript",
        "ts",
    ],
    "Python": [
        "python",
    ],
    "Git": [
        "git",
        "github",
    ],
    "DSA": [
        "data structures",
        "algorithms",
        "dsa",
    ],
    "System Design": [
        "system design",
    ],
}


# ============================================================
# HELPERS
# ============================================================

def ensure_directories():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_companies() -> List[Dict]:
    """
    New companies.json format:

    {
      "companies": [
        {
          "name": "Postman",
          "source": "greenhouse",
          "slug": "postman",
          "careers_url": "https://www.postman.com/careers/",
          "enabled": true
        }
      ]
    }
    """

    if not COMPANIES_FILE.exists():
        print(f"ERROR: Companies file not found: {COMPANIES_FILE}")
        return []

    try:
        with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"ERROR loading companies.json: {e}")
        return []

    companies = config.get("companies", [])

    if not isinstance(companies, list):
        print("ERROR: 'companies' must be a list in companies.json")
        return []

    enabled_companies = []

    for company in companies:
        if not isinstance(company, dict):
            continue

        if company.get("enabled", True) is False:
            continue

        if not company.get("name"):
            continue

        enabled_companies.append(company)

    return enabled_companies


def load_seen_jobs() -> Set[str]:
    if not STATE_FILE.exists():
        return set()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(str(x) for x in data)

        if isinstance(data, dict):
            jobs = data.get("seen_jobs", [])
            return set(str(x) for x in jobs)

    except Exception as e:
        print(f"WARNING: Could not load seen jobs: {e}")

    return set()


def save_seen_jobs(seen_jobs: Set[str]):
    ensure_directories()

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                sorted(seen_jobs),
                f,
                indent=2,
                ensure_ascii=False,
            )

    except Exception as e:
        print(f"ERROR saving seen jobs: {e}")


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", str(text))
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# JOB NORMALIZATION
# ============================================================

def get_job_text(job: Dict) -> str:
    parts = [
        job.get("title", ""),
        job.get("description", ""),
        job.get("location", ""),
        job.get("department", ""),
        job.get("team", ""),
        job.get("employment_type", ""),
    ]

    return clean_text(" ".join(str(x) for x in parts)).lower()


def extract_experience_years(text: str):
    """
    Attempts to extract explicit experience requirements.

    Examples:
        0-2 years
        1-3 years
        2+ years
        3 years experience
        minimum 2 years
    """

    patterns = [
        r"(\d+)\s*[-–]\s*(\d+)\s*years?",
        r"(\d+)\s*\+\s*years?",
        r"(\d+)\s*years?\s*(?:of)?\s*experience",
        r"minimum\s*(?:of\s*)?(\d+)\s*years?",
        r"at least\s*(\d+)\s*years?",
    ]

    matches = []

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()

            try:
                if len(groups) >= 2 and groups[1]:
                    minimum = int(groups[0])
                    maximum = int(groups[1])
                    matches.append((minimum, maximum))
                else:
                    minimum = int(groups[0])
                    matches.append((minimum, minimum))
            except Exception:
                continue

    if not matches:
        return None

    # Return the lowest minimum experience requirement found.
    return min(matches, key=lambda x: x[0])


def is_experience_eligible(job: Dict) -> bool:
    """
    Keep fresher / entry-level / 0-2 YOE jobs.

    Jobs with no explicit experience requirement are allowed,
    because many fresher jobs do not mention experience.
    """

    text = get_job_text(job)

    experience = extract_experience_years(text)

    if experience is None:
        return True

    minimum_years, maximum_years = experience

    if minimum_years > MAX_YEARS_EXPERIENCE:
        return False

    return True


# ============================================================
# ROLE FILTER
# ============================================================

def is_role_eligible(job: Dict) -> bool:
    title = clean_text(job.get("title", "")).lower()

    if not title:
        return False

    # Exclude clearly senior roles first.
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in title:
            return False

    # Then require one of our target roles.
    for keyword in INCLUDE_KEYWORDS:
        if keyword.lower() in title:
            return True

    return False


# ============================================================
# LOCATION FILTER
# ============================================================

def location_matches(job: Dict) -> bool:
    location = clean_text(job.get("location", "")).lower()

    # If no location is provided, don't reject automatically.
    if not location:
        return True

    for preferred in PREFERRED_LOCATIONS:
        if preferred.lower() in location:
            return True

    return False


# ============================================================
# SKILL MATCHING
# ============================================================

def extract_skills(job: Dict) -> List[str]:
    text = get_job_text(job)

    found = []

    for skill, keywords in SKILL_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                found.append(skill)
                break

    return found


# ============================================================
# MATCH SCORING
# ============================================================

def score_job(job: Dict):
    title = clean_text(job.get("title", "")).lower()
    location = clean_text(job.get("location", "")).lower()
    description = clean_text(job.get("description", "")).lower()

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Role score
    # --------------------------------------------------------

    if "software engineer" in title:
        score += 30
        reasons.append("Software Engineer role")

    elif "software developer" in title:
        score += 28
        reasons.append("Software Developer role")

    elif "sde" in title:
        score += 30
        reasons.append("SDE role")

    elif "associate software engineer" in title:
        score += 28
        reasons.append("ASE role")

    elif "backend" in title:
        score += 25
        reasons.append("Backend role")

    elif "full stack" in title or "fullstack" in title:
        score += 22
        reasons.append("Full Stack role")

    elif "java" in title:
        score += 25
        reasons.append("Java role")

    # --------------------------------------------------------
    # Fresher / entry-level
    # --------------------------------------------------------

    fresher_terms = [
        "fresher",
        "fresh graduate",
        "graduate",
        "new grad",
        "entry level",
        "entry-level",
        "0-1 years",
        "0-2 years",
        "1-2 years",
        "early career",
    ]

    for term in fresher_terms:
        if term in title or term in description:
            score += 20
            reasons.append("Fresher/entry-level indication")
            break

    # --------------------------------------------------------
    # Location
    # --------------------------------------------------------

    for location_keyword in PREFERRED_LOCATIONS:
        if location_keyword.lower() in location:
            score += 15
            reasons.append(f"Preferred location: {location_keyword}")
            break

    # --------------------------------------------------------
    # Skills
    # --------------------------------------------------------

    skills = extract_skills(job)

    skill_score = min(len(skills) * 4, 25)

    if skill_score:
        score += skill_score
        reasons.append(
            "Skills: " + ", ".join(skills[:6])
        )

    # --------------------------------------------------------
    # Direct Java preference
    # --------------------------------------------------------

    if "java" in title:
        score += 10
        reasons.append("Java explicitly mentioned in title")

    elif "java" in description:
        score += 5
        reasons.append("Java mentioned in description")

    # --------------------------------------------------------
    # Backend preference
    # --------------------------------------------------------

    if "backend" in title:
        score += 8
        reasons.append("Backend explicitly mentioned")

    # --------------------------------------------------------
    # Internship / irrelevant reduction
    # --------------------------------------------------------

    if "intern" in title:
        score -= 5

    return score, skills, reasons


# ============================================================
# JOB DEDUPLICATION
# ============================================================

def get_job_id(job: Dict) -> str:
    """
    Prefer stable source IDs.

    Falls back to URL, then a title/company combination.
    """

    source = str(job.get("source", "")).strip().lower()
    source_id = str(job.get("source_id", "")).strip()

    if source_id:
        return f"{source}:{source_id}"

    url = str(job.get("url", "")).strip()

    if url:
        return url

    company = str(job.get("company", "")).strip().lower()
    title = str(job.get("title", "")).strip().lower()

    return f"{company}|{title}"


def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    unique = {}
    duplicates = 0

    for job in jobs:
        job_id = get_job_id(job)

        if job_id in unique:
            duplicates += 1
            continue

        job["id"] = job_id
        unique[job_id] = job

    print(f"Unique jobs: {len(unique)}")
    print(f"Duplicates removed: {duplicates}")

    return list(unique.values())


# ============================================================
# AUTHENTICITY
# ============================================================

def get_authenticity(job: Dict) -> str:
    source = str(job.get("source", "")).lower()

    if source in {
        "greenhouse",
        "lever",
        "workday",
        "smartrecruiters",
        "ashby",
        "company_native",
        "json_ld",
    }:
        return "Official company careers source"

    return "Official career source"


# ============================================================
# TELEGRAM MESSAGE
# ============================================================

def escape_markdown(text: str) -> str:
    """
    Telegram MarkdownV2 escaping.
    """

    if text is None:
        return ""

    text = str(text)

    special_chars = r"_*[]()~`>#+-=|{}.!"

    for char in special_chars:
        text = text.replace(char, "\\" + char)

    return text


def format_job_message(job: Dict) -> str:
    company = escape_markdown(job.get("company", "Unknown Company"))
    title = escape_markdown(job.get("title", "Unknown Role"))
    location = escape_markdown(job.get("location", "Not specified"))

    skills = job.get("skills", [])

    if skills:
        skills_text = escape_markdown(", ".join(skills))
    else:
        skills_text = "Not specified"

    score = job.get("score", 0)

    authenticity = escape_markdown(
        job.get(
            "authenticity",
            "Official company careers source",
        )
    )

    posted = escape_markdown(
        str(job.get("posted", "Not specified"))
    )

    reasons = job.get("reasons", [])

    reason_text = ""

    if reasons:
        reason_text = "\n".join(
            f"• {escape_markdown(reason)}"
            for reason in reasons[:5]
        )

    url = job.get("url", "")

    career_url = job.get("career_url") or url

    message = (
        "🚨 *NEW JOB MATCH*\n\n"
        f"*{company}*\n"
        f"*{title}*\n\n"
        f"📍 {location}\n"
        f"🎯 Match Score: *{score}*\n"
        f"🛠 Skills: {skills_text}\n"
        f"🕒 Posted: {posted}\n"
        f"🔐 Source: {authenticity}\n\n"
    )

    if reason_text:
        message += "*Why it matched:*\n"
        message += reason_text
        message += "\n\n"

    if url:
        message += f"👉 *[APPLY DIRECTLY]({url})*\n"

    if career_url and career_url != url:
        message += f"🌐 *[Company Careers]({career_url})*\n"

    return message


# ============================================================
# TELEGRAM SEND
# ============================================================

def get_chat_ids() -> List[str]:
    """
    Supports both:

    TELEGRAM_CHAT_ID=123456789

    OR

    TELEGRAM_CHAT_IDS=123456789,987654321
    """

    ids = []

    if TELEGRAM_CHAT_ID.strip():
        ids.append(TELEGRAM_CHAT_ID.strip())

    if TELEGRAM_CHAT_IDS.strip():
        ids.extend(
            x.strip()
            for x in TELEGRAM_CHAT_IDS.split(",")
            if x.strip()
        )

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(ids))


def send_telegram(job: Dict) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not configured.")
        return False

    chat_ids = get_chat_ids()

    if not chat_ids:
        print("ERROR: No Telegram chat ID configured.")
        return False

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    # Use plain text first.
    # This avoids MarkdownV2 parsing errors caused by
    # company/job titles containing characters such as
    # -, (, ), ., /, +, etc.
    message = (
        f"🚨 NEW JOB MATCH\n\n"
        f"Company: {job.get('company', 'Unknown')}\n"
        f"Role: {job.get('title', 'Unknown')}\n"
        f"Location: {job.get('location', 'Not specified')}\n"
        f"Match Score: {job.get('score', 0)}\n"
        f"Skills: {', '.join(job.get('skills', [])) or 'Not specified'}\n"
        f"Posted: {job.get('posted', 'Not specified')}\n"
        f"Source: {job.get('authenticity', 'Official career source')}\n\n"
    )

    reasons = job.get("reasons", [])

    if reasons:
        message += "Why it matched:\n"

        for reason in reasons[:5]:
            message += f"• {reason}\n"

        message += "\n"

    apply_url = job.get("url", "")
    career_url = job.get("career_url") or apply_url

    if apply_url:
        message += f"APPLY DIRECTLY:\n{apply_url}\n\n"

    if career_url and career_url != apply_url:
        message += f"COMPANY CAREERS:\n{career_url}\n"

    success = True

    for chat_id in chat_ids:

        payload = {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=30,
            )

            # Don't hide Telegram's actual error.
            if not response.ok:
                print(
                    f"Telegram API error for {chat_id}: "
                    f"{response.status_code} "
                    f"{response.text}"
                )
                success = False
                continue

            data = response.json()

            if not data.get("ok"):
                print(
                    f"Telegram API error for {chat_id}: "
                    f"{data}"
                )
                success = False
                continue

            print(
                f"Telegram alert sent to {chat_id}: "
                f"{job.get('title')}"
            )

        except Exception as e:
            print(
                f"Telegram error for {chat_id}: {e}"
            )
            success = False

    return success


# ============================================================
# FILTER + SCORE
# ============================================================

def process_jobs(
    jobs: List[Dict],
    seen_jobs: Set[str],
):
    matched = []
    already_seen = 0
    rejected_role = 0
    rejected_experience = 0
    rejected_location = 0

    for job in jobs:

        job_id = get_job_id(job)

        if job_id in seen_jobs:
            already_seen += 1
            continue

        # ----------------------------------------------------
        # Role
        # ----------------------------------------------------

        if not is_role_eligible(job):
            rejected_role += 1
            continue

        # ----------------------------------------------------
        # Experience
        # ----------------------------------------------------

        if not is_experience_eligible(job):
            rejected_experience += 1
            continue

        # ----------------------------------------------------
        # Location
        # ----------------------------------------------------

        if not location_matches(job):
            rejected_location += 1
            continue

        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        score, skills, reasons = score_job(job)

        job["id"] = job_id
        job["score"] = score
        job["skills"] = skills
        job["reasons"] = reasons
        job["authenticity"] = get_authenticity(job)

        matched.append(job)

    matched.sort(
        key=lambda x: x.get("score", 0),
        reverse=True,
    )

    print()
    print("========== FILTER RESULTS ==========")
    print(f"Total jobs fetched: {len(jobs)}")
    print(f"Already seen: {already_seen}")
    print(f"Rejected role: {rejected_role}")
    print(f"Rejected experience: {rejected_experience}")
    print(f"Rejected location: {rejected_location}")
    print(f"New matching jobs: {len(matched)}")
    print("====================================")
    print()

    return matched


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("==========================================")
    print("       JOB ALERT BOT")
    print("       Multi-ATS Edition")
    print("==========================================")
    print()

    ensure_directories()

    # --------------------------------------------------------
    # Load companies
    # --------------------------------------------------------

    companies = load_companies()

    print(
        f"Companies configured: {len(companies)}"
    )

    if not companies:
        print("No enabled companies found.")
        return

    # --------------------------------------------------------
    # Load seen state
    # --------------------------------------------------------

    seen_jobs = load_seen_jobs()

    print(
        f"Previously seen jobs: {len(seen_jobs)}"
    )
    print()

    # --------------------------------------------------------
    # Fetch from ALL configured ATS sources
    #
    # Greenhouse
    # Lever
    # Workday
    # SmartRecruiters
    # Ashby
    # Company Native
    # JSON-LD fallback
    # --------------------------------------------------------

    print("Fetching jobs from configured sources...")
    print()

    try:
        all_jobs = fetch_all(companies)
    except Exception as e:
        print(f"ERROR fetching jobs: {e}")
        return

    print()
    print(
        f"Total jobs collected from sources: "
        f"{len(all_jobs)}"
    )
    print()

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    all_jobs = deduplicate_jobs(all_jobs)

    # --------------------------------------------------------
    # Filter + Score
    # --------------------------------------------------------

    matching_jobs = process_jobs(
        all_jobs,
        seen_jobs,
    )

    # --------------------------------------------------------
    # Send Telegram alerts
    # --------------------------------------------------------

    if not matching_jobs:
        print("No new matching jobs found.")
        save_seen_jobs(seen_jobs)
        return

    print(
        f"Sending {len(matching_jobs)} "
        f"new job alerts..."
    )
    print()

    successfully_sent = 0

    for job in matching_jobs:

        print(
            f"Sending: "
            f"{job.get('company')} - "
            f"{job.get('title')}"
        )

        success = send_telegram(job)

        if success:
            seen_jobs.add(
                get_job_id(job)
            )
            successfully_sent += 1

    # --------------------------------------------------------
    # Save state
    # --------------------------------------------------------

    save_seen_jobs(seen_jobs)

    print()
    print("==========================================")
    print("RUN COMPLETE")
    print(f"Alerts sent: {successfully_sent}")
    print(f"Seen jobs stored: {len(seen_jobs)}")
    print("==========================================")
    print()


if __name__ == "__main__":
    main()