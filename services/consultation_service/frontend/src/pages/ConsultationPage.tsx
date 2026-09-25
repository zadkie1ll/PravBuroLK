import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { getReport, saveReport } from "../api/client";
import { ReportPages } from "../components/report/ReportPages";
import type { ReportFields, ReportResponse } from "../types";

type Status = "loading" | "ready" | "error";

export function ConsultationPage() {
  const { dealId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";

  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState("");
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [fields, setFields] = useState<ReportFields | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");

  useEffect(() => {
    if (!dealId || !token) {
      setStatus("error");
      setError("Ссылка неполная — отсутствует сделка или токен.");
      return;
    }
    getReport(dealId, token)
      .then((data) => {
        setReport(data);
        setFields(data.fields);
        setStatus("ready");
      })
      .catch((err) => {
        setError(err.message || "Не удалось загрузить отчёт");
        setStatus("error");
      });
  }, [dealId, token]);

  function handleFieldChange(key: keyof ReportFields, value: string) {
    setFields((prev) => (prev ? { ...prev, [key]: value } : prev));
    setSavedMessage("");
  }

  async function handleSave() {
    if (!fields) return;
    setSaving(true);
    setSavedMessage("");
    try {
      await saveReport(dealId, token, fields);
      setSavedMessage("Сохранено и сформирован PDF.");
    } catch (err) {
      setSavedMessage(err instanceof Error ? err.message : "Не удалось сохранить");
    } finally {
      setSaving(false);
    }
  }

  if (status === "loading") {
    return <div style={{ padding: 24 }}>Загрузка…</div>;
  }

  if (status === "error" || !report || !fields) {
    return <div style={{ padding: 24, color: "#a51b2d" }}>{error}</div>;
  }

  return (
    <div>
      <ReportPages
        fields={fields}
        computed={report.computed}
        manager={report.manager}
        links={report.links}
        editable
        onFieldChange={handleFieldChange}
      />
      <div style={{ textAlign: "center", fontSize: 12, color: "#8593a5", padding: "4px 20px 0" }}>
        * — поля, которые пока не сохраняются в Bitrix (временно)
      </div>
      <div
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: 0,
          padding: "14px 20px",
          background: "#fff",
          borderTop: "1px solid #dae3ed",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
        }}
      >
        {savedMessage ? <span style={{ fontSize: 14, color: "#617186" }}>{savedMessage}</span> : null}
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            background: "#1479eb",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            padding: "12px 22px",
            fontSize: 15,
            fontWeight: 600,
            cursor: saving ? "default" : "pointer",
            opacity: saving ? 0.7 : 1,
          }}
        >
          {saving ? "Сохраняем…" : "Сохранить и сформировать"}
        </button>
      </div>
      {/* Место под фикс-панель, чтобы не перекрывала последнюю страницу */}
      <div style={{ height: 72 }} />
    </div>
  );
}
