from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'type', 'is_read', 'emailed', 'created_at']
    list_filter = ['type', 'is_read', 'emailed']
    search_fields = ['title', 'user__email']
