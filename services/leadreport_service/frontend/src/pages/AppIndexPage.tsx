import { Link } from "react-router-dom";

export function AppIndexPage() {
  return (
    <div className="min-h-screen bg-[#f8f8f8] text-[13px] text-[#333]">
      <div className="bg-[#417690] px-6 py-3 text-white">
        <span className="text-lg">Django administration</span>
      </div>
      <div className="bg-white px-6 py-2 text-xs text-[#666]">
        <Link to="/admin" className="text-[#417690] hover:underline">
          Главная
        </Link>{" "}
        › Leadreport
      </div>

      <div className="mx-auto max-w-3xl px-6 py-6">
        <div className="rounded border border-[#ccc] bg-white">
          <div className="bg-[#79aec8] px-3 py-2 text-sm font-semibold text-white">Leadreport</div>
          <ul className="divide-y divide-[#eee]">
            <li className="flex items-center justify-between px-3 py-2">
              <Link to="/admin/managers-list" className="text-[#417690] hover:underline">
                Sales managers
              </Link>
            </li>
            <li className="flex items-center justify-between px-3 py-2">
              <Link to="/admin/sources-list" className="text-[#417690] hover:underline">
                Lead sources
              </Link>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
