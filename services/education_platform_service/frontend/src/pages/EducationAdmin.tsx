import { useEffect, useState } from "react";
import { CircularProgress, Box, Alert } from "@mui/material";
import HrDashboard from "./hr/HrDashboard";
import { backend } from "../lib/utils";
import { setToken } from "../lib/token";

export default function EducationAdmin() {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setState("error");
      return;
    }

    fetch(`${backend}/auth/admin-exchange?token=${encodeURIComponent(token)}`, { method: "POST" })
      .then(async (response) => {
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Не удалось открыть обучение");
        return response.json();
      })
      .then((data: { access_token: string }) => {
        setToken(data.access_token);
        window.history.replaceState({}, "", `${import.meta.env.BASE_URL}admin`);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, []);

  if (state === "loading") {
    return <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}><CircularProgress /></Box>;
  }
  if (state === "error") {
    return <Box sx={{ p: 4 }}><Alert severity="error">Не удалось открыть раздел обучения. Перезайдите в админ-панель.</Alert></Box>;
  }
  return <HrDashboard />;
}
