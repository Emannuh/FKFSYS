"""
verify_python_lead.py
Run: python verify_python_lead.py

Verifies all "Python takes the lead" changes are working correctly.
Safe to delete after verification.
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fkf_league.settings')
django.setup()

errors = []

def check(label, condition, detail=''):
    if condition:
        print(f'  ✓  {label}')
    else:
        msg = f'  ✗  {label}' + (f': {detail}' if detail else '')
        print(msg)
        errors.append(label)

print('\n── 1. New modules ──────────────────────────────────────────────────')
try:
    from fkf_league.permissions import (
        is_super_admin, is_league_admin, is_league_admin_or_manager,
        is_team_manager, is_referees_manager, is_any_admin,
    )
    check('fkf_league.permissions', True)
except Exception as e:
    check('fkf_league.permissions', False, str(e))

try:
    from fkf_league.constants import MatchStatus, TeamStatus, TransferStatus, ReportStatus
    check('fkf_league.constants', True)
except Exception as e:
    check('fkf_league.constants', False, str(e))

try:
    from fkf_league.context_processors import league_settings_context, site_info_context
    check('fkf_league.context_processors', True)
except Exception as e:
    check('fkf_league.context_processors', False, str(e))

try:
    from teams.utils import get_match_squad_data
    check('teams.utils', True)
except Exception as e:
    check('teams.utils', False, str(e))

try:
    from admin_dashboard.email import send_welcome_email, send_password_reset_email
    check('admin_dashboard.email', True)
except Exception as e:
    check('admin_dashboard.email', False, str(e))


print('\n── 2. Match model properties ───────────────────────────────────────')
from matches.models import Match, LeagueTable

m = Match()
m.status = 'completed'; m.home_score = 2; m.away_score = 1
check('Match.is_completed', m.is_completed)
check('Match.is_live (False)', not m.is_live)
check('Match.is_upcoming (False)', not m.is_upcoming)
check('Match.is_scheduled (False)', not m.is_scheduled)
check("Match.score_display '2 – 1'", m.score_display == '2 \u2013 1')

m2 = Match(); m2.status = 'scheduled'
check('Match.is_scheduled', m2.is_scheduled)
check('Match.is_upcoming (scheduled)', m2.is_upcoming)

# result_for via direct dict injection
m3 = Match()
m3.__dict__.update({'status': 'completed', 'home_score': 3, 'away_score': 0,
                    'home_team_id': 5, 'away_team_id': 9})
class FT:
    def __init__(self, pk): self.pk = pk
check('Match.result_for W', m3.result_for(FT(5)) == 'W')
check('Match.result_for L', m3.result_for(FT(9)) == 'L')
m3.__dict__['home_score'] = 1; m3.__dict__['away_score'] = 1
check('Match.result_for D', m3.result_for(FT(5)) == 'D')

# kickoff_datetime
from django.utils import timezone
import datetime
m4 = Match()
m4.__dict__['match_date'] = timezone.make_aware(datetime.datetime(2026, 8, 10, 0, 0))
m4.__dict__['kickoff_time'] = '15:30'
kdt = m4.kickoff_datetime
check('Match.kickoff_datetime', kdt.hour == 15 and kdt.minute == 30)

print('\n── 3. LeagueTable auto-calculate ───────────────────────────────────')
lt = LeagueTable()
lt.wins = 4; lt.draws = 2; lt.losses = 1
lt.goals_for = 10; lt.goals_against = 5
lt.calculate_points()
check('LeagueTable.calculate_points', lt.points == 14)


print('\n── 4. Team / Player model properties ──────────────────────────────')
from teams.models import Team, Player

t = Team(); t.status = 'approved'
check('Team.is_approved', t.is_approved)
check('Team.is_pending (False)', not t.is_pending)
t2 = Team(); t2.status = 'pending'
check('Team.is_pending', t2.is_pending)
check('Team.is_approved (False)', not t2.is_approved)

p = Player(); p.yellow_cards = 3; p.red_cards = 0
check("Player.card_summary '3Y / 0R'", p.card_summary == '3Y / 0R')

p.is_suspended = True; p.is_captain = False
check("Player.status_label 'Suspended'", p.status_label == 'Suspended')
p.is_suspended = False; p.is_captain = True
check("Player.status_label 'Captain'", p.status_label == 'Captain')
p.is_captain = False
check("Player.status_label 'Active'", p.status_label == 'Active')


print('\n── 5. Constants ─────────────────────────────────────────────────────')
check("MatchStatus.COMPLETED == 'completed'", MatchStatus.COMPLETED == 'completed')
check('MatchStatus.SCHEDULED in ACTIVE_STATUSES', MatchStatus.SCHEDULED in MatchStatus.ACTIVE_STATUSES)
check('MatchStatus.COMPLETED in INACTIVE_STATUSES', MatchStatus.COMPLETED in MatchStatus.INACTIVE_STATUSES)
check("TeamStatus.APPROVED == 'approved'", TeamStatus.APPROVED == 'approved')
check("TransferStatus.PENDING_PARENT == 'pending_parent'", TransferStatus.PENDING_PARENT == 'pending_parent')


print('\n── 6. Context processors ───────────────────────────────────────────')
from django.test import RequestFactory
req = RequestFactory().get('/')
result = league_settings_context(req)
check("league_settings_context has 'league_settings'", 'league_settings' in result)
site = site_info_context(req)
check("site_info_context has 'current_year'", 'current_year' in site)
check("site_info_context has 'site_name'", 'site_name' in site)


print('\n── 7. Permissions ───────────────────────────────────────────────────')
class FakeGroups:
    def __init__(self, names): self._names = names
    def filter(self, **kw):
        name_in = kw.get('name__in', [kw.get('name')])
        class R:
            def __init__(self, hit): self._hit = hit
            def exists(self): return self._hit
        if isinstance(name_in, str): name_in = [name_in]
        hit = any(n in self._names for n in (name_in or []))
        return R(hit)

def make_user(staff=False, super_=False, groups=()):
    return type('U', (), {
        'is_staff': staff, 'is_superuser': super_,
        'groups': FakeGroups(groups)
    })()

check('is_super_admin: superuser', is_super_admin(make_user(super_=True)))
check('is_super_admin: staff only → False', not is_super_admin(make_user(staff=True)))
check('is_league_admin: staff', is_league_admin(make_user(staff=True)))
check('is_league_admin: League Admin group', is_league_admin(make_user(groups=['League Admin'])))
check('is_team_manager', is_team_manager(make_user(groups=['Team Managers'])))
check('is_referees_manager: staff', is_referees_manager(make_user(staff=True)))
check('is_referees_manager: group', is_referees_manager(make_user(groups=['Referees Manager'])))


print('\n── 8. Django system check ──────────────────────────────────────────')
from django.core.management import call_command
from io import StringIO
out = StringIO()
try:
    call_command('check', stdout=out, stderr=out)
    output = out.getvalue()
    has_issues = 'System check identified' in output and 'no issues' not in output
    check('manage.py check — 0 issues', not has_issues, output.strip())
except SystemExit:
    check('manage.py check', False, 'exited with error')


print()
if errors:
    print(f'FAILED: {len(errors)} check(s): {", ".join(errors)}')
    sys.exit(1)
else:
    print('=' * 50)
    print('  ALL CHECKS PASSED — Python is now in the lead')
    print('=' * 50)
