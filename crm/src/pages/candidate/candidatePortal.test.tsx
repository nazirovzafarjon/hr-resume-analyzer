import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("../../services/candidatePortalService", () => ({
  loginCandidate: vi.fn(),
  loginCandidateWithGoogle: vi.fn(),
  registerCandidate: vi.fn(),
  logoutCandidate: vi.fn(),
  fetchCandidateProfile: vi.fn(),
  fetchCandidateDashboard: vi.fn(),
  fetchCandidateApplications: vi.fn(),
  fetchCandidateApplication: vi.fn(),
  fetchCandidateInterviews: vi.fn(),
  downloadCandidateResume: vi.fn(),
  updateCandidateProfile: vi.fn(),
  changeCandidatePassword: vi.fn(),
  uploadCandidateProfileImage: vi.fn(),
  removeCandidateProfileImage: vi.fn(),
}));

import * as service from "../../services/candidatePortalService";
import RequireCandidate from "../../components/routing/RequireCandidate";
import { safeNext } from "../../components/candidate/safeNext";
import CandidateLoginPage from "./auth/CandidateLoginPage";
import CandidateRegisterPage from "./auth/CandidateRegisterPage";
import CandidateDashboardPage from "./CandidateDashboardPage";
import CandidateApplicationsPage from "./CandidateApplicationsPage";
import CandidateApplicationDetailPage from "./CandidateApplicationDetailPage";
import CandidateInterviewsPage from "./CandidateInterviewsPage";
import CandidateProfilePage from "./CandidateProfilePage";
import { getCandidateToken, getToken, saveCandidateTokens, saveTokens } from "../../auth/tokenStorage";
import { ApiError } from "../../utils/apiError";
import { fakeJwt, renderWithProviders } from "../../test/utils";
import type {
  CandidateApplicationDetail,
  CandidateDashboard,
  CandidateInterview,
  CandidateProfile,
} from "../../types/candidatePortal";

const mocked = vi.mocked(service);

const PROFILE: CandidateProfile = {
  id: 7,
  email: "jane@example.com",
  full_name: "Jane Candidate",
  phone: "+998 90 000 00 00",
  profile_image: null,
  created_at: "2026-09-01T10:00:00Z",
  has_password: true,
  is_email_verified: true,
};

const SUMMARY = {
  id: 11,
  position: "Backend Engineer QA-1",
  company_name: "Company QA-1",
  submitted_at: "2026-09-28T10:00:00Z",
  status: "hr_review" as const,
  analysis_state: "analyzed" as const,
  interview_state: "not_scheduled" as const,
  next_interview_at: null,
};

const INTERVIEW: CandidateInterview = {
  id: 3,
  application_id: 11,
  position: "Backend Engineer QA-1",
  company_name: "Company QA-1",
  scheduled_at: "2026-10-02T14:00:00Z",
  duration_minutes: 45,
  status: "upcoming",
  is_online: true,
  meeting_link: "https://meet.example.com/abc",
};

function detail(overrides: Partial<CandidateApplicationDetail> = {}): CandidateApplicationDetail {
  return {
    ...SUMMARY,
    job: {
      position: SUMMARY.position,
      company_name: SUMMARY.company_name,
      description: "Build APIs QA-desc",
      required_skills: "Python, FastAPI",
      required_experience: "2+ years",
    },
    has_resume: true,
    answers: [
      { label: "Full name", type: "text", value: "Jane Candidate", file_attached: false },
      { label: "Resume", type: "file", value: null, file_attached: true },
    ],
    analysis: {
      state: "analyzed",
      match_percentage: 78,
      matched_skills: ["Python", "FastAPI"],
      skills_to_improve: ["Docker"],
      requirements_met: [],
      requirements_to_strengthen: [],
      analyzed_at: "2026-09-28T11:00:00Z",
    },
    timeline: [
      { key: "submitted", state: "done", date: "2026-09-28T10:00:00Z", outcome: null },
      { key: "resume_review", state: "done", date: "2026-09-28T11:00:00Z", outcome: null },
      { key: "hr_review", state: "current", date: null, outcome: null },
      { key: "interview", state: "upcoming", date: null, outcome: null },
      { key: "decision", state: "upcoming", date: null, outcome: null },
    ],
    interviews: [],
    ...overrides,
  };
}

function signedInCandidate() {
  saveCandidateTokens("candidate-access", "candidate-refresh");
  mocked.fetchCandidateProfile.mockResolvedValue(PROFILE);
}

function render(ui: ReactNode, path: string, pattern?: string) {
  return renderWithProviders(ui, { path, pattern });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("safeNext", () => {
  it("keeps same-site paths and rejects external ones", () => {
    expect(safeNext("/apply/abc")).toBe("/apply/abc");
    expect(safeNext("https://evil.example")).toBe("/candidate");
    expect(safeNext("//evil.example")).toBe("/candidate");
    expect(safeNext(null)).toBe("/candidate");
  });
});

describe("RequireCandidate", () => {
  it("sends visitors without a candidate session to the portal sign-in", () => {
    render(<RequireCandidate>portal content</RequireCandidate>, "/candidate");
    expect(screen.getByTestId("location").textContent).toBe("/candidate/login");
    expect(screen.queryByText("portal content")).toBeNull();
  });

  it("does not accept an HR session", () => {
    saveTokens(fakeJwt({ role: "admin" }), null);
    render(<RequireCandidate>portal content</RequireCandidate>, "/candidate");
    expect(screen.getByTestId("location").textContent).toBe("/candidate/login");
  });

  it("renders for a candidate session", () => {
    signedInCandidate();
    render(<RequireCandidate>portal content</RequireCandidate>, "/candidate");
    expect(screen.getByText("portal content")).toBeTruthy();
  });
});

describe("Candidate sign-in", () => {
  it("stores a candidate session (not an HR one) and opens the portal", async () => {
    mocked.loginCandidate.mockResolvedValue({
      access_token: "a",
      refresh_token: "r",
      token_type: "bearer",
      candidate: PROFILE,
    });
    render(<CandidateLoginPage />, "/candidate/login");
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "CandidatePass1" } });
    fireEvent.submit(screen.getByLabelText("Email").closest("form")!);
    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/candidate"));
    expect(mocked.loginCandidate).toHaveBeenCalledWith({ email: "jane@example.com", password: "CandidatePass1" });
    expect(getCandidateToken()).toBe("a");
    expect(getToken()).toBeNull();
  });

  it("shows the server's message for wrong credentials", async () => {
    mocked.loginCandidate.mockRejectedValue(new ApiError(401, "Incorrect email or password."));
    render(<CandidateLoginPage />, "/candidate/login");
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    fireEvent.submit(screen.getByLabelText("Email").closest("form")!);
    expect(await screen.findByText("Incorrect email or password.")).toBeTruthy();
    expect(getCandidateToken()).toBeNull();
  });
});

describe("Candidate registration", () => {
  it("validates the password length before calling the API", async () => {
    render(<CandidateRegisterPage />, "/candidate/register");
    fireEvent.change(await screen.findByLabelText("Full name"), { target: { value: "Jane" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "short" } });
    fireEvent.submit(screen.getByLabelText("Email").closest("form")!);
    expect((await screen.findAllByText("Use 8–72 characters.")).length).toBeGreaterThan(0);
    expect(mocked.registerCandidate).not.toHaveBeenCalled();
  });
});

describe("Candidate dashboard", () => {
  it("shows backend counts, the next interview and recent applications", async () => {
    signedInCandidate();
    const data: CandidateDashboard = {
      total_applications: 4,
      active_applications: 3,
      upcoming_interviews: 1,
      completed_applications: 1,
      next_interview: INTERVIEW,
      recent_applications: [SUMMARY],
    };
    mocked.fetchCandidateDashboard.mockResolvedValue(data);
    render(<CandidateDashboardPage />, "/candidate");
    expect(await screen.findByText("Welcome back, Jane 👋")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("Your next interview")).toBeTruthy();
    expect(screen.getAllByText("Backend Engineer QA-1").length).toBe(2);
    expect(screen.getByText("Under HR review")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Join interview/ }).getAttribute("href")).toBe(INTERVIEW.meeting_link);
  });

  it("shows a contextual error with retry", async () => {
    signedInCandidate();
    mocked.fetchCandidateDashboard.mockRejectedValueOnce(new ApiError(0, "Unable to connect to the server."));
    render(<CandidateDashboardPage />, "/candidate");
    expect(await screen.findByText("We couldn't load your dashboard")).toBeTruthy();
    mocked.fetchCandidateDashboard.mockResolvedValue({
      total_applications: 0,
      active_applications: 0,
      upcoming_interviews: 0,
      completed_applications: 0,
      next_interview: null,
      recent_applications: [],
    });
    fireEvent.click(screen.getByRole("button", { name: /Retry|Try again/i }));
    expect(await screen.findByText("You don't have any applications yet.")).toBeTruthy();
  });
});

describe("Candidate applications", () => {
  it("shows the empty state", async () => {
    signedInCandidate();
    mocked.fetchCandidateApplications.mockResolvedValue([]);
    render(<CandidateApplicationsPage />, "/candidate/applications");
    expect(await screen.findByText("You don't have any applications yet.")).toBeTruthy();
  });

  it("lists application cards with friendly statuses", async () => {
    signedInCandidate();
    mocked.fetchCandidateApplications.mockResolvedValue([SUMMARY, { ...SUMMARY, id: 12, status: "accepted" }]);
    render(<CandidateApplicationsPage />, "/candidate/applications");
    expect(await screen.findByText("Application accepted")).toBeTruthy();
    expect(screen.getByText("Under HR review")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "View application" })[1].getAttribute("href")).toBe("/candidate/applications/12");
  });
});

describe("Candidate application detail", () => {
  const route = "/candidate/applications/:id";

  it("shows progress, what happens next and safe compatibility feedback", async () => {
    signedInCandidate();
    mocked.fetchCandidateApplication.mockResolvedValue(detail());
    render(<CandidateApplicationDetailPage />, "/candidate/applications/11", route);
    expect(await screen.findByText("Application progress")).toBeTruthy();
    expect(mocked.fetchCandidateApplication).toHaveBeenCalledWith(11);
    for (const title of ["Application submitted", "Resume review", "HR review", "Interview", "Final decision"]) {
      expect(screen.getAllByText(title).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("78%")).toBeTruthy();
    expect(screen.getByText("Docker")).toBeTruthy();
    expect(screen.getByText(/not a hiring decision/)).toBeTruthy();
    expect(screen.getByText(/The hiring team is reviewing your application/)).toBeTruthy();
    expect(screen.getByText("File attached")).toBeTruthy();
    expect(screen.getByText("No interviews scheduled yet.")).toBeTruthy();
  });

  it("presents a failed analysis as unavailable, not as a failed application", async () => {
    signedInCandidate();
    mocked.fetchCandidateApplication.mockResolvedValue(
      detail({
        analysis_state: "failed",
        analysis: {
          state: "failed",
          match_percentage: null,
          matched_skills: [],
          skills_to_improve: [],
          requirements_met: [],
          requirements_to_strengthen: [],
          analyzed_at: null,
        },
      }),
    );
    render(<CandidateApplicationDetailPage />, "/candidate/applications/11", route);
    expect(await screen.findByText("We couldn't complete the resume analysis yet.")).toBeTruthy();
    expect(screen.getByText(/Your application was still submitted successfully/)).toBeTruthy();
  });

  it("shows not-found for someone else's (or a missing) application", async () => {
    signedInCandidate();
    mocked.fetchCandidateApplication.mockRejectedValue(new ApiError(404, "Application not found"));
    render(<CandidateApplicationDetailPage />, "/candidate/applications/99", route);
    expect(await screen.findByText("Application not found")).toBeTruthy();
  });
});

describe("Candidate interviews", () => {
  it("splits upcoming and past interviews", async () => {
    signedInCandidate();
    mocked.fetchCandidateInterviews.mockResolvedValue([
      { ...INTERVIEW, id: 1, status: "completed", meeting_link: null, scheduled_at: "2026-09-01T10:00:00Z" },
      INTERVIEW,
    ]);
    render(<CandidateInterviewsPage />, "/candidate/interviews");
    expect(await screen.findByText("Past interviews")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /Join interview/ })).toHaveLength(1);
    expect(screen.getByText("Completed")).toBeTruthy();
  });

  it("shows the empty state", async () => {
    signedInCandidate();
    mocked.fetchCandidateInterviews.mockResolvedValue([]);
    render(<CandidateInterviewsPage />, "/candidate/interviews");
    expect(await screen.findByText("No interviews scheduled yet.")).toBeTruthy();
  });
});

describe("Candidate profile", () => {
  it("shows and saves the candidate's details", async () => {
    signedInCandidate();
    mocked.updateCandidateProfile.mockResolvedValue({ ...PROFILE, full_name: "Jane D." });
    render(<CandidateProfilePage />, "/candidate/profile");
    const name = (await screen.findByDisplayValue("Jane Candidate")) as HTMLInputElement;
    expect(screen.getByDisplayValue("jane@example.com")).toBeTruthy();
    fireEvent.change(name, { target: { value: "Jane D." } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(mocked.updateCandidateProfile).toHaveBeenCalledWith({
        full_name: "Jane D.",
        email: "jane@example.com",
        phone: "+998 90 000 00 00",
      }),
    );
  });

  it("hides the change-password form for a Google-only account", async () => {
    saveCandidateTokens("candidate-access", "candidate-refresh");
    mocked.fetchCandidateProfile.mockResolvedValue({ ...PROFILE, has_password: false });
    render(<CandidateProfilePage />, "/candidate/profile");
    // The "no local password" notice replaces the form; the Change button is gone.
    expect(await screen.findByText(/signed up with Google/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Change password" })).toBeNull();
  });
});
