import type { Application } from "../../types/application";

/**
 * Mock job applications. Each one links a candidate to a job plus the
 * simulated AI screening result shown on the Applications pages.
 */
export const mockApplications: Application[] = [
  {
    id: 1,
    job_id: 1,
    candidate_id: 1,
    candidate_name: "John Doe",
    candidate_email: "john.doe@example.com",
    status: "shortlisted",
    ai_score: 87,
    ai_summary:
      "Strong backend profile with production FastAPI experience. Top match for the Senior Python role.",
    matched_skills: ["Python", "FastAPI", "PostgreSQL", "REST API"],
    missing_skills: ["Docker"],
    submitted_at: "2026-09-04T10:10:00Z",
    resume_file_name: "John_Doe_Resume.pdf",
  },
  {
    id: 2,
    job_id: 1,
    candidate_id: 2,
    candidate_name: "Jane Smith",
    candidate_email: "jane.smith@example.com",
    status: "screening",
    ai_score: 72,
    ai_summary:
      "Solid Python foundation, limited FastAPI exposure. Worth a screening call to assess ramp-up speed.",
    matched_skills: ["Python", "PostgreSQL"],
    missing_skills: ["FastAPI", "REST API", "Docker"],
    submitted_at: "2026-09-03T08:40:00Z",
    resume_file_name: "Jane_Smith_CV.pdf",
  },
  {
    id: 3,
    job_id: 1,
    candidate_id: 3,
    candidate_name: "Michael Brown",
    candidate_email: "michael.brown@example.com",
    status: "screening",
    ai_score: 78,
    ai_summary:
      "Good all-round backend experience with strong REST fundamentals. FastAPI gap is closable.",
    matched_skills: ["Python", "REST API", "Docker"],
    missing_skills: ["FastAPI", "PostgreSQL"],
    submitted_at: "2026-09-01T16:05:00Z",
    resume_file_name: "Michael_Brown_Resume.pdf",
  },
  {
    id: 4,
    job_id: 2,
    candidate_id: 4,
    candidate_name: "Alice Brown",
    candidate_email: "alice.brown@example.com",
    status: "hired",
    ai_score: 90,
    ai_summary:
      "Excellent frontend profile covering every required skill. Recommended for offer.",
    matched_skills: ["React", "TypeScript", "JavaScript"],
    missing_skills: [],
    submitted_at: "2026-08-28T11:20:00Z",
    resume_file_name: "Alice_Brown_Resume.pdf",
  },
  {
    id: 5,
    job_id: 2,
    candidate_id: 5,
    candidate_name: "Bob Johnson",
    candidate_email: "bob.johnson@example.com",
    status: "new",
    ai_score: 61,
    ai_summary:
      "TypeScript-comfortable but thin React experience. Possible conversion candidate.",
    matched_skills: ["TypeScript"],
    missing_skills: ["React", "JavaScript"],
    submitted_at: "2026-08-27T13:15:00Z",
    resume_file_name: "Bob_Johnson_CV.pdf",
  },
  {
    id: 6,
    job_id: 3,
    candidate_id: 6,
    candidate_name: "Carol White",
    candidate_email: "carol.white@example.com",
    status: "shortlisted",
    ai_score: 82,
    ai_summary:
      "Strong DevOps track record across containers, orchestration and cloud delivery.",
    matched_skills: ["Docker", "AWS", "CI/CD", "Kubernetes"],
    missing_skills: [],
    submitted_at: "2026-08-20T09:30:00Z",
    resume_file_name: "Carol_White_Resume.pdf",
  },
  {
    id: 7,
    job_id: 3,
    candidate_id: 7,
    candidate_name: "David Lee",
    candidate_email: "david.lee@example.com",
    status: "rejected",
    ai_score: 44,
    ai_summary:
      "Early-stage DevOps exposure. Several core requirements missing for a senior role.",
    matched_skills: ["Docker"],
    missing_skills: ["Kubernetes", "AWS", "CI/CD"],
    submitted_at: "2026-08-19T14:45:00Z",
    resume_file_name: "David_Lee_Resume.pdf",
  },
  {
    id: 8,
    job_id: 4,
    candidate_id: 8,
    candidate_name: "Emma Green",
    candidate_email: "emma.green@example.com",
    status: "new",
    ai_score: 69,
    ai_summary:
      "Practical delivery and roadmapping skills with lighter strategy depth.",
    matched_skills: ["Agile", "Roadmapping"],
    missing_skills: ["Product Strategy"],
    submitted_at: "2026-08-12T10:00:00Z",
    resume_file_name: "Emma_Green_CV.pdf",
  },
  {
    id: 9,
    job_id: 5,
    candidate_id: 9,
    candidate_name: "Frank Black",
    candidate_email: "frank.black@example.com",
    status: "shortlisted",
    ai_score: 85,
    ai_summary:
      "Complete coverage of the data stack with strong hands-on reporting experience.",
    matched_skills: ["SQL", "Python", "Pandas", "Tableau"],
    missing_skills: [],
    submitted_at: "2026-08-05T15:10:00Z",
    resume_file_name: "Frank_Black_Resume.pdf",
  },
  {
    id: 10,
    job_id: 6,
    candidate_id: 10,
    candidate_name: "Grace Blue",
    candidate_email: "grace.blue@example.com",
    status: "screening",
    ai_score: 76,
    ai_summary:
      "Good testing mindset and Python skills; Selenium gap looks closable.",
    matched_skills: ["Python", "Testing"],
    missing_skills: ["Selenium"],
    submitted_at: "2026-07-30T11:45:00Z",
    resume_file_name: "Grace_Blue_Resume.pdf",
  },
];

export function getMockApplication(id: number): Application | undefined {
  return mockApplications.find((app) => app.id === id);
}
