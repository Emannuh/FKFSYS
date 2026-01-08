from .models import Suspension
from django.utils import timezone

def apply_suspensions(match):
    """Apply suspensions after match report is approved"""
    cards = Card.objects.filter(match=match)
    
    for card in cards:
        player = card.player
        
        if card.card_type == 'red':
            # Direct red card - 3 match ban
            suspension = Suspension.objects.create(
                player=player,
                match=match,
                reason='red_card',
                details=f"Direct red card in match against {match.away_team if card.team == match.home_team else match.home_team}",
                matches_missed=3,
                start_date=timezone.now().date(),
                is_active=True
            )
            
            player.is_suspended = True
            player.suspension_reason = "Direct red card - 3 match ban"
            player.save()
        
        elif card.card_type == 'yellow':
            # Check for second yellow in same match
            yellow_cards_in_match = cards.filter(
                player=player,
                card_type='yellow',
                match=match
            ).count()
            
            if yellow_cards_in_match >= 2:
                # Two yellows in one match - 2 match ban
                suspension = Suspension.objects.create(
                    player=player,
                    match=match,
                    reason='double_yellow',
                    details="Two yellow cards in one match",
                    matches_missed=2,
                    start_date=timezone.now().date(),
                    is_active=True
                )
                
                player.is_suspended = True
                player.suspension_reason = "Two yellow cards in one match - 2 match ban"
                player.save()
            
            # Check for accumulated yellows (6 total)
            if player.yellow_cards >= 6:
                # 6 accumulated yellows - 1 match ban
                suspension = Suspension.objects.create(
                    player=player,
                    match=match,
                    reason='accumulated_yellow',
                    details=f"Accumulated {player.yellow_cards} yellow cards",
                    matches_missed=1,
                    start_date=timezone.now().date(),
                    is_active=True
                )
                
                player.is_suspended = True
                player.suspension_reason = f"6 accumulated yellow cards - 1 match ban"
                player.yellow_cards = 0  # Reset after suspension
                player.save()

def update_suspensions():
    """Update suspension status based on matches played"""
    active_suspensions = Suspension.objects.filter(is_active=True)
    
    for suspension in active_suspensions:
        player = suspension.player
        team = player.team
        
        # Count matches the player has missed since suspension
        matches_missed = Match.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            status='completed',
            match_date__date__gte=suspension.start_date
        ).count()
        
        suspension.matches_served = matches_missed
        
        if suspension.matches_served >= suspension.matches_missed:
            suspension.is_active = False
            suspension.end_date = timezone.now().date()
            
            # Check if player has other active suspensions
            other_suspensions = Suspension.objects.filter(
                player=player,
                is_active=True
            ).exclude(id=suspension.id)
            
            if not other_suspensions.exists():
                player.is_suspended = False
                player.suspension_end = None
                player.save()
        
        suspension.save()