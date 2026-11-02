import { Navigate, type RouteObject } from "react-router-dom";
import { lazy, Suspense, type ReactNode } from "react";
import { landingPath, useAuth } from "../context/AuthContext";
import RequireAuth from "../components/routing/RequireAuth";
import RequireAdmin from "../components/routing/RequireAdmin";
import RequireCandidate from "../components/routing/RequireCandidate";
import CandidateLayout from "../components/candidate/CandidateLayout";
import { useCandidateAuth } from "../context/CandidateAuthContext";
import AppLayout from "../components/layout/AppLayout";
import GoogleAuthCallback from "../components/auth/GoogleAuthCallback";
import Spinner from "../components/ui/Spinner";
import LoginPage from "../pages/auth/LoginPage";
import RegisterPage from "../pages/auth/RegisterPage";
const ForgotPasswordPage = lazy(() => import("../pages/auth/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("../pages/auth/ResetPasswordPage"));
const VerifyEmailPage = lazy(() => import("../pages/auth/VerifyEmailPage"));
const RoleSelectPage = lazy(() => import("../pages/auth/RoleSelectPage"));
const DashboardPage = lazy(() => import("../pages/dashboard/DashboardPage"));
const JobListPage = lazy(() => import("../pages/jobs/JobListPage"));
const JobCreatePage = lazy(() => import("../pages/jobs/JobCreatePage"));
const JobDetailsPage = lazy(() => import("../pages/jobs/JobDetailsPage"));
const JobEditPage = lazy(() => import("../pages/jobs/JobEditPage"));
const ApplyPage = lazy(() => import("../pages/apply/ApplyPage"));
const CandidatesPage = lazy(() => import("../pages/candidates/CandidatesPage"));
const CandidateDetailsPage = lazy(() => import("../pages/candidates/CandidateDetailsPage"));
const ApplicationsPage = lazy(() => import("../pages/applications/ApplicationsPage"));
const ApplicationDetailsPage = lazy(() => import("../pages/applications/ApplicationDetailsPage"));
const InterviewsPage = lazy(() => import("../pages/interviews/InterviewsPage"));
const InterviewDetailsPage = lazy(() => import("../pages/interviews/InterviewDetailsPage"));
const AnalyticsPage = lazy(() => import("../pages/analytics/AnalyticsPage"));
const SettingsPage = lazy(() => import("../pages/settings/SettingsPage"));
// Admin console (separate chunks: regular HR users never download them).
const AdminDashboardPage = lazy(() => import("../pages/admin/AdminDashboardPage"));
const AdminUsersPage = lazy(() => import("../pages/admin/AdminUsersPage"));
const AdminUserDetailPage = lazy(() => import("../pages/admin/AdminUserDetailPage"));
const AdminJobsPage = lazy(() => import("../pages/admin/AdminJobsPage"));
const AdminApplicationsPage = lazy(() => import("../pages/admin/AdminApplicationsPage"));
const AdminApplicationDetailPage = lazy(() => import("../pages/admin/AdminApplicationDetailPage"));
const AdminInterviewsPage = lazy(() => import("../pages/admin/AdminInterviewsPage"));
const AdminNotificationsPage = lazy(() => import("../pages/admin/AdminNotificationsPage"));
const AdminAIAnalysisPage = lazy(() => import("../pages/admin/AdminAIAnalysisPage"));
const AdminAnalyticsPage = lazy(() => import("../pages/admin/AdminAnalyticsPage"));
const AdminAuditLogsPage = lazy(() => import("../pages/admin/AdminAuditLogsPage"));
const AdminSystemErrorsPage = lazy(() => import("../pages/admin/AdminSystemErrorsPage"));
const AdminSettingsPage = lazy(() => import("../pages/admin/AdminSettingsPage"));
const AdminSystemHealthPage = lazy(() => import("../pages/admin/AdminSystemHealthPage"));
// Candidate Portal (its own chunks and shell; see components/candidate).
const CandidateLoginPage = lazy(() => import("../pages/candidate/auth/CandidateLoginPage"));
const CandidateRegisterPage = lazy(() => import("../pages/candidate/auth/CandidateRegisterPage"));
const CandidateForgotPasswordPage = lazy(() => import("../pages/candidate/auth/CandidateForgotPasswordPage"));
const CandidateResetPasswordPage = lazy(() => import("../pages/candidate/auth/CandidateResetPasswordPage"));
const CandidateVerifyEmailPage = lazy(() => import("../pages/candidate/auth/CandidateVerifyEmailPage"));
const CandidateDashboardPage = lazy(() => import("../pages/candidate/CandidateDashboardPage"));
const CandidateApplicationsPage = lazy(() => import("../pages/candidate/CandidateApplicationsPage"));
const CandidateApplicationDetailPage = lazy(() => import("../pages/candidate/CandidateApplicationDetailPage"));
const CandidateInterviewsPage = lazy(() => import("../pages/candidate/CandidateInterviewsPage"));
const CandidateProfilePage = lazy(() => import("../pages/candidate/CandidateProfilePage"));

/**
 * Pages are code-split per route (charts, the form builder and the analysis
 * views only download when first visited). While a chunk loads, the app shell
 * stays on screen and only the content area shows a spinner.
 */
function PageFallback() {
  return (
    <div className="route-fallback">
      <Spinner />
    </div>
  );
}

/** Wraps a page in the authenticated shell + route guard. */
function protectedPage(element: ReactNode) {
  return (
    <RequireAuth>
      <AppLayout>
        <Suspense fallback={<PageFallback />}>{element}</Suspense>
      </AppLayout>
    </RequireAuth>
  );
}

/**
 * Wraps an admin page in the admin shell + admin guard. The guard only
 * improves UX; every /api/admin endpoint enforces the role server-side.
 */
function adminPage(element: ReactNode) {
  return (
    <RequireAdmin>
      <AppLayout variant="admin">
        <Suspense fallback={<PageFallback />}>{element}</Suspense>
      </AppLayout>
    </RequireAdmin>
  );
}

/**
 * Wraps a Candidate Portal page in the candidate shell + guard. Candidate
 * sessions are separate from HR sessions (different tokens), so neither
 * guard lets the other identity in.
 */
function candidatePage(element: ReactNode) {
  return (
    <RequireCandidate>
      <CandidateLayout>
        <Suspense fallback={<PageFallback />}>{element}</Suspense>
      </CandidateLayout>
    </RequireCandidate>
  );
}

/** Public lazily loaded page (no shell). */
function publicPage(element: ReactNode) {
  return <Suspense fallback={<PageFallback />}>{element}</Suspense>;
}

/**
 * Root/unknown path: an HR session goes to its workspace's home, a pending
 * workspace choice back to the choice, a candidate session to the Candidate
 * Portal, everyone else to login.
 */
function RootRedirect() {
  const { isAuthenticated, activeRole, pendingSelection } = useAuth();
  const candidate = useCandidateAuth();
  const target = isAuthenticated
    ? landingPath(activeRole)
    : pendingSelection
      ? "/select-role"
      : candidate.isAuthenticated
        ? "/candidate"
        : "/login";
  return <Navigate to={target} replace />;
}

/**
 * Application route table. Auth pages are public; everything else lives inside
 * the protected application shell and redirects to /login when signed out.
 */
export const routes: RouteObject[] = [
  { path: "/", element: <RootRedirect /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/forgot-password", element: publicPage(<ForgotPasswordPage />) },
  { path: "/reset-password", element: publicPage(<ResetPasswordPage />) },
  { path: "/verify-email", element: publicPage(<VerifyEmailPage />) },
  { path: "/select-role", element: publicPage(<RoleSelectPage />) },
  { path: "/oauth/callback", element: <GoogleAuthCallback /> },
  { path: "/apply/:token", element: publicPage(<ApplyPage />) },
  { path: "/dashboard", element: protectedPage(<DashboardPage />) },
  { path: "/jobs", element: protectedPage(<JobListPage />) },
  { path: "/jobs/create", element: protectedPage(<JobCreatePage />) },
  { path: "/jobs/:id", element: protectedPage(<JobDetailsPage />) },
  { path: "/jobs/:id/edit", element: protectedPage(<JobEditPage />) },
  { path: "/candidates", element: protectedPage(<CandidatesPage />) },
  { path: "/candidates/:id", element: protectedPage(<CandidateDetailsPage />) },
  { path: "/applications", element: protectedPage(<ApplicationsPage />) },
  { path: "/applications/:id", element: protectedPage(<ApplicationDetailsPage />) },
  { path: "/interviews", element: protectedPage(<InterviewsPage />) },
  { path: "/interviews/:id", element: protectedPage(<InterviewDetailsPage />) },
  { path: "/analytics", element: protectedPage(<AnalyticsPage />) },
  { path: "/settings", element: protectedPage(<SettingsPage />) },
  { path: "/candidate/login", element: publicPage(<CandidateLoginPage />) },
  { path: "/candidate/register", element: publicPage(<CandidateRegisterPage />) },
  { path: "/candidate/forgot-password", element: publicPage(<CandidateForgotPasswordPage />) },
  { path: "/candidate/reset-password", element: publicPage(<CandidateResetPasswordPage />) },
  { path: "/candidate/verify-email", element: publicPage(<CandidateVerifyEmailPage />) },
  { path: "/candidate", element: candidatePage(<CandidateDashboardPage />) },
  { path: "/candidate/applications", element: candidatePage(<CandidateApplicationsPage />) },
  { path: "/candidate/applications/:id", element: candidatePage(<CandidateApplicationDetailPage />) },
  { path: "/candidate/interviews", element: candidatePage(<CandidateInterviewsPage />) },
  { path: "/candidate/profile", element: candidatePage(<CandidateProfilePage />) },
  { path: "/candidate/*", element: <Navigate to="/candidate" replace /> },
  { path: "/admin", element: <Navigate to="/admin/dashboard" replace /> },
  { path: "/admin/dashboard", element: adminPage(<AdminDashboardPage />) },
  { path: "/admin/users", element: adminPage(<AdminUsersPage />) },
  { path: "/admin/users/:id", element: adminPage(<AdminUserDetailPage />) },
  { path: "/admin/jobs", element: adminPage(<AdminJobsPage />) },
  { path: "/admin/applications", element: adminPage(<AdminApplicationsPage mode="applications" />) },
  { path: "/admin/applications/:id", element: adminPage(<AdminApplicationDetailPage />) },
  { path: "/admin/candidates", element: adminPage(<AdminApplicationsPage mode="candidates" />) },
  { path: "/admin/candidates/:id", element: adminPage(<AdminApplicationDetailPage />) },
  { path: "/admin/interviews", element: adminPage(<AdminInterviewsPage />) },
  { path: "/admin/notifications", element: adminPage(<AdminNotificationsPage />) },
  { path: "/admin/ai-analysis", element: adminPage(<AdminAIAnalysisPage />) },
  { path: "/admin/analytics", element: adminPage(<AdminAnalyticsPage />) },
  { path: "/admin/audit-logs", element: adminPage(<AdminAuditLogsPage />) },
  { path: "/admin/system-errors", element: adminPage(<AdminSystemErrorsPage />) },
  { path: "/admin/settings", element: adminPage(<AdminSettingsPage />) },
  { path: "/admin/system-health", element: adminPage(<AdminSystemHealthPage />) },
  { path: "/admin/*", element: <Navigate to="/admin/dashboard" replace /> },
  { path: "*", element: <RootRedirect /> },
];

