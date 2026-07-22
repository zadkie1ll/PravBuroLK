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
  const [error, setError] = useState<string | null>(null);
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
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [ready, id]);

  const toggleDept = (code: string) => {
    setSelectedDepts((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  const handleSave = async () => {
    if (!id) return;
    setSaved(false);
    try {
      const updated = await updateTrainee(Number(id), { department_codes: selectedDepts, is_active: isActive });
      setTrainee(updated);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
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
  if (error || !trainee) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error || "Стажёр не найден"}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 700, mx: "auto" }}>
      <Button onClick={() => navigate("/hr/trainees")} sx={{ mb: 2 }}>
        ← Назад к стажёрам
      </Button>
      <Typography variant="h4" fontWeight="bold" sx={{ mb: 3 }}>
        Стажёр: {trainee.username}
      </Typography>

      {saved && <Alert severity="success" sx={{ mb: 2 }}>Доступы стажёра обновлены.</Alert>}

      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <Stack spacing={2}>
          <Box>
            <Typography variant="subtitle2">Отделы</Typography>
            {departments.map((d) => (
              <FormControlLabel
                key={d.code}
                control={<Checkbox checked={selectedDepts.includes(d.code)} onChange={() => toggleDept(d.code)} />}
                label={d.name}
              />
            ))}
          </Box>
          <FormControlLabel control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />} label="Активен" />
          <Button variant="contained" onClick={handleSave} sx={{ alignSelf: "flex-start" }}>
            Сохранить доступы
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
