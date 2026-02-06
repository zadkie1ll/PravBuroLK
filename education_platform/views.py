from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

def auth_page(request):
    """
    Страница авторизации (HTML).
    Никакой логики логина — только UI.
    """
    return render(request, "education/auth.html")


@require_POST
@csrf_exempt
def auth_api_login(request):
    """
    API-эндпоинт для логина.
    Принимает username + password.
    """

    username = request.POST.get("username")
    password = request.POST.get("password")

    if not username or not password:
        return JsonResponse(
            {"detail": "username and password required"},
            status=400,
        )

    user = authenticate(request, username=username, password=password)

    if user is None:
        return JsonResponse(
            {"detail": "Неверный логин или пароль"},
            status=401,
        )

    if not user.is_active:
        return JsonResponse(
            {"detail": "Пользователь деактивирован"},
            status=403,
        )

    login(request, user)

    return JsonResponse(
        {
            "detail": "ok",
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        }
    )