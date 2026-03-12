// Dashboard.tsx
import { Typography, Box, CircularProgress } from "@mui/material";
import "./Dashboard.css";
import { CourseList } from "../components/CourseList";
import type { Course } from "../lib/types/components"; // Предполагаем, что тип Course включает id, name, description, image_url, department, modules_count, user_progress (number | null)
import { LoadCourses } from "../lib/api";
import { useState, useEffect } from "react"; // Добавляем хуки для асинхронной загрузки
import {  useNavigate } from "react-router-dom";

const Dashboard = () => {
  const [courses, setCourses] = useState<Course[]>([]); // Состояние для курсов
  const [loading, setLoading] = useState(true); // Для индикации загрузки
  const [error, setError] = useState<string | null>(null); // Для ошибок

  const user_id = localStorage.getItem("user"); // string | null
  const department = localStorage.getItem("department"); // string | null
  const username = localStorage.getItem("username"); // string | null
  const navigate = useNavigate();
  const depsName = {
    'sales': "продажи",
    'marketing': "маркетинг",
    'moderation': "модерация",
    'firstline': "первая линия",
    'support': "сопровождение",
    'law': "юридический"
  }
  useEffect(() => {
    const fetchCourses = async () => {
      if (!user_id || !department) {
        setError("Отсутствует информация о пользователе или отделе");
        navigate("/auth", { replace: true });
        setLoading(false);
        
        return;
      }

      try {
        const parsedUserId = parseInt(user_id, 10); // Парсим в number
        if (isNaN(parsedUserId)) {
          throw new Error("Неверный ID пользователя");
        }
        const loadedCourses = await LoadCourses(parsedUserId, department);
        setCourses(loadedCourses);
      } catch (err) {
        setError((err as Error).message || "Ошибка загрузки курсов");
      } finally {
        setLoading(false);
      }
    };

    fetchCourses();
  }, []); // Загружаем один раз при монтировании

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
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        width: "100vw",
        height: "100vh",
        bgcolor: "background.default",
        overflow: "hidden",
        p: 0,
        m: 0,
      }}
      className="dashboard"
    >
      <Box
        sx={{
          p: 4,
          bgcolor: "lightblue",
        }}
        className="dashboard-header"
      >
        <Typography variant="h4" fontWeight="bold" color="black">
          Привет, {username} 👋
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Отдел: {department && department in depsName ? depsName[department as keyof typeof depsName] : "Неизвестный"}
        </Typography>
      </Box>
      <Box sx={{ flexGrow: 1, overflowY: "auto", p: 4 }}>
        <CourseList courses={courses} />
      </Box>
    </Box>
  );
};

export default Dashboard;