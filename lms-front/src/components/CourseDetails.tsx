// CourseDetails.tsx
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
import CheckCircleIcon from "@mui/icons-material/CheckCircle"; // Иконка для завершённых модулей
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked"; // Иконка для не начатых
import TimelapseIcon from "@mui/icons-material/Timelapse"; // Иконка для в процессе
import { LoadModules } from "../lib/api"; // Ваша функция для загрузки модулей

// Новые API функции (предполагаем, что они реализованы в ../lib/api)
async function LoadTest(moduleId: number, userId: number) {
  // Вызов /api/get_test?module=moduleId&user=userId
  const response = await fetch(`${backend}/api/get_test?module=${moduleId}&user=${userId}`);
  if (!response.ok) {
    if (response.status === 404) return null; // Нет теста
    throw new Error("Ошибка загрузки теста");
  }
  return await response.json();
}

async function SubmitTest(moduleId: number, userId: number, answers: Record<number, any>) {
  // Вызов /api/submit_test с POST {user_id, module_id, answers}
  const response = await fetch(`${backend}/api/submit_test/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, module_id: moduleId, answers }),
  });
  if (!response.ok) throw new Error("Ошибка отправки теста");
  return await response.json();
}

async function UpdateModuleStatus(moduleId: number, userId: number, status: string) {
  // POST /api/update_module_progress {user_id, module_id, status}
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
  const { id } = useParams<{ id: string }>(); // ID курса из URL
  const [modules, setModules] = useState<Module[]>([]);
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);
  const [currentStep, setCurrentStep] = useState<"video" | "test">("video");
  const [test, setTest] = useState<Test | null>(null);
  const [answers, setAnswers] = useState<Record<number, any>>({});
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ score: number; passed: boolean; attempts_left: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const user_id = parseInt(localStorage.getItem("user") || "0", 10); // Получаем user_id
  const navigate = useNavigate();
  // const isSubmitDisabled =
  // !test ||
  // test.attempts_left <= 0 ||
  // Object.keys(answers).length < test.questions.length;
  // Вычисляем прогресс курса
  const completedModules = modules.filter((mod) => mod.status === "completed").length;
  const progress = (completedModules / modules.length) * 100 || 0;

  useEffect(() => {
    const fetchModules = async () => {
      if (!id || isNaN(user_id)) {
        setError("Неверный ID курса или пользователя");
        setLoading(false);
        return;
      }
      try {
        let loadedModules = await LoadModules(parseInt(id, 10), user_id);
        // Сортируем модули по order (на всякий случай)
        loadedModules = loadedModules.sort((a, b) => a.order - b.order);
        setModules(loadedModules);
        // Выбираем первый не завершённый модуль по умолчанию
        const firstIncomplete = loadedModules.find(
          (mod) => mod.status !== "completed"
        ) || loadedModules[0];
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
    if (selectedModule) {
      setCurrentStep("video");
      setTest(null);
      setAnswers({});
      setTestResult(null);
      setTestError(null);
      fetchTest();
      // Set to in_progress if not started
      if (selectedModule.status === "not_started") {
        UpdateModuleStatus(selectedModule.id, user_id, "in_progress").catch((err) => console.error(err));
        updateLocalStatus(selectedModule.id, "in_progress");
      }
    }
  }, [selectedModule]);

  const fetchTest = async () => {
    if (!selectedModule) return;
    setTestLoading(true);
    try {
      const testData = await LoadTest(selectedModule.id, user_id);
      setTest(testData?.test || null);
    } catch (err) {
      setTestError((err as Error).message);
    } finally {
      setTestLoading(false);
    }
  };

  // Функция для перехода к следующему модулю
  const goToNextModule = () => {
    if (!selectedModule) return;
    const currentIndex = modules.findIndex((mod) => mod.id === selectedModule.id);
    if (currentIndex < modules.length - 1) {
      const nextModule = modules[currentIndex + 1];
      setSelectedModule(nextModule);
    }
  };

  // Обработка завершения видео (кнопкой)
// Обработка завершения видео
const handleCompleteVideo = async () => {
  if (!selectedModule) return;

  try {
    // Отмечаем, что модуль в процессе (если ещё не стоит)
    if (selectedModule.status !== "in_progress" && selectedModule.status !== "completed") {
      await UpdateModuleStatus(selectedModule.id, user_id, "in_progress");
      updateLocalStatus(selectedModule.id, "in_progress");
    }

    if (test) {
      // Есть тест → переходим к нему
      setCurrentStep("test");
    } else {
      // Нет теста → сразу завершаем модуль
      await UpdateModuleStatus(selectedModule.id, user_id, "completed");
      updateLocalStatus(selectedModule.id, "completed");
      goToNextModule();
    }
  } catch (err) {
    setError((err as Error).message || "Ошибка при обновлении статуса");
  }
};

  // Обновление локального статуса
  const updateLocalStatus = (moduleId: number, newStatus: string) => {
    setModules((prev) =>
      prev.map((mod) => (mod.id === moduleId ? { ...mod, status: newStatus } : mod))
    );
  };

  // Обработка изменения ответа
  const handleAnswerChange = (questionId: number, value: any) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  // Отправка теста
  const handleSubmitTest = async () => {
    if (!selectedModule || !test) return;
    try {
      const result = await SubmitTest(selectedModule.id, user_id, answers);
      setTestResult(result);
      if (result.passed) {
        updateLocalStatus(selectedModule.id, "completed");
        setTimeout(goToNextModule, 2000); // Задержка для показа результата
      } else {
        // Обновить attempts_left в test
        setTest((prev) => prev ? { ...prev, attempts_left: result.attempts_left } : null);
      }
    } catch (err) {
      setTestError((err as Error).message);
    }
  };

  // Рендер вопроса
  const renderQuestion = (question: Question) => {
    switch (question.question_type) {
      case "choice":
        return (
          <Box>
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
                color="black"
                sx={{color: 'black'}}
              />
            ))}
          </Box>
        );
      case "multi_choice":
        return (
          <Box>
            {question.options.map((opt) => (
              <FormControlLabel
                key={opt.id}
                control={
                  <Checkbox
                    
                    checked={answers[question.id]?.ids?.includes(opt.id) || false}
                    onChange={(e) => {
                      const ids = answers[question.id]?.ids || [];
                      const newIds = e.target.checked ? [...ids, opt.id] : ids.filter((id: number) => id !== opt.id);
                      handleAnswerChange(question.id, { ids: newIds });
                    }}
                  />
                }
                label={opt.text}
                color="black"
                sx={{color:'black'}}
              />
            ))}
          </Box>
        );
      case "text":
        return (
          <TextField
            fullWidth
            sx={{color:'black'}}
            value={answers[question.id]?.text || ""}
            onChange={(e) => handleAnswerChange(question.id, { text: e.target.value })}
          />
        );
      default:
        return null;
    }
  };

  // Функция для получения иконки статуса
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
        <Typography color="error">Ошибка: {error}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{
      display: "flex",
      flexDirection: { xs: "column", sm: "row" },
      width: "100vw", // Change to 100vw for full viewport width
      maxWidth: "none", // Override any max-width
      height: "100vh",
      bgcolor: "background.default",
      overflow: "hidden",
      margin: 0, // Remove any implicit margins
      padding: 0,
    }}>
      {/* Левая часть: Список модулей (sidebar как в Khan Academy) */}
      <Paper
        elevation={3}
        sx={{
          width: { xs: "100%", sm: "30%" },
          borderRight: { sm: 0 },
          borderBottom: { xs: 1, sm: 0 },
          borderColor: "divider",
          pr: 2,
          overflowY: "auto",
          p: 2,
          bgcolor: "white",
        }}
      >
        <Button onClick={()=>navigate("/dashboard")}>Вернуться в меню</Button>
        <Typography variant="h5" sx={{ fontWeight: "bold", mb: 1 }}>
          Модули курса
        </Typography>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Прогресс: {completedModules}/{modules.length} модулей завершено
          </Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mt: 1, height: 8, borderRadius: 4 }} />
        </Box>
        <Divider sx={{ mb: 2 }} />
        <List>
          {modules.map((module) => (
            <ListItem disablePadding key={module.id}>
              <ListItemButton
                selected={selectedModule?.id === module.id}
                onClick={() => setSelectedModule(module)}
                sx={{
                  borderRadius: 2,
                  mb: 1,
                  "&.Mui-selected": {
                    bgcolor: "primary.light",
                    color: "primary.main",
                  },
                  "&:hover": {
                    bgcolor: "action.hover",
                  },
                }}
              >
                <ListItemIcon>
                  {getStatusIcon(module.status)}
                </ListItemIcon>
                <ListItemText
                  primary={<Typography variant="subtitle1" sx={{ fontWeight: "medium" }}>{module.name}</Typography>}
                  secondary={
                    <Typography variant="body2" color="text.secondary">
                      Статус: {module.status === "completed" ? "Завершено" : module.status === "in_progress" ? "В процессе" : "Не начато"}
                    </Typography>
                  }
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Paper>
      {/* Правая часть: Видео или тест (основной контент) */}
      <Box
        sx={{
          width: { xs: "100%", sm: "70%" },
          pl: { sm: 4 },
          pr: 2,
          py: 4,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          flexGrow: 1,
        }}
      >
        {selectedModule ? (
          <>
            <Typography variant="h4" sx={{ fontWeight: "bold", mb: 2, textAlign: "center", color: 'black' }}>
              {selectedModule.name}
            </Typography>
            <Typography variant="body1" sx={{ mb: 4, color: "black", lineHeight: 1.6, maxWidth: 800, textAlign: "center" }}>
              {selectedModule.description}
            </Typography>
            {currentStep === "video" ? (
              <Box sx={{ width: "100%", maxWidth: 800, mb: 4 }}>
                <div style={{ position: 'relative', paddingBottom: '56.25%', height: 0, overflow: 'hidden', borderRadius: 2 }}>
                  <iframe
                    src={selectedModule.video_url}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: "#000" }}
                    frameBorder="0"
                    allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
                    allowFullScreen
                  ></iframe>
                </div>

                {testError && <Alert severity="error" sx={{ mt: 2 }}>{testError}</Alert>}

                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleCompleteVideo}
                  disabled={testLoading}  // отключаем пока грузится тест
                  sx={{ mt: 3, display: 'block', mx: 'auto', minWidth: 220 }}
                >
                  {test ? "Завершить видео и перейти к тесту" : "Завершить модуль"}
                </Button>
              </Box>
            ) : test ? (
              // ── блок с тестом остаётся без изменений ──
              <Box sx={{ width: "100%", maxWidth: 800 }}>
                <Typography variant="h5" sx={{ mb: 2, color: 'black' }}>
                  {test.name}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
                  {test.description} | Попыток осталось: {test.attempts_left}
                </Typography>

                {test.questions.map((question) => (
                  <Box key={question.id} sx={{ mb: 4, p: 2, border: 1, borderColor: "divider", borderRadius: 2 }}>
                    <Typography variant="subtitle1" sx={{ mb: 1, color: 'black' }}>
                      {question.text}
                    </Typography>
                    {renderQuestion(question)}
                  </Box>
                ))}

                {testError && <Alert severity="error" sx={{ mb: 2 }}>{testError}</Alert>}
                {testResult && (
                  <Alert severity={testResult.passed ? "success" : "warning"} sx={{ mb: 2 }}>
                    Баллы: {testResult.score} | {testResult.passed ? "Пройдено!" : "Не пройдено"} | Попыток осталось: {testResult.attempts_left}
                  </Alert>
                )}

                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleSubmitTest}
                  disabled={test.attempts_left <= 0 || Object.keys(answers).length < test.questions.length}
                  sx={{ minWidth: 220 }}
                >
                  Отправить тест
                </Button>
              </Box>
            ) : (
              <Typography color="text.secondary" sx={{ mt: 4 }}>
                Нет теста для этого модуля. Модуль можно завершить.
              </Typography>
            )}            {currentStep === "video" && test && (
              <Button
                variant="outlined"
                onClick={() => setCurrentStep("test")}
                sx={{ mt: 2 }}
              >
                Перейти к тесту (если видео просмотрено)
              </Button>
            )}
          </>
        ) : (
          <Typography variant="h6" sx={{ mt: 4 }}>
            Выберите модуль из списка слева
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default CourseDetails;