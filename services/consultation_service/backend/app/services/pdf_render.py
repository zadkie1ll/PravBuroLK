from __future__ import annotations

from playwright.sync_api import sync_playwright

from ..config import settings


def render_deal_to_pdf(deal_id: str, token: str) -> bytes:
    """Открывает read-only print-роут собственного React-фронтенда и печатает его в PDF.

    Один источник дизайна: и интерактивная страница, и эта — один и тот же React-компонент
    отчёта (см. frontend/src/components/report), поэтому PDF не может разъехаться с тем,
    что видел клиент на сайте.
    """
    url = f"{settings.print_base_url}/{deal_id}/print?token={token}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30_000)
            # Фронтенд сам выставляет @page{size: 120mm 213.333mm; margin:0} под текущий
            # дизайн (см. report.css) — здесь просто печатаем фон и не навязываем формат.
            pdf_bytes = page.pdf(print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()

    return pdf_bytes
