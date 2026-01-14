# Matchday Squad Management System - Quick Start Guide

## 🎯 **System Overview**

The Matchday Squad Management System automates the complete workflow from squad submission to in-match substitutions with intelligent validations and time-based controls.

---

## 📋 **User Roles & Access**

### 1. **Team Manager**
- **URL**: `/referees/matchday/squads/`
- **Can**:
  - View upcoming matches 2 hours before kick-off
  - Submit 25-player squads (11 starting + 14 subs)
  - Edit squads until match kick-off
  - View squad approval status

### 2. **Main Referee**
- **URL**: `/referees/matchday/referee/approvals/`
- **Can**:
  - View both teams' submitted squads
  - Approve individual players or entire squads
  - See real-time squad composition

### 3. **Fourth Official**
- **URL**: `/referees/matchday/fourth-official/{match_id}/`
- **Can**:
  - Effect substitutions (up to 5 per team)
  - Manage substitution opportunities (max 3, excluding halftime)
  - View current squad status

### 4. **Reserve Referee**
- **URL**: `/referees/matchday/fourth-official/{match_id}/`
- **Can**:
  - Everything Fourth Official can do
  - **PLUS**: Activate concussion substitute (6th sub)

---

## ⏱️ **Timeline**

```
T-2:00 hours ────> Squad submission window opens
                    ↓
T-1:30 hours ────> Referee can start approving
                    ↓
T-0:00 (Kick-off) ─> Squad LOCKS automatically
                    ↓
During Match ────> Substitutions managed by 4th Official/Reserve
```

---

## 🔐 **Validation Rules**

### Squad Composition:
- ✅ **Starting XI**: Exactly 11 players (must include 1+ GK)
- ✅ **Substitutes**: Exactly 14 players (must include 1+ GK)
- ✅ **Total**: 25 players
- ❌ No duplicate selections
- ❌ Suspended players automatically blocked

### Substitutions:
- ✅ Maximum 5 normal substitutions per team
- ✅ Maximum 3 substitution opportunities (halftime doesn't count)
- ✅ Additional concussion substitute (6th) - Reserve Referee only
- ✅ Player must be in starting XI to be substituted out
- ✅ Substitute must be on bench and not already on field

---

## 📝 **Step-by-Step Workflows**

### **Workflow 1: Team Manager Submits Squad**

1. Navigate to **Matchday Squads** (opens 2 hours before match)
2. Click **Submit Squad** for your match
3. Select **11 starting players** (left column):
   - Must include at least 1 goalkeeper
   - Select captain
   - Assign jersey numbers
4. Select **14 substitute players** (right column):
   - Must include at least 1 goalkeeper
   - Assign jersey numbers
5. Click **Submit Squad**
6. Squad status changes to **Submitted** (yellow badge)

### **Workflow 2: Referee Approves Squads**

1. Navigate to **Squad Approvals**
2. Click on the match to review
3. See both teams side-by-side
4. **Option A**: Check individual players and click **Approve Selected**
5. **Option B**: Click **Approve All** button for entire team
6. Squad status changes to **Approved** (green badge)

### **Workflow 3: Fourth Official Manages Substitutions**

1. Navigate to **Manage Substitutions** during match
2. View pending substitution requests
3. Click **Approve** to effect the substitution
4. System automatically:
   - Tracks substitution count (max 5 per team)
   - Records substitution opportunity
   - Prevents exceeding 3 opportunities
5. Substitution appears in **Completed Substitutions** section

### **Workflow 4: Reserve Referee Activates Concussion Sub**

1. Navigate to **Manage Substitutions** during match
2. Scroll to **Activate Concussion Substitute** section (red card)
3. Select:
   - Team (Home/Away)
   - Injured player (from starting XI)
   - Concussion substitute (from bench)
   - Minute of substitution
   - Medical notes
4. Click **Activate Concussion Substitute**
5. This is the **6th substitution** - doesn't count against the 5-sub limit

---

## 🚨 **Common Scenarios**

### **Scenario 1: Team tries to submit incomplete squad**
- **System**: Shows error message specifying what's missing
- **Action**: Complete missing selections and resubmit

### **Scenario 2: Team includes suspended player**
- **System**: Automatically removes suspended players from selection list
- **Action**: Select only eligible players

### **Scenario 3: Team tries to edit after kick-off**
- **System**: Squad is locked, edit button disabled
- **Action**: Contact referee manager for special circumstances

### **Scenario 4: Team reaches 5 substitutions**
- **System**: Disables normal substitution option
- **Reserve Referee**: Can still activate concussion substitute if needed

### **Scenario 5: Team uses all 3 substitution opportunities**
- **System**: Blocks further substitutions even if under 5 subs
- **Exception**: Concussion substitute (6th) can still be used

---

## 💡 **Tips & Best Practices**

### For Team Managers:
1. Submit squads as early as possible (opens 2 hours before)
2. Double-check jersey numbers match your team kit
3. Designate captain clearly
4. Ensure at least 1 goalkeeper in both starting XI and bench

### For Referees:
1. Review squads at least 1.5 hours before kick-off
2. Verify jersey numbers don't duplicate within a team
3. Check goalkeeper positions are correct
4. Approve both teams before match starts

### For Fourth Officials:
1. Track substitution opportunities carefully
2. Confirm with bench before approving requests
3. Note halftime substitutions don't count as opportunities
4. Communicate remaining subs to teams

### For Reserve Referees:
1. Monitor for potential concussion incidents
2. Document medical assessment before activating concussion sub
3. Remember: Concussion sub is additional (6th sub)
4. Inform main referee and both teams immediately

---

## 📊 **Status Indicators**

| Badge | Meaning | Action Required |
|-------|---------|----------------|
| 🔵 Pending | Squad not submitted | Team manager must submit |
| 🟡 Submitted | Awaiting approval | Referee must approve |
| 🟢 Approved | Ready for match | None - squad is locked at kick-off |
| 🔒 Locked | Match in progress | No edits allowed |

---

## 🔗 **Quick Navigation Links**

### Add to Team Dashboard:
```html
<a href="{% url 'referees:team_matchday_squad_list' %}" class="btn btn-primary">
    <i class="fas fa-users me-1"></i> Matchday Squads
</a>
```

### Add to Referee Dashboard:
```html
<a href="{% url 'referees:referee_squad_approval_list' %}" class="btn btn-warning">
    <i class="fas fa-clipboard-check me-1"></i> Squad Approvals
</a>
```

### Add to Match Officials Section:
```html
<!-- For 4th Official or Reserve Referee -->
<a href="{% url 'referees:fourth_official_substitutions' match.id %}" class="btn btn-info">
    <i class="fas fa-exchange-alt me-1"></i> Manage Substitutions
</a>
```

---

## 🆘 **Troubleshooting**

### Issue: "Squad submission button not visible"
- **Check**: Is it at least 2 hours before kick-off?
- **Fix**: Wait until submission window opens

### Issue: "Cannot select player"
- **Check**: Is player suspended?
- **Fix**: Choose different player - system blocks suspended players

### Issue: "Approval button disabled"
- **Check**: Has squad been submitted by team?
- **Fix**: Wait for team manager to submit squad

### Issue: "Cannot effect substitution"
- **Check**: Team at 5 subs? Used 3 opportunities?
- **Fix**: Check counters, may need concussion sub instead

### Issue: "Concussion sub button not available"
- **Check**: Are you the Reserve Referee?
- **Fix**: Only Reserve Referee has this authority

---

## 📧 **Support**

For technical issues or questions:
- Contact FKF Technical Team
- Email: tech@fkf.co.ke
- Phone: +254 XXX XXX XXX

---

**System Version**: 1.0  
**Last Updated**: {{ now|date:"F Y" }}  
**Status**: ✅ Production Ready
