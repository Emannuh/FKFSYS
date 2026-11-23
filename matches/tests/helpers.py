"""Synthetic-data factories for matches tests (plain functions, no extra deps)."""
from datetime import datetime, timedelta
from itertools import count

from django.contrib.auth.models import Group, User
from django.utils import timezone

from matches.models import Match
from teams.models import Team, Zone

_seq = count(1)


def make_zone(name=None, **kw):
    return Zone.objects.create(name=name or f"Zone {next(_seq)}", **kw)


def make_team(zone=None, status='approved', **kw):
    n = next(_seq)
    defaults = dict(
        team_name=f"Team {n}", location="Meru", home_ground=f"Ground {n}", contact_person="C",
        phone_number=f"+2547{n:08d}", email=f"team{n}@example.test", zone=zone, status=status,
    )
    defaults.update(kw)
    return Team.objects.create(**defaults)


def make_match(home, away, zone=None, status=Match.Status.SCHEDULED, home_score=0, away_score=0,
               when=None, round_number=1, **kw):
    return Match.objects.create(
        home_team=home, away_team=away, zone=zone or home.zone, status=status,
        home_score=home_score, away_score=away_score, round_number=round_number,
        match_date=when or timezone.now() + timedelta(days=3), venue="V", **kw,
    )


def make_user(username=None, groups=(), **kw):
    user = User.objects.create_user(username or f"user{next(_seq)}", password="pw", **kw)
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def local_dt(y, m, d, hh=0, mm=0):
    return timezone.make_aware(datetime(y, m, d, hh, mm))
