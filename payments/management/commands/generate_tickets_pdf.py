from django.core.management.base import BaseCommand
from django.conf import settings
from administration.models import Ticket

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

import qrcode
import os
import io
import random
import string
from datetime import datetime

# =========================
# Генерация кода билета
# =========================
def generate_code():
    return ''.join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )


class Command(BaseCommand):
    help = "Генерация билетов с QR-кодами в PDF"

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Количество билетов'
        )

    def handle(self, *args, **options):
        count = options['count']

        file_name = f"tickets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        output_path = os.path.join(settings.BASE_DIR, file_name)

        c = canvas.Canvas(output_path, pagesize=A4)

        # =========================
        # Сетка A4 (2 x 4)
        # =========================
        cols = 2
        rows = 4

        ticket_w = 105 * mm   # половина A4
        ticket_h = 74 * mm

        margin_x = 0 * mm
        margin_y = 10 * mm

        tickets_per_page = cols * rows

        for i in range(count):
            if i % tickets_per_page == 0 and i != 0:
                c.showPage()

            col = i % cols
            row = (i // cols) % rows

            x = margin_x + col * ticket_w
            y = A4[1] - margin_y - (row + 1) * ticket_h

            # =========================
            # Билет
            # =========================
            code = self.generate_unique_code()
            Ticket.objects.create(code=code)

            qr_reader = self.make_qr(code)

            # --- рамка билета ---
            c.roundRect(
                x + 5 * mm,
                y + 5 * mm,
                ticket_w - 10 * mm,
                ticket_h - 10 * mm,
                10
            )

            # --- QR ---
            c.drawImage(
                qr_reader,
                x + 10 * mm,
                y + 15 * mm,
                width=50 * mm,
                height=50 * mm
            )

            # --- Заголовок ---
            c.setFont("Helvetica-Bold", 14)
            c.drawString(x + 57 * mm, y + 45 * mm, "Komanda.GAME")

            # --- Подпись ---
            c.setFont("Helvetica", 12)
            c.drawString(x + 65 * mm, y + 30 * mm, "Ticket code:")

            # --- Код ---
            c.setFont("Helvetica-Bold", 18)
            c.drawString(x + 65 * mm, y + 18 * mm, code)

        c.save()

        self.stdout.write(
            self.style.SUCCESS(f"PDF создан: {output_path}")
        )

    # =========================
    # Уникальный код
    # =========================
    def generate_unique_code(self):
        while True:
            code = generate_code()
            if not Ticket.objects.filter(code=code).exists():
                return code

    # =========================
    # QR-код
    # =========================
    def make_qr(self, code):
        url = f"https://prav-buro.ru/casino/?code={code}"

        qr = qrcode.make(url)

        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)

        return ImageReader(buffer)