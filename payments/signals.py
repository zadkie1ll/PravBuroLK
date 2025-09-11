# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from datetime import datetime
# from dateutil.relativedelta import relativedelta
# from .models import Contract, InstallmentPlan, InstallmentPayment
# from .views import calculate_payments 

# @receiver(post_save, sender=Contract)
# def create_installment_plan(sender, instance: Contract, created, **kwargs):
#     if created:
#         plan = InstallmentPlan.objects.create(contract=instance)
#         payments_data = calculate_payments(
#             num_payments=instance.number_of_payments,
#             total_amount=float(instance.total_amount),
#             discount=float(instance.discount),
#             start_date=instance.first_payment_date.strftime("%d.%m.%Y"),
#             first_payment=float(instance.first_payment),
#             second_payment_day=instance.preferred_payment_day
#         )
#         for number, due_date_str, amount in payments_data:
#             due_date = datetime.strptime(due_date_str, "%d.%m.%Y").date()
#             InstallmentPayment.objects.create(
#                 plan=plan,
#                 number=number,
#                 due_date=due_date,
#                 amount_due=amount
#             )
#         plan.calculated = True
#         plan.save()