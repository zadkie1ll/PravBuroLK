import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/", label: "Новая UTM-система", end: true },
  { to: "/marketing/links", label: "Управление ссылками", end: true },
  { to: "/marketing/dictionaries", label: "Справочники", end: true },
  { to: "/legacy", label: "Старая UTM-система", end: true },
];

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f7f7f8] text-[#1c1c1e]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 md:px-6">
          <div className="flex min-w-0 flex-wrap items-center gap-3 md:gap-6">
            <h1 className="whitespace-nowrap text-base font-semibold">Статистика по источникам</h1>
            <nav className="flex flex-wrap gap-1 rounded-lg bg-[#f2f2f3] p-1">
              {TABS.map((tab) => (
                <NavLink
                  key={tab.to}
                  to={tab.to}
                  end={tab.end}
                  className={({ isActive }) =>
                    `whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition ${
                      isActive ? "bg-white text-[#1c1c1e] shadow-sm" : "text-gray-500 hover:text-[#1c1c1e]"
                    }`
                  }
                >
                  {tab.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <NavLink
            to="/marketing/create"
            className="whitespace-nowrap rounded-lg bg-[#1c1c1e] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#333]"
          >
            + Создать ссылку
          </NavLink>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 md:px-6">{children}</main>
    </div>
  );
}
