#!/usr/bin/env python3
"""
Personal Job Alert Bot
-----------------------
Fetches fresh job postings from *genuine* sources (company ATS boards +
Adzuna aggregator), filters them against your profile, scores each match,
and pushes a formatted "job match card" to your Telegram bot with a tappable
Apply button.

Genuine-link sources used:
  1. Greenhouse public job board API   -> link is the real company apply page
  2. Lever public job board API        -> link is the real company apply page
  3. Adzuna API (free tier)            -> aggregator, but redirect_url points
                                           to the employer's own posting

No LinkedIn/Naukri scraping is used — that violates their ToS and links rot fast.

SETUP (see README.md for full steps):
  1. pip install requests
  2. Set these as environment variables (or edit the CONFIG block below):
       TELEGRAM_BOT_TOKEN
       TELEGRAM_CHAT_ID
       ADZUNA_APP_ID      (optional, free at https://developer.adzuna.com/)
       ADZUNA_APP_KEY     (optional)
  3. Edit GREENHOUSE_COMPANIES / LEVER_COMPANIES below with the company
     slugs you actually want to track (verify each slug works before relying
     on it — see README).
  4. Run: python job_alert.py
  5. For automatic recurring alerts, wire this into GitHub Actions
     (workflow file provided) so it runs on a schedule for free, no server.

Note on the "Save Job" button seen in some UI mockups: a save/callback
button requires a bot that stays online listening for button presses
(a webhook or long-polling process), which is a different setup than this
scheduled script. This script sends a real "Apply Directly" link-button
(no server needed for that, since it just opens a URL) and skips Save.
"""

import os
import re
import json
import time
import requests
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# CONFIG — edit this section
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRY = "in"  # India

# Greenhouse board slugs — find a company's slug by checking if
# https://boards.greenhouse.io/<slug> resolves to their careers page.
GREENHOUSE_COMPANIES = [
    # "razorpay",
    # "cred",
    # "meesho",
    # add verified slugs here
]

# Lever company slugs — check https://jobs.lever.co/<slug>
LEVER_COMPANIES = [
    # "some-company",
]

# Keywords that define YOUR target roles (profile: Java backend / full-stack,
# SDE-1 / ASE level, product companies). Edit freely.
INCLUDE_KEYWORDS = [
    "sde", "sde-1", "sde1", "software engineer", "software development engineer",
    "associate software engineer", "ase", "java developer", "java backend",
    "backend engineer", "backend developer", "full stack", "fullstack",
    "spring boot", "graduate engineer trainee", "software engineer i",
    "software developer intern" , "software engineer intern", "java intern", "backend intern",
]

EXCLUDE_KEYWORDS = [
    "senior", "sr.", "staff", "principal", "lead", "manager", "architect",
    "sde-3", "sde3", "sde-2", "sde2", "10+ years", "8+ years",
]

# Skills to detect in the title/description and show on the card
SKILL_KEYWORDS = [
    "java", "spring boot", "spring", "sql", "postgresql", "mysql", "mongodb",
    "microservices", "rest api", "kafka", "redis", "docker", "kubernetes",
    "aws", "react", "node.js", "javascript", "typescript", "python", "git",
    "hibernate", "system design", "data structures", "dsa",
]

# Roughly matches "fresher / 0-2 yrs" experience band when experience info exists
MAX_YEARS_EXPERIENCE = 2

STATE_FILE = "seen_jobs.json"  # tracks already-alerted job IDs so you don't get repeats

# ---------------------------------------------------------------------------
# STATE (dedupe across runs)
# ---------------------------------------------------------------------------

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

# ---------------------------------------------------------------------------
# FETCHERS — each returns a list of normalized dicts
# ---------------------------------------------------------------------------

def strip_html(raw_html):
    if not raw_html:
        return ""
    return re.sub("<[^<]+?>", " ", raw_html)

def fetch_greenhouse(company):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[greenhouse:{company}] fetch failed: {e}")
        return []

    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "id": f"gh_{company}_{j['id']}",
            "title": j.get("title", ""),
            "company": company.capitalize(),
            "location": (j.get("location") or {}).get("name", "N/A"),
            "url": j.get("absolute_url", ""),
            "source": "Greenhouse",
            "authenticity": "✅ Official Careers",
            "posted": j.get("updated_at", ""),
            "description": strip_html(j.get("content", "")),
        })
    return jobs

def fetch_lever(company):
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[lever:{company}] fetch failed: {e}")
        return []

    jobs = []
    for j in data:
        desc = j.get("descriptionPlain") or strip_html(j.get("description", ""))
        jobs.append({
            "id": f"lv_{company}_{j.get('id')}",
            "title": j.get("text", ""),
            "company": company.capitalize(),
            "location": (j.get("categories") or {}).get("location", "N/A"),
            "url": j.get("hostedUrl", ""),
            "source": "Lever",
            "authenticity": "✅ Official Careers",
            "posted": j.get("createdAt", ""),
            "description": desc,
        })
    return jobs

def fetch_adzuna(query="java backend developer", location="India", max_results=30):
    if not (ADZUNA_APP_ID and ADZUNA_APP_KEY):
        return []
    url = (
        f"https://api.adzuna.com/v1/api/jobs/{ADZUNA_COUNTRY}/search/1"
        f"?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}"
        f"&results_per_page={max_results}&what={requests.utils.quote(query)}"
        f"&content-type=application/json"
    )
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[adzuna] fetch failed: {e}")
        return []

    jobs = []
    for j in data.get("results", []):
        jobs.append({
            "id": f"adz_{j.get('id')}",
            "title": j.get("title", ""),
            "company": (j.get("company") or {}).get("display_name", "N/A"),
            "location": (j.get("location") or {}).get("display_name", "N/A"),
            "url": j.get("redirect_url", ""),
            "source": "Adzuna",
            "authenticity": "🔎 Aggregator — verify on employer site",
            "posted": j.get("created", ""),
            "description": strip_html(j.get("description", "")),
        })
    return jobs

# ---------------------------------------------------------------------------
# FILTERING + SCORING
# ---------------------------------------------------------------------------

def matches_profile(job):
    title = job["title"].lower()

    if not any(k in title for k in INCLUDE_KEYWORDS):
        return False
    if any(k in title for k in EXCLUDE_KEYWORDS):
        return False

    m = re.search(r"(\d+)\s*\+?\s*(?:-\s*\d+\s*)?years?", title)
    if m and int(m.group(1)) > MAX_YEARS_EXPERIENCE:
        return False

    return True

def detect_skills(job):
    blob = (job["title"] + " " + job.get("description", "")).lower()
    found = []
    for skill in SKILL_KEYWORDS:
        if skill in blob and skill.title() not in found:
            found.append(skill.title() if skill != "sql" else skill.upper())
    return found[:6]  # keep the card readable

def score_job(job, skills):
    """Very rough transparent scoring — not a magic AI score, just a
    weighted match against your stated profile, so you can trust what it means."""
    blob = (job["title"] + " " + job.get("description", "")).lower()
    reasons = []
    score = 0

    if any(k in job["title"].lower() for k in ["sde", "software engineer", "software development engineer", "ase", "associate software engineer"]):
        score += 30
        reasons.append("Exact target role matched")

    if "java" in blob:
        score += 20
        reasons.append("Java in stack")
    if "spring" in blob:
        score += 15
        reasons.append("Spring / Spring Boot in stack")
    if any(k in blob for k in ["full stack", "fullstack", "backend"]):
        score += 15
        reasons.append("Backend / full-stack focus")

    if re.search(r"\b0\s*-\s*2\b|\bfresher\b|\b0\s*-\s*1\b|\b1\s*-\s*2\b", blob):
        score += 15
        reasons.append("0–2 YOE / fresher focus")
    elif not re.search(r"\d+\s*\+?\s*years?", blob):
        score += 5  # no experience mentioned — neutral, small credit

    if any(k in blob for k in ["india", "bangalore", "bengaluru", "delhi", "gurugram", "gurgaon", "hyderabad", "pune"]):
        score += 5
        reasons.append("India location")

    return min(score, 100), reasons

def minutes_since(iso_timestamp):
    if not iso_timestamp:
        return None
    try:
        ts = iso_timestamp.replace("Z", "+00:00")
        posted = datetime.fromisoformat(ts)
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - posted
        return max(int(delta.total_seconds() // 60), 0)
    except Exception:
        return None

# ---------------------------------------------------------------------------
# TELEGRAM
# ---------------------------------------------------------------------------

def send_job_card(job, score, reasons, skills):
    text = format_job_message(job, score, reasons, skills)

    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram not configured — printing instead:\n", text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    reply_markup = {
        "inline_keyboard": [
            [{"text": "🚀 Apply Directly", "url": job["url"]}]
        ]
    }

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": json.dumps(reply_markup),
    }
    r = requests.post(url, data=payload, timeout=15)
    if not r.ok:
        print("Telegram send failed:", r.text)

def format_job_message(job, score, reasons, skills):
    mins = minutes_since(job.get("posted"))
    detected = f"{mins} minutes after posting" if mins is not None else "just now"
    skills_line = " • ".join(skills) if skills else "Not specified in listing"
    reasons_lines = "\n".join(f"✓ {r}" for r in reasons) if reasons else "✓ Keyword match"

    return (
        "🚀 <b>NEW JOB MATCH</b>\n\n"
        f"🏢 <b>COMPANY</b>\n{job['company']}\n\n"
        f"💼 <b>ROLE</b>\n{job['title']}\n\n"
        f"📍 <b>LOCATION</b>: {job['location']}\n"
        f"🎓 <b>EXPERIENCE</b>: 0-2 years (est.)\n\n"
        f"🛠 <b>SKILLS</b>\n{skills_line}\n"
        "━━━━━━━━━━━━━━\n"
        f"⭐ <b>MATCH SCORE</b>: {score}/100\n"
        f"🔵 <b>AUTHENTICITY</b>: {job['authenticity']}\n"
        f"🕒 <b>DETECTED</b>: {detected}\n\n"
        f"<b>WHY IT MATCHES</b>\n{reasons_lines}\n"
    )

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    seen = load_seen()
    all_jobs = []

    for c in GREENHOUSE_COMPANIES:
        all_jobs.extend(fetch_greenhouse(c))
    for c in LEVER_COMPANIES:
        all_jobs.extend(fetch_lever(c))

    for q in ["java backend developer fresher", "sde 1 java", "associate software engineer"]:
        all_jobs.extend(fetch_adzuna(query=q))
        time.sleep(1)  # be polite to the API

    new_matches = [j for j in all_jobs if matches_profile(j) and j["id"] not in seen]

    print(f"Fetched {len(all_jobs)} total, {len(new_matches)} new matches.")

    if not new_matches:
        return

    for job in new_matches:
        skills = detect_skills(job)
        score, reasons = score_job(job, skills)
        send_job_card(job, score, reasons, skills)
        seen.add(job["id"])
        time.sleep(0.5)  # avoid Telegram rate limits

    save_seen(seen)

if __name__ == "__main__":
    main()
