from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from matches.utils.fixture_generator import generate_fixtures_for_zone

from .models import LeagueSettings, Player, Team, TeamOfficial, TransferHistory, TransferRequest, Zone

MIN_TEAMS_FOR_FIXTURES = 4


@admin.action(description="Approve teams & auto-generate fixtures if zone ready")
def action_approve_teams(modeladmin, request, queryset):
    """Approve teams and trigger fixture generation for zones that now have enough teams."""
    team_ids = list(queryset.values_list('pk', flat=True))
    updated = Team.objects.filter(pk__in=team_ids).update(status=Team.Status.APPROVED)
    for zone in Zone.objects.filter(team__pk__in=team_ids, fixtures_generated=False).distinct():
        if zone.approved_teams_count >= MIN_TEAMS_FOR_FIXTURES:
            generate_fixtures_for_zone(zone.id)
    modeladmin.message_user(request, f"Approved {updated} teams")


# Zone is registered by matches/admin.py (fixture-generation tooling lives there).


@admin.register(Team)
class TeamAdmin(ImportExportModelAdmin):
    list_display = ['team_name', 'zone', 'status', 'payment_status', 'registration_date']
    list_filter = ['zone', 'status', 'payment_status']
    search_fields = ['team_name', 'contact_person', 'phone_number']
    list_editable = ['zone', 'status']  # Super Admin can change zone and status directly
    readonly_fields = ['team_code', 'registration_date']
    
    actions = ['mark_as_paid', action_approve_teams]
    list_select_related = ['zone']

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
    
    @admin.action(description="Mark selected teams as paid")
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(payment_status=True)
        self.message_user(request, f'{updated} teams marked as paid.')


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
    list_select_related = ['team']

    @admin.action(description="Suspend selected players")
    def suspend_players(self, request, queryset):
        updated = queryset.update(is_suspended=True)
        self.message_user(request, f'{updated} players suspended.')

    @admin.action(description="Clear suspension for selected players")
    def clear_suspension(self, request, queryset):
        updated = queryset.update(is_suspended=False, suspension_end=None, suspension_reason='',
                                  suspension_matches=0)
        self.message_user(request, f'{updated} players suspension cleared.')


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
    
    list_display = ['player', 'from_team', 'to_team', 'status', 'request_date', 'admin_override']
    list_select_related = ['player', 'from_team', 'to_team']
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
    
    @admin.action(description="Force approve selected rejected transfers (override)")
    def force_approve_transfer(self, request, queryset):
        """Super admin can override rejections and force approval."""
        count = 0
        for transfer in queryset.filter(status=TransferRequest.Status.REJECTED):
            transfer.override_by_admin(user=request.user, reason="Admin override: Approved by super admin")
            count += 1
        if count:
            self.message_user(request, f"{count} transfer(s) force-approved")
        else:
            self.message_user(request, "No rejected transfers selected", level='warning')

    @admin.action(description="Cancel selected pending transfers")
    def cancel_transfer(self, request, queryset):
        count = queryset.filter(status=TransferRequest.Status.PENDING_PARENT).update(
            status=TransferRequest.Status.CANCELLED
        )
        self.message_user(request, f"{count} transfer(s) cancelled")


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
