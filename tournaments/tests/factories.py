"""Plain helper factories with synthetic data (no third-party deps)."""
import itertools
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.utils import timezone

from referees.models import Referee
from teams.models import Player, Team

from ..models import (
    ExternalPlayer,
    ExternalTeam,
    Tournament,
    TournamentMatch,
    TournamentMatchOfficials,
    TournamentTeamRegistration,
)

_seq = itertools.count(1)
PASSWORD = 'Synthetic-pass-9481'


def n() -> int:
    return next(_seq)


def make_user(*groups: str, **extra) -> User:
    i = n()
    user = User.objects.create_user(
        username=f'user{i}', email=f'user{i}@example.test', password=PASSWORD, **extra,
    )
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def make_tournament(**kw) -> Tournament:
    i = n()
    defaults = dict(
        name=f'Test Cup {i}',
        start_date=date.today() + timedelta(days=30),
        end_date=date.today() + timedelta(days=40),
        registration_deadline=timezone.now() + timedelta(days=10),
        status=Tournament.Status.REGISTRATION,
        format=Tournament.Format.ROUND_ROBIN,
        max_teams=16,
    )
    defaults.update(kw)
    return Tournament.objects.create(**defaults)


def make_team(manager=None, **kw) -> Team:
    i = n()
    defaults = dict(
        team_name=f'Synthetic FC {i}', location='Testville', home_ground='Test Ground',
        contact_person='Test Person', phone_number=f'+2547{i:08d}',
        email=f'team{i}@example.test', status='approved', manager=manager,
    )
    defaults.update(kw)
    return Team.objects.create(**defaults)


def make_player(team, position='MF', **kw) -> Player:
    i = n()
    defaults = dict(
        first_name='Player', last_name=str(i), date_of_birth=date(2000, 1, 1),
        id_number=f'ID{i:08d}', team=team, position=position, jersey_number=i % 99 + 1,
    )
    defaults.update(kw)
    return Player.objects.create(**defaults)


def make_league_reg(tournament, team=None, status='approved', **kw) -> TournamentTeamRegistration:
    return TournamentTeamRegistration.objects.create(
        tournament=tournament, team=team or make_team(), team_type='league', status=status, **kw,
    )


def make_external_reg(tournament, manager=None, status='approved') -> TournamentTeamRegistration:
    i = n()
    ext = ExternalTeam.objects.create(
        tournament=tournament, team_name=f'Outside XI {i}', contact_person='Ext Person',
        phone_number='+254700000001', manager_user=manager,
    )
    return TournamentTeamRegistration.objects.create(
        tournament=tournament, external_team=ext, team_type='external', status=status,
    )


def make_external_player(ext_team, position='MF') -> ExternalPlayer:
    i = n()
    return ExternalPlayer.objects.create(
        external_team=ext_team, first_name='Ext', last_name=str(i), position=position, jersey_number=i,
    )


def make_match(tournament, home=None, away=None, **kw) -> TournamentMatch:
    defaults = dict(
        tournament=tournament, stage='group', match_number=n(),
        home_team=home, away_team=away, match_date=timezone.now() + timedelta(days=5),
    )
    defaults.update(kw)
    return TournamentMatch.objects.create(**defaults)


def make_referee(user=None) -> Referee:
    i = n()
    return Referee.objects.create(
        user=user, first_name='Ref', last_name=str(i), fkf_number=f'FKF{i:06d}',
        email=f'ref{i}@example.test', phone_number=f'+2541{i:08d}', status='approved',
        id_number=f'RID{i:07d}',
    )


def appoint(match, referee) -> TournamentMatchOfficials:
    return TournamentMatchOfficials.objects.create(match=match, main_referee=referee, status='APPOINTED')
