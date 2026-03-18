import { useNavigate, useParams } from "react-router-dom";
import { useState, useEffect } from "react";
import { backend } from "../lib/utils";
import {
  Typography,
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  CircularProgress,
  Button,
  Divider,
  LinearProgress,
  Paper,
  Radio,
  Checkbox,
  FormControlLabel,
  TextField,
  Alert,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import TimelapseIcon from "@mui/icons-material/Timelapse";
import { LoadModules } from "../lib/api";

// API-функции
async function LoadTest(moduleId: number, userId: number) {
  const response = await fetch(`${backend}/api/get_test?module=${moduleId}&user=${userId}`);
  if (!response.ok) {
    if (response.status === 404) return null;
    throw new Error("Ошибка загрузки теста");
  }
  return await response.json();
}

async function SubmitTest(moduleId: number, userId: number, answers: Record<number, any>) {
  const response = await fetch(`${backend}/api/submit_test/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, module_id: moduleId, answers }),
  });
  if (!response.ok) throw new Error("Ошибка отправки теста");
  return await response.json();
}

async function UpdateModuleStatus(moduleId: number, userId: number, status: string) {
  const response = await fetch(`${backend}/api/update_module_progress/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, module_id: moduleId, status }),
  });
  if (!response.ok) throw new Error("Ошибка обновления статуса");
  return await response.json();
}

interface Module {
  id: number;
  name: string;
  description: string;
  video_url: string;
  order: number;
  status: string; // "not_started", "in_progress", "completed"
}

interface Question {
  id: number;
  text: string;
  question_type: "choice" | "multi_choice" | "text";
  options: { id: number; text: string }[];
  score: number;
  order: number;
}

interface Test {
  id: number;
  name: string;
  description: string;
  max_score: number;
  passing_score: number;
  max_attempts: number;
  attempts_left: number;
  questions: Question[];
}

const CourseDetails = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const user_id = parseInt(localStorage.getItem("user") || "0", 10);

  const [modules, setModules] = useState<Module[]>([]);
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);
  const [test, setTest] = useState<Test | null>(null);
  const [answers, setAnswers] = useState<Record<number, any>>({});
  const [testResult, setTestResult] = useState<{ score: number; passed: boolean; attempts_left: number } | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [step, setStep] = useState<"video" | "test">("video");

  // Прогресс
  const completedModules = modules.filter((m) => m.status === "completed").length;
  const progress = modules.length > 0 ? (completedModules / modules.length) * 100 : 0;

  useEffect(() => {
    const fetchModules = async () => {
      if (!id || isNaN(user_id)) {
        setError("Неверный ID курса или пользователя");
        setLoading(false);
        return;
      }

      try {
        let loadedModules = await LoadModules(parseInt(id, 10), user_id);
        loadedModules = loadedModules.sort((a, b) => a.order - b.order);
        setModules(loadedModules);

        const firstIncomplete = loadedModules.find((mod) => mod.status !== "completed") || loadedModules[0];
        setSelectedModule(firstIncomplete);
      } catch (err) {
        setError((err as Error).message || "Ошибка загрузки модулей");
      } finally {
        setLoading(false);
      }
    };

    fetchModules();
  }, [id]);

  useEffect(() => {
    if (!selectedModule) return;

    setStep("video");
    setTest(null);
    setAnswers({});
    setTestResult(null);
    setTestError(null);

    // Если модуль только начали — отмечаем "in_progress"
    if (selectedModule.status === "not_started") {
      UpdateModuleStatus(selectedModule.id, user_id, "in_progress").catch(console.error);
      updateLocalStatus(selectedModule.id, "in_progress");
    }

    // Загружаем тест
    const load = async () => {
      setTestLoading(true);
      try {
        const data = await LoadTest(selectedModule.id, user_id);
        setTest(data?.test || null);
      } catch (err) {
        setTestError((err as Error).message || "Не удалось загрузить тест");
      } finally {
        setTestLoading(false);
      }
    };

    load();
  }, [selectedModule]);

  const updateLocalStatus = (moduleId: number, newStatus: string) => {
    setModules((prev) =>
      prev.map((mod) => (mod.id === moduleId ? { ...mod, status: newStatus } : mod))
    );
  };

  const goToNextModule = () => {
    if (!selectedModule) return;
    const idx = modules.findIndex((m) => m.id === selectedModule.id);
    if (idx >= 0 && idx < modules.length - 1) {
      setSelectedModule(modules[idx + 1]);
    }
  };

  const handleVideoWatched = async () => {
    if (!selectedModule) return;

    // Если тест существует и в нём есть хотя бы один вопрос → показываем тест
    if (test && test.questions?.length > 0) {
      setStep("test");
    } else {
      // Нет теста или пустой → сразу завершаем
      try {
        await UpdateModuleStatus(selectedModule.id, user_id, "completed");
        updateLocalStatus(selectedModule.id, "completed");
        goToNextModule();
      } catch (err) {
        setError((err as Error).message || "Не удалось завершить модуль");
      }
    }
  };

  const handleAnswerChange = (questionId: number, value: any) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleSubmitTest = async () => {
    if (!selectedModule || !test) return;

    try {
      const result = await SubmitTest(selectedModule.id, user_id, answers);
      setTestResult(result);

      if (result.passed) {
        updateLocalStatus(selectedModule.id, "completed");
        setTimeout(goToNextModule, 1800);
      } else {
        setTest((prev) => (prev ? { ...prev, attempts_left: result.attempts_left } : null));
      }
    } catch (err) {
      setTestError((err as Error).message || "Ошибка при отправке теста");
    }
  };

  const renderQuestion = (question: Question) => {
    switch (question.question_type) {
      case "choice":
        return (
          <Box sx={{ mt: 1 }}>
            {question.options.map((opt) => (
              <FormControlLabel
                key={opt.id}
                control={
                  <Radio
                    checked={answers[question.id]?.id === opt.id}
                    onChange={() => handleAnswerChange(question.id, { id: opt.id })}
                  />
                }
                label={opt.text}
              />
            ))}
          </Box>
        );

      case "multi_choice":
        return (
          <Box sx={{ mt: 1 }}>
            {question.options.map((opt) => (
              <FormControlLabel
                key={opt.id}
                control={
                  <Checkbox
                    checked={answers[question.id]?.ids?.includes(opt.id) || false}
                    onChange={(e) => {
                      const ids = answers[question.id]?.ids || [];
                      const newIds = e.target.checked
                        ? [...ids, opt.id]
                        : ids.filter((id: number) => id !== opt.id);
                      handleAnswerChange(question.id, { ids: newIds });
                    }}
                  />
                }
                label={opt.text}
              />
            ))}
          </Box>
        );

      case "text":
        return (
          <TextField
            fullWidth
            multiline
            rows={3}
            value={answers[question.id]?.text || ""}
            onChange={(e) => handleAnswerChange(question.id, { text: e.target.value })}
            placeholder="Введите ответ..."
            variant="outlined"
            sx={{ mt: 1 }}
          />
        );

      default:
        return null;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircleIcon color="success" />;
      case "in_progress":
        return <TimelapseIcon color="primary" />;
      default:
        return <RadioButtonUncheckedIcon color="action" />;
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4, textAlign: "center" }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: { xs: "column", sm: "row" },
        height: "100vh",
        width: "100vw",
        overflow: "hidden",
        bgcolor: "background.default",
        m: 0,
        p: 0,
      }}
    >
      {/* Sidebar */}
      <Paper
        elevation={3}
        sx={{
          width: { xs: "100%", sm: "320px" },
          overflowY: "auto",
          p: 3,
          borderRight: { sm: "1px solid" },
          borderColor: "divider",
          bgcolor: "white",
        }}
      >
        <Button variant="outlined" onClick={() => navigate("/dashboard")} sx={{ mb: 3 }}>
          ← Назад в меню
        </Button>

        <Typography variant="h5" fontWeight="bold" gutterBottom>
          Модули курса
        </Typography>

        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" color="text.secondary">
            Прогресс: {completedModules} / {modules.length}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{ mt: 1, height: 8, borderRadius: 4 }}
          />
        </Box>

        <Divider sx={{ my: 2 }} />

        <List disablePadding>
          {modules.map((module) => (
            <ListItem disablePadding key={module.id}>
              <ListItemButton
                selected={selectedModule?.id === module.id}
                onClick={() => setSelectedModule(module)}
                sx={{
                  borderRadius: 2,
                  mb: 1,
                  "&.Mui-selected": { bgcolor: "primary.light", color: "primary.main" },
                }}
              >
                <ListItemIcon>{getStatusIcon(module.status)}</ListItemIcon>
                <ListItemText
                  primary={module.name}
                  secondary={
                    module.status === "completed"
                      ? "Завершено"
                      : module.status === "in_progress"
                      ? "В процессе"
                      : "Не начато"
                  }
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Paper>

      {/* Основной контент */}
      <Box
        sx={{
          flex: 1,
          p: { xs: 2, sm: 4 },
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        {selectedModule ? (
          <>
            <Typography variant="h4" fontWeight="bold" gutterBottom sx={{ color: "black", textAlign: "center" }}>
              {selectedModule.name}
            </Typography>

            <Typography
              variant="body1"
              sx={{ mb: 4, maxWidth: 800, textAlign: "center", color: "text.primary", lineHeight: 1.6 }}
            >
              {selectedModule.description}
            </Typography>

            {step === "video" ? (
              <Box sx={{ width: "100%", maxWidth: 880, mb: 5 }}>
                <div
                  style={{
                    position: "relative",
                    paddingBottom: "56.25%",
                    height: 0,
                    overflow: "hidden",
                    borderRadius: 12,
                    background: "#000",
                  }}
                >
                  <iframe
                    src={selectedModule.video_url}
                    style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}
                    frameBorder="0"
                    allow="autoplay; fullscreen; picture-in-picture"
                    allowFullScreen
                  />
                </div>

                <Box sx={{ mt: 4, textAlign: "center" }}>
                  <Button
                    variant="contained"
                    size="large"
                    onClick={handleVideoWatched}
                    disabled={testLoading}
                    sx={{ minWidth: 240, py: 1.5, fontSize: "1.1rem" }}
                  >
                    Посмотрел
                  </Button>

                  {testLoading && (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                      Проверка наличия теста...
                    </Typography>
                  )}
                </Box>
              </Box>
            ) : (
              <Box sx={{ width: "100%", maxWidth: 800 }}>
                <Typography variant="h5" gutterBottom sx={{ color: "black" }}>
                  {test?.name || "Проверка знаний"}
                </Typography>

                <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
                  {test?.description} • Попыток осталось: {test?.attempts_left ?? "?"}
                </Typography>

                {test?.questions.map((q) => (
                  <Paper key={q.id} variant="outlined" sx={{ p: 3, mb: 3, borderRadius: 2 }}>
                    <Typography variant="subtitle1" fontWeight={500} gutterBottom sx={{ color: "black" }}>
                      {q.text}
                    </Typography>
                    {renderQuestion(q)}
                  </Paper>
                ))}

                {testError && <Alert severity="error" sx={{ mb: 3 }}>{testError}</Alert>}

                {testResult && (
                  <Alert severity={testResult.passed ? "success" : "warning"} sx={{ mb: 3 }}>
                    {testResult.passed
                      ? `Поздравляем! Набрано ${testResult.score} баллов`
                      : `Не пройдено (${testResult.score} / ${test?.max_score}). Осталось попыток: ${testResult.attempts_left}`}
                  </Alert>
                )}

                <Box sx={{ textAlign: "center", mt: 4 }}>
                  <Button
                    variant="contained"
                    size="large"
                    onClick={handleSubmitTest}
                    disabled={
                      !!test?.attempts_left && test.attempts_left <= 0 ||
                      Object.keys(answers).length < (test?.questions.length || 1)
                    }
                    sx={{ minWidth: 240, py: 1.5, fontSize: "1.1rem" }}
                  >
                    Отправить ответы
                  </Button>
                </Box>
              </Box>
            )}
          </>
        ) : (
          <Typography variant="h6" color="text.secondary" sx={{ mt: 8 }}>
            Выберите модуль слева
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default CourseDetails;