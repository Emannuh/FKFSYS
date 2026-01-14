from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import F
from .models import MatchGoal, Caution, Expulsion
from teams.models import Player
from matches.models import Match


@receiver(post_save, sender=MatchGoal)
def update_player_goals_on_save(sender, instance, created, **kwargs):
    """
    Automatically update player's goal count when a goal is added.
    This updates the league top scorers list automatically.
    """
    if created and instance.goal_type != 'own_goal':
        # Increment the player's goals_scored count
        Player.objects.filter(pk=instance.player.pk).update(
            goals_scored=F('goals_scored') + 1
        )


@receiver(post_delete, sender=MatchGoal)
def update_player_goals_on_delete(sender, instance, **kwargs):
    """
    Automatically decrease player's goal count when a goal is deleted.
    """
    if instance.goal_type != 'own_goal':
        # Decrement the player's goals_scored count (but don't go below 0)
        player = Player.objects.get(pk=instance.player.pk)
        if player.goals_scored > 0:
            player.goals_scored = F('goals_scored') - 1
            player.save(update_fields=['goals_scored'])


@receiver(post_save, sender=Caution)
def update_player_yellow_cards_on_save(sender, instance, created, **kwargs):
    """
    Automatically update player's yellow card count when a caution is issued.
    """
    if created:
        Player.objects.filter(pk=instance.player.pk).update(
            yellow_cards=F('yellow_cards') + 1
        )


@receiver(post_delete, sender=Caution)
def update_player_yellow_cards_on_delete(sender, instance, **kwargs):
    """
    Automatically decrease player's yellow card count when a caution is deleted.
    """
    player = Player.objects.get(pk=instance.player.pk)
    if player.yellow_cards > 0:
        player.yellow_cards = F('yellow_cards') - 1
        player.save(update_fields=['yellow_cards'])


@receiver(post_save, sender=Expulsion)
def update_player_red_cards_on_save(sender, instance, created, **kwargs):
    """
    Automatically update player's red card count when an expulsion is issued.
    """
    if created:
        Player.objects.filter(pk=instance.player.pk).update(
            red_cards=F('red_cards') + 1
        )


@receiver(post_delete, sender=Expulsion)
def update_player_red_cards_on_delete(sender, instance, **kwargs):
    """
    Automatically decrease player's red card count when an expulsion is deleted.
    """
    player = Player.objects.get(pk=instance.player.pk)
    if player.red_cards > 0:
        player.red_cards = F('red_cards') - 1
        player.save(update_fields=['red_cards'])


@receiver(post_save, sender=Match)
def update_goalkeeper_clean_sheets(sender, instance, created, **kwargs):
    """
    Automatically update goalkeeper's clean sheet count when a match score is saved.
    A goalkeeper gets a clean sheet if:
    - Their team won or drew AND didn't concede any goals
    - They played in the match (we'll assume the regular GK played)
    """
    if not created:  # Only when updating an existing match (score added)
        # Home team clean sheet - home team conceded 0 goals
        if instance.away_score == 0 and instance.home_score >= 0:
            # Find home team's goalkeeper
            home_goalkeepers = Player.objects.filter(
                team=instance.home_team,
                position='GK'
            )
            for gk in home_goalkeepers:
                # Increment clean sheets
                Player.objects.filter(pk=gk.pk).update(
                    clean_sheets=F('clean_sheets') + 1
                )
        
        # Away team clean sheet - away team conceded 0 goals
        if instance.home_score == 0 and instance.away_score >= 0:
            # Find away team's goalkeeper
            away_goalkeepers = Player.objects.filter(
                team=instance.away_team,
                position='GK'
            )
            for gk in away_goalkeepers:
                # Increment clean sheets
                Player.objects.filter(pk=gk.pk).update(
                    clean_sheets=F('clean_sheets') + 1
                )
