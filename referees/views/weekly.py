"""Weekly officials report (JSON + HTML shell) and Excel export — admins / Referees Manager only."""
from datetime import date, datetime, time, timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from fkf_league.permissions import is_any_admin
from matches.models import Match

from ._common import role_required

DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 366
FORMULA_PREFIXES = ('=', '+', '-', '@', chr(9), chr(13))

report_viewer_required = role_required(is_any_admin)


class BadRange(ValueError):
    pass


def _date_range(params) -> tuple[date, date]:
    start_s, end_s = params.get('start_date'), params.get('end_date')
    if start_s and end_s:
        try:
            start, end = date.fromisoformat(start_s), date.fromisoformat(end_s)
        except ValueError as exc:
            raise BadRange('Dates must be in YYYY-MM-DD format.') from exc
    else:
        end = timezone.localdate()
        start = end - timedelta(days=DEFAULT_RANGE_DAYS)
    if start > end:
        raise BadRange('start_date must be on or before end_date.')
    if (end - start).days > MAX_RANGE_DAYS:
        raise BadRange(f'Date range may not exceed {MAX_RANGE_DAYS} days.')
    return start, end


def _matches_between(start: date, end: date):
    return Match.objects.filter(
        match_date__gte=timezone.make_aware(datetime.combine(start, time.min)),
        match_date__lte=timezone.make_aware(datetime.combine(end, time.max)),
    ).select_related(
        'home_team', 'away_team', 'zone',
        'referee__user', 'assistant_referee_1__user', 'assistant_referee_2__user',
    ).order_by('match_date', 'kickoff_time')


def _official_name(official) -> str | None:
    if not official:
        return None
    if official.user_id and official.user.get_full_name():
        return official.user.get_full_name()
    return official.full_name


def _hhmm(kickoff) -> str:
    parts = str(kickoff or '').strip().split(':')
    return f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else ''


def _match_base(match) -> dict:
    home = match.home_team.team_name
    away = match.away_team.team_name
    return {
        'id': match.id,
        'date': match.match_date.isoformat(),
        'time': _hhmm(match.kickoff_time),
        'venue': match.venue or '',
        'zone': match.zone.name if match.zone_id else '',
        'teams': f"{home} vs {away}",
        'scores': {'home': match.home_score, 'away': match.away_score},
        'status': match.status,
    }


def _manager_report(matches, start, end, user) -> dict:
    rows, counts = [], {'fully_assigned': 0, 'partially_assigned': 0, 'unassigned': 0}
    needs = {'referees': 0, 'assistant_referee_1': 0, 'assistant_referee_2': 0}
    for m in matches:
        present = [m.referee_id, m.assistant_referee_1_id, m.assistant_referee_2_id]
        status = ('fully_assigned' if all(present)
                  else 'partially_assigned' if any(present) else 'unassigned')
        counts[status] += 1
        needs['referees'] += not m.referee_id
        needs['assistant_referee_1'] += not m.assistant_referee_1_id
        needs['assistant_referee_2'] += not m.assistant_referee_2_id
        rows.append({
            **_match_base(m),
            'home_team': {'id': m.home_team_id, 'name': m.home_team.team_name, 'code': m.home_team.team_code},
            'away_team': {'id': m.away_team_id, 'name': m.away_team.team_name, 'code': m.away_team.team_code},
            'assignment_status': status,
            'officials': {
                'referee': _official_name(m.referee),
                'assistant_referee_1': _official_name(m.assistant_referee_1),
                'assistant_referee_2': _official_name(m.assistant_referee_2),
            },
            'needs_attention': status != 'fully_assigned',
        })
    return {
        'report_type': 'manager_overview',
        'user_role': 'manager' if not user.is_staff else 'admin',
        'date_range': {'start': start.isoformat(), 'end': end.isoformat(), 'days': (end - start).days + 1},
        'summary': {
            'total_matches': len(rows),
            **counts,
            'officials_needed': {**needs, 'total': sum(needs.values())},
        },
        'matches': rows,
        'matches_needing_attention': [r for r in rows if r['needs_attention']],
    }


@report_viewer_required
@require_GET
def generate_weekly_report(request):
    """JSON officials overview for admins and the Referees Manager (feeds weekly_report_display)."""
    try:
        start, end = _date_range(request.GET)
    except BadRange as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse(_manager_report(_matches_between(start, end), start, end, request.user))


@report_viewer_required
def weekly_report_display(request):
    return render(request, 'referees/weekly_report_modern.html')


def _cell(value):
    """Neutralise spreadsheet formula injection in user-supplied text."""
    if isinstance(value, str) and value[:1] in FORMULA_PREFIXES:
        return f"'{value}"
    return value


def _vacant_or_name(official) -> str:
    """Only approved referees with an account are shown; anyone else is VACANT."""
    if not official or official.status != 'approved' or not official.user_id:
        return 'VACANT'
    return _official_name(official)


@report_viewer_required
@require_GET
def export_appointments_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    try:
        start, end = _date_range(request.GET)
    except BadRange as exc:
        return HttpResponse(str(exc), status=400, content_type='text/plain')

    wb = Workbook()
    ws = wb.active
    ws.title = "Match Officials Report"
    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.merge_cells('A1:H1')
    ws['A1'] = f"FKF Meru League - Match Officials Report ({start} to {end})"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    headers = ['Date', 'Time', 'Match', 'Venue', 'Zone', 'Referee', 'AR1', 'AR2']
    widths = [12, 10, 35, 25, 15, 20, 20, 20]
    for col, (header, width) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=3, column=col, value=header)
        cell.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF", size=12)
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
        ws.column_dimensions[cell.column_letter].width = width

    for row, m in enumerate(_matches_between(start, end), 4):
        values = [
            timezone.localtime(m.match_date).strftime('%Y-%m-%d'),
            m.kickoff_time or 'TBD',
            f"{m.home_team.team_name} vs {m.away_team.team_name}",
            m.venue or 'TBD',
            m.zone.name if m.zone_id else '',
            _vacant_or_name(m.referee),
            _vacant_or_name(m.assistant_referee_1),
            _vacant_or_name(m.assistant_referee_2),
        ]
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=_cell(value))
            cell.border = border

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Match_Officials_Report_{start}_{end}.xlsx"'
    wb.save(response)
    return response
