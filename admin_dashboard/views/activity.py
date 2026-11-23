"""Read-only audit trail views (staff only). There is deliberately no edit,
delete or undo endpoint: the activity log is append-only."""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from ..models import ActivityLog
from .common import staff_required

User = get_user_model()


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@staff_required
def activity_logs(request):
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '').strip()

    logs = ActivityLog.objects.select_related('user', 'content_type')
    if action_filter:
        logs = logs.filter(action=action_filter)
    if user_filter.isdigit():
        logs = logs.filter(user_id=int(user_filter))
    if start := _parse_date(date_from):
        logs = logs.filter(timestamp__date__gte=start)
    if end := _parse_date(date_to):
        logs = logs.filter(timestamp__date__lte=end)
    if search_query:
        logs = logs.filter(
            Q(description__icontains=search_query)
            | Q(object_repr__icontains=search_query)
            | Q(user__username__icontains=search_query)
        )

    context = {
        'page_obj': Paginator(logs, 50).get_page(request.GET.get('page')),
        'total_logs': logs.count(),
        'today_logs': logs.filter(timestamp__date=timezone.localdate()).count(),
        'action_stats': logs.values('action').annotate(count=Count('id')).order_by('-count')[:10],
        'user_stats': (
            logs.exclude(user=None).values('user__username', 'user__id')
            .annotate(count=Count('id')).order_by('-count')[:10]
        ),
        'all_actions': ActivityLog.objects.order_by('action').values_list('action', flat=True).distinct(),
        'all_users': User.objects.filter(activity_logs__isnull=False).distinct().order_by('username'),
        'action_filter': action_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    return render(request, 'admin_dashboard/activity_logs.html', context)


@staff_required
def activity_log_detail(request, log_id):
    log = get_object_or_404(ActivityLog.objects.select_related('user', 'content_type'), id=log_id)
    return render(request, 'admin_dashboard/activity_log_detail.html', {'log': log})
