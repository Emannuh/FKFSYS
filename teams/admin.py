from django.contrib import admin
from django.utils.html import format_html
from .models import Team, Player, Zone, LeagueSettings, TransferRequest, TransferHistory, TeamOfficial
from import_export.admin import ImportExportModelAdmin
from matches.utils.fixture_generator import generate_fixtures_for_zone, regenerate_fixtures_for_zone
from matches.models import Match

# ⬇⬇⬇ NEW ADMIN ACTIONS FOR FIXTURE GENERATION ⬇⬇⬇
@admin.action(description="⚽ GENERATE FIXTURES for selected zones")
def action_generate_fixtures(modeladmin, request, queryset):
    """Super Admin: Manually generate fixtures for zones"""
    for zone in queryset:
        success, message = generate_fixtures_for_zone(zone.id)
        if success:
            modeladmin.message_user(request, message)
        else:
            modeladmin.message_user(request, f"❌ {zone.name}: {message}", level='error')

@admin.action(description="🔄 REGENERATE FIXTURES (delete & recreate)")
def action_regenerate_fixtures(modeladmin, request, queryset):
    """Super Admin: Delete and regenerate fixtures"""
    for zone in queryset:
        success, message = regenerate_fixtures_for_zone(zone.id)
        if success:
            modeladmin.message_user(request, message)
        else:
            modeladmin.message_user(request, f"❌ {zone.name}: {message}", level='error')

@admin.action(description="✅ APPROVE teams & auto-generate if zone ready")
def action_approve_teams(modeladmin, request, queryset):
    """Approve teams and trigger fixture generation if zone ready"""
    for team in queryset:
        team.status = 'approved'
        team.save()
    
    # Trigger fixture generation for zones that now have enough teams
    zones_with_updated_teams = Zone.objects.filter(
        team__in=queryset
    ).distinct()
    
    for zone in zones_with_updated_teams:
        approved_count = Team.objects.filter(zone=zone, status='approved').count()
        if approved_count >= 4 and not zone.fixtures_generated:
            generate_fixtures_for_zone(zone.id)
    
    modeladmin.message_user(request, f"✅ Approved {queryset.count()} teams")
# ⬆⬆⬆ NEW ADMIN ACTIONS FOR FIXTURE GENERATION ⬆⬆⬆


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'approved_teams_display', 'fixtures_status', 
                   'fixture_generation_date', 'match_day_display', 'actions_column']
    list_filter = ['fixtures_generated', 'match_day_of_week']
    search_fields = ['name']
    
    # ⬇⬇⬇ ADD FIXTURE GENERATION ACTIONS ⬇⬇⬇
    actions = [action_generate_fixtures, action_regenerate_fixtures]
    
    def approved_teams_display(self, obj):
        count = obj.team_set.filter(status='approved').count()
        color = 'green' if count >= 4 else 'orange' if count >= 2 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, f"{count} approved"
        )
    approved_teams_display.short_description = 'Approved Teams'
    
    def fixtures_status(self, obj):
        if obj.fixtures_generated:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ GENERATED</span>'
            )
        return format_html(
            '<span style="color: orange; font-weight: bold;">⏳ PENDING</span>'
        )
    fixtures_status.short_description = 'Fixtures Status'
    
    def match_day_display(self, obj):
        days = {6: 'Saturday', 0: 'Sunday'}
        return days.get(obj.match_day_of_week, 'Sunday')
    match_day_display.short_description = 'Match Day'
    
    def actions_column(self, obj):
        """Quick action buttons in list view"""
        buttons = []
        if not obj.fixtures_generated:
            buttons.append(
                f'<a href="/admin/matches/match/generate/?zone={obj.id}" '
                f'class="button" style="background: green; color: white; padding: 5px 10px; '
                f'border-radius: 3px; text-decoration: none;">GENERATE</a>'
            )
        else:
            buttons.append(
                f'<a href="/matches/fixtures/?zone={obj.id}" '
                f'class="button" style="background: blue; color: white; padding: 5px 10px; '
                f'border-radius: 3px; text-decoration: none;" target="_blank">VIEW</a>'
            )
            buttons.append(
                f'<a href="/admin/teams/zone/{obj.id}/change/" '
                f'class="button" style="background: orange; color: white; padding: 5px 10px; '
                f'border-radius: 3px; text-decoration: none;">EDIT</a>'
            )
        return format_html(' '.join(buttons))
    actions_column.short_description = 'Quick Actions'


@admin.register(Team)
class TeamAdmin(ImportExportModelAdmin):
    list_display = ['team_name', 'zone', 'status', 'payment_status', 'registration_date']
    list_filter = ['zone', 'status', 'payment_status']
    search_fields = ['team_name', 'contact_person', 'phone_number']
    list_editable = ['zone', 'status']  # Super Admin can change zone and status directly
    readonly_fields = ['team_code', 'registration_date']
    
    # ⬇⬇⬇ ADD FIXTURE-AWARE TEAM APPROVAL ACTION ⬇⬇⬇
    actions = ['approve_registration', 'mark_as_paid', action_approve_teams]
    
    # ⬇⬇⬇ UPDATED FIELDSETS ⬇⬇⬇
    fieldsets = (
        ('Team Information', {
            'fields': ('team_name', 'team_code', 'logo', 'status')
        }),
        ('Location Details', {
            'fields': ('zone', 'location', 'home_ground', 'map_location', 'latitude', 'longitude')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'phone_number', 'email')
        }),
        ('Payment & Registration', {
            'fields': ('payment_status', 'payment_date', 'registration_date'),
            'classes': ('collapse',)
        }),
    )
    
    def approve_registration(self, request, queryset):
        updated = queryset.update(status='approved')
        self.message_user(request, f'{updated} teams approved successfully.')
    approve_registration.short_description = "Approve selected teams"
    
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(payment_status=True)
        self.message_user(request, f'{updated} teams marked as paid.')
    mark_as_paid.short_description = "Mark selected teams as paid"


@admin.register(Player)
class PlayerAdmin(ImportExportModelAdmin):
    list_display = ['full_name', 'team', 'position', 'jersey_number', 'is_suspended']
    list_filter = ['position', 'is_suspended', 'team', 'team__zone']
    search_fields = ['first_name', 'last_name', 'id_number', 'team__team_name']
    readonly_fields = ['registration_date']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'date_of_birth', 'nationality', 'id_number', 'photo')
        }),
        ('FKF License Information', {
            'fields': ('fkf_license_number', 'license_expiry_date')
        }),
        ('Team Information', {
            'fields': ('team', 'position', 'jersey_number', 'is_captain')
        }),
        ('Statistics', {
            'fields': ('yellow_cards', 'red_cards', 'goals_scored', 'matches_played')
        }),
        ('Suspension', {
            'fields': ('is_suspended', 'suspension_end', 'suspension_reason')
        }),
    )
    
    actions = ['suspend_players', 'clear_suspension']
    
    def suspend_players(self, request, queryset):
        updated = queryset.update(is_suspended=True)
        self.message_user(request, f'{updated} players suspended.')
    suspend_players.short_description = "Suspend selected players"
    
    def clear_suspension(self, request, queryset):
        updated = queryset.update(is_suspended=False, suspension_end=None, suspension_reason='')
        self.message_user(request, f'{updated} players suspension cleared.')
    clear_suspension.short_description = "Clear suspension for selected players"


@admin.register(LeagueSettings)
class LeagueSettingsAdmin(admin.ModelAdmin):
    """Admin interface for league-wide settings"""
    
    def has_add_permission(self, request):
        # Prevent adding multiple instances
        return not LeagueSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion
        return False
    
    fieldsets = (
        ('Registration Windows', {
             'fields': (
                'team_registration_open', 'team_registration_deadline',
                'player_registration_open', 'player_registration_deadline',
                'transfer_window_open', 'transfer_window_deadline'
            ),
            'description': 'Control when teams can register, add players, and request transfers; deadlines auto-close windows'
        }),
        ('Meta Information', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['updated_at', 'updated_by']
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TransferRequest)
class TransferRequestAdmin(admin.ModelAdmin):
    """Admin interface for managing transfer requests"""
    
    list_display = ['player', 'from_team', 'to_team', 'status', 'request_date', 'admin_override', 'actions_column']
    list_filter = ['status', 'admin_override', 'request_date']
    search_fields = ['player__first_name', 'player__last_name', 'from_team__team_name', 'to_team__team_name']
    readonly_fields = ['request_date', 'updated_at', 'parent_decision_date', 'admin_override_date']
    
    fieldsets = (
        ('Transfer Details', {
            'fields': ('player', 'from_team', 'to_team', 'status')
        }),
        ('Request Information', {
            'fields': ('requested_by', 'request_date')
        }),
        ('Parent Club Decision', {
            'fields': ('parent_decision_by', 'parent_decision_reason', 'parent_decision_date'),
            'classes': ('collapse',)
        }),
        ('Admin Override', {
            'fields': ('admin_override', 'admin_override_by', 'admin_override_reason', 'admin_override_date'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['force_approve_transfer', 'cancel_transfer']
    
    def force_approve_transfer(self, request, queryset):
        """Super admin can override rejections and force approval"""
        count = 0
        for transfer in queryset:
            if transfer.status == 'rejected':
                transfer.override_by_admin(
                    user=request.user,
                    reason="Admin override: Approved by super admin"
                )
                count += 1
                self.message_user(request, f"✅ Forced approval: {transfer.player} → {transfer.to_team}")
        
        if count == 0:
            self.message_user(request, "No rejected transfers selected", level='warning')
        else:
            self.message_user(request, f"✅ {count} transfer(s) forced approved")
    
    force_approve_transfer.short_description = "🔓 Force Approve Selected Transfers (Override Rejection)"
    
    def cancel_transfer(self, request, queryset):
        """Admin can cancel pending transfers"""
        count = queryset.filter(status='pending_parent').update(status='cancelled')
        self.message_user(request, f"❌ {count} transfer(s) cancelled")
    
    cancel_transfer.short_description = "❌ Cancel Selected Transfers"
    
    def actions_column(self, obj):
        """Quick action buttons"""
        if obj.status == 'rejected':
            return format_html(
                '<a href="#" onclick="return confirm(\'Force approve this transfer?\');" '
                'style="background: green; color: white; padding: 5px 10px; '
                'border-radius: 3px; text-decoration: none;">OVERRIDE & APPROVE</a>'
            )
        elif obj.status == 'pending_parent':
            return format_html(
                '<span style="color: orange;">⏳ Awaiting Parent Club</span>'
            )
        elif obj.status == 'approved':
            return format_html(
                '<span style="color: green;">✅ Complete</span>'
            )
        return '-'
    
    actions_column.short_description = 'Actions'


@admin.register(TransferHistory)
class TransferHistoryAdmin(admin.ModelAdmin):
    """Read-only admin for transfer history"""
    
    list_display = ['player', 'from_team', 'to_team', 'transfer_date', 'approved_by', 'admin_override']
    list_filter = ['admin_override', 'transfer_date']
    search_fields = ['player__first_name', 'player__last_name', 'from_team__team_name', 'to_team__team_name']
    readonly_fields = ['transfer_request', 'player', 'from_team', 'to_team', 'approved_by', 'admin_override', 'transfer_date']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TeamOfficial)
class TeamOfficialAdmin(admin.ModelAdmin):
    """Admin interface for team officials"""
    
    list_display = ['full_name', 'position', 'team', 'phone_number', 'caf_license_number', 'license_expiry_date']
    list_filter = ['position', 'team__zone']
    search_fields = ['full_name', 'id_number', 'team__team_name', 'caf_license_number']
    readonly_fields = ['registration_date']
    
    fieldsets = (
        ('Team & Position', {
            'fields': ('team', 'position')
        }),
        ('Personal Information', {
            'fields': ('full_name', 'id_number', 'phone_number', 'photo')
        }),
        ('License Information (Coaches)', {
            'fields': ('caf_license_number', 'license_expiry_date'),
            'classes': ('collapse',)
        }),
        ('Registration', {
            'fields': ('registration_date',),
            'classes': ('collapse',)
        }),
    )
