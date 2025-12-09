from django.contrib import admin
from .models import Team, Player, Zone
from import_export.admin import ImportExportModelAdmin

@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']

@admin.register(Team)
class TeamAdmin(ImportExportModelAdmin):
    list_display = ['team_name', 'team_code', 'location', 'zone', 'status', 'payment_status']
    list_filter = ['status', 'payment_status', 'zone', 'registration_date']
    search_fields = ['team_name', 'team_code', 'contact_person', 'phone_number']
    readonly_fields = ['team_code', 'registration_date']
    fieldsets = (
        ('Team Information', {
            'fields': ('team_name', 'team_code', 'logo')
        }),
        ('Location Details', {
            'fields': ('location', 'home_ground', 'map_location', 'latitude', 'longitude')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'phone_number', 'email')
        }),
        ('League Details', {
            'fields': ('zone', 'status')
        }),
        ('Payment Information', {
            'fields': ('payment_status', 'payment_date')
        }),
        ('Timestamps', {
            'fields': ('registration_date',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_registration', 'mark_as_paid']
    
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