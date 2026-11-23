"""Synthetic-data helpers for teams tests (no external factory library)."""
import datetime
import itertools

from django.contrib.auth.models import Group, User
from django.utils import timezone

from teams.models import LeagueSettings, Player, Team, TeamOfficial, TransferRequest, Zone

_seq = itertools.count(1)

ROLES = ('League Admin', 'League Manager', 'Referees Manager', 'Team Managers', 'Referee')


def make_user(role=None, *, staff=False, superuser=False, username=None):
    n = next(_seq)
    if superuser:
        user = User.objects.create_superuser(username or f'super{n}', f'super{n}@example.test', 'pw')
    else:
        user = User.objects.create_user(username or f'user{n}', f'user{n}@example.test', 'pw', is_staff=staff)
    if role:
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
    return user


def make_zone(name=None):
    return Zone.objects.create(name=name or f'Zone {next(_seq)}')


def make_team(manager=None, *, status=Team.Status.APPROVED, kit=True, zone=None, **extra):
    n = next(_seq)
    defaults = dict(
        team_name=f'Team {n}',
        location='Meru',
        home_ground='Ground',
        contact_person='Contact',
        phone_number=f'+2547{n:08d}',
        email=f'team{n}@example.test',
        status=status,
        manager=manager,
        kit_colors_set=kit,
        zone=zone,
    )
    defaults.update(extra)
    return Team.objects.create(**defaults)


def make_manager_with_team(**team_kwargs):
    user = make_user('Team Managers')
    return user, make_team(user, **team_kwargs)


def make_player(team, *, jersey=None, **extra):
    n = next(_seq)
    defaults = dict(
        first_name=f'First{n}',
        last_name=f'Last{n}',
        date_of_birth=datetime.date(2000, 1, 1),
        id_number=f'{10000000 + n}',
        position=Player.Position.MIDFIELDER,
        jersey_number=jersey if jersey is not None else (n % 99) + 1,
        team=team,
    )
    defaults.update(extra)
    return Player.objects.create(**defaults)


def make_official(team, position=TeamOfficial.Position.TEAM_DOCTOR, **extra):
    n = next(_seq)
    defaults = dict(team=team, position=position, full_name=f'Official {n}',
                    id_number=f'{20000000 + n}', phone_number='+254700000000')
    defaults.update(extra)
    return TeamOfficial.objects.create(**defaults)


def make_transfer(player, to_team, requested_by=None, **extra):
    return TransferRequest.objects.create(
        player=player, from_team=player.team, to_team=to_team, requested_by=requested_by, **extra
    )


def open_windows(**overrides):
    league = LeagueSettings.get_settings()
    for field in ('team_registration_open', 'player_registration_open', 'transfer_window_open'):
        setattr(league, field, overrides.get(field, True))
    league.save()
    return league


def adult_dob(years=25):
    return datetime.date(timezone.localdate().year - years, 6, 15)
