"""Shared payloads used by several test modules (pure data, no imports)."""

JOB_PAYLOAD = {
    "company_name": "Acme Corp",
    "position": "Backend Developer",
    "description": "Build and maintain REST APIs.",
    "required_skills": "Python, FastAPI, PostgreSQL",
    "required_experience": "2+ years",
}

WORKER_PAYLOAD = {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "resume_path": "/resumes/jane-doe.pdf",
}

INTERVIEW_PAYLOAD = {
    "interviewer": "Anna HR",
    "scheduled_at": "2026-09-15T10:00:00Z",
    "duration_minutes": 60,
    "status": "upcoming",
    "meeting_link": "https://meet.example.com/round-1",
    "notes": "Round 1 — backend deep dive.",
}