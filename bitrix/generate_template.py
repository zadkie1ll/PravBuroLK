import os
import json
import tempfile
import requests
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

import matplotlib
matplotlib.use("Agg")  # важно: ДО pyplot
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Arial"


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
    try:
        return float(amt)
    except ValueError:
        return None


def download_photo(url: str, filepath: str):
    """
    Скачивает фото по url и сохраняет в filepath.
    Возвращает filepath или None.
    ВАЖНО: не падает, если фото недоступно.
    """
    if not url:
        return None
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(r.content)
        return filepath
    except Exception:
        return None


def generate_placeholder_avatar(filepath: str, size_px: int = 220) -> str:
    """
    Делает простую синюю аватарку-плейсхолдер PNG,
    чтобы <img> всегда имел валидный src.
    """
    fig, ax = plt.subplots(figsize=(size_px / 100, size_px / 100), dpi=100)
    ax.axis("off")
    # круг + "голова" + "плечи" без шрифтов (стабильно)
    # фон-круг
    circle = plt.Circle((0.5, 0.5), 0.48, transform=ax.transAxes)
    ax.add_artist(circle)
    circle.set_facecolor("#1f50bb")
    circle.set_edgecolor("#1f50bb")

    # голова
    head = plt.Circle((0.5, 0.62), 0.14, transform=ax.transAxes)
    ax.add_artist(head)
    head.set_facecolor("#dbeafe")
    head.set_edgecolor("#dbeafe")

    # плечи (полукруг/овал)
    shoulders = plt.Circle((0.5, 0.28), 0.28, transform=ax.transAxes)
    ax.add_artist(shoulders)
    shoulders.set_facecolor("#dbeafe")
    shoulders.set_edgecolor("#dbeafe")

    plt.tight_layout(pad=0)
    fig.savefig(filepath, transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return filepath


def generate_bar_chart(work_cost, installment, filepath: str):
    """
    Рисует график и сохраняет в filepath.
    Возвращает filepath.
    """
    work_cost = work_cost or 0
    installment = installment or 0

    labels = ["Стоимость", "Сумма долга"]
    values = [work_cost, installment]

    fig, ax = plt.subplots(figsize=(6, 2))
    ax.barh(labels, values, height=0.2)
    ax.tick_params(axis="y", labelsize=26)

    mx = max(values) if max(values) > 0 else 1
    for i, v in enumerate(values):
        ax.text(v + mx * 0.01, i, rub(v), va="center", ha="left", fontsize=26)

    # Clean look
    for s in ["top", "right", "bottom", "left"]:
        ax.spines[s].set_visible(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)

    plt.tight_layout()
    fig.savefig(filepath, bbox_inches="tight", transparent=True, dpi=150)
    plt.close(fig)
    return filepath


# ---------- main PDF generator ----------
def generate_pdf(data) -> bytes:
    """
    ВАЖНО: возвращает bytes (PDF), чтобы handler мог:
    - save_pdf_temp(pdf_bytes, filename)
    - upload_to_bitrix(...)
    - HttpResponse(pdf_bytes, ...)
    """

    data = json.loads(json.dumps(data, ensure_ascii=False))

    data["consultation"] = {
        "date": data["document"]["generated_at"],
        "contract_link": None
    }

    # Parse finance amounts
    debt = parse_amount(data["finance"].get("debt_amount"))
    work_cost = parse_amount(data["finance"].get("work_cost"))
    work_bonus = parse_amount(data["finance"].get("work_bonus"))
    installment = parse_amount(data["finance"].get("installment_plan"))

    data["finance"]["debt_amount_rub"] = rub(debt)
    data["finance"]["work_cost_rub"] = rub(work_cost)
    data["finance"]["work_bonus_rub"] = rub(work_bonus)
    data["finance"]["installment_plan"] = rub(installment)

    # ---- income fields for template (official + after KM) ----
    show_km = bool(data.get("summary", {}).get("show_km", False))
    data.setdefault("summary", {})
    data["summary"]["show_km"] = show_km

    km = data.get("km") or {}
    base_income = None
    remain_after_km = None

    try:
        base_income = (km.get("result") or {}).get("base_income")
        remain_after_km = (km.get("result") or {}).get("remain_to_person")
    except Exception:
        base_income = None
        remain_after_km = None

    if base_income is None:
        base_income = parse_amount(data["summary"].get("income")) or 0

    data["summary"]["official_income_rub"] = rub(base_income)

    if show_km and remain_after_km is not None:
        data["summary"]["income_after_km_rub"] = rub(remain_after_km)
    else:
        data["summary"]["income_after_km_rub"] = ""

    # backward compat
    data["summary"]["income_rub"] = data["summary"]["official_income_rub"]

    with tempfile.TemporaryDirectory() as tmp:
        # chart
        bar_chart_path = os.path.join(tmp, "bar_chart.png")
        generate_bar_chart(work_cost, debt, bar_chart_path)
        data["finance"]["bar_chart_file"] = "bar_chart.png"

        # photo: download or placeholder
        photo_url = data.get("manager", {}).get("photo")
        photo_path = os.path.join(tmp, "manager_photo.jpg")
        photo_file = download_photo(photo_url, photo_path) if photo_url else None

        if not photo_file:
            # делаем плейсхолдер, чтобы img всегда был валидным
            placeholder_path = os.path.join(tmp, "manager_photo.png")
            generate_placeholder_avatar(placeholder_path)
            data["manager"]["photo_file"] = "manager_photo.png"
        else:
            data["manager"]["photo_file"] = "manager_photo.jpg"

        # template
        env = Environment(loader=FileSystemLoader("bitrix/templates"))
        template = env.get_template("template.html")
        html_content = template.render(data=data)

        pdf_bytes = HTML(string=html_content, base_url=tmp).write_pdf()

    return pdf_bytes


# ---------- RUN ----------
if __name__ == "__main__":
    with open("card.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    pdf_bytes = generate_pdf(data)
    with open("client_report.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("✅ PDF создан: client_report.pdf (bytes =", len(pdf_bytes), ")")
