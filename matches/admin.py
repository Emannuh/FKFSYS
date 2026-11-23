from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from teams.models import Zone

from .models import Card, Goal, LeagueTable, Match, Suspension
from .utils.fixture_generator import generate_fixtures_for_zone, regenerate_fixtures_for_zone, update_match_date


# ── Zone (overrides teams' ZoneAdmin, whose fixture actions are disabled) ────

@admin.action(description="Generate fixtures for selected zones")
def generate_zone_fixtures(modeladmin, request, queryset):
    for zone in queryset:
        success, message = generate_fixtures_for_zone(zone.pk)
        modeladmin.message_user(request, message if success else f"{zone.name}: {message}",
                                level=messages.SUCCESS if success else messages.WARNING)


@admin.action(description="Regenerate fixtures (only zones with no played matches)")
def regenerate_zone_fixtures(modeladmin, request, queryset):
    for zone in queryset:
        success, message = regenerate_fixtures_for_zone(zone.pk)
        modeladmin.message_user(request, message if success else f"{zone.name}: {message}",
                                level=messages.SUCCESS if success else messages.WARNING)


class ZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'fixtures_generated', 'fixture_generation_date', 'team_count']
    list_filter = ['fixtures_generated']
    actions = [generate_zone_fixtures, regenerate_zone_fixtures]

    @admin.display(description='Approved Teams')
    def team_count(self, obj):
        return obj.team_set.filter(status='approved').count()


if admin.site.is_registered(Zone):
    admin.site.unregister(Zone)
admin.site.register(Zone, ZoneAdmin)


# ── Match ────────────────────────────────────────────────────────────────────

STATUS_COLOURS = {
    'scheduled': 'blue', 'live': 'crimson', 'ongoing': 'orange',
    'completed': 'green', 'postponed': 'red', 'cancelled': 'gray',
}


def _set_status(queryset, status):
    """Save one by one so signals (league-table recalculation) run."""
    count = 0
    for match in queryset:
        match.status = status
        match.save(update_fields=['status', 'updated_at'])
        count += 1
    return count


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['match_display', 'zone', 'round_number', 'match_date_display',
                    'kickoff_time', 'status', 'status_badge', 'score', 'reschedule_link']
    list_filter = ['zone', 'status', 'round_number', 'match_date']
    list_editable = ['status']
    list_select_related = ['home_team', 'away_team', 'zone']
    search_fields = ['home_team__team_name', 'away_team__team_name', 'zone__name']
    date_hierarchy = 'match_date'
    ordering = ['match_date']
    actions = ['mark_ongoing', 'postpone_matches', 'complete_matches']

    @admin.display(description='Match')
    def match_display(self, obj):
        return format_html('<strong>{} vs {}</strong><br><small>Round {}</small>',
                           obj.home_team.team_name, obj.away_team.team_name, obj.round_number)

    @admin.display(description='Date', ordering='match_date')
    def match_date_display(self, obj):
        return f"{obj.match_date:%a, %b %d, %Y}"

    @admin.display(description='Status')
    def status_badge(self, obj):
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:10px;font-size:12px;">{}</span>',
            STATUS_COLOURS.get(obj.status, 'gray'), obj.get_status_display(),
        )

    @admin.display(description='Score')
    def score(self, obj):
        return obj.score_display if obj.status == 'completed' else 'vs'

    @admin.display(description='Reschedule')
    def reschedule_link(self, obj):
        if obj.status not in ('scheduled', 'postponed'):
            return ''
        url = reverse('admin:matches_match_reschedule', args=[obj.pk])
        return format_html('<a class="button" href="{}">Reschedule</a>', url)

    @admin.action(description="Mark selected matches as ongoing")
    def mark_ongoing(self, request, queryset):
        self.message_user(request, f"Marked {_set_status(queryset, 'ongoing')} matches as ongoing")

    @admin.action(description="Postpone selected matches")
    def postpone_matches(self, request, queryset):
        self.message_user(request, f"Postponed {_set_status(queryset, 'postponed')} matches")

    @admin.action(description="Mark selected matches as completed")
    def complete_matches(self, request, queryset):
        self.message_user(request, f"Marked {_set_status(queryset, 'completed')} matches as completed")

    def get_urls(self):
        custom = [
            path('<int:object_id>/reschedule/', self.admin_site.admin_view(self.reschedule_single_view),
                 name='matches_match_reschedule'),
        ]
        return custom + super().get_urls()

    def reschedule_single_view(self, request, object_id):
        if not self.has_change_permission(request):
            raise PermissionDenied
        match = get_object_or_404(Match, pk=object_id)
        if request.method == 'POST':
            success, message = update_match_date(match.pk, request.POST.get('new_date'), request.POST.get('new_time'))
            self.message_user(request, message, level=messages.SUCCESS if success else messages.ERROR)
            return redirect('admin:matches_match_changelist')
        return render(request, 'admin/reschedule_single.html', {
            **self.admin_site.each_context(request), 'match': match,
        })


admin.site.register(Goal)
admin.site.register(Card)
admin.site.register(LeagueTable)
admin.site.register(Suspension)
