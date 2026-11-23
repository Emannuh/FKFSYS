"""Plain-function factories for synthetic test data (no external dependencies)."""
from datetime import date, timedelta
from itertools import count

from django.contrib.auth.models import Group, Permission, User
from django.utils import timezone

from matches.models import Match
from referees.models import MatchdaySquad, MatchOfficials, Referee, SquadPlayer
from teams.models import Player, Team, Zone

_seq = count(1)


def n() -> int:
    return next(_seq)


def group(name: str, *perm_codenames: str) -> Group:
    g, _ = Group.objects.get_or_create(name=name)
    if perm_codenames:
        g.permissions.add(*Permission.objects.filter(codename__in=perm_codenames))
    return g


def user(*groups: str, perms: tuple[str, ...] = (), **kwargs) -> User:
    i = n()
    u = User.objects.create_user(username=f'user{i}', password='x', email=f'user{i}@example.com', **kwargs)
    for name in groups:
        u.groups.add(group(name))
    if perms:
        u.user_permissions.add(*Permission.objects.filter(codename__in=perms))
    return u


def referees_manager() -> User:
    return user('Referees Manager', perms=('appoint_referees', 'replace_referee', 'approve_prematch_form_manager'))


def referee(status=Referee.Status.APPROVED, with_user=True, **kwargs) -> Referee:
    i = n()
    u = user('Referee', perms=('confirm_appointment', 'submit_match_report')) if with_user else None
    return Referee.objects.create(
        user=u, first_name=f'Ref{i}', last_name='Official', fkf_number=f'FKF-{i}',
        email=f'ref{i}@example.com', status=status,
        is_active=status == Referee.Status.APPROVED, unique_id=f'REF-T-{i}' if with_user else None,
        **kwargs,
    )


def zone() -> Zone:
    return Zone.objects.create(name=f'Zone {n()}')


def team(z=None, manager=None) -> Team:
    i = n()
    return Team.objects.create(
        team_name=f'Team {i}', location='Meru', home_ground='Ground', contact_person='C',
        phone_number=f'+2547{i:08d}', email=f'team{i}@example.com', zone=z or zone(),
        status='pending', manager=manager,
    )


def player(t: Team, position='MF', **kwargs) -> Player:
    i = n()
    return Player.objects.create(
        first_name=f'P{i}', last_name='Player', date_of_birth=date(2000, 1, 1), id_number=f'ID{i}',
        team=t, position=position, jersey_number=i % 99 + 1, **kwargs,
    )


def match(home=None, away=None, when=None, **kwargs) -> Match:
    home = home or team()
    away = away or team(z=home.zone)
    return Match.objects.create(
        home_team=home, away_team=away, zone=home.zone,
        match_date=when or timezone.now() + timedelta(days=2), venue='Stadium', **kwargs,
    )


def officials(m: Match, **roles) -> MatchOfficials:
    o = MatchOfficials(match=m, status=MatchOfficials.Status.APPOINTED, **roles)
    o.save(validate=False)
    return o


def squad(m: Match, t: Team, status=MatchdaySquad.Status.SUBMITTED, starters=7, subs=2) -> MatchdaySquad:
    s = MatchdaySquad.objects.create(match=m, team=t, status=status)
    for i in range(starters):
        SquadPlayer.objects.create(squad=s, player=player(t, 'GK' if i == 0 else 'MF'), is_starting=True,
                                   jersey_number=i + 1)
    for i in range(subs):
        SquadPlayer.objects.create(squad=s, player=player(t, 'GK' if i == 0 else 'DF'), is_starting=False,
                                   jersey_number=50 + i)
    return s
