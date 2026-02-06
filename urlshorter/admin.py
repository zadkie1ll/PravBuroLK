from django.contrib import admin
from .models import UrlShortener, Click

@admin.register(UrlShortener)
class UrlShortenerAdmin(admin.ModelAdmin):
    list_display = ('source', 'destination', 'created_at')
    search_fields = ('source', 'destination')

@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ('url', 'social', 'clicked_at', 'ip_address')
    list_filter = ('social', 'clicked_at')
    search_fields = ('social',)