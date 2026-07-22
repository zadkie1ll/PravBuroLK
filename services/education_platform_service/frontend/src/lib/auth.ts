import type { LoginResponse, MeResponse, RegistrationResponse } from "./types/auth"
import { backend } from "./utils"
import { authHeaders, setToken } from "./token"

export async function RegistateUser(login: string, password: string, department: string): Promise<RegistrationResponse> {
  const response = await fetch(`${backend}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: login, password, department }),
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || "Ошибка регистрации")
  }
  setToken(data.access_token)
  return data as RegistrationResponse
}

export async function GetInfoAboutMe(): Promise<MeResponse> {
  const response = await fetch(`${backend}/auth/me`, {
    headers: authHeaders(),
  })
  if (!response.ok) {
    throw new Error(String(response.status))
  }
  return response.json() as Promise<MeResponse>
}

export async function LoginUser(login: string, password: string, department?: string) {
  const response = await fetch(`${backend}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: login, password, ...(department ? { department } : {}) }),
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || "Ошибка входа")
  }
  setToken(data.access_token)
  return data as LoginResponse
}
