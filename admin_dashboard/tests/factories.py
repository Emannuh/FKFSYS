"""Plain-function test factories (synthetic data only)."""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone

from matches.models import Match
from referees.models import MatchReport, Referee
from teams.models import Player, Team, Zone

User = get_user_model()
_seq = itertools.count(1)

ROLE_GROUPS = ['League Admin', 'League Manager', 'Referees Manager', 'Team Managers', 'Referee']


def n() -> int:
    return next(_seq)


def ensure_groups():
    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)


def make_user(*groups, password='pw-Test-12345', **kwargs):
    i = n()
    kwargs.setdefault('username', f'user{i}')
    kwargs.setdefault('email', f'user{i}@example.test')
    user = User.objects.create_user(password=password, **kwargs)
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def make_superuser(**kwargs):
    return make_user(is_superuser=True, is_staff=True, **kwargs)


def _fill(model, overrides):
    """Fill required concrete fields of ``model`` with synthetic values."""
    data = dict(overrides)
    for field in model._meta.concrete_fields:
        if field.primary_key or field.name in data or field.attname in data:
            continue
        if field.has_default() or field.null or getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False):
            continue
        if field.blank and not isinstance(field, models.ForeignKey):
            continue
        i = n()
        if field.choices:
            data[field.name] = field.choices[0][0]
        elif isinstance(field, models.EmailField):
            data[field.name] = f'f{i}@example.test'
        elif isinstance(field, (models.CharField, models.TextField)):
            data[field.name] = f'v{i}'[: field.max_length or 50]
        elif isinstance(field, models.DateTimeField):
            data[field.name] = timezone.now()
        elif isinstance(field, models.DateField):
            data[field.name] = datetime.date(1995, 1, 1)
        elif isinstance(field, models.DecimalField):
            data[field.name] = Decimal('1')
        elif isinstance(field, (models.IntegerField, models.FloatField)):
            data[field.name] = i
        elif isinstance(field, models.BooleanField):
            data[field.name] = False
        elif isinstance(field, models.ForeignKey):
            raise ValueError(f"{model.__name__}.{field.name} must be supplied")
    return data


def make_zone(**kw):
    return Zone.objects.create(name=kw.pop('name', f'Zone {n()}'), **kw)


def make_team(**kw):
    i = n()
    kw.setdefault('team_name', f'Team {i}')
    kw.setdefault('email', f'team{i}@example.test')
    kw.setdefault('contact_person', 'Test Contact')
    kw.setdefault('location', 'Meru')
    kw.setdefault('home_ground', 'Ground')
    kw.setdefault('phone_number', f'+2547{i:08d}')
    return Team.objects.create(**_fill(Team, kw))


def make_player(team, **kw):
    i = n()
    kw.setdefault('first_name', 'Test')
    kw.setdefault('last_name', f'Player{i}')
    kw.setdefault('date_of_birth', datetime.date(2000, 1, 1))
    kw.setdefault('id_number', f'ID{i}')
    kw.setdefault('position', 'MF')
    kw.setdefault('jersey_number', i % 99 + 1)
    return Player.objects.create(team=team, **kw)


def make_match(home, away, zone, **kw):
    kw.setdefault('match_date', timezone.now() + datetime.timedelta(days=7))
    kw.setdefault('venue', 'Ground')
    return Match.objects.create(**_fill(Match, {'home_team': home, 'away_team': away, 'zone': zone, **kw}))


def make_referee(user, **kw):
    return Referee.objects.create(**_fill(Referee, {'user': user, **kw}))


def make_report(match, referee, **kw):
    return MatchReport.objects.create(**_fill(MatchReport, {'match': match, 'referee': referee, **kw}))
