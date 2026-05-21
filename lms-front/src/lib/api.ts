// api.ts (LoadCourses с параметрами в URL)
import type { Course } from "./types/components"; // Убедитесь, что тип Course включает user_progress: number | null;
import { backend } from "./utils";
import type { Module } from "./types/components";
export async function LoadCourses(department: string): Promise<Course[]> {
  const params = new URLSearchParams({
    department: department,
  });

  const response = await fetch(`${backend}/api/education/courses/?${params.toString()}`, {
    method: 'GET', // GET по умолчанию, но уточняем
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json', // Изменяем на json, так как ответ JSON
    },
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'Ошибка загрузки курсов');
  }
  return data.courses as Course[]; // Возвращаем массив курсов из {detail: "ok", courses: [...]}
}
export async function LoadModules(course_id: number): Promise<Module[]> {
  const params = new URLSearchParams({
    course: course_id.toString(),
  });

  const response = await fetch(`${backend}/api/education/modules/?${params.toString()}`, {
    method: 'GET',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'Ошибка загрузки модулей');
  }
  return data.modules as Module[]; // Предполагаем ответ {detail: "ok", modules: [...]}
}
