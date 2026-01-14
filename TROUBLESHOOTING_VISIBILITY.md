# 🔧 MATCHDAY SQUAD SYSTEM - VISIBILITY TROUBLESHOOTING GUIDE

## ✅ Issues Fixed

### **Problem**: Couldn't see the new matchday squad functionalities

### **Root Cause**: User attribute mismatch
- The views were looking for `request.user.team_profile`
- But your system uses `request.user.managed_teams`

### **Solution Applied**: ✅ FIXED
Updated `referees/matchday_views.py` to use the correct attribute:

```python
# OLD CODE (INCORRECT):
try:
    team = request.user.team_profile
except AttributeError:
    messages.error(request, "You need to be associated with a team.")
    return redirect('dashboard')

# NEW CODE (CORRECT):
if hasattr(request.user, 'managed_teams'):
    team = request.user.managed_teams.first()
else:
    team = None

if not team:
    messages.error(request, "You need to be associated with a team to manage squads.")
    return redirect('dashboard')
```

---

## 🎯 How to Access the Features Now

### **For Team Managers:**

1. **Login** to your account
2. **Navigate** to your team dashboard
3. **Look for** the "Matchday Squad Management" card (blue header)
4. **Click** "View Matchday Squads"
5. **You'll see** all upcoming matches where you can submit squads

**Direct URL**: http://127.0.0.1:8000/referees/matchday/squads/

### **For Referees:**

1. **Login** to your referee account
2. **Navigate** to your referee dashboard
3. **Look for** the "Squad Approvals" button in the Quick Actions section (blue button)
4. **Click** "Squad Approvals"
5. **You'll see** matches with submitted squads awaiting your approval

**Direct URL**: http://127.0.0.1:8000/referees/matchday/referee/approvals/

---

## 🔍 Verification Steps

### **Step 1: Check if Dashboard Links are Visible**

#### **Team Dashboard** (templates/teams/dashboard.html):
```html
<!-- Should appear BEFORE the "Actions" card -->
<div class="card mb-4">
    <div class="card-header bg-primary text-white">
        <h5 class="mb-0"><i class="fas fa-users"></i> Matchday Squad Management</h5>
    </div>
    <div class="card-body">
        <p class="mb-3">Submit and manage your 25-player matchday squads...</p>
        <a href="{% url 'referees:team_matchday_squad_list' %}" class="btn btn-primary">
            <i class="fas fa-clipboard-list me-2"></i>View Matchday Squads
        </a>
    </div>
</div>
```

#### **Referee Dashboard** (templates/referees/dashboard.html):
```html
<!-- Should appear in Quick Actions section -->
<div class="btn-group" role="group">
    <a href="..." class="btn btn-success">Find Matches</a>
    <a href="..." class="btn btn-info">Fixtures</a>
    <a href="..." class="btn btn-warning">League Table</a>
    <a href="{% url 'referees:referee_squad_approval_list' %}" class="btn btn-primary">
        <i class="fas fa-clipboard-check me-2"></i>Squad Approvals
    </a>
</div>
```

### **Step 2: Test Direct Access**

Open these URLs in your browser:

1. **Team Squads**: http://127.0.0.1:8000/referees/matchday/squads/
2. **Referee Approvals**: http://127.0.0.1:8000/referees/matchday/referee/approvals/

**Expected Results**:
- If NOT logged in → Redirected to login page ✅
- If logged in as Team Manager → See upcoming matches ✅
- If logged in as Referee → See matches needing approval ✅

---

## 🐛 Common Issues & Solutions

### **Issue 1: "404 Page Not Found"**

**Symptoms**: Clicking the link shows "Page not found"

**Solution**:
```bash
# Check if URLs are properly configured
python manage.py show_urls | grep matchday

# You should see:
# /referees/matchday/squads/
# /referees/matchday/referee/approvals/
# etc.
```

### **Issue 2: "You need to be associated with a team"**

**Symptoms**: Error message when trying to access team squad management

**Possible Causes**:
1. User is not linked to any team
2. Team relationship not set up correctly

**Solution**:
```python
# Check in Django admin or shell:
python manage.py shell

>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='your_username')
>>> user.managed_teams.all()  # Should return teams
>>> # If empty, assign team:
>>> from teams.models import Team
>>> team = Team.objects.get(id=1)
>>> team.manager = user
>>> team.save()
```

### **Issue 3: "Server Error (500)"**

**Symptoms**: Page shows server error

**Solution**:
```bash
# Check server logs for detailed error
# Look at terminal where server is running

# Check for migration issues:
python manage.py migrate
python manage.py showmigrations referees
```

### **Issue 4: Links Not Appearing in Dashboard**

**Symptoms**: Dashboard looks the same as before

**Possible Causes**:
1. Browser cache
2. Server not restarted
3. Template not saved

**Solution**:
```bash
# 1. Hard refresh browser (Ctrl+F5 or Cmd+Shift+R)

# 2. Restart Django server:
# Press Ctrl+C in terminal, then:
python manage.py runserver

# 3. Verify template changes were saved:
# Check if files contain the new links:
# - templates/teams/dashboard.html
# - templates/referees/dashboard.html

# 4. Clear Django cache (if enabled):
python manage.py clear_cache  # If you have cache configured
```

### **Issue 5: "No upcoming matches"**

**Symptoms**: Squad page shows "No upcoming matches to display"

**This is NORMAL if**:
- No matches are scheduled for next 7 days
- Matches are more than 7 days away
- Matches are in the past

**Solution**: Create a test match
```python
python manage.py shell

>>> from matches.models import Match
>>> from teams.models import Team
>>> from datetime import datetime, timedelta
>>> 
>>> # Create a test match 3 hours from now
>>> home = Team.objects.first()
>>> away = Team.objects.last()
>>> 
>>> match = Match.objects.create(
...     home_team=home,
...     away_team=away,
...     match_date=datetime.now().date(),
...     kickoff_time=(datetime.now() + timedelta(hours=3)).time(),
...     venue="Test Stadium",
...     status='scheduled'
... )
```

---

## ✅ Verification Checklist

Run through this checklist to confirm everything is working:

- [ ] Server is running without errors
- [ ] Can access http://127.0.0.1:8000/
- [ ] Can login successfully
- [ ] Team dashboard shows "Matchday Squad Management" card
- [ ] Referee dashboard shows "Squad Approvals" button
- [ ] Clicking team squad link doesn't show 404
- [ ] Clicking referee approval link doesn't show 404
- [ ] No server errors in terminal

---

## 🚀 Server Status

**Current Status**: ✅ Server Running
- **URL**: http://127.0.0.1:8000/
- **Django Version**: 4.2.7
- **Python Version**: 3.13.5
- **Migrations**: All applied
- **System Check**: No issues

---

## 📞 Still Having Issues?

If you're still unable to see the features:

1. **Check User Role**:
   - Login as a user who is a TEAM MANAGER (has managed_teams)
   - Login as a user who is a REFEREE (has referee_profile)

2. **Check Browser Console** (F12):
   - Look for JavaScript errors
   - Check Network tab for failed requests

3. **Check Server Terminal**:
   - Look for any error messages
   - Check for 404 or 500 errors

4. **Verify Files**:
   ```bash
   # List matchday files
   dir templates\referees\matchday
   # Should show 5 .html files
   
   # Check views file exists
   dir referees\matchday_views.py
   # Should exist (455 lines)
   ```

---

## 🎯 Quick Test Commands

```bash
# 1. Check migrations applied
python manage.py showmigrations referees
# Should show [X] for 0013_matchdaysquad...

# 2. Check URLs registered
python manage.py show_urls | findstr matchday
# Should show 6 matchday URLs

# 3. Test view import
python manage.py shell
>>> from referees import matchday_views
>>> # No error = success

# 4. Check models
python manage.py shell
>>> from referees.models import MatchdaySquad
>>> MatchdaySquad.objects.count()
# Returns number (0 is OK if no squads yet)
```

---

**Last Updated**: January 12, 2026, 20:45  
**Status**: ✅ System Fixed and Running  
**Server**: http://127.0.0.1:8000/
