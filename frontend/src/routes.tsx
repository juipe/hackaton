import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { RequireAuth } from "@/components/layout/RequireAuth";
import AcceptInvitePage from "@/pages/AcceptInvitePage";
import DashboardPage from "@/pages/DashboardPage";
import GroupDetailPage from "@/pages/GroupDetailPage";
import GroupInvitePage from "@/pages/GroupInvitePage";
import GroupSettingsPage from "@/pages/GroupSettingsPage";
import GroupsPage from "@/pages/GroupsPage";
import LoginPage from "@/pages/LoginPage";
import NewGroupPage from "@/pages/NewGroupPage";
import NotFoundPage from "@/pages/NotFoundPage";
import ProfilePage from "@/pages/ProfilePage";
import RegisterPage from "@/pages/RegisterPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* The invite landing page handles both anonymous and signed-in visitors:
          it is the one authenticated-ish screen a brand-new user can land on. */}
      <Route path="/invite/:token" element={<AcceptInvitePage />} />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/groups" element={<GroupsPage />} />
        <Route path="/groups/new" element={<NewGroupPage />} />
        <Route path="/groups/:groupId" element={<GroupDetailPage />} />
        <Route path="/groups/:groupId/settings" element={<GroupSettingsPage />} />
        <Route path="/groups/:groupId/invite" element={<GroupInvitePage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Route>

      <Route path="/dashboard" element={<Navigate to="/" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
