import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(false);
    try {
      const response = await api.login(username, password);
      setToken(response.access_token);
      navigate(response.user.is_staff ? "/admin-panel" : "/");
    } catch (err) {
      setError(true);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f7f7f8]">
      <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <h2 className="mb-6 text-center text-lg font-semibold text-[#1c1c1e]">Вход в личный кабинет</h2>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">Неверное имя пользователя или пароль.</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-xs font-medium text-gray-500">
              Имя пользователя
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-[#1c1c1e] shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-medium text-gray-500">
              Пароль
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-[#1c1c1e] shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>

          <button
            type="submit"
            className="w-full rounded-lg bg-[#1c1c1e] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#333]"
          >
            Войти
          </button>
        </form>
      </div>
    </div>
  );
}
