import type { JobInput } from "../../types/job";

/**
 * Static demo jobs. Shapes mirror `JobResponse` from the backend so swapping in
 * real API data later is a find-and-replace of the store's initial value.
 * `leads_count` reflects the number of demo candidates per job.
 */
export const mockJobs: JobInput[] = [
  {
    id: 1,
    public_id: "550e8400-e29b-41d4-a716-446655440001",
    company_name: "Jafton Inc",
    position: "Senior Python Developer",
    description:
      "Build and maintain high-traffic REST APIs with Python and FastAPI, " +
      "working closely with product and data teams.",
    required_skills: "Python, FastAPI, PostgreSQL, REST API",
    required_experience: "3+ years",
    leads_count: 3,
    created_at: "2026-09-04T09:00:00Z",
  },
  {
    id: 2,
    public_id: "550e8400-e29b-41d4-a716-446655440002",
    company_name: "Acme Corp",
    position: "Frontend Engineer",
    description:
      "Craft responsive, accessible product UIs with React and TypeScript " +
      "across a growing SaaS platform.",
    required_skills: "React, TypeScript, JavaScript",
    required_experience: "2+ years",
    leads_count: 2,
    created_at: "2026-08-28T09:00:00Z",
  },
  {
    id: 3,
    public_id: "550e8400-e29b-41d4-a716-446655440003",
    company_name: "Unicon Soft",
    position: "DevOps Engineer",
    description:
      "Own the delivery pipeline, container strategy and cloud infrastructure " +
      "for a fast-moving engineering team.",
    required_skills: "Docker, Kubernetes, AWS, CI/CD",
    required_experience: "3+ years",
    leads_count: 2,
    created_at: "2026-08-20T09:00:00Z",
  },
  {
    id: 4,
    public_id: "550e8400-e29b-41d4-a716-446655440004",
    company_name: "Jafton Inc",
    position: "Product Manager",
    description:
      "Drive roadmap discovery and delivery for our analytics suite, pairing " +
      "customer research with clear execution.",
    required_skills: "Product Strategy, Agile, Roadmapping",
    required_experience: "4+ years",
    leads_count: 1,
    created_at: "2026-08-12T09:00:00Z",
  },
  {
    id: 5,
    public_id: "550e8400-e29b-41d4-a716-446655440005",
    company_name: "Unicon Soft",
    position: "Data Analyst",
    description:
      "Turn recruiting and product data into clear reports and dashboards for " +
      "business stakeholders.",
    required_skills: "SQL, Python, Pandas, Tableau",
    required_experience: "2+ years",
    leads_count: 1,
    created_at: "2026-08-05T09:00:00Z",
  },
  {
    id: 6,
    public_id: "550e8400-e29b-41d4-a716-446655440006",
    company_name: "Acme Corp",
    position: "QA Engineer",
    description:
      "Design and maintain automated test suites that keep our releases fast " +
      "and regressions low.",
    required_skills: "Selenium, Python, Testing",
    required_experience: "1+ years",
    leads_count: 1,
    created_at: "2026-07-30T09:00:00Z",
  },
];