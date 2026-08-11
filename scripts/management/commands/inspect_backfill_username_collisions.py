from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

# ID сделок из прогона backfill_client_credentials --execute (2026-08-11),
# см. вывод команды в чате — bitrix_id сохранён на Client при создании.
BACKFILL_DEAL_IDS = [
    15804, 12108, 7450, 7020, 7086, 7138, 7208, 6412, 6452, 7042,
    7044, 7084, 7098, 7336, 7346, 7636, 6478, 7216, 7302, 7456,
    16208, 7122, 7422, 7554, 12098,
]


class Command(BaseCommand):
    help = (
        "Для клиентов, созданных backfill_client_credentials, находит случаи, когда "
        "username получил суффикс (телефон уже был занят другим клиентом) — "
        "показывает оба конфликтующих клиента рядом для ручного разбора."
    )

    def handle(self, *args, **kwargs):
        from clients.models import Client

        clients = Client.objects.select_related("user").filter(bitrix_id__in=[str(d) for d in BACKFILL_DEAL_IDS])

        found_any = False
        for client in clients:
            username = client.user.username
            # суффикс — это username без последнего символа, если такой существует как ЧУЖОЙ логин
            base = username[:-1]
            if not base:
                continue
            other = User.objects.filter(username=base).exclude(id=client.user.id).first()
            if not other:
                continue

            found_any = True
            other_client = getattr(other, "client", None)

            self.stdout.write(self.style.WARNING(f"\n=== Конфликт: {username} ==="))
            self.stdout.write(
                f"  НОВЫЙ  client={client.id} bitrix_deal={client.bitrix_id} "
                f"ФИО={client.surname} {client.name} {client.middlename or ''} username={username}"
            )
            if other_client:
                self.stdout.write(
                    f"  СТАРЫЙ client={other_client.id} bitrix_deal={other_client.bitrix_id} "
                    f"ФИО={other_client.surname} {other_client.name} {other_client.middlename or ''} "
                    f"username={other.username}"
                )
            else:
                self.stdout.write(f"  СТАРЫЙ user={other.id} (нет связанного Client?) username={other.username}")

        if not found_any:
            self.stdout.write(self.style.SUCCESS("Коллизий не найдено."))
