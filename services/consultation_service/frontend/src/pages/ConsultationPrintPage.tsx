import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { getReport } from "../api/client";
import { ReportPages } from "../components/report/ReportPages";
import type { ReportResponse } from "../types";

/**
 * Read-only рендер отчёта — открывается только headless Chromium (Playwright) на
 * бэкенде, чтобы напечатать PDF. Тот же ReportPages, что и в ConsultationPage,
 * просто editable=false и без кнопки сохранения — дизайн не может разъехаться.
 */
export function ConsultationPrintPage() {
  const { dealId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.body.classList.add("print-mode");
    if (!dealId || !token) {
      setError("Missing dealId or token");
      return;
    }
    getReport(dealId, token)
      .then(setReport)
      .catch((err) => setError(err.message || "Failed to load report"));
  }, [dealId, token]);

  if (error) return <div>{error}</div>;
  if (!report) return null;

  return (
    <ReportPages
      fields={report.fields}
      computed={report.computed}
      manager={report.manager}
      links={report.links}
      editable={false}
      onFieldChange={() => {}}
    />
  );
}
