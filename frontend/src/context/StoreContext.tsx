import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { mockCandidates } from "../data/mock/candidates";
import { mockJobs } from "../data/mock/jobs";
import { mockApplications } from "../data/mock/applications";
import { mockInterviews } from "../data/mock/interviews";
import type { JobCreateInput, JobInput } from "../types/job";
import type { Candidate, CandidateStatusUpdate } from "../types/worker";
import type {
  Application,
  ApplicationStatus,
  Interview,
} from "../types/application";

type StoreValue = {
  jobs: JobInput[];
  candidates: Candidate[];
  applications: Application[];
  interviews: Interview[];
  getJobById: (id: number) => JobInput | undefined;
  getCandidatesByJob: (jobId: number) => Candidate[];
  getCandidateById: (id: number) => Candidate | undefined;
  getApplicationById: (id: number) => Application | undefined;
  getApplicationsByJob: (jobId: number) => Application[];
  getInterviewById: (id: number) => Interview | undefined;
  createJob: (input: JobCreateInput) => JobInput;
  updateJob: (id: number, input: JobCreateInput) => void;
  deleteJob: (id: number) => void;
  deleteCandidate: (id: number) => void;
  updateCandidateStatus: (id: number, patch: CandidateStatusUpdate) => void;
  updateApplicationStatus: (id: number, status: ApplicationStatus) => void;
};

const StoreContext = createContext<StoreValue | undefined>(undefined);

/**
 * Holds the in-memory jobs, candidates, applications and interviews for the
 * whole authenticated app. Mock state only — when the backend is connected
 * these actions will call the API instead while the UI stays the same.
 */
export function StoreProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<JobInput[]>(mockJobs);
  const [candidates, setCandidates] = useState<Candidate[]>(mockCandidates);
  const [applications, setApplications] =
    useState<Application[]>(mockApplications);
  const [interviews] = useState<Interview[]>(mockInterviews);

  function getJobById(id: number): JobInput | undefined {
    return jobs.find((job) => job.id === id);
  }

  function getCandidatesByJob(jobId: number): Candidate[] {
    return candidates.filter((candidate) => candidate.job_id === jobId);
  }

  function getCandidateById(id: number): Candidate | undefined {
    return candidates.find((candidate) => candidate.id === id);
  }

  function getApplicationById(id: number): Application | undefined {
    return applications.find((application) => application.id === id);
  }

  function getApplicationsByJob(jobId: number): Application[] {
    return applications.filter((application) => application.job_id === jobId);
  }

  function getInterviewById(id: number): Interview | undefined {
    return interviews.find((interview) => interview.id === id);
  }

  function createJob(input: JobCreateInput): JobInput {
    const nextId = jobs.reduce((max, job) => Math.max(max, job.id), 0) + 1;
    // The in-memory store has no backend, so no public token is generated —
    // the real API returns the published application form with the job.
    const job: JobInput = {
      id: nextId,
      public_id: `550e8400-e29b-41d4-a716-4466554400${nextId.toString().padStart(2, "0")}`,
      company_name: input.company_name,
      position: input.position,
      description: input.description,
      required_skills: input.required_skills,
      required_experience: input.required_experience,
      requirement_source: input.requirement_source,
      requirement_file_name: input.requirement_file_name,
      ai_instructions: input.ai_instructions,
      ai_analysis: input.ai_analysis,
      leads_count: 0,
      created_at: new Date().toISOString(),
    };
    setJobs((current) => [...current, job]);
    return job;
  }

  function updateJob(id: number, input: JobCreateInput): void {
    setJobs((current) =>
      current.map((job) =>
        job.id === id
          ? {
              ...job,
              company_name: input.company_name,
              position: input.position,
              description: input.description,
              required_skills: input.required_skills,
              required_experience: input.required_experience,
              requirement_source: input.requirement_source,
              requirement_file_name: input.requirement_file_name,
              ai_instructions: input.ai_instructions,
              ai_analysis: input.ai_analysis,
              // Mock store has no backend: the published form configuration
              // (and its token) stays backend-owned.
              application_form: job.application_form,
              form_url: input.form_url ?? job.form_url,
            }
          : job,
      ),
    );
  }

  function deleteJob(id: number): void {
    setJobs((current) => current.filter((job) => job.id !== id));
    // Removing a job also removes the candidates attached to it.
    setCandidates((current) =>
      current.filter((candidate) => candidate.job_id !== id),
    );
    setApplications((current) =>
      current.filter((application) => application.job_id !== id),
    );
  }

  function deleteCandidate(id: number): void {
    setCandidates((current) => current.filter((candidate) => candidate.id !== id));
    setApplications((current) =>
      current.filter((application) => application.candidate_id !== id),
    );
  }

  function updateCandidateStatus(id: number, patch: CandidateStatusUpdate): void {
    setCandidates((current) =>
      current.map((candidate) =>
        candidate.id === id ? { ...candidate, ...patch } : candidate,
      ),
    );
  }

  function updateApplicationStatus(id: number, status: ApplicationStatus): void {
    setApplications((current) =>
      current.map((application) =>
        application.id === id ? { ...application, status } : application,
      ),
    );
  }

  const value: StoreValue = {
    jobs,
    candidates,
    applications,
    interviews,
    getJobById,
    getCandidatesByJob,
    getCandidateById,
    getApplicationById,
    getApplicationsByJob,
    getInterviewById,
    createJob,
    updateJob,
    deleteJob,
    deleteCandidate,
    updateCandidateStatus,
    updateApplicationStatus,
  };

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

/** Access the shared mock store; must be used within a StoreProvider. */
export function useStore(): StoreValue {
  const context = useContext(StoreContext);
  if (!context) {
    throw new Error("useStore must be used within a StoreProvider");
  }
  return context;
}
