import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Box, Typography, Button, Paper, Stack, Chip, CircularProgress, Alert, Table, TableHead, TableRow, TableCell, TableBody } from "@mui/material";
import { useStaffGuard } from "../../lib/useStaffGuard";
import { listTrainees, type HrTraineeListItem } from "../../lib/hrApi";

export default function Trainees() {
  const ready = useStaffGuard();
  const navigate = useNavigate();
  const [trainees, setTrainees] = useState<HrTraineeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    listTrainees()
      .then(setTrainees)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [ready]);

  if (!ready) return null;
  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 900, mx: "auto" }}>
      <Button onClick={() => navigate("/hr")} sx={{ mb: 2 }}>
        ← Назад в HR
      </Button>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          Стажёры
        </Typography>
        <Button variant="contained" onClick={() => navigate("/hr/trainees/new")}>
          + Новый стажёр
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Логин</TableCell>
              <TableCell>Отделы</TableCell>
              <TableCell>Прогресс</TableCell>
              <TableCell>Тесты пройдено</TableCell>
              <TableCell>Статус</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {trainees.map((t) => (
              <TableRow key={t.id} hover sx={{ cursor: "pointer" }} onClick={() => navigate(`/hr/trainees/${t.id}`)}>
                <TableCell>{t.username}</TableCell>
                <TableCell>
                  {t.departments.map((d) => (
                    <Chip key={d.code} label={d.name} size="small" sx={{ mr: 0.5 }} />
                  ))}
                </TableCell>
                <TableCell>
                  {t.completed_count} / {t.progress_count}
                </TableCell>
                <TableCell>
                  {t.passed_attempts_count} / {t.attempts_count}
                </TableCell>
                <TableCell>{t.is_active ? "активен" : "деактивирован"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
