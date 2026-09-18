import { Navigate, type RouteObject } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../context/AuthContext";
import RequireAuth from "../components/routing/RequireAuth";
import AppLayout from "../components/layout/AppLayout";
import GoogleAuthCallback from "../components/auth/GoogleAuthCallback";
import LoginPage from "../pages/auth/LoginPage";
import RegisterPage from "../pages/auth/RegisterPage";
import ForgotPasswordPage from "../pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "../pages/auth/ResetPasswordPage";
import DashboardPage from "../pages/dashboard/DashboardPage";
import JobListPage from "../pages/jobs/JobListPage";
import JobCreatePage from "../pages/jobs/JobCreatePage";
import JobDetailsPage from "../pages/jobs/JobDetailsPage";
import JobEditPage from "../pages/jobs/JobEditPage";
import ApplyPage from "../pages/apply/ApplyPage";
import CandidatesPage from "../pages/candidates/CandidatesPage";
import CandidateDetailsPage from "../pages/candidates/CandidateDetailsPage";
import ApplicationsPage from "../pages/applications/ApplicationsPage";
import ApplicationDetailsPage from "../pages/applications/ApplicationDetailsPage";
import InterviewsPage from "../pages/interviews/InterviewsPage";
import InterviewDetailsPage from "../pages/interviews/InterviewDetailsPage";
import AnalyticsPage from "../pages/analytics/AnalyticsPage";
import SettingsPage from "../pages/settings/SettingsPage";

/** Wraps a page in the authenticated shell + route guard. */
function protectedPage(element: ReactNode) {
  return (
    <RequireAuth>
      <AppLayout>{element}</AppLayout>
    </RequireAuth>
  );
}

/** Root/unknown path: send signed-in users to the dashboard, others to login. */
function RootRedirect() {
  const { isAuthenticated } = useAuth();
  return <Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />;
}

/**
 * Application route table. Auth pages are public; everything else lives inside
 * the protected application shell and redirects to /login when signed out.
 */
export const routes: RouteObject[] = [
  { path: "/", element: <RootRedirect /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/oauth/callback", element: <GoogleAuthCallback /> },
  { path: "/apply/:token", element: <ApplyPage /> },
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
  { path: "*", element: <RootRedirect /> },
];

