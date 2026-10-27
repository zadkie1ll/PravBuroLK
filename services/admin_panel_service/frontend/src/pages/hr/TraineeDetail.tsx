import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Box, Typography, Button, Paper, Checkbox, FormControlLabel, Stack, Alert, CircularProgress, Divider, LinearProgress } from "@mui/material";
import { useStaffGuard } from "../../lib/useStaffGuard";
import { getTrainee, updateTrainee, listDepartments, type HrTraineeDetail, type HrDepartment } from "../../lib/hrApi";

export default function TraineeDetail() {
  const ready = useStaffGuard();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [trainee, setTrainee] = useState<HrTraineeDetail | null>(null);
  const [departments, setDepartments] = useState<HrDepartment[]>([]);
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [isActive, setIsActive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!ready || !id) return;
    Promise.all([getTrainee(Number(id)), listDepartments()])
      .then(([t, depts]) => {
        setTrainee(t);
        setDepartments(depts);
        setSelectedDepts(t.departments.map((d) => d.code));
        setIsActive(t.is_active);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Не удалось загрузить стажёра"))
      .finally(() => setLoading(false));
  }, [ready, id]);

  const toggleDept = (code: string) => {
    setSaved(false);
    setSelectedDepts((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  const handleSave = async () => {
    if (!id || saving) return;
    setSaved(false);
    setSaveError(null);
    setSaving(true);
    try {
      const updated = await updateTrainee(Number(id), { department_codes: selectedDepts, is_active: isActive });
      setTrainee(updated);
      setSelectedDepts(updated.departments.map((d) => d.code));
      setIsActive(updated.is_active);
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Не удалось сохранить доступы стажёра");
    } finally {
      setSaving(false);
    }
  };

  if (!ready) return null;
  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 6 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (loadError || !trainee) {
    return (
      <Box sx={{ p: 4 }}>
        <Button onClick={() => navigate("/admin-panel/education/trainees")} sx={{ mb: 2 }}>
          ← Назад к стажёрам
        </Button>
        <Alert severity="error">{loadError || "Стажёр не найден"}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 700, mx: "auto" }}>
      <Button onClick={() => navigate("/admin-panel/education/trainees")} sx={{ mb: 2 }}>
        ← Назад к стажёрам
      </Button>
      <Typography variant="h4" fontWeight="bold" sx={{ mb: 3 }}>
        Стажёр: {trainee.username}
      </Typography>

      {saved && <Alert severity="success" sx={{ mb: 2 }}>Доступы стажёра обновлены.</Alert>}
      {saveError && <Alert severity="error" sx={{ mb: 2 }}>{saveError} Выбранные настройки сохранены в форме. Можно повторить попытку.</Alert>}

      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <Stack spacing={2}>
          <Box>
            <Typography variant="subtitle2">Отделы</Typography>
            {departments.map((d) => (
              <FormControlLabel
                key={d.code}
                control={<Checkbox disabled={saving} checked={selectedDepts.includes(d.code)} onChange={() => toggleDept(d.code)} />}
                label={d.name}
              />
            ))}
          </Box>
          <FormControlLabel control={<Checkbox disabled={saving} checked={isActive} onChange={(e) => { setIsActive(e.target.checked); setSaved(false); }} />} label="Активен" />
          <Button variant="contained" disabled={saving} onClick={handleSave} sx={{ alignSelf: "flex-start" }}>
            {saving ? "Сохранение…" : "Сохранить доступы"}
          </Button>
        </Stack>
      </Paper>

      <Typography variant="h6" sx={{ mb: 1 }}>
        Прогресс по курсам
      </Typography>
      {trainee.course_rows.length === 0 && <Typography color="text.secondary">Нет доступных курсов (не назначен отдел).</Typography>}
      {trainee.course_rows.map((row) => (
        <Paper key={row.course_id} variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography fontWeight="bold">{row.course_name}</Typography>
          <LinearProgress variant="determinate" value={row.total ? (row.completed / row.total) * 100 : 0} sx={{ my: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {row.completed} / {row.total} модулей
          </Typography>
          <Divider sx={{ my: 1 }} />
          {row.modules.map((m) => (
            <Stack key={m.module_id} direction="row" justifyContent="space-between" sx={{ py: 0.5 }}>
              <Typography variant="body2">{m.module_name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {m.status}
                {m.test_id ? ` · попыток: ${m.attempts_used} · балл: ${m.latest_score ?? "—"} (${m.latest_passed ? "сдан" : "не сдан"})` : ""}
              </Typography>
            </Stack>
          ))}
        </Paper>
      ))}
    </Box>
  );
}
