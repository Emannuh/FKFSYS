# matches/admin.py - COMPLETE FIXED VERSION (OPTION A)
from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Match, Goal, Card, LeagueTable, Suspension
from teams.models import Zone
from .utils.fixture_generator import generate_fixtures_for_zone, regenerate_fixtures_for_zone, update_match_date

# Zone Admin Configuration
@admin.action(description="🎯 Generate fixtures for selected zones")
def generate_zone_fixtures(modeladmin, request, queryset):
    for zone in queryset:
        success, message = generate_fixtures_for_zone(zone.id)
        if success:
            modeladmin.message_user(request, message)
        else:
            modeladmin.message_user(request, f"⚠️ {zone.name}: {message}", level='warning')

@admin.action(description="🔄 Regenerate fixtures (delete & recreate)")
def regenerate_zone_fixtures(modeladmin, request, queryset):
    for zone in queryset:
        success, message = regenerate_fixtures_for_zone(zone.id)
        if success:
            modeladmin.message_user(request, message)
        else:
            modeladmin.message_user(request, f"⚠️ {zone.name}: {message}", level='warning')

class ZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'fixtures_generated', 'fixture_generation_date', 'team_count']
    list_filter = ['fixtures_generated']
    actions = [generate_zone_fixtures, regenerate_zone_fixtures]
    
    def team_count(self, obj):
        return obj.team_set.filter(status='approved').count()
    team_count.short_description = 'Approved Teams'

# Unregister and re-register Zone with new admin
from django.contrib import admin
try:
    admin.site.unregister(Zone)
except admin.sites.NotRegistered:
    pass

# SUPER ADMIN: Custom view for manual fixture generation
class MatchAdmin(admin.ModelAdmin):
    # FIXED: Added 'status' to list_display so it can be in list_editable
    list_display = ['match_display', 'zone', 'round_number', 'match_date_display', 
                   'kickoff_time_display', 'status', 'status_badge', 'score_display', 'actions_column']
    list_filter = ['zone', 'status', 'round_number', 'match_date']
    search_fields = ['home_team__team_name', 'away_team__team_name', 'zone__name']
    
    # ⬇⬇⬇ FIXED LINE: OPTION A - Only 'status' is editable in list view ⬇⬇⬇
    list_editable = ['status']  # Super Admin can only change status in list view
    # ⬆⬆⬆ FIXED LINE ⬆⬆⬆
    
    date_hierarchy = 'match_date'
    ordering = ['match_date']
    
    # SUPER ADMIN: Add custom actions
    actions = ['reschedule_matches', 'postpone_matches', 'complete_matches']
    
    # SUPER ADMIN: Custom change form for editing dates and times
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make match_date and kickoff_time editable for Super Admin
        form.base_fields['match_date'].widget.attrs.update({
            'style': 'width: 200px;'
        })
        # Add kickoff_time field if not already in form
        if 'kickoff_time' in form.base_fields:
            form.base_fields['kickoff_time'].help_text = "Format: HH:MM (e.g., 15:00 for 3 PM)"
            form.base_fields['kickoff_time'].widget.attrs.update({
                'style': 'width: 100px;',
                'placeholder': '15:00'
            })
        return form
    
    # Custom display methods
    def match_display(self, obj):
        return format_html(
            '<strong>{} vs {}</strong><br><small>Round {}</small>',
            obj.home_team.team_name, obj.away_team.team_name, obj.round_number
        )
    match_display.short_description = 'Match'
    
    def match_date_display(self, obj):
        return obj.match_date.strftime("%a, %b %d, %Y")
    match_date_display.short_description = 'Date'
    
    def kickoff_time_display(self, obj):
        if obj.kickoff_time:
            return obj.kickoff_time
        return obj.match_date.strftime("%I:%M %p")
    kickoff_time_display.short_description = 'Kickoff'
    
    def status_badge(self, obj):
        colors = {
            'scheduled': 'blue',
            'ongoing': 'orange',
            'completed':'green',
            'postponed': 'red',
            'cancelled': 'gray'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'), obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def score_display(self, obj):
        if obj.status == 'completed':
            return format_html(
                '<span style="font-weight: bold; font-size: 16px;">{} - {}</span>',
                obj.home_score, obj.away_score
            )
        return "vs"
    score_display.short_description = 'Score'
    
    def actions_column(self, obj):
        """Quick action buttons for Super Admin"""
        buttons = []
        if obj.status == 'scheduled':
            buttons.append(
                f'<a href="/admin/matches/match/{obj.id}/reschedule/" '
                f'class="button" style="background: purple; color: white; padding: 3px 8px; '
                f'border-radius: 3px; text-decoration: none; font-size: 12px;">RESCHEDULE</a>'
            )
        if obj.status in ['scheduled', 'postponed']:
            buttons.append(
                f'<a href="/admin/matches/match/{obj.id}/mark_ongoing/" '
                f'class="button" style="background: orange; color: white; padding: 3px 8px; '
                f'border-radius: 3px; text-decoration: none; font-size: 12px;">START</a>'
            )
        return format_html(' '.join(buttons))
    actions_column.short_description = 'Actions'
    
    # SUPER ADMIN: Custom actions
    @admin.action(description="📅 Reschedule selected matches")
    def reschedule_matches(self, request, queryset):
        """Bulk reschedule matches to a new date"""
        if 'apply' in request.POST:
            new_date = request.POST.get('new_date')
            new_time = request.POST.get('new_time')
            
            for match in queryset:
                update_match_date(match.id, new_date, new_time)
            
            self.message_user(request, f"✅ Rescheduled {queryset.count()} matches")
            return redirect(request.get_full_path())
        
        # Show reschedule form
        context = {
            'matches': queryset,
            'action': 'reschedule_matches',
        }
        return render(request, 'admin/reschedule_matches.html', context)
    
    @admin.action(description="⏸️ Postpone selected matches")
    def postpone_matches(self, request, queryset):
        """Bulk postpone matches"""
        updated = queryset.update(status='postponed')
        self.message_user(request, f"✅ Postponed {updated} matches")
    
    @admin.action(description="✅ Mark as completed")
    def complete_matches(self, request, queryset):
        """Bulk mark matches as completed"""
        updated = queryset.update(status='completed')
        self.message_user(request, f"✅ Marked {updated} matches as completed")
    
    # SUPER ADMIN: Custom URLs for match actions
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('generate/', self.admin_site.admin_view(self.generate_fixtures_view), 
                 name='matches_match_generate'),
            path('<path:object_id>/reschedule/', self.admin_site.admin_view(self.reschedule_single_view),
                 name='matches_match_reschedule'),
            path('<path:object_id>/mark_ongoing/', self.admin_site.admin_view(self.mark_ongoing_view),
                 name='matches_match_mark_ongoing'),
        ]
        return custom_urls + urls
    
    def generate_fixtures_view(self, request):
        """Custom view for manual fixture generation"""
        zone_id = request.GET.get('zone')
        
        if zone_id:
            success, message = generate_fixtures_for_zone(zone_id)
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return redirect('/admin/teams/zone/')
        
        zones = Zone.objects.filter(fixtures_generated=False)
        return render(request, 'admin/generate_fixtures.html', {'zones': zones})
    
    def reschedule_single_view(self, request, object_id):
        """Reschedule single match"""
        match = Match.objects.get(id=object_id)
        
        if request.method == 'POST':
            new_date = request.POST.get('new_date')
            new_time = request.POST.get('new_time')
            
            success, message = update_match_date(match.id, new_date, new_time)
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
            
            return redirect('/admin/matches/match/')
        
        return render(request, 'admin/reschedule_single.html', {'match': match})
    
    def mark_ongoing_view(self, request, object_id):
        """Mark match as ongoing"""
        match = Match.objects.get(id=object_id)
        match.status = 'ongoing'
        match.save()
        messages.success(request, f"✅ Match marked as ongoing: {match}")
        return redirect('/admin/matches/match/')

# Register models
admin.site.register(Zone, ZoneAdmin)
admin.site.register(Match, MatchAdmin)
admin.site.register(Goal)
admin.site.register(Card)
admin.site.register(LeagueTable)
admin.site.register(Suspension)