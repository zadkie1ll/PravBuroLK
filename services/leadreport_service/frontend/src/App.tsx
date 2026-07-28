import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { MyStatsPage } from "./pages/MyStatsPage";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { AdminManagerDetailPage } from "./pages/AdminManagerDetailPage";
import { AppIndexPage } from "./pages/AppIndexPage";
import { ManagersListPage } from "./pages/ManagersListPage";
import { SourcesListPage } from "./pages/SourcesListPage";
import { setToken } from "./api/client";

function isAuthenticated() {
  return Boolean(localStorage.getItem("access_token"));
}

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  return children;
}

/** Приём токена из хаба (admin_panel_service): при переходе по карточке "Отчет по
 * менеджерам" туда добавляется ?token=..., поскольку это разные origin (разные порты) —
 * localStorage напрямую не расшарить. Забираем токен один раз, сохраняем и убираем из URL. */
function useTokenHandoff(): boolean {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const incomingToken = params.get("token");
    if (incomingToken) {
      setToken(incomingToken);
      window.history.replaceState({}, "", window.location.pathname);
    }
    setReady(true);
  }, []);

  return ready;
}

export default function App() {
  const ready = useTokenHandoff();
  if (!ready) return null;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <MyStatsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAuth>
            <AdminDashboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/leadreport"
        element={
          <RequireAuth>
            <AppIndexPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/managers-list"
        element={
          <RequireAuth>
            <ManagersListPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/sources-list"
        element={
          <RequireAuth>
            <SourcesListPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/manager/:managerId"
        element={
          <RequireAuth>
            <AdminManagerDetailPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to={isAuthenticated() ? "/" : "/login"} replace />} />
    </Routes>
  );
}
