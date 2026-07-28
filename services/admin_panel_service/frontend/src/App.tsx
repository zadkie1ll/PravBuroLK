import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { AdminPanelPage } from "./pages/AdminPanelPage";

function isAuthenticated() {
  return Boolean(localStorage.getItem("access_token"));
}

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/admin-panel"
        element={
          <RequireAuth>
            <AdminPanelPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to={isAuthenticated() ? "/admin-panel" : "/login"} replace />} />
    </Routes>
  );
}
