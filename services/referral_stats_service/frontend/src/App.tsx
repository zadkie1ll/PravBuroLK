import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { setToken } from "./api/client";
import { ReferralStatsPage } from "./pages/ReferralStatsPage";
import { DashboardVisitsPage } from "./pages/DashboardVisitsPage";

const ADMIN_PANEL_BASE_URL = import.meta.env.VITE_ADMIN_PANEL_BASE_URL || "http://localhost:5176";

function isAuthenticated() {
  return Boolean(localStorage.getItem("access_token"));
}

/** Приём токена из хаба (admin_panel_service), тот же паттерн, что и в остальных
 * сервисах — см. services/leadreport_service/frontend/src/App.tsx:useTokenHandoff. */
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

  if (!isAuthenticated()) {
    window.location.href = `${ADMIN_PANEL_BASE_URL}/login`;
    return null;
  }

  return (
    <Routes>
      <Route path="/" element={<ReferralStatsPage />} />
      <Route path="/visits" element={<DashboardVisitsPage />} />
    </Routes>
  );
}
