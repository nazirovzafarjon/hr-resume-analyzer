import { Navigate, type RouteObject } from "react-router-dom";
import { lazy, Suspense, type ReactNode } from "react";
import { useAuth } from "../context/AuthContext";
import RequireAuth from "../components/routing/RequireAuth";
import AppLayout from "../components/layout/AppLayout";
import GoogleAuthCallback from "../components/auth/GoogleAuthCallback";
import Spinner from "../components/ui/Spinner";
import LoginPage from "../pages/auth/LoginPage";
import RegisterPage from "../pages/auth/RegisterPage";
const ForgotPasswordPage = lazy(() => import("../pages/auth/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("../pages/auth/ResetPasswordPage"));
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

/** Public lazily loaded page (no shell). */
function publicPage(element: ReactNode) {
  return <Suspense fallback={<PageFallback />}>{element}</Suspense>;
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
  { path: "/forgot-password", element: publicPage(<ForgotPasswordPage />) },
  { path: "/reset-password", element: publicPage(<ResetPasswordPage />) },
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
  { path: "*", element: <RootRedirect /> },
];

