// Dashboard.tsx
import { Typography, Box, CircularProgress } from "@mui/material";
import "./Dashboard.css";
import { CourseList } from "../components/CourseList";
import type { Course } from "../lib/types/components"; // Предполагаем, что тип Course включает id, name, description, image_url, department, modules_count, user_progress (number | null)
import { LoadCourses } from "../lib/api";
import { useState, useEffect } from "react"; // Добавляем хуки для асинхронной загрузки
import {  useNavigate } from "react-router-dom";
import { GetInfoAboutMe } from "../lib/auth";

const Dashboard = () => {
  const [courses, setCourses] = useState<Course[]>([]); // Состояние для курсов
  const [loading, setLoading] = useState(true); // Для индикации загрузки
  const [error, setError] = useState<string | null>(null); // Для ошибок

  const [department, setDepartment] = useState<string | null>(localStorage.getItem("department"));
  const [username, setUsername] = useState<string | null>(localStorage.getItem("username"));
  const [departmentNames, setDepartmentNames] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("departments") || "[]") as { name: string }[];
      return saved.map((item) => item.name).filter(Boolean);
    } catch {
      return [];
    }
  });
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
      try {
        let activeDepartment = department;
        if (!activeDepartment) {
          const me = await GetInfoAboutMe();
          activeDepartment = me.user.department;
          localStorage.setItem("user", me.user.id.toString());
          localStorage.setItem("username", me.user.username);
          localStorage.setItem("department", activeDepartment);
          localStorage.setItem("departments", JSON.stringify(me.user.departments || []));
          localStorage.setItem("is_staff", String(me.user.is_staff));
          setUsername(me.user.username);
          setDepartment(activeDepartment);
          setDepartmentNames((me.user.departments || []).map((item) => item.name));
        }
        if (!activeDepartment) {
          navigate("/auth", { replace: true });
          return;
        }
        const loadedCourses = await LoadCourses(activeDepartment);
        setCourses(loadedCourses);
      } catch (err) {
        if ((err as Error).message === "403" || (err as Error).message === "401") {
          navigate("/auth", { replace: true });
          return;
        }
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
        width: "100%",
        p: 0,
        m: 0,
      }}
      className="dashboard"
    >
      <Box
        className="dashboard-header"
      >
        <div className="dashboard-container">
        <Typography variant="h4" fontWeight="bold" color="black">
          Привет, {username} 👋
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Отделы: {departmentNames.length > 0 ? departmentNames.join(", ") : department && department in depsName ? depsName[department as keyof typeof depsName] : "Неизвестный"}
        </Typography>
        </div>
      </Box>
      <Box component="main" className="dashboard-content">
        <div className="dashboard-container">
          <Typography component="h2" variant="h5" fontWeight="bold" sx={{ mb: 3 }}>Мои курсы</Typography>
          <CourseList courses={courses} />
        </div>
      </Box>
    </Box>
  );
};

export default Dashboard;
