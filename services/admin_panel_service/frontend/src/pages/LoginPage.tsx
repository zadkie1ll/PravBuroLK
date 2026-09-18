import { FormEvent, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, setToken } from "../api/client";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const expired = searchParams.has("expired");
  const ssoFailed = searchParams.has("sso_failed");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(false);
    try {
      const response = await api.login(username, password);
      setToken(response.access_token);
      navigate("/admin-panel");
    } catch (err) {
      setError(true);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f3f4f6] px-4">
      <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="mb-6 flex flex-col items-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-[#1c1c1e]">
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={1.8} className="h-6 w-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-[#333]">Вход в админ-панель</h2>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">
            Неверное имя пользователя или пароль.
          </div>
        )}

        {!error && expired && (
          <div className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-700">
            Сессия истекла, войдите заново
          </div>
        )}

        {!error && ssoFailed && (
          <div className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-700">
            Не удалось войти через админку ботов — попробуйте обычный вход
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-500">
              Имя пользователя
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
              autoCapitalize="none"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-3 text-base text-[#333] shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-500">
              Пароль
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-3 text-base text-[#333] shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>

          <button
            type="submit"
            className="w-full rounded-lg bg-[#1c1c1e] px-4 py-3 text-base font-medium text-white transition hover:bg-[#333]"
          >
            Войти
          </button>
        </form>
      </div>
    </div>
  );
}
