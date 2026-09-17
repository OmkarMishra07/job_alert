import requests
from datetime import datetime, timezone


class TelegramBot:

    def __init__(self, token, chat_id):

        self.token = token
        self.chat_id = chat_id

        self.base_url = (
            f"https://api.telegram.org/bot{token}"
        )

    def minutes_since(self, timestamp):

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
                int(delta.total_seconds() / 60),
                0
            )

        except Exception:
            return None

    def format_message(self, job):

        mins = self.minutes_since(
            job.get("posted")
        )

        if mins is None:
            detected = "Recently detected"
        else:
            detected = (
                f"{mins} minutes after posting"
            )

        skills = job.get(
            "skills",
            []
        )

        skills_text = (
            " • ".join(
                skill.title()
                for skill in skills
            )
            if skills
            else "Not specified"
        )

        reasons = job.get(
            "match_reasons",
            []
        )

        reasons_text = "\n".join(
            f"✓ {reason}"
            for reason in reasons
        )

        return (
            "🚨 <b>NEW JOB MATCH</b>\n\n"

            f"🏢 <b>COMPANY</b>\n"
            f"{job['company']}\n\n"

            f"💼 <b>ROLE</b>\n"
            f"{job['title']}\n\n"

            f"📍 <b>LOCATION</b>\n"
            f"{job['location']}\n\n"

            "🧑‍💻 <b>EXPERIENCE</b>\n"
            "Fresher / 0–2 years\n\n"

            f"🛠 <b>SKILLS</b>\n"
            f"{skills_text}\n\n"

            "━━━━━━━━━━━━━━\n"

            f"⭐ <b>MATCH</b>: "
            f"{job['match_score']}/100\n"

            f"🔵 <b>SOURCE</b>: "
            f"{job['authenticity']}\n"

            f"🕒 <b>DETECTED</b>: "
            f"{detected}\n\n"

            "<b>WHY IT MATCHES</b>\n"
            f"{reasons_text}"
        )

    def send_job(self, job):

        if not self.token or not self.chat_id:
            print(
                "Telegram credentials missing."
            )
            return False

        text = self.format_message(job)

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
                            job.get("career_url")
                            or job["url"]
                        )
                    }
                ],
                [
                    {
                        "text": "⭐ SAVE",
                        "callback_data": (
                            "save:"
                            + job["id"]
                        )
                    }
                ]
            ]
        }

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": keyboard
        }

        try:

            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=20
            )

            response.raise_for_status()

            return True

        except Exception as exc:

            print(
                f"Telegram ERROR: {exc}"
            )

            return False