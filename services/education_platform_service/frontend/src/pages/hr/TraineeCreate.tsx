import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Box, Typography, Button, Paper, TextField, Checkbox, FormControlLabel, Stack, Alert } from "@mui/material";
import { useStaffGuard } from "../../lib/useStaffGuard";
import { createTrainee, listDepartments, type HrDepartment } from "../../lib/hrApi";

export default function TraineeCreate() {
  const ready = useStaffGuard();
  const navigate = useNavigate();
  const [departments, setDepartments] = useState<HrDepartment[]>([]);
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [isActive, setIsActive] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [credentials, setCredentials] = useState<{ username: string; password: string } | null>(null);

  useEffect(() => {
    if (ready) listDepartments().then(setDepartments);
  }, [ready]);

  const toggleDept = (code: string) => {
    setSelectedDepts((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  const handleSubmit = async () => {
    setError(null);
    try {
      const result = await createTrainee({
        username,
        first_name: firstName,
        last_name: lastName,
        password,
        department_codes: selectedDepts,
        is_active: isActive,
      });
      setCredentials({ username: result.username, password: result.password });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (!ready) return null;

  return (
    <Box sx={{ p: 4, maxWidth: 500, mx: "auto" }}>
      <Button onClick={() => navigate("/hr/trainees")} sx={{ mb: 2 }}>
        ← Назад к стажёрам
      </Button>
      <Typography variant="h4" fontWeight="bold" sx={{ mb: 3 }}>
        Новый стажёр
      </Typography>

      {credentials && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Аккаунт создан. Логин: {credentials.username} Пароль: {credentials.password}
        </Alert>
      )}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Stack spacing={2}>
          <TextField label="Логин" value={username} onChange={(e) => setUsername(e.target.value)} fullWidth />
          <TextField label="Имя" value={firstName} onChange={(e) => setFirstName(e.target.value)} fullWidth />
          <TextField label="Фамилия" value={lastName} onChange={(e) => setLastName(e.target.value)} fullWidth />
          <TextField label="Пароль (пусто — сгенерировать)" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth />
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
          <Button variant="contained" onClick={handleSubmit} disabled={!username}>
            Создать
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
