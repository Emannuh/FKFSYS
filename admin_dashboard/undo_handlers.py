# admin_dashboard/undo_handlers.py
"""
Undo handlers for reversing administrative actions
"""

from django.utils import timezone
from teams.models import Team, Player, Zone
from matches.models import Match, Suspension
from django.contrib.auth import get_user_model

User = get_user_model()


def log_activity(user, action, description, obj=None, previous_state=None, 
                new_state=None, can_undo=False, request=None):
    """
    Helper function to log activities with undo support
    """
    from admin_dashboard.models import ActivityLog
    from django.contrib.contenttypes.models import ContentType
    
    log = ActivityLog(
        user=user,
        action=action,
        description=description,
        previous_state=previous_state,
        new_state=new_state,
        can_undo=can_undo
    )
    
    if obj:
        log.content_type = ContentType.objects.get_for_model(obj)
        log.object_id = obj.pk
        log.object_repr = str(obj)
    
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            log.ip_address = x_forwarded_for.split(',')[0]
        else:
            log.ip_address = request.META.get('REMOTE_ADDR')
        log.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    
    log.save()
    return log


def undo_team_approval(log):
    """Undo team approval"""
    try:
        team = Team.objects.get(pk=log.object_id)
        if team.status == 'approved':
            team.status = log.previous_state.get('status', 'pending')
            team.save()
            return True, f"Team '{team.team_name}' reverted to {team.status} status"
        return False, "Team status already changed"
    except Team.DoesNotExist:
        return False, "Team no longer exists"


def undo_team_rejection(log):
    """Undo team rejection"""
    try:
        team = Team.objects.get(pk=log.object_id)
        team.status = log.previous_state.get('status', 'pending')
        team.save()
        return True, f"Team '{team.team_name}' status restored to {team.status}"
    except Team.DoesNotExist:
        return False, "Team no longer exists"


def undo_team_suspension(log):
    """Undo team suspension"""
    try:
        team = Team.objects.get(pk=log.object_id)
        if team.status == 'suspended':
            team.status = log.previous_state.get('status', 'approved')
            team.save()
            return True, f"Team '{team.team_name}' suspension lifted"
        return False, "Team is not currently suspended"
    except Team.DoesNotExist:
        return False, "Team no longer exists"


def undo_fixtures_generation(log):
    """Undo fixture generation"""
    try:
        zone = Zone.objects.get(pk=log.object_id)
        
        # Check if any matches have been played
        matches = Match.objects.filter(zone=zone)
        played = matches.filter(status__in=['completed', 'ongoing']).count()
        
        if played > 0:
            return False, f"Cannot undo: {played} match(es) have been played"
        
        # Delete all matches
        count = matches.count()
        matches.delete()
        
        # Reset zone status
        zone.fixtures_generated = False
        zone.fixture_generation_date = None
        zone.save()
        
        return True, f"Deleted {count} fixtures for zone '{zone.name}'"
    except Zone.DoesNotExist:
        return False, "Zone no longer exists"


def undo_player_suspension(log):
    """Undo player suspension"""
    try:
        player = Player.objects.get(pk=log.object_id)
        # Lift active suspensions
        lifted = Suspension.objects.filter(
            player=player, 
            is_active=True
        ).update(is_active=False)
        return True, f"Lifted suspension for '{player.full_name}' ({lifted} suspension(s) removed)"
    except Player.DoesNotExist:
        return False, "Player no longer exists"


def undo_user_deactivation(log):
    """Undo user deactivation"""
    try:
        user = User.objects.get(pk=log.object_id)
        if not user.is_active:
            user.is_active = True
            user.save()
            return True, f"User '{user.username}' reactivated"
        return False, "User is already active"
    except User.DoesNotExist:
        return False, "User no longer exists"


def undo_user_role_change(log):
    """Undo user role change"""
    try:
        user = User.objects.get(pk=log.object_id)
        prev_state = log.previous_state
        
        # Restore previous groups
        if 'groups' in prev_state:
            user.groups.clear()
            for group_id in prev_state['groups']:
                from django.contrib.auth.models import Group
                try:
                    group = Group.objects.get(id=group_id)
                    user.groups.add(group)
                except Group.DoesNotExist:
                    pass
        
        # Restore staff status
        if 'is_staff' in prev_state:
            user.is_staff = prev_state['is_staff']
        
        user.save()
        return True, f"User '{user.username}' role restored"
    except User.DoesNotExist:
        return False, "User no longer exists"


def undo_zone_assignment(log):
    """Undo zone assignment"""
    try:
        team = Team.objects.get(pk=log.object_id)
        if log.previous_state and 'zone_id' in log.previous_state:
            old_zone_id = log.previous_state['zone_id']
            if old_zone_id:
                team.zone_id = old_zone_id
            else:
                team.zone = None
            team.save()
            zone_name = team.zone.name if team.zone else "None"
            return True, f"Team '{team.team_name}' zone restored to {zone_name}"
        return False, "Previous zone information not available"
    except Team.DoesNotExist:
        return False, "Team no longer exists"


# Undo handler registry
UNDO_HANDLERS = {
    'TEAM_APPROVE': undo_team_approval,
    'TEAM_REJECT': undo_team_rejection,
    'TEAM_SUSPEND': undo_team_suspension,
    'FIXTURE_GENERATE': undo_fixtures_generation,
    'FIXTURE_REGENERATE': undo_fixtures_generation,
    'SUSPENSION_CREATE': undo_player_suspension,
    'USER_DELETE': None,  # Cannot undo deletion
    'USER_ROLE_CHANGE': undo_user_role_change,
    'ZONE_ASSIGN': undo_zone_assignment,
}


def perform_undo(log, user, reason=""):
    """
    Perform undo operation
    
    Args:
        log: ActivityLog instance to undo
        user: User performing the undo
        reason: Reason for undo
    
    Returns:
        (success, message) tuple
    """
    if not log.can_be_undone():
        return False, "This action cannot be undone (already undone, too old, or not undoable)"
    
    # Get undo handler
    handler = UNDO_HANDLERS.get(log.action)
    
    if handler is None:
        return False, f"Undo not implemented for action type: {log.get_action_display()}"
    
    # Perform the undo
    try:
        success, message = handler(log)
        
        if success:
            # Mark as undone
            log.is_undone = True
            log.undone_at = timezone.now()
            log.undone_by = user
            log.undo_reason = reason
            log.save()
            
            # Log the undo action itself
            log_activity(
                user=user,
                action='OTHER',
                description=f"Undid action: {log.description}. Reason: {reason}",
                obj=None,
                can_undo=False
            )
            
        return success, message
        
    except Exception as e:
        return False, f"Error during undo: {str(e)}"
