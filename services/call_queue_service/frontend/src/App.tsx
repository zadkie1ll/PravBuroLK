import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { QueuePage } from "./pages/QueuePage";

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
        path="/"
        element={
          <RequireAuth>
            <QueuePage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to={isAuthenticated() ? "/" : "/login"} replace />} />
    </Routes>
  );
}
