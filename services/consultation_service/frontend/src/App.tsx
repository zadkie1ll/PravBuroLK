import { Route, Routes } from "react-router-dom";
import { ConsultationPage } from "./pages/ConsultationPage";
import { ConsultationPrintPage } from "./pages/ConsultationPrintPage";

export default function App() {
  return (
    <Routes>
      {/* Свой поддомен (pdf.prav-buro.ru) — без префикса /consultation/, домен уже
          говорит, что это за сервис. */}
      <Route path="/:dealId/print" element={<ConsultationPrintPage />} />
      <Route path="/:dealId" element={<ConsultationPage />} />
    </Routes>
  );
}
