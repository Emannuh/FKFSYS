"""Matchday squads, squad-edit requests and in-match substitutions."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from matches.models import Match
from teams.models import Player

from .. import services
from ..models import (
    MatchdaySquad, MatchOfficials, SquadEditRequest, SquadPlayer, Substitution,
    SubstitutionOpportunity, SubstitutionRequest,
)
from ._common import current_referee

SQUAD_SUBMISSION_OPENS = timedelta(hours=2)
MIN_STARTERS, MAX_STARTERS, MAX_SUBS = 7, 11, 14
MAX_NORMAL_SUBS = 5
MAX_EDIT_REQUESTS_PER_MATCH = 2
MAX_PLAYERS_PER_EDIT_REQUEST = 2


def _managed_team(user):
    return user.managed_teams.first() if user.is_authenticated else None


def _team_for_match(request, match):
    """The requesting manager's team if it plays in ``match``; else (None, redirect)."""
    team = _managed_team(request.user)
    if team is None:
        messages.error(request, "You need to be associated with a team to manage squads.")
        return None, redirect('dashboard')
    if team.pk not in (match.home_team_id, match.away_team_id):
        messages.error(request, "Your team is not playing in this match.")
        return None, redirect('teams:team_manager_dashboard')
    return team, None


def _referee_or_redirect(request):
    referee = current_referee(request.user)
    if referee is None:
        messages.error(request, "You need to be a registered referee.")
    return referee


# ========== TEAM MANAGER ==========

@login_required
def team_matchday_squad_list(request):
    """Upcoming (7-day) matches for the manager's team and their squad status."""
    team = _managed_team(request.user)
    if team is None:
        messages.error(request, "You need to be associated with a team to manage squads.")
        return redirect('dashboard')

    now = timezone.now()
    today = timezone.localdate()
    matches = list(Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        match_date__date__gte=today,
        match_date__date__lte=today + timedelta(days=7),
        status='scheduled',
    ).select_related('home_team', 'away_team').order_by('match_date', 'kickoff_time'))

    squads = {
        s.match_id: s
        for s in MatchdaySquad.objects.filter(team=team, match__in=matches).annotate(
            starting_count=Count('squad_players', filter=Q(squad_players__is_starting=True)),
            subs_count=Count('squad_players', filter=Q(squad_players__is_starting=False)),
        )
    }
    matches_data = []
    for match in matches:
        squad = squads.get(match.pk)
        if squad is None:
            squad = MatchdaySquad.objects.create(match=match, team=team)
            squad.starting_count = squad.subs_count = 0
        squad.match = match
        submission_opens = match.kickoff_datetime - SQUAD_SUBMISSION_OPENS if match.kickoff_time else None
        matches_data.append({
            'match': match,
            'squad': squad,
            'can_submit': bool(submission_opens and now >= submission_opens and not squad.is_locked()),
            'submission_opens': submission_opens,
            'starting_count': squad.starting_count,
            'subs_count': squad.subs_count,
        })
    return render(request, 'referees/matchday/team_squad_list.html', {'team': team, 'matches_data': matches_data})


def _validate_squad_selection(starting_ids, sub_ids, eligible):
    """Return (starters, subs, error). Every id must be an eligible player of the team."""
    if len(starting_ids) < MIN_STARTERS:
        return [], [], f"You must select at least {MIN_STARTERS} starting players. You selected {len(starting_ids)}."
    if len(starting_ids) > MAX_STARTERS:
        return [], [], f"You cannot select more than {MAX_STARTERS} starting players. You selected {len(starting_ids)}."
    if len(sub_ids) > MAX_SUBS:
        return [], [], f"You cannot select more than {MAX_SUBS} substitute players. You selected {len(sub_ids)}."
    duplicates = set(starting_ids) & set(sub_ids)
    if duplicates or len(set(starting_ids)) != len(starting_ids) or len(set(sub_ids)) != len(sub_ids):
        names = ', '.join(p.full_name for p in eligible.filter(pk__in=[d for d in duplicates if d.isdigit()]))
        return [], [], f"Player(s) cannot be selected in both starting lineup AND substitutes: {names}"
    wanted = {i for i in set(starting_ids) | set(sub_ids)}
    if not all(i.isdigit() for i in wanted):
        return [], [], "Invalid player selection."
    players = {str(p.pk): p for p in eligible.filter(pk__in=wanted)}
    if len(players) != len(wanted):
        return [], [], "Only eligible (non-suspended) players from your team can be selected."
    starters = [players[i] for i in starting_ids]
    subs = [players[i] for i in sub_ids]
    if not any(p.position == 'GK' for p in starters):
        return [], [], "Starting lineup must include at least 1 goalkeeper."
    if not any(p.position == 'GK' for p in subs):
        return [], [], "Substitutes must include at least 1 goalkeeper."
    return starters, subs, None


@login_required
@require_http_methods(['GET', 'POST'])
def submit_matchday_squad(request, match_id):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    team, response = _team_for_match(request, match)
    if response:
        return response

    squad, _ = MatchdaySquad.objects.get_or_create(match=match, team=team)
    can_edit = squad.can_edit()
    can_view = can_edit or squad.status in (MatchdaySquad.Status.APPROVED, MatchdaySquad.Status.LOCKED)
    if not can_view:
        messages.error(request, "You don't have permission to view or edit this squad.")
        return redirect('teams:team_manager_dashboard')

    eligible = team.players.filter(is_suspended=False).order_by('position', 'jersey_number')
    context = {
        'match': match,
        'squad': squad,
        'team': team,
        'eligible_players': eligible,
        'selected_starting': list(squad.squad_players.filter(is_starting=True).values_list('player_id', flat=True)),
        'selected_subs': list(squad.squad_players.filter(is_starting=False).values_list('player_id', flat=True)),
        'can_edit': can_edit,
        'can_view': can_view,
        'can_request_edit': squad.can_request_edit(),
    }

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, "This squad can no longer be edited.")
            return redirect('referees:submit_matchday_squad', match_id=match.id)
        starters, subs, error = _validate_squad_selection(
            request.POST.getlist('starting_players'), request.POST.getlist('substitute_players'), eligible,
        )
        if error:
            messages.error(request, error)
            return render(request, 'referees/matchday/submit_squad.html', context)

        with transaction.atomic():
            squad.squad_players.all().delete()
            SquadPlayer.objects.bulk_create(
                [SquadPlayer(squad=squad, player=p, is_starting=True, position_order=i, jersey_number=p.jersey_number)
                 for i, p in enumerate(starters)]
                + [SquadPlayer(squad=squad, player=p, is_starting=False, jersey_number=p.jersey_number) for p in subs]
            )
            squad.status = MatchdaySquad.Status.SUBMITTED
            squad.submitted_at = timezone.now()
            squad.submitted_by = request.user
            squad.save()
        messages.success(request, "Matchday squad submitted successfully! Awaiting referee approval.")
        return redirect('referees:team_matchday_squad_list')

    return render(request, 'referees/matchday/submit_squad.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def team_request_squad_edit(request, match_id):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    team, response = _team_for_match(request, match)
    if response:
        return response
    squad = get_object_or_404(MatchdaySquad, match=match, team=team)

    if not squad.can_request_edit():
        if squad.is_locked():
            messages.error(request, "Cannot request edit - match has already started.")
        elif squad.status != MatchdaySquad.Status.APPROVED:
            messages.error(request, "Can only request edits for approved squads.")
        else:
            messages.error(request, "You already have a pending edit request.")
        return redirect('teams:team_manager_dashboard')

    context = {'match': match, 'squad': squad, 'team': team}
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        edit_ids = request.POST.getlist('edit_players')
        if SquadEditRequest.objects.filter(squad=squad).count() >= MAX_EDIT_REQUESTS_PER_MATCH:
            messages.error(
                request,
                f"You have reached the maximum of {MAX_EDIT_REQUESTS_PER_MATCH} squad edit requests for this match.",
            )
        elif len(edit_ids) > MAX_PLAYERS_PER_EDIT_REQUEST:
            messages.error(request, f"You can only request to edit up to {MAX_PLAYERS_PER_EDIT_REQUEST} players per request.")
        elif not reason:
            messages.error(request, "Please provide a reason for the edit request.")
        else:
            names = list(
                squad.squad_players.filter(player_id__in=[i for i in edit_ids if i.isdigit()])
                .values_list('player__first_name', 'player__last_name')
            )
            if names:
                reason += " | Players to edit: " + ", ".join(f"{first} {last}" for first, last in names)
            SquadEditRequest.objects.create(squad=squad, requested_by=request.user, reason=reason)
            messages.success(request, "Edit request submitted! Awaiting referee approval.")
            return redirect('teams:team_manager_dashboard')
    return render(request, 'referees/matchday/request_squad_edit.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def team_request_substitution(request, match_id):
    """Team manager requests substitutions (only after kick-off)."""
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    team, response = _team_for_match(request, match)
    if response:
        return response
    squad = get_object_or_404(
        MatchdaySquad, match=match, team=team,
        status__in=[MatchdaySquad.Status.APPROVED, MatchdaySquad.Status.LOCKED],
    )
    if timezone.now() < match.kickoff_datetime:
        messages.warning(request, "Substitution requests are only available after match kickoff.")
        return redirect('referees:team_matchday_squad_list')

    requests_qs = SubstitutionRequest.objects.filter(match=match, team=team).select_related('player_out', 'player_in')
    completed = requests_qs.filter(status=SubstitutionRequest.Status.COMPLETED)
    remaining_subs = MAX_NORMAL_SUBS - completed.filter(sub_type=SubstitutionRequest.SubType.NORMAL).count()

    if request.method == 'POST':
        outs = request.POST.getlist('player_out[]')
        ins = request.POST.getlist('player_in[]')
        minutes = request.POST.getlist('sub_minute[]')
        sub_type = request.POST.get('sub_type', SubstitutionRequest.SubType.NORMAL)
        # Concussion substitutes are activated by the referee, never requested by the team.
        if sub_type not in SubstitutionRequest.SubType.values or sub_type == SubstitutionRequest.SubType.CONCUSSION:
            sub_type = SubstitutionRequest.SubType.NORMAL
        notes = request.POST.get('notes', '').strip()
        squad_ids = dict(squad.squad_players.values_list('player_id', 'is_starting'))
        active = requests_qs.filter(status__in=[SubstitutionRequest.Status.PENDING, SubstitutionRequest.Status.COMPLETED])
        used = set(active.values_list('player_out_id', flat=True)) | set(active.values_list('player_in_id', flat=True))
        errors, created = [], 0

        for idx in range(min(max(remaining_subs, 0), len(outs))):
            n = idx + 1
            out_raw = outs[idx]
            in_raw = ins[idx] if idx < len(ins) else ''
            minute_raw = minutes[idx] if idx < len(minutes) else ''
            if not (out_raw.isdigit() and in_raw.isdigit() and minute_raw):
                errors.append(f"Substitution {n}: Please select both players and time.")
                continue
            out_id, in_id = int(out_raw), int(in_raw)
            if out_id == in_id:
                errors.append(f"Substitution {n}: Cannot substitute a player for themselves.")
            elif out_id not in squad_ids:
                errors.append(f"Substitution {n}: Player out is not in the matchday squad.")
            elif squad_ids.get(in_id, True):
                errors.append(f"Substitution {n}: Player in is not available as a substitute.")
            elif out_id in used or in_id in used:
                errors.append(f"Substitution {n}: One of these players has already been substituted.")
            elif not (minute_raw == 'HT' or (minute_raw.isdigit() and 1 <= int(minute_raw) <= 130)):
                errors.append(f"Substitution {n}: Invalid minute value.")
            else:
                SubstitutionRequest.objects.create(
                    match=match, squad=squad, team=team, player_out_id=out_id, player_in_id=in_id,
                    sub_type=sub_type, minute=45 if minute_raw == 'HT' else int(minute_raw),
                    status=SubstitutionRequest.Status.PENDING, requested_by=request.user, notes=notes,
                )
                used |= {out_id, in_id}
                created += 1

        for err in errors:
            messages.error(request, err)
        if created:
            messages.success(request, f"{created} substitution request(s) submitted. Awaiting referee approval.")
            return redirect('referees:team_request_substitution', match_id=match.id)

    context = {
        'match': match,
        'team': team,
        'squad': squad,
        'starting_players': squad.squad_players.filter(is_starting=True).select_related('player'),
        'substitute_players': squad.squad_players.filter(is_starting=False).select_related('player'),
        'pending_requests': requests_qs.filter(status=SubstitutionRequest.Status.PENDING),
        'completed_subs': completed,
        'remaining_subs': remaining_subs,
        'min_range': range(1, 121),
    }
    return render(request, 'referees/matchday/team_request_substitution.html', context)


# ========== MAIN REFEREE ==========

@login_required
def referee_squad_approval_list(request):
    referee = _referee_or_redirect(request)
    if referee is None:
        return redirect('referees:referee_dashboard')

    appointments = list(MatchOfficials.objects.filter(
        main_referee=referee, match__match_date__date__gte=timezone.localdate(), match__status='scheduled',
    ).select_related('match__home_team', 'match__away_team').order_by('match__match_date'))
    match_ids = [a.match_id for a in appointments]
    squads = {(s.match_id, s.team_id): s for s in MatchdaySquad.objects.filter(match_id__in=match_ids)}
    now = timezone.now()

    context = {
        'referee': referee,
        'matches_data': [
            {
                'match': a.match,
                'home_squad': squads.get((a.match_id, a.match.home_team_id)),
                'away_squad': squads.get((a.match_id, a.match.away_team_id)),
                'can_approve': now < a.match.kickoff_datetime,
            }
            for a in appointments
        ],
        'pending_edit_requests': SquadEditRequest.objects.filter(
            squad__match_id__in=match_ids, status=SquadEditRequest.Status.PENDING,
        ).select_related('squad__match', 'squad__team', 'requested_by'),
        'approved_count': SquadEditRequest.objects.filter(
            reviewed_by=referee, status=SquadEditRequest.Status.APPROVED,
        ).count(),
    }
    return render(request, 'referees/matchday/referee_approval_list.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def approve_matchday_squads(request, match_id):
    """Main referee approves one or both teams' squads."""
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    referee = _referee_or_redirect(request)
    if referee is None:
        return redirect('referees:referee_dashboard')
    if not MatchOfficials.objects.filter(match=match, main_referee=referee).exists():
        messages.error(request, "You are not the main referee for this match.")
        return redirect('referees:referee_dashboard')

    home_squad = get_object_or_404(MatchdaySquad, match=match, team=match.home_team)
    away_squad = get_object_or_404(MatchdaySquad, match=match, team=match.away_team)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve_team':
            squad = {'home': home_squad, 'away': away_squad}.get(request.POST.get('team'))
            if squad is None:
                messages.error(request, "Invalid team selection.")
            elif services.approve_squad(squad, referee):
                messages.success(request, f"{squad.team.team_name}'s squad has been approved and match report populated!")
            else:
                messages.warning(request, f"{squad.team.team_name}'s squad is not ready for approval.")
            return redirect('referees:approve_matchday_squads', match_id=match.id)
        if action == 'approve_both':
            approved = sum(services.approve_squad(s, referee) for s in (home_squad, away_squad))
            if approved:
                messages.success(request, f"{approved} team(s) approved and match report populated!")
            else:
                messages.warning(request, "No teams ready for approval.")
            return redirect('referees:referee_squad_approval_list')
        messages.error(request, "Unknown action.")
        return redirect('referees:approve_matchday_squads', match_id=match.id)

    for squad in (home_squad, away_squad):
        if squad.status != MatchdaySquad.Status.SUBMITTED:
            messages.warning(request, f"{squad.team.team_name} has not submitted their squad yet.")

    context = {
        'match': match,
        'referee': referee,
        'home_squad': home_squad,
        'away_squad': away_squad,
        'home_starting': home_squad.get_starting_eleven().select_related('player'),
        'home_subs': home_squad.get_substitutes().select_related('player'),
        'away_starting': away_squad.get_starting_eleven().select_related('player'),
        'away_subs': away_squad.get_substitutes().select_related('player'),
    }
    return render(request, 'referees/matchday/referee_approve_squads.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def referee_review_squad_edit_requests(request):
    """Main referee reviews pending squad-edit requests for the matches they referee."""
    referee = _referee_or_redirect(request)
    if referee is None:
        return redirect('referees:referee_dashboard')

    match_ids = MatchOfficials.objects.filter(main_referee=referee, match__status='scheduled').values('match_id')
    pending = SquadEditRequest.objects.filter(
        squad__match_id__in=match_ids, status=SquadEditRequest.Status.PENDING,
    ).select_related('squad__match', 'squad__team', 'requested_by')

    if request.method == 'POST':
        request_id = request.POST.get('request_id', '')
        edit_request = get_object_or_404(pending, id=int(request_id) if request_id.isdigit() else 0)
        action = request.POST.get('action')
        notes = request.POST.get('notes', '').strip()
        if action == 'approve':
            with transaction.atomic():
                edit_request.approve_request(referee, notes)
            messages.success(request, f"Edit request approved for {edit_request.squad.team.team_name}.")
        elif action == 'decline':
            edit_request.decline_request(referee, notes)
            messages.success(request, f"Edit request declined for {edit_request.squad.team.team_name}.")
        else:
            messages.error(request, "Unknown action.")
        return redirect('referees:referee_review_edit_requests')

    context = {
        'referee': referee,
        'pending_requests': pending,
        'approved_count': SquadEditRequest.objects.filter(
            reviewed_by=referee, status=SquadEditRequest.Status.APPROVED,
        ).count(),
    }
    return render(request, 'referees/matchday/referee_review_edit_requests.html', context)


# ========== RESERVE REFEREE / FOURTH OFFICIAL ==========

def _sub_officials(match, referee):
    """MatchOfficials row if ``referee`` is main, fourth or reserve referee for ``match``."""
    return MatchOfficials.objects.filter(match=match).filter(
        Q(main_referee=referee) | Q(fourth_official=referee) | Q(reserve_referee=referee)
    ).first()


def _record_substitution(match, sub_request, minute: int) -> None:
    """SubstitutionOpportunity bookkeeping plus the match-report Substitution row."""
    is_halftime = 45 <= minute <= 60
    opportunity = SubstitutionOpportunity.objects.filter(match=match, team=sub_request.team, minute=minute).first()
    if opportunity is None:
        if is_halftime:
            number = 0
        else:
            number = SubstitutionOpportunity.objects.filter(
                match=match, team=sub_request.team, is_halftime=False,
            ).values('minute').distinct().count() + 1
        opportunity = SubstitutionOpportunity.objects.create(
            match=match, team=sub_request.team, minute=minute, opportunity_number=number, is_halftime=is_halftime,
        )
    opportunity.substitutions.add(sub_request)
    Substitution.objects.create(
        match=match, team=sub_request.team, minute=minute,
        player_out=sub_request.player_out, player_in=sub_request.player_in,
        jersey_out=sub_request.player_out.jersey_number, jersey_in=sub_request.player_in.jersey_number,
    )


def _squad_json(squad) -> dict:
    if not squad:
        return {'starting': [], 'subs': []}
    rows = list(squad.squad_players.select_related('player'))

    def entry(sp):
        return {'id': sp.player_id, 'jersey': sp.jersey_number, 'name': sp.player.full_name}

    return {
        'starting': [entry(sp) for sp in rows if sp.is_starting],
        'subs': [entry(sp) for sp in rows if not sp.is_starting],
    }


def _valid_minute(raw: str) -> int | None:
    return int(raw) if raw.isdigit() and 1 <= int(raw) <= 130 else None


@login_required
@require_http_methods(['GET', 'POST'])
def reserve_referee_substitutions(request, match_id):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    referee = _referee_or_redirect(request)
    if referee is None:
        return redirect('referees:referee_dashboard')
    appointment = _sub_officials(match, referee)
    if appointment is None:
        messages.error(request, "You are not assigned to this match as an official.")
        return redirect('referees:referee_dashboard')

    if request.method == 'POST':
        if request.POST.get('action') == 'effect_substitution':
            request_id = request.POST.get('request_id', '')
            sub_request = get_object_or_404(
                SubstitutionRequest.objects.select_related('player_out', 'player_in', 'team'),
                id=int(request_id) if request_id.isdigit() else 0,
                match=match, status=SubstitutionRequest.Status.PENDING,
            )
            minute = _valid_minute(request.POST.get('minute', ''))
            if minute is None:
                messages.error(request, "Please specify a valid minute for the substitution.")
            else:
                with transaction.atomic():
                    sub_request.minute = minute
                    sub_request.status = SubstitutionRequest.Status.COMPLETED
                    sub_request.effected_at = timezone.now()
                    sub_request.effected_by = referee
                    sub_request.save()
                    _record_substitution(match, sub_request, minute)
                messages.success(
                    request,
                    f"Substitution completed: {sub_request.player_out.full_name} → {sub_request.player_in.full_name}",
                )
        return redirect('referees:reserve_referee_substitutions', match_id=match.id)

    home_squad = MatchdaySquad.objects.filter(match=match, team=match.home_team).first()
    away_squad = MatchdaySquad.objects.filter(match=match, team=match.away_team).first()
    subs = SubstitutionRequest.objects.filter(match=match).select_related('player_out', 'player_in', 'team')
    completed = subs.filter(status=SubstitutionRequest.Status.COMPLETED)
    pending = subs.filter(status=SubstitutionRequest.Status.PENDING).order_by('-requested_at')
    home_used = completed.filter(team=match.home_team).count()
    away_used = completed.filter(team=match.away_team).count()
    is_main = appointment.main_referee_id == referee.pk
    is_reserve = referee.pk in (appointment.fourth_official_id, appointment.reserve_referee_id)

    context = {
        'match': match,
        'referee': referee,
        'is_main_referee': is_main,
        'is_reserve_referee': is_reserve,
        'can_approve_subs': is_main or is_reserve,
        'home_squad': home_squad,
        'away_squad': away_squad,
        'home_squad_data': _squad_json(home_squad),
        'away_squad_data': _squad_json(away_squad),
        'home_requests': pending.filter(team=match.home_team),
        'away_requests': pending.filter(team=match.away_team),
        'home_opportunities': home_used,
        'away_opportunities': away_used,
        'home_opportunities_used': home_used,
        'away_opportunities_used': away_used,
        'home_progress_percentage': min(home_used * 33.33, 100),
        'away_progress_percentage': min(away_used * 33.33, 100),
        'completed_subs': completed.order_by('minute'),
        'home_subs_count': home_used,
        'away_subs_count': away_used,
        'home_concussion_sub': completed.filter(team=match.home_team, sub_type='concussion').exists(),
        'away_concussion_sub': completed.filter(team=match.away_team, sub_type='concussion').exists(),
    }
    return render(request, 'referees/matchday/reserve_referee_subs.html', context)


@login_required
@require_POST
def activate_concussion_substitute(request, match_id):
    """Main/fourth/reserve referee activates the concussion substitute (6th sub)."""
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    back = redirect('referees:reserve_referee_substitutions', match_id=match.id)
    referee = current_referee(request.user)
    if referee is None or _sub_officials(match, referee) is None:
        messages.error(request, 'You are not authorized to activate concussion substitutes for this match.')
        return redirect('referees:referee_dashboard')

    team_id, out_id, in_id = (request.POST.get(k, '') for k in ('team_id', 'player_out_id', 'player_in_id'))
    minute = _valid_minute(request.POST.get('minute', ''))
    if not (team_id.isdigit() and out_id.isdigit() and in_id.isdigit()) or minute is None:
        messages.error(request, 'All fields are required.')
        return back
    team_id = int(team_id)
    if team_id not in (match.home_team_id, match.away_team_id):
        messages.error(request, 'Invalid team selection.')
        return back
    squad = MatchdaySquad.objects.filter(match=match, team_id=team_id).first()
    player_out = Player.objects.filter(pk=out_id, team_id=team_id).first()
    player_in = Player.objects.filter(pk=in_id, team_id=team_id).first()
    if squad is None or player_out is None or player_in is None:
        messages.error(request, 'Invalid team or player selection.')
        return back

    sub_request = SubstitutionRequest(
        match=match, squad=squad, team_id=team_id, player_out=player_out, player_in=player_in,
        minute=minute, sub_type=SubstitutionRequest.SubType.CONCUSSION,
        status=SubstitutionRequest.Status.COMPLETED, requested_by=request.user,
        effected_at=timezone.now(), effected_by=referee,
        notes=request.POST.get('notes', '').strip() or 'Concussion substitute activated by referee',
    )
    try:
        sub_request.full_clean()  # squad membership + one concussion sub per team
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)
        return back
    with transaction.atomic():
        sub_request.save()
        Substitution.objects.create(
            match=match, team_id=team_id, minute=minute, player_out=player_out, player_in=player_in,
            jersey_out=player_out.jersey_number, jersey_in=player_in.jersey_number,
        )
    messages.success(request, f'Concussion substitute activated: {player_out.full_name} → {player_in.full_name}')
    return back
