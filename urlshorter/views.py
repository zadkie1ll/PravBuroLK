from django.shortcuts import render, redirect, get_object_or_404
from .models import UrlShortener, Click
from django.db.models import Count
from urllib.parse import urlencode  # Для добавления UTM к destination
from django.contrib.auth.decorators import login_required
from collections import defaultdict
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError


@csrf_exempt
def generate_url(request):
    source = request.GET.get('source')
    social = request.GET.get('social', '')  # По умолчанию пусто, если не передан

    if not source:
        return redirect("index")

    # Находим объект по source или 404
    obj = get_object_or_404(UrlShortener, source=source)

    # Логируем клик
    Click.objects.create(
        url=obj,
        social=social,
        ip_address=request.META.get('REMOTE_ADDR'),  
        user_agent=request.META.get('HTTP_USER_AGENT') 
    )

    utm_params = {
        'utm_source': social if social else 'unknown',
        'utm_medium': 'social', 
        'utm_campaign': source,
    }
    destination_with_utm = obj.destination + '?' + urlencode(utm_params)

    # Редирект на destination с UTM (permanent=False по умолчанию — 302)
    return redirect(destination_with_utm)

@csrf_exempt
@login_required
def show_stats(request):
    messages = []  # список кортежей ('success'/'error', текст)

    if request.method == 'POST':
        # Добавление нового назначения + первого источника
        if 'add_new_destination' in request.POST:
            new_dest = request.POST.get('new_destination', '').strip()
            new_source = request.POST.get('new_source', '').strip()
            if new_dest and new_source:
                try:
                    UrlShortener.objects.create(source=new_source, destination=new_dest)
                    messages.append(('success', f'Новое назначение "{new_dest}" с источником "{new_source}" добавлено!'))
                except IntegrityError:
                    messages.append(('error', 'Источник с таким кодом уже существует.'))
                except Exception as e:
                    messages.append(('error', f'Ошибка: {str(e)}'))
            else:
                messages.append(('error', 'Заполните оба поля.'))

        # Добавление источника в существующее назначение
        elif 'add_source' in request.POST:
            dest = request.POST.get('destination')
            new_source = request.POST.get('new_source', '').strip()
            if dest and new_source:
                try:
                    UrlShortener.objects.create(source=new_source, destination=dest)
                    messages.append(('success', f'Источник "{new_source}" добавлен к назначению.'))
                except IntegrityError:
                    messages.append(('error', 'Источник с таким кодом уже существует.'))

        # Удаление источника
        elif 'delete_source' in request.POST:
            src = request.POST.get('source')
            if src:
                try:
                    obj = UrlShortener.objects.get(source=src)
                    obj.delete()
                    messages.append(('success', f'Источник "{src}" удалён.'))
                except UrlShortener.DoesNotExist:
                    messages.append(('error', 'Источник не найден.'))
                except Exception as e:
                    messages.append(('error', f'Ошибка удаления: {str(e)}'))

        # Изменение источника (код и/или назначение)
        elif 'edit_source' in request.POST:
            old_source = request.POST.get('old_source')
            new_source = request.POST.get('new_source', '').strip()
            new_dest = request.POST.get('new_destination', '').strip()
            if old_source and new_source and new_dest:
                try:
                    obj = UrlShortener.objects.get(source=old_source)
                    if new_source != old_source:
                        if UrlShortener.objects.filter(source=new_source).exists():
                            raise IntegrityError('Новый код источника уже занят.')
                        obj.source = new_source
                    obj.destination = new_dest
                    obj.save()
                    messages.append(('success', f'Источник обновлён: "{new_source}" → "{new_dest}".'))
                except IntegrityError as e:
                    messages.append(('error', str(e)))
                except Exception as e:
                    messages.append(('error', f'Ошибка: {str(e)}'))

        # Изменение назначения (URL для всех источников внутри)
        elif 'edit_destination' in request.POST:
            old_dest = request.POST.get('old_destination')
            new_dest = request.POST.get('new_destination', '').strip()
            if old_dest and new_dest and old_dest != new_dest:
                updated_count = UrlShortener.objects.filter(destination=old_dest).update(destination=new_dest)
                if updated_count > 0:
                    messages.append(('success', f'URL назначения изменён для {updated_count} источников.'))
                else:
                    messages.append(('error', 'Нет источников для изменения.'))

        # Удаление назначения целиком (все источники)
        elif 'delete_destination' in request.POST:
            dest = request.POST.get('destination')
            if dest:
                deleted_count, _ = UrlShortener.objects.filter(destination=dest).delete()
                if deleted_count > 0:
                    messages.append(('success', f'Назначение и {deleted_count} источников удалено.'))
                else:
                    messages.append(('error', 'Ничего не удалено.'))

    # Формируем статистику: группируем по destination
    grouped = defaultdict(list)
    all_objs = UrlShortener.objects.annotate(click_count=Count('clicks')).order_by('destination', 'source')
    for obj in all_objs:
        grouped[obj.destination].append({
            'source': obj.source,
            'clicks': obj.click_count,
            'destination': obj.destination,  # для формы edit
        })

    stats = []
    for dest, sources_list in sorted(grouped.items()):  # сортировка по URL назначения
        total = sum(s['clicks'] for s in sources_list)
        stats.append({
            'destination': dest,
            'sources': sources_list,
            'total_clicks': total,
        })

    return render(request, 'url-stats.html', {
        'stats': stats,
        'messages': messages,
    })