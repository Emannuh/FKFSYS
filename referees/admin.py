# referees/admin.py - FIXED VERSION FOR MERGED MODELS
from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.utils.html import format_html
from .models import (
    Referee, RefereeAvailability, MatchReport, MatchOfficials, TeamOfficial, PlayingKit,
    MatchVenueDetails, StartingLineup, ReservePlayer, 
    Substitution, Caution, Expulsion, MatchGoal
)

# ========== REFEREE ADMIN ==========
@admin.register(Referee)
class RefereeAdmin(admin.ModelAdmin):
    # ✅ FIXED: Changed 'grade' to 'level', removed 'id_number' from list_display
    list_display = [
        'full_name', 'fkf_number', 'email', 'level', 
        'status_badge', 'is_active', 'date_joined', 'approved_at_short'
    ]
    list_filter = ['level', 'county', 'is_active', 'status']
    search_fields = ['first_name', 'last_name', 'fkf_number', 'email', 'id_number']
    list_editable = ['is_active', 'level']  # ✅ Changed 'grade' to 'level'
    readonly_fields = [
        'date_joined', 'updated_at', 'approved_at', 'unique_id',
        'full_name', 'status_badge_display', 'user'
    ]
    actions = ['approve_selected_referees', 'reject_selected_referees', 'suspend_selected_referees', 'mark_as_pending']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone_number', 'photo')
        }),
        ('Identification', {
            'fields': ('unique_id', 'fkf_number', 'id_number', 'county')
        }),
        ('Referee Details', {
            'fields': ('level',)
        }),
        ('Approval Status', {
            'fields': ('status_badge_display', 'status', 'rejection_reason', 'suspension_reason', 'approved_by', 'approved_at'),
            'classes': ('collapse', 'wide')
        }),
        ('Account Status', {
            'fields': ('is_active',)
        }),
        ('User Account', {
            'fields': ('user',),
            'classes': ('collapse',),
            'description': 'User account is created automatically after approval.'
        }),
        ('Timestamps', {
            'fields': ('date_joined', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Custom display methods
    def status_badge(self, obj):
        """Display status with colored badge"""
        colors = {
            'approved': 'success',
            'pending': 'warning',
            'rejected': 'danger',
            'suspended': 'dark'
        }
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            colors.get(obj.status, 'secondary'),
            obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def status_badge_display(self, obj):
        """Display in readonly fields"""
        return self.status_badge(obj)
    status_badge_display.short_description = 'Current Status'
    
    def approved_at_short(self, obj):
        """Display short approved date"""
        if obj.approved_at:
            return obj.approved_at.strftime("%Y-%m-%d %H:%M")
        return "Not approved"
    approved_at_short.short_description = 'Approved'
    
    # Custom actions
    def approve_selected_referees(self, request, queryset):
        """Admin action to approve selected referees"""
        approved_count = 0
        credentials = []
        
        for referee in queryset:
            if referee.status != 'approved':
                unique_id, password = referee.approve(request.user)
                approved_count += 1
                credentials.append({
                    'name': referee.full_name,
                    'unique_id': unique_id,
                    'password': password
                })
        
        if approved_count > 0:
            # Show credentials in success message
            cred_text = "<br>".join([
                f"<strong>{c['name']}</strong>: ID={c['unique_id']}, Password={c['password']}"
                for c in credentials
            ])
            
            self.message_user(
                request, 
                format_html(
                    "Successfully approved {} referee(s).<br><br>"
                    "<strong>Login Credentials:</strong><br>{}",
                    approved_count,
                    cred_text
                ),
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                "No referees needed approval (already approved).",
                messages.WARNING
            )
    approve_selected_referees.short_description = "✅ Approve selected referees"
    
    def reject_selected_referees(self, request, queryset):
        """Admin action to reject selected referees"""
        rejected_count = 0
        for referee in queryset:
            if referee.status != 'rejected':
                referee.reject("Rejected by admin via admin panel")
                rejected_count += 1
        
        if rejected_count > 0:
            self.message_user(
                request,
                f"Successfully rejected {rejected_count} referee(s).",
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                "No referees needed rejection (already rejected).",
                messages.WARNING
            )
    reject_selected_referees.short_description = "❌ Reject selected referees"
    
    def suspend_selected_referees(self, request, queryset):
        """Admin action to suspend selected referees"""
        suspended_count = 0
        for referee in queryset:
            if referee.status == 'approved':
                referee.suspend("Suspended by admin via admin panel")
                suspended_count += 1
        
        if suspended_count > 0:
            self.message_user(
                request,
                f"Successfully suspended {suspended_count} referee(s).",
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                "No approved referees were selected for suspension.",
                messages.WARNING
            )
    suspend_selected_referees.short_description = "🚫 Suspend selected referees"
    
    def mark_as_pending(self, request, queryset):
        """Admin action to mark referees as pending"""
        updated_count = queryset.update(
            status='pending',
            approved_by=None,
            approved_at=None,
            rejection_reason='',
            suspension_reason=''
        )
        self.message_user(
            request,
            f"Marked {updated_count} referee(s) as pending.",
            messages.SUCCESS
        )
    mark_as_pending.short_description = "⏳ Mark selected as pending"
    
    # Customize change list view
    def changelist_view(self, request, extra_context=None):
        """Add statistics to the changelist view"""
        extra_context = extra_context or {}
        total = Referee.objects.count()
        approved = Referee.objects.filter(status='approved').count()
        pending = Referee.objects.filter(status='pending').count()
        rejected = Referee.objects.filter(status='rejected').count()
        suspended = Referee.objects.filter(status='suspended').count()
        
        extra_context['stats'] = {
            'total': total,
            'approved': approved,
            'pending': pending,
            'rejected': rejected,
            'suspended': suspended,
            'approval_rate': (approved / total * 100) if total > 0 else 0,
        }
        
        return super().changelist_view(request, extra_context=extra_context)


# ========== REFEREE AVAILABILITY ADMIN ==========
@admin.register(RefereeAvailability)
class RefereeAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['referee', 'date', 'is_available', 'reason']
    list_filter = ['is_available', 'date']
    search_fields = ['referee__first_name', 'referee__last_name', 'reason']
    date_hierarchy = 'date'


# ========== MATCH OFFICIALS ADMIN ==========
@admin.register(MatchOfficials)
class MatchOfficialsAdmin(admin.ModelAdmin):
    # ✅ FIXED: Removed 'position' and 'name' fields (don't exist in merged model)
    list_display = [
        'match', 'status', 'get_main_referee', 'get_assistant_1', 
        'get_assistant_2', 'appointment_made_at'
    ]
    list_filter = ['status', 'appointment_made_at']
    search_fields = [
        'match__home_team__name', 'match__away_team__name',
        'main_referee__first_name', 'main_referee__last_name'
    ]
    readonly_fields = [
        'appointment_made_at', 'appointment_made_by', 
        'last_reminder_sent', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Match Information', {
            'fields': ('match', 'status')
        }),
        ('Required Officials', {
            'fields': ('main_referee', 'assistant_1', 'assistant_2')
        }),
        ('Optional Officials', {
            'fields': ('reserve_referee', 'reserve_assistant', 'var', 'avar1', 'fourth_official', 'match_commissioner'),
            'classes': ('collapse',)
        }),
        ('Confirmation Status', {
            'fields': (
                'main_confirmed', 'main_confirmed_at',
                'ar1_confirmed', 'ar1_confirmed_at',
                'ar2_confirmed', 'ar2_confirmed_at',
                'reserve_confirmed', 'var_confirmed', 'fourth_confirmed'
            ),
            'classes': ('collapse',)
        }),
        ('Emergency Manual Entry', {
            'fields': (
                'main_referee_name', 'main_referee_mobile',
                'ar1_name', 'ar1_mobile',
                'ar2_name', 'ar2_mobile'
            ),
            'classes': ('collapse',),
            'description': 'Use only when officials are not in the system'
        }),
        ('Appointment Tracking', {
            'fields': ('appointment_made_at', 'appointment_made_by', 'last_reminder_sent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_main_referee(self, obj):
        return obj.main_referee.full_name if obj.main_referee else obj.main_referee_name or "Not Assigned"
    get_main_referee.short_description = 'Main Referee'
    
    def get_assistant_1(self, obj):
        return obj.assistant_1.full_name if obj.assistant_1 else obj.ar1_name or "Not Assigned"
    get_assistant_1.short_description = 'AR1'
    
    def get_assistant_2(self, obj):
        return obj.assistant_2.full_name if obj.assistant_2 else obj.ar2_name or "Not Assigned"
    get_assistant_2.short_description = 'AR2'


# ========== MATCH REPORT ADMIN ==========
@admin.register(MatchReport)
class MatchReportAdmin(admin.ModelAdmin):
    list_display = ['match_display', 'referee_name', 'status', 'submitted_at', 'approved_at']
    list_filter = ['status', 'submitted_at', 'league_level']
    search_fields = ['match__home_team__name', 'match__away_team__name', 'referee__first_name', 'referee__last_name']
    readonly_fields = ['created_at', 'updated_at', 'submitted_at', 'approved_at']
    actions = ['approve_reports', 'reject_reports']
    
    fieldsets = (
        ('Match Information', {
            'fields': ('match', 'referee', 'status', 'match_number', 'round_number', 'league_level')
        }),
        ('Match Incidents', {
            'fields': ('penalties_not_converted', 'serious_incidents', 'referee_comments'),
            'classes': ('collapse',)
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'submitted_at'),
            'classes': ('collapse',)
        })
    )
    
    def match_display(self, obj):
        """Display match teams"""
        return f"{obj.match.home_team} vs {obj.match.away_team}"
    match_display.short_description = 'Match'
    
    def referee_name(self, obj):
        """Display referee full name"""
        return obj.referee.full_name if obj.referee else "N/A"
    referee_name.short_description = 'Referee'
    
    def approve_reports(self, request, queryset):
        """Approve selected reports"""
        updated = queryset.filter(status='submitted').update(
            status='approved',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f"Approved {updated} report(s).", messages.SUCCESS)
    approve_reports.short_description = "✅ Approve selected reports"
    
    def reject_reports(self, request, queryset):
        """Reject selected reports"""
        updated = queryset.filter(status='submitted').update(
            status='rejected',
            approved_by=request.user
        )
        self.message_user(request, f"Rejected {updated} report(s).", messages.SUCCESS)
    reject_reports.short_description = "❌ Reject selected reports"


# ========== OTHER MODEL ADMINS ==========
@admin.register(TeamOfficial)
class TeamOfficialAdmin(admin.ModelAdmin):
    list_display = ['match', 'team', 'position', 'name', 'mobile']
    list_filter = ['position', 'team']
    search_fields = ['name', 'mobile']


@admin.register(PlayingKit)
class PlayingKitAdmin(admin.ModelAdmin):
    list_display = ['match', 'team', 'item', 'condition', 'notes']
    list_filter = ['condition', 'item', 'team']
    search_fields = ['team__name', 'notes']


@admin.register(MatchVenueDetails)
class MatchVenueDetailsAdmin(admin.ModelAdmin):
    list_display = ['match', 'pitch_condition', 'attendance', 'weather_during']
    list_filter = ['pitch_condition']
    search_fields = ['match__home_team__name', 'match__away_team__name']


@admin.register(StartingLineup)
class StartingLineupAdmin(admin.ModelAdmin):
    list_display = ['match', 'team', 'player', 'jersey_number', 'position']
    list_filter = ['team', 'position']
    search_fields = ['player__first_name', 'player__last_name']


@admin.register(ReservePlayer)
class ReservePlayerAdmin(admin.ModelAdmin):
    list_display = ['match', 'team', 'player', 'jersey_number']
    list_filter = ['team']
    search_fields = ['player__first_name', 'player__last_name']


@admin.register(Substitution)
class SubstitutionAdmin(admin.ModelAdmin):
    list_display = ['match', 'team', 'minute', 'player_out', 'player_in', 'jersey_out', 'jersey_in']
    list_filter = ['team']
    search_fields = ['player_out__first_name', 'player_out__last_name', 'player_in__first_name', 'player_in__last_name']
    ordering = ['match', 'minute']


@admin.register(Caution)
class CautionAdmin(admin.ModelAdmin):
    list_display = ['match', 'player', 'team', 'minute', 'jersey_number', 'reason_short']
    list_filter = ['team']
    search_fields = ['player__first_name', 'player__last_name', 'reason']
    ordering = ['match', 'minute']
    
    def reason_short(self, obj):
        """Show first 50 chars of reason"""
        return obj.reason[:50] + '...' if len(obj.reason) > 50 else obj.reason
    reason_short.short_description = 'Reason'


@admin.register(Expulsion)
class ExpulsionAdmin(admin.ModelAdmin):
    list_display = ['match', 'player', 'team', 'minute', 'jersey_number', 'reason_short']
    list_filter = ['team']
    search_fields = ['player__first_name', 'player__last_name', 'reason']
    ordering = ['match', 'minute']
    
    def reason_short(self, obj):
        """Show first 50 chars of reason"""
        return obj.reason[:50] + '...' if len(obj.reason) > 50 else obj.reason
    reason_short.short_description = 'Reason'


@admin.register(MatchGoal)
class MatchGoalAdmin(admin.ModelAdmin):
    list_display = ['match', 'player', 'team', 'minute', 'goal_type', 'jersey_number', 'assist_by']
    list_filter = ['team', 'goal_type']
    search_fields = ['player__first_name', 'player__last_name']
    ordering = ['match', 'minute']