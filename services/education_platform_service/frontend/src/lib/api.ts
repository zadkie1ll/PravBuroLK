// api.ts (LoadCourses с параметрами в URL)
import type { Course } from "./types/components"; // Убедитесь, что тип Course включает user_progress: number | null;
import { backend } from "./utils";
import { authHeaders } from "./token";
import type { Module } from "./types/components";
export async function LoadCourses(department: string): Promise<Course[]> {
  const params = new URLSearchParams({
    department: department,
  });

  const response = await fetch(`${backend}/courses?${params.toString()}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
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

  const response = await fetch(`${backend}/modules?${params.toString()}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'Ошибка загрузки модулей');
  }
  return data.modules as Module[]; // Предполагаем ответ {detail: "ok", modules: [...]}
}
