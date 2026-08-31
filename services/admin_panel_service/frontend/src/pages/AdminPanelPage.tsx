import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearToken, UserOut } from "../api/client";

const LEADREPORT_BASE_URL = import.meta.env.VITE_LEADREPORT_BASE_URL || "http://localhost:5175";
const CLIENT_SEARCH_BASE_URL = import.meta.env.VITE_CLIENT_SEARCH_BASE_URL || "http://localhost:5177";
const REFERRAL_STATS_BASE_URL = import.meta.env.VITE_REFERRAL_STATS_BASE_URL || "http://localhost:5178";
const PAYMENTS_DASHBOARD_BASE_URL = import.meta.env.VITE_CLIENT_SEARCH_BASE_URL || "http://localhost:5177";
const URLSHORTER_BASE_URL = import.meta.env.VITE_URLSHORTER_BASE_URL || "http://localhost:5179";

interface NavItem {
  id: string;
  label: string;
  description: string;
  icon: JSX.Element;
  url: (token: string) => string;
}

function Icon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  );
}

const NAV_ITEMS: NavItem[] = [
  {
    id: "client-search",
    label: "Поиск клиентов",
    description: "ФИО, телефон, ID",
    icon: <Icon path="M21 21l-4.35-4.35M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z" />,
    url: (token) => `${CLIENT_SEARCH_BASE_URL}/?token=${encodeURIComponent(token)}`,
  },
  {
    id: "referral-stats",
    label: "Реферальная статистика",
    description: "Клики и заявки по рефералкам",
    icon: <Icon path="M3 3v18h18M7 15l4-6 3 4 5-8" />,
    url: (token) => `${REFERRAL_STATS_BASE_URL}/?token=${encodeURIComponent(token)}`,
  },
  {
    id: "dashboard-visits",
    label: "Посещения ЛК",
    description: "Заходы по дням/неделям/месяцам",
    icon: <Icon path="M8 7V3m8 4V3M3 11h18M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" />,
    url: (token) => `${REFERRAL_STATS_BASE_URL}/visits?token=${encodeURIComponent(token)}`,
  },
  {
    id: "payments-dashboard",
    label: "Фактические платежи",
    description: "Статистика и последние платежи",
    icon: <Icon path="M12 2v20m5-17H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />,
    url: (token) => `${PAYMENTS_DASHBOARD_BASE_URL}/payments-dashboard?token=${encodeURIComponent(token)}`,
  },
  {
    id: "leadreport",
    label: "Отчёт по менеджерам",
    description: "Звонки и время разговоров",
    icon: <Icon path="M3 5a2 2 0 0 1 2-2h2.28a2 2 0 0 1 2 1.72l.45 3.16a2 2 0 0 1-.57 1.77l-1.4 1.4a16 16 0 0 0 6.19 6.19l1.4-1.4a2 2 0 0 1 1.77-.57l3.16.45a2 2 0 0 1 1.72 2V19a2 2 0 0 1-2 2h-1C9.72 21 3 14.28 3 6V5z" />,
    url: (token) => `${LEADREPORT_BASE_URL}/admin?token=${encodeURIComponent(token)}`,
  },
  {
    id: "urlshorter",
    label: "Статистика по источникам",
    description: "Короткие ссылки, клики по UTM",
    icon: <Icon path="M13.5 10.5 21 3m0 0h-5.5M21 3v5.5M10 6H6a3 3 0 0 0-3 3v9a3 3 0 0 0 3 3h9a3 3 0 0 0 3-3v-4" />,
    url: (token) => `${URLSHORTER_BASE_URL}/?token=${encodeURIComponent(token)}`,
  },
];

export function AdminPanelPage() {
  const navigate = useNavigate();
  const [activeId, setActiveId] = useState(NAV_ITEMS[0].id);
  const [user, setUser] = useState<UserOut | null>(null);
  const token = localStorage.getItem("access_token") || "";

  useEffect(() => {
    api
      .me()
      .then((res) => setUser(res.user))
      .catch(() => setUser(null));
  }, []);

  function logout() {
    clearToken();
    navigate("/login");
  }

  const active = NAV_ITEMS.find((item) => item.id === activeId) ?? NAV_ITEMS[0];

  return (
    <div className="flex h-screen bg-[#f3f4f6] text-[#333]">
      <aside className="flex w-64 flex-shrink-0 flex-col bg-[#1c1c1e] text-gray-200">
        <div className="flex items-center gap-2 border-b border-white/10 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600">
            <Icon path="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">Админ-панель</div>
            <div className="text-xs text-gray-400">панель управления</div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveId(item.id)}
              className={`flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${
                item.id === activeId
                  ? "bg-white/10 text-white"
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-100"
              }`}
            >
              <span className="mt-0.5">{item.icon}</span>
              <span>
                <span className="block font-medium">{item.label}</span>
                <span className="block text-xs text-gray-500">{item.description}</span>
              </span>
            </button>
          ))}
        </nav>

        <div className="border-t border-white/10 px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-600 text-xs font-semibold text-white">
                {(user?.username || "?").slice(0, 1).toUpperCase()}
              </div>
              <div>
                <div className="text-sm font-medium text-white">{user?.username ?? "..."}</div>
                <div className="text-xs text-gray-500">{user?.is_staff ? "администратор" : "сотрудник"}</div>
              </div>
            </div>
            <button
              onClick={logout}
              title="Выйти"
              className="rounded-md p-2 text-gray-400 transition hover:bg-white/10 hover:text-white"
            >
              <Icon path="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4m7 14 5-5-5-5m5 5H9" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-[#333]">{active.label}</h1>
            <p className="text-sm text-gray-500">{active.description}</p>
          </div>
        </header>

        <main className="flex-1 overflow-hidden bg-[#f3f4f6]">
          {token ? (
            <iframe
              key={active.id}
              src={active.url(token)}
              title={active.label}
              className="h-full w-full border-0"
            />
          ) : (
            <div className="p-6 text-sm text-gray-500">Не удалось получить токен доступа.</div>
          )}
        </main>
      </div>
    </div>
  );
}
