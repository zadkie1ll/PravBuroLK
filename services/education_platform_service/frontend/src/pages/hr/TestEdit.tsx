import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Box,
  Typography,
  Button,
  Paper,
  TextField,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Stack,
  Divider,
  IconButton,
  CircularProgress,
  Alert,
  Select,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import { useStaffGuard } from "../../lib/useStaffGuard";
import {
  getOrCreateTest,
  updateTest,
  createQuestion,
  updateQuestion,
  deleteQuestion,
  createOption,
  updateOption,
  deleteOption,
  type HrTest,
  type HrQuestion,
} from "../../lib/hrApi";

function QuestionEditor({ question, onChanged }: { question: HrQuestion; onChanged: () => void }) {
  const [text, setText] = useState(question.text);
  const [type, setType] = useState(question.question_type);
  const [score, setScore] = useState(question.score);
  const [order, setOrder] = useState(question.order);
  const [newOptionText, setNewOptionText] = useState("");

  const save = async () => {
    await updateQuestion(question.id, { text, question_type: type, score, order });
    onChanged();
  };

  const addOption = async () => {
    if (!newOptionText.trim()) return;
    await createOption(question.id, { text: newOptionText, is_correct: false, order: question.options.length + 1 });
    setNewOptionText("");
    onChanged();
  };

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Stack spacing={1}>
        <TextField label="Текст вопроса" value={text} onChange={(e) => setText(e.target.value)} multiline fullWidth />
        <Stack direction="row" spacing={2}>
          <Select value={type} onChange={(e) => setType(e.target.value)} size="small">
            <MenuItem value="choice">Один вариант</MenuItem>
            <MenuItem value="multi_choice">Несколько вариантов</MenuItem>
            <MenuItem value="text">Текстовый ответ</MenuItem>
          </Select>
          <TextField label="Баллы" type="number" size="small" value={score} onChange={(e) => setScore(Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="Порядок" type="number" size="small" value={order} onChange={(e) => setOrder(Number(e.target.value))} sx={{ width: 100 }} />
          <Button variant="outlined" onClick={save}>
            Сохранить вопрос
          </Button>
          <IconButton
            onClick={async () => {
              await deleteQuestion(question.id);
              onChanged();
            }}
          >
            <DeleteIcon />
          </IconButton>
        </Stack>

        <Divider sx={{ my: 1 }} />
        <Typography variant="subtitle2">Варианты ответа</Typography>
        {question.options.map((option) => (
          <Stack key={option.id} direction="row" spacing={2} alignItems="center">
            <TextField
              size="small"
              value={option.text}
              sx={{ flexGrow: 1 }}
              onChange={(e) => {
                option.text = e.target.value;
                onChanged();
              }}
              onBlur={() => updateOption(option.id, { text: option.text, is_correct: option.is_correct, order: option.order })}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={option.is_correct}
                  onChange={async (e) => {
                    await updateOption(option.id, { text: option.text, is_correct: e.target.checked, order: option.order });
                    onChanged();
                  }}
                />
              }
              label="Верный"
            />
            <IconButton
              size="small"
              onClick={async () => {
                await deleteOption(option.id);
                onChanged();
              }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Stack>
        ))}
        <Stack direction="row" spacing={1}>
          <TextField
            size="small"
            placeholder="Новый вариант ответа"
            value={newOptionText}
            onChange={(e) => setNewOptionText(e.target.value)}
            sx={{ flexGrow: 1 }}
          />
          <Button size="small" onClick={addOption}>
            + Вариант
          </Button>
        </Stack>
      </Stack>
    </Paper>
  );
}

export default function TestEdit() {
  const ready = useStaffGuard();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [test, setTest] = useState<HrTest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    if (!id) return;
    try {
      const data = await getOrCreateTest(Number(id));
      setTest(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (ready) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, id]);

  const saveMeta = async () => {
    if (!test) return;
    const updated = await updateTest(test.id, {
      name: test.name,
      description: test.description,
      max_score: test.max_score,
      passing_score: test.passing_score,
      max_attempts: test.max_attempts,
      is_active: test.is_active,
    });
    setTest(updated);
  };

  const addQuestion = async () => {
    if (!test) return;
    await createQuestion(test.id, { text: "Новый вопрос", question_type: "choice", score: 1, order: test.questions.length + 1 });
    refresh();
  };

  if (!ready) return null;
  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 6 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (error || !test) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error || "Тест не найден"}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 800, mx: "auto" }}>
      <Button onClick={() => navigate("/hr")} sx={{ mb: 2 }}>
        ← Назад в HR
      </Button>
      <Typography variant="h5" fontWeight="bold" sx={{ mb: 2 }}>
        Редактирование теста
      </Typography>

      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Stack spacing={2}>
          <TextField label="Название" value={test.name} onChange={(e) => setTest({ ...test, name: e.target.value })} fullWidth />
          <TextField label="Описание" value={test.description} onChange={(e) => setTest({ ...test, description: e.target.value })} multiline fullWidth />
          <Stack direction="row" spacing={2}>
            <TextField label="Макс. баллов" type="number" value={test.max_score} onChange={(e) => setTest({ ...test, max_score: Number(e.target.value) })} />
            <TextField label="Проходной балл" type="number" value={test.passing_score} onChange={(e) => setTest({ ...test, passing_score: Number(e.target.value) })} />
            <TextField label="Макс. попыток" type="number" value={test.max_attempts} onChange={(e) => setTest({ ...test, max_attempts: Number(e.target.value) })} />
          </Stack>
          <FormControlLabel
            control={<Checkbox checked={test.is_active} onChange={(e) => setTest({ ...test, is_active: e.target.checked })} />}
            label="Активен"
          />
          <Button variant="contained" onClick={saveMeta} sx={{ alignSelf: "flex-start" }}>
            Сохранить тест
          </Button>
        </Stack>
      </Paper>

      <Typography variant="h6" sx={{ mb: 1 }}>
        Вопросы
      </Typography>
      {test.questions.map((question) => (
        <QuestionEditor key={question.id} question={question} onChanged={refresh} />
      ))}
      <Button variant="outlined" onClick={addQuestion}>
        + Вопрос
      </Button>
    </Box>
  );
}
