import { Routes, Route, Navigate } from "react-router-dom";
import { RequireAuth } from "@/components/RequireAuth";
import { AppShell } from "@/components/layout/AppShell";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { PrivacyPage, TermsPage } from "@/pages/LegalPages";
import { DashboardPage } from "@/pages/DashboardPage";
import { BusinessSearchPage } from "@/pages/BusinessSearchPage";
import { BusinessProfilePage } from "@/pages/BusinessProfilePage";
import { ReviewQueuePage } from "@/pages/ReviewQueuePage";
import { DistrictAnalyticsPage } from "@/pages/DistrictAnalyticsPage";
import { CorrectionsPage } from "@/pages/CorrectionsPage";
import { IngestionPage } from "@/pages/IngestionPage";
import { JobsPage } from "@/pages/JobsPage";
import { MatchingConfigPage } from "@/pages/MatchingConfigPage";
import { UsersPage } from "@/pages/UsersPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />

      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="businesses" element={<BusinessSearchPage />} />
        <Route path="businesses/:ubid" element={<BusinessProfilePage />} />
        <Route path="reviews" element={<ReviewQueuePage />} />
        <Route path="districts" element={<DistrictAnalyticsPage />} />
        <Route
          path="corrections"
          element={
            <RequireAuth role="reviewer">
              <CorrectionsPage />
            </RequireAuth>
          }
        />
        <Route
          path="ingest"
          element={
            <RequireAuth role="admin">
              <IngestionPage />
            </RequireAuth>
          }
        />
        <Route
          path="jobs"
          element={
            <RequireAuth role="admin">
              <JobsPage />
            </RequireAuth>
          }
        />
        <Route
          path="matching"
          element={
            <RequireAuth role="admin">
              <MatchingConfigPage />
            </RequireAuth>
          }
        />
        <Route
          path="users"
          element={
            <RequireAuth role="admin">
              <UsersPage />
            </RequireAuth>
          }
        />
        <Route path="404" element={<NotFoundPage />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Route>
    </Routes>
  );
}
