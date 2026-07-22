import { backend } from "./utils";
import { authHeaders } from "./token";

export interface HrDepartment {
  code: string;
  name: string;
}

export interface HrMaterial {
  id: number;
  title: string;
  material_type: string;
  file: string;
  order: number;
  is_active: boolean;
}

export interface HrTestSummary {
  id: number;
  name: string;
  is_active: boolean;
  questions_count: number;
}

export interface HrModule {
  id: number;
  course_id: number;
  name: string;
  description: string;
  video_url: string;
  private_video: string;
  order: number;
  is_active: boolean;
  materials: HrMaterial[];
  test: HrTestSummary | null;
}

export interface HrCourse {
  id: number;
  name: string;
  description: string;
  image_url: string;
  photo_url: string;
  department_codes: string[];
  is_active: boolean;
}

export interface HrCourseTree extends HrCourse {
  modules: HrModule[];
}

export interface HrQuestionOption {
  id: number;
  text: string;
  is_correct: boolean;
  order: number;
}

export interface HrQuestion {
  id: number;
  text: string;
  question_type: string;
  score: number;
  order: number;
  options: HrQuestionOption[];
}

export interface HrTest {
  id: number;
  module_id: number;
  name: string;
  description: string;
  max_score: number;
  passing_score: number;
  max_attempts: number;
  is_active: boolean;
  questions: HrQuestion[];
}

export interface HrTraineeListItem {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  departments: HrDepartment[];
  progress_count: number;
  completed_count: number;
  attempts_count: number;
  passed_attempts_count: number;
}

export interface HrModuleProgressRow {
  module_id: number;
  module_name: string;
  status: string;
  test_id: number | null;
  attempts_used: number;
  latest_score: number | null;
  latest_passed: boolean | null;
}

export interface HrCourseProgressRow {
  course_id: number;
  course_name: string;
  total: number;
  completed: number;
  modules: HrModuleProgressRow[];
}

export interface HrTraineeDetail {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  departments: HrDepartment[];
  course_rows: HrCourseProgressRow[];
}

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${backend}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((data as { detail?: string }).detail || `Ошибка запроса (${response.status})`);
  }
  return data as T;
}

function jsonBody(body: unknown): RequestInit {
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export const listDepartments = () => req<HrDepartment[]>("/hr/departments");
export const loadDashboard = () => req<HrCourseTree[]>("/hr/dashboard");

export const createCourse = (payload: Partial<HrCourse>) =>
  req<HrCourse>("/hr/courses", { method: "POST", ...jsonBody(payload) });
export const updateCourse = (id: number, payload: Partial<HrCourse>) =>
  req<HrCourse>(`/hr/courses/${id}`, { method: "PUT", ...jsonBody(payload) });

function moduleFormData(payload: {
  course_id: number;
  name: string;
  description?: string;
  video_url?: string;
  order?: number;
  is_active?: boolean;
  private_video?: File | null;
}): FormData {
  const fd = new FormData();
  fd.append("course_id", String(payload.course_id));
  fd.append("name", payload.name);
  fd.append("description", payload.description || "");
  fd.append("video_url", payload.video_url || "");
  fd.append("order", String(payload.order ?? 1));
  fd.append("is_active", String(payload.is_active ?? true));
  if (payload.private_video) fd.append("private_video", payload.private_video);
  return fd;
}

export const createModule = (payload: Parameters<typeof moduleFormData>[0]) =>
  req<HrModule>("/hr/modules", { method: "POST", body: moduleFormData(payload) });
export const updateModule = (id: number, payload: Parameters<typeof moduleFormData>[0]) =>
  req<HrModule>(`/hr/modules/${id}`, { method: "PUT", body: moduleFormData(payload) });

function materialFormData(payload: {
  title: string;
  material_type?: string;
  order?: number;
  is_active?: boolean;
  file?: File | null;
}): FormData {
  const fd = new FormData();
  fd.append("title", payload.title);
  fd.append("material_type", payload.material_type || "pdf");
  fd.append("order", String(payload.order ?? 1));
  fd.append("is_active", String(payload.is_active ?? true));
  if (payload.file) fd.append("file", payload.file);
  return fd;
}

export const createMaterial = (moduleId: number, payload: Parameters<typeof materialFormData>[0]) =>
  req<HrMaterial>(`/hr/modules/${moduleId}/materials`, { method: "POST", body: materialFormData(payload) });
export const updateMaterial = (id: number, payload: Parameters<typeof materialFormData>[0]) =>
  req<HrMaterial>(`/hr/materials/${id}`, { method: "PUT", body: materialFormData(payload) });
export const deleteMaterial = (id: number) => req<{ detail: string }>(`/hr/materials/${id}`, { method: "DELETE" });

export const getOrCreateTest = (moduleId: number) => req<HrTest>(`/hr/tests/${moduleId}`);
export const updateTest = (id: number, payload: Partial<HrTest>) =>
  req<HrTest>(`/hr/tests/${id}`, { method: "PUT", ...jsonBody(payload) });

export const createQuestion = (testId: number, payload: Partial<HrQuestion>) =>
  req<HrQuestion>(`/hr/tests/${testId}/questions`, { method: "POST", ...jsonBody(payload) });
export const updateQuestion = (id: number, payload: Partial<HrQuestion>) =>
  req<HrQuestion>(`/hr/questions/${id}`, { method: "PUT", ...jsonBody(payload) });
export const deleteQuestion = (id: number) => req<{ detail: string }>(`/hr/questions/${id}`, { method: "DELETE" });

export const createOption = (questionId: number, payload: Partial<HrQuestionOption>) =>
  req<HrQuestionOption>(`/hr/questions/${questionId}/options`, { method: "POST", ...jsonBody(payload) });
export const updateOption = (id: number, payload: Partial<HrQuestionOption>) =>
  req<HrQuestionOption>(`/hr/options/${id}`, { method: "PUT", ...jsonBody(payload) });
export const deleteOption = (id: number) => req<{ detail: string }>(`/hr/options/${id}`, { method: "DELETE" });

export const listTrainees = () => req<HrTraineeListItem[]>("/hr/trainees");
export const createTrainee = (payload: {
  username: string;
  first_name?: string;
  last_name?: string;
  password?: string;
  department_codes: string[];
  is_active?: boolean;
}) => req<{ detail: string; username: string; password: string; user: HrTraineeListItem }>("/hr/trainees", { method: "POST", ...jsonBody(payload) });
export const getTrainee = (id: number) => req<HrTraineeDetail>(`/hr/trainees/${id}`);
export const updateTrainee = (id: number, payload: { department_codes: string[]; is_active: boolean }) =>
  req<HrTraineeDetail>(`/hr/trainees/${id}`, { method: "PUT", ...jsonBody(payload) });
