from django.contrib import admin
from .models import (
    Tournament,
    TournamentTeamRegistration,
    TournamentPlayerRegistration,
    TournamentGroup,
    TournamentGroupStanding,
    TournamentMatch,
    TournamentMatchOfficials,
    TournamentGoal,
    TournamentCard,
    ExternalTeam,
    ExternalPlayer,
    TournamentMatchdaySquad,
    TournamentSquadPlayer,
)


class TournamentTeamRegistrationInline(admin.TabularInline):
    model = TournamentTeamRegistration
    extra = 0


class TournamentGroupInline(admin.TabularInline):
    model = TournamentGroup
    extra = 0


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['name', 'format', 'status', 'start_date', 'end_date', 'allow_external_teams', 'registered_teams_count']
    list_filter = ['status', 'format', 'allow_external_teams']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TournamentTeamRegistrationInline, TournamentGroupInline]


@admin.register(TournamentTeamRegistration)
class TournamentTeamRegistrationAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'tournament', 'team_type', 'status', 'payment_confirmed', 'registered_at']
    list_filter = ['status', 'team_type', 'tournament']


@admin.register(TournamentPlayerRegistration)
class TournamentPlayerRegistrationAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'tournament', 'jersey_number', 'status']
    list_filter = ['tournament', 'status']


@admin.register(TournamentMatch)
class TournamentMatchAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'tournament', 'stage', 'status', 'match_date', 'match_duration']
    list_filter = ['tournament', 'stage', 'status']
    list_editable = ['match_duration']


@admin.register(TournamentGoal)
class TournamentGoalAdmin(admin.ModelAdmin):
    list_display = ['scorer_name', 'match', 'minute', 'is_penalty', 'is_own_goal']


@admin.register(TournamentCard)
class TournamentCardAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'match', 'card_type', 'minute']


class ExternalPlayerInline(admin.TabularInline):
    model = ExternalPlayer
    extra = 0


@admin.register(ExternalTeam)
class ExternalTeamAdmin(admin.ModelAdmin):
    list_display = ['team_name', 'tournament', 'contact_person', 'phone_number', 'created_at']
    list_filter = ['tournament']
    search_fields = ['team_name', 'contact_person']
    inlines = [ExternalPlayerInline]


@admin.register(ExternalPlayer)
class ExternalPlayerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'external_team', 'position', 'jersey_number']
    list_filter = ['external_team__tournament', 'position']


@admin.register(TournamentMatchOfficials)
class TournamentMatchOfficialsAdmin(admin.ModelAdmin):
    list_display = ['match', 'main_referee', 'status', 'appointed_at']
    list_filter = ['status']


class TournamentSquadPlayerInline(admin.TabularInline):
    model = TournamentSquadPlayer
    extra = 0


@admin.register(TournamentMatchdaySquad)
class TournamentMatchdaySquadAdmin(admin.ModelAdmin):
    list_display = ['team_registration', 'match', 'status', 'submitted_at']
    list_filter = ['status', 'match__tournament']
    inlines = [TournamentSquadPlayerInline]
