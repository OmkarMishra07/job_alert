import re


class ProfileFilter:

    def __init__(self, profile):
        self.max_years = profile["max_years_experience"]
        self.include = [
            x.lower()
            for x in profile["include_keywords"]
        ]
        self.exclude = [
            x.lower()
            for x in profile["exclude_keywords"]
        ]
        self.skills = [
            x.lower()
            for x in profile["skill_keywords"]
        ]
        self.locations = [
            x.lower()
            for x in profile["preferred_locations"]
        ]

    def job_text(self, job):
        return (
            f"{job.get('title', '')} "
            f"{job.get('description', '')} "
            f"{job.get('location', '')}"
        ).lower()

    def matches_role(self, job):

        title = job.get("title", "").lower()

        if not any(
            keyword in title
            for keyword in self.include
        ):
            return False

        if any(
            keyword in title
            for keyword in self.exclude
        ):
            return False

        return True

    def experience_years(self, text):

        patterns = [
            r"(\d+)\s*-\s*(\d+)\s*years?",
            r"(\d+)\s*\+\s*years?",
            r"(\d+)\s*years?"
        ]

        for pattern in patterns:

            match = re.search(pattern, text)

            if not match:
                continue

            try:
                return int(match.group(1))
            except ValueError:
                pass

        return None

    def matches_experience(self, job):

        text = self.job_text(job)

        years = self.experience_years(text)

        if years is not None:
            return years <= self.max_years

        return True

    def detect_skills(self, job):

        text = self.job_text(job)

        found = []

        for skill in self.skills:

            if skill in text and skill not in found:
                found.append(skill)

        return found[:8]

    def location_match(self, job):

        location = job.get(
            "location",
            ""
        ).lower()

        return any(
            loc in location
            for loc in self.locations
        )

    def score(self, job, skills):

        title = job.get(
            "title",
            ""
        ).lower()

        text = self.job_text(job)

        score = 0
        reasons = []

        if any(
            x in title
            for x in [
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
                "Target software-engineering role"
            )

        if "java" in text:
            score += 20
            reasons.append("Java")

        if "spring boot" in text:
            score += 15
            reasons.append("Spring Boot")

        elif "spring" in text:
            score += 10
            reasons.append("Spring")

        if any(
            x in text
            for x in [
                "backend",
                "back-end",
                "full stack",
                "fullstack"
            ]
        ):
            score += 15
            reasons.append("Backend / Full Stack")

        if re.search(
            r"\bfresher\b|0\s*-\s*1|0\s*-\s*2|1\s*-\s*2|entry[- ]level|new grad|graduate",
            text
        ):
            score += 15
            reasons.append(
                "Fresher / entry-level"
            )

        if self.location_match(job):
            score += 5
            reasons.append(
                "Preferred location"
            )

        return min(score, 100), reasons

    def process(self, job):

        if not self.matches_role(job):
            return None

        if not self.matches_experience(job):
            return None

        skills = self.detect_skills(job)

        score, reasons = self.score(
            job,
            skills
        )

        job["skills"] = skills
        job["match_score"] = score
        job["match_reasons"] = reasons

        return job