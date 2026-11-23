"""Public team registration (step 1 of 2; payment is handled by the payments app)."""
from django.contrib import messages
from django.shortcuts import redirect, render

from ..forms import TeamRegistrationForm
from ..models import LeagueSettings, Team

REGISTRATION_FEE_KSH = 16000  # keep in sync with payments.views.payment_page


def team_registration(request):
    league = LeagueSettings.get_settings()
    if not league.team_registration_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Team Registration Closed',
            'message': 'Team registration is currently closed. Please check back later or '
                       'contact the league administrator for more information.',
            'deadline': league.team_registration_deadline,
        })

    form = TeamRegistrationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            team = form.save(commit=False)
            team.status = Team.Status.PENDING
            team.save()
            request.session['registration_success'] = True
            request.session['success_team_name'] = team.team_name
            request.session['success_team_code'] = team.team_code
            request.session['team_id_for_payment'] = team.id
            messages.success(request, f'Team "{team.team_name}" registered successfully! Please proceed to payment.')
            return redirect('payments:payment_page', team_id=team.id)
        messages.error(request, 'Please correct the errors below.')

    return render(request, 'teams/register_improved.html', {
        'form': form, 'registration_fee': REGISTRATION_FEE_KSH,
    })


def registration_success(request):
    success = request.session.pop('registration_success', False)
    team_name = request.session.pop('success_team_name', '')
    team_code = request.session.pop('success_team_code', '')
    if not success:
        messages.info(request, 'Please complete team registration first.')
        return redirect('teams:team_registration')
    return render(request, 'teams/registration_success.html', {
        'team_name': team_name, 'team_code': team_code, 'success': success,
    })
