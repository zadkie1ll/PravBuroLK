import os
import json
import uuid
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------- helpers ----------
def rub(amount):
    if amount is None:
        return ""
    amount = int(float(amount))
    return f"{amount:,}".replace(",", " ") + "Р"


def parse_amount(val):
    if val is None:
        return None
    s = str(val)
    if "|" in s:
        amt, _ = s.split("|", 1)
    else:
        amt = s
    return float(amt)


def _ensure_tmp_assets_dir(templates_dir: str) -> str:
    """
    Создаём папку templates/_assets_tmp (если нет).
    Всё, что туда положим, будет доступно из WeasyPrint через base_url=templates_dir.
    """
    assets_dir = os.path.join(templates_dir, "_assets_tmp")
    os.makedirs(assets_dir, exist_ok=True)
    return assets_dir


def _make_asset_paths(templates_dir: str, ext: str, prefix: str) -> tuple[str, str]:
    """
    Возвращает:
      abs_path: абсолютный путь, куда сохранить файл
      rel_path: относительный путь относительно templates_dir (то, что подставляется в шаблон)
    """
    assets_dir = _ensure_tmp_assets_dir(templates_dir)
    fname = f"{prefix}_{uuid.uuid4().hex}.{ext.lstrip('.')}"
    abs_path = os.path.join(assets_dir, fname)

    # относительный путь: "_assets_tmp/....png"
    rel_path = os.path.relpath(abs_path, templates_dir)
    return abs_path, rel_path


def download_photo(url: str, templates_dir: str, timeout=15) -> tuple[str | None, str | None]:
    """
    Скачивает фото и сохраняет ВНУТРИ templates_dir/_assets_tmp,
    чтобы WeasyPrint нашёл его по base_url.
    Возвращает (abs_path, rel_path).
    """
    if not url:
        return None, None

    abs_path, rel_path = _make_asset_paths(templates_dir, ext="png", prefix="manager_photo")

    headers = {"User-Agent": "Mozilla/5.0"}  # иногда CDN/защита требуют UA
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    # пишем как есть (png/jpg — не важно, WeasyPrint обычно распознаёт по содержимому)
    with open(abs_path, "wb") as f:
        f.write(resp.content)

    return abs_path, rel_path


def generate_bar_chart(debt, full_work_total, templates_dir: str) -> tuple[str, str]:
    """
    Сравнение: Долг vs Полная стоимость работы юристов (work_cost + work_bonus).
    Сохраняет png в templates_dir/_assets_tmp и возвращает (abs_path, rel_path).
    """
    if debt is None:
        debt = 0
    if full_work_total is None:
        full_work_total = 0

    abs_path, rel_path = _make_asset_paths(templates_dir, ext="png", prefix="bar_chart")

    labels = ["Юристы (полная)", "Долг"]
    values = [float(debt), float(full_work_total)]
    colors = ["#ef4444", "#2563eb"]  # красный долг, синий стоимость

    fig, ax = plt.subplots(figsize=(6, 2))
    ax.barh(labels, values, color=colors, height=0.42)

    maxv = max(values) if max(values) > 0 else 1

    # Подписи сумм
    for i, v in enumerate(values):
        ax.text(v + maxv * 0.01, i, rub(v), va="center", ha="left", fontsize=10)

    # (опционально) маленькая подсказка разницы
    diff = full_work_total - debt
    sign = "+" if diff >= 0 else "-"
    diff_text = f"Разница: {sign}{rub(abs(diff))}"
    ax.text(maxv * 0.02, -0.65, diff_text, fontsize=9)  # чуть выше/ниже — можно подправить

    # Чистый вид
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)

    plt.tight_layout()
    fig.savefig(abs_path, bbox_inches="tight", transparent=True, dpi=150)
    plt.close(fig)

    return abs_path, rel_path


# ---------- main PDF generator ----------
def generate_pdf(data):
    # --- Load template dir early (нужно для путей ресурсов) ---
    templates_dir = os.path.join(BASE_DIR, "templates")

    # --- Compatibility block ---
    data["consultation"] = {
        "date": data["document"]["generated_at"],
        "contract_link": None
    }

    # --- Parse finance amounts ---
    debt = parse_amount(data["finance"]["debt_amount"])
    work_cost = parse_amount(data["finance"]["work_cost"])
    work_bonus = parse_amount(data["finance"]["work_bonus"])
    installment = parse_amount(data["finance"]["installment_plan"])
    income = parse_amount(data["summary"]["income"])

    # --- Format values for template ---
    data["finance"]["debt_amount_rub"] = rub(debt)
    data["finance"]["work_cost_rub"] = rub(work_cost)
    data["finance"]["work_bonus_rub"] = rub(work_bonus)
    data["finance"]["installment_plan_rub"] = rub(installment)
    data["summary"]["income_rub"] = rub(income)

    # --- Generate assets INSIDE templates_dir so base_url resolves them ---
    chart_abs = chart_rel = None
    photo_abs = photo_rel = None

    try:
        chart_abs, chart_rel = generate_bar_chart(work_cost, debt, templates_dir=templates_dir)
        data["finance"]["bar_chart_file"] = chart_rel  # <-- ВАЖНО: относительный путь

        photo_abs, photo_rel = download_photo(data["manager"]["photo"], templates_dir=templates_dir)
        data["manager"]["photo_file"] = photo_rel      # <-- ВАЖНО: относительный путь

        # --- Load template ---
        env = Environment(loader=FileSystemLoader(templates_dir))
        template = env.get_template("template.html")

        html_content = template.render(data=data)

        # --- Generate PDF in memory ---
        pdf_bytes = HTML(
            string=html_content,
            base_url=templates_dir  # теперь img src="...rel..." резолвится
        ).write_pdf()

        if not pdf_bytes.startswith(b"%PDF"):
            raise ValueError("Generated file is not a valid PDF")

        return pdf_bytes

    finally:
        # --- Cleanup temp files ---
        # Удаляем именно по abs-путям (они точные)
        if photo_abs and os.path.exists(photo_abs):
            try:
                os.remove(photo_abs)
            except OSError:
                pass

        if chart_abs and os.path.exists(chart_abs):
            try:
                os.remove(chart_abs)
            except OSError:
                pass
