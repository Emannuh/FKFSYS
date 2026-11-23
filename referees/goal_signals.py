"""
Keep the denormalised Player tallies (goals, cards, clean sheets) in step with
match events.

Every handler works on *deltas* between the previously stored row and the new
one, so re-saving an unchanged row (e.g. re-saving a draft report) is a no-op,
editing a row moves the tally to the right player, and deleting reverses it.
All counter updates use F() expressions; decrements never go below zero.
"""
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from matches.models import Match
from teams.models import Player

from .models import Caution, Expulsion, MatchGoal

COMPLETED = 'completed'


def _bump(player_id, field: str, delta: int) -> None:
    if not player_id or not delta:
        return
    qs = Player.objects.filter(pk=player_id)
    if delta > 0:
        qs.update(**{field: F(field) + delta})
    else:
        # Never go negative (tallies may have been reset manually, e.g. after a suspension).
        qs.filter(**{f'{field}__gte': -delta}).update(**{field: F(field) + delta})
        qs.filter(**{f'{field}__lt': -delta}).update(**{field: 0})


def _remember_previous(instance, attrs: tuple[str, ...]) -> None:
    previous = None
    if instance.pk:
        previous = type(instance).objects.filter(pk=instance.pk).values(*attrs).first()
    instance._tally_previous = previous


# --------------------------------------------------------------- goals
def _goal_credit(player_id, goal_type):
    """The player credited with a goal (own goals credit nobody)."""
    return None if goal_type == MatchGoal.GoalType.OWN_GOAL else player_id


@receiver(pre_save, sender=MatchGoal)
def _goal_pre_save(sender, instance, raw=False, **kwargs):
    if not raw:
        _remember_previous(instance, ('player_id', 'goal_type'))


@receiver(post_save, sender=MatchGoal)
def update_player_goals_on_save(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    prev = getattr(instance, '_tally_previous', None)
    old = _goal_credit(prev['player_id'], prev['goal_type']) if prev else None
    new = _goal_credit(instance.player_id, instance.goal_type)
    if old != new:
        _bump(old, 'goals_scored', -1)
        _bump(new, 'goals_scored', +1)


@receiver(post_delete, sender=MatchGoal)
def update_player_goals_on_delete(sender, instance, **kwargs):
    _bump(_goal_credit(instance.player_id, instance.goal_type), 'goals_scored', -1)


# --------------------------------------------------------------- cards
def _card_handlers(model, field: str) -> None:
    def pre(sender, instance, raw=False, **kwargs):
        if not raw:
            _remember_previous(instance, ('player_id',))

    def post(sender, instance, created, raw=False, **kwargs):
        if raw:
            return
        prev = getattr(instance, '_tally_previous', None)
        old = prev['player_id'] if prev else None
        if old != instance.player_id:
            _bump(old, field, -1)
            _bump(instance.player_id, field, +1)

    def delete(sender, instance, **kwargs):
        _bump(instance.player_id, field, -1)

    pre_save.connect(pre, sender=model, weak=False, dispatch_uid=f'tally_pre_{model.__name__}')
    post_save.connect(post, sender=model, weak=False, dispatch_uid=f'tally_post_{model.__name__}')
    post_delete.connect(delete, sender=model, weak=False, dispatch_uid=f'tally_del_{model.__name__}')


_card_handlers(Caution, 'yellow_cards')
_card_handlers(Expulsion, 'red_cards')


# --------------------------------------------------------- clean sheets
def _clean_sheet_teams(status, home_team_id, away_team_id, home_score, away_score) -> set:
    """Team ids credited with a clean sheet by a match in this state."""
    if status != COMPLETED or home_score is None or away_score is None:
        return set()
    teams = set()
    if away_score == 0:
        teams.add(home_team_id)
    if home_score == 0:
        teams.add(away_team_id)
    return teams


_MATCH_ATTRS = ('status', 'home_team_id', 'away_team_id', 'home_score', 'away_score')


@receiver(pre_save, sender=Match)
def _match_pre_save(sender, instance, raw=False, **kwargs):
    if not raw:
        _remember_previous(instance, _MATCH_ATTRS)


@receiver(post_save, sender=Match)
def update_goalkeeper_clean_sheets(sender, instance, created, raw=False, **kwargs):
    """
    Credit (or withdraw) a clean sheet to the goalkeepers of a team when a match
    *enters* (or leaves / changes) a completed state in which that team conceded
    nothing. Saving a match again in the same state changes nothing, and
    scheduled/unplayed matches never count.
    """
    if raw:
        return
    prev = getattr(instance, '_tally_previous', None)
    before = _clean_sheet_teams(*(prev[a] for a in _MATCH_ATTRS)) if prev else set()
    after = _clean_sheet_teams(*(getattr(instance, a) for a in _MATCH_ATTRS))
    changes = [(t, -1) for t in before - after] + [(t, +1) for t in after - before]
    for team_id, delta in changes:
        gk_ids = Player.objects.filter(team_id=team_id, position='GK').values_list('pk', flat=True)
        for gk_id in gk_ids:
            _bump(gk_id, 'clean_sheets', delta)
