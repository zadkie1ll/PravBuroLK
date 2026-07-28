import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { setToken } from "./api/client";
import { ClientSearchPage } from "./pages/ClientSearchPage";
import { ClientDetailPage } from "./pages/ClientDetailPage";
import { PaymentsDashboardPage } from "./pages/PaymentsDashboardPage";

const ADMIN_PANEL_BASE_URL = import.meta.env.VITE_ADMIN_PANEL_BASE_URL || "http://localhost:5176";

function isAuthenticated() {
  return Boolean(localStorage.getItem("access_token"));
}

/** Приём токена из хаба (admin_panel_service), тот же паттерн, что и в leadreport_service:
 * см. services/leadreport_service/frontend/src/App.tsx:useTokenHandoff. Эта карточка не умеет
 * логиниться сама — единственный вход сюда — клик по карточке "Поиск клиентов" в хабе. */
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
      <Route path="/" element={<ClientSearchPage />} />
      <Route path="/clients/:clientId" element={<ClientDetailPage />} />
      <Route path="/payments-dashboard" element={<PaymentsDashboardPage />} />
    </Routes>
  );
}
