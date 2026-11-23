from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Read-only view of the audit trail: no add, change or delete for anyone."""

    list_display = ('id', 'user', 'action', 'description_short', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
    list_select_related = ('user',)
    search_fields = ('description', 'object_repr', 'user__username', 'ip_address')
    # Legacy changes_json / undo columns are deliberately not shown: old rows may
    # contain raw form data.
    fields = ('user', 'action', 'description', 'timestamp', 'content_type',
              'object_id', 'object_repr', 'ip_address', 'user_agent', 'extra_data')
    readonly_fields = fields
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    actions = None

    @admin.display(description="Description")
    def description_short(self, obj):
        return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
