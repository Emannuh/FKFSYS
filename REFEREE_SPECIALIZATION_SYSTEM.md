# Referee Specialization System

## Overview
The system now supports referee specialization during registration and ensures that only qualified referees can be appointed to specific roles.

## Specialization Types

### 1. **REFEREE**
Can be appointed as:
- Main Referee
- Reserve Referee
- VAR (Video Assistant Referee)
- AR2 (Assistant Referee 2) - if needed

### 2. **ASSISTANT REFEREE**
Can be appointed as:
- AR1 (Assistant Referee 1)
- AR2 (Assistant Referee 2)
- Fourth Official
- AVAR1 (Assistant VAR 1)
- Reserve Assistant Referee

### 3. **MATCH COMMISSIONER**
Can only be appointed as:
- Match Commissioner

## Special Rules

### AR2 Flexibility
AR2 position can be filled by either:
- Referees (REFEREE specialization)
- Assistant Referees (ASSISTANT_REFEREE specialization)

This provides flexibility in match official appointments.

## Registration Process

### During Registration
1. Referee fills in basic information (Name, Email, FKF Number, etc.)
2. **NEW:** Selects specialization from dropdown:
   - Referee
   - Assistant Referee
   - Match Commissioner
3. Specialization is optional during initial registration
4. Can be added/updated later in profile

### After Approval
- Referees can edit their profile to add or change specialization
- Specialization determines which appointment roles they're eligible for

## Appointment System

### Automatic Filtering
When appointing match officials, the system automatically:

1. **Filters by Specialization**
   - Main Referee field: Shows only REFEREE specialists
   - AR1 field: Shows only ASSISTANT_REFEREE specialists
   - AR2 field: Shows both REFEREE and ASSISTANT_REFEREE specialists
   - Commissioner field: Shows only MATCH_COMMISSIONER specialists

2. **Excludes Already-Appointed Referees**
   - Checks same round number
   - Checks overlapping time (±2 hours window)
   - Removes referees already appointed to other matches in that time slot
   - Ensures fair distribution across all matches

3. **Shows Only Available Referees**
   - Status = 'approved'
   - is_active = True
   - Not marked unavailable for that date
   - Not appointed to conflicting matches

### Backward Compatibility
- Referees without specialization set can be appointed to any role
- This ensures existing referees continue to function normally
- Encourages gradual adoption of specialization system

## Profile Management

### Referee Profile Page
Referees can:
- View their current specialization
- Edit specialization in profile settings
- Update other profile information
- Upload/change profile photo

### Admin Dashboard
Referees Manager can:
- View all referees with their specializations
- See appointment statistics by specialization
- Identify referees without specialization set

## Database Changes

### New Field: `Referee.specialization`
```python
specialization = models.CharField(
    max_length=30,
    choices=SPECIALIZATION_CHOICES,
    blank=True,
    null=True,
    verbose_name="Specialization"
)
```

### Migration Applied
- Migration: `0015_referee_specialization.py`
- Status: Applied ✅

## Benefits

1. **Role-Specific Appointments**
   - Right person for the right role
   - Professional match management

2. **Fair Distribution**
   - Prevents double-booking
   - Ensures all matches have officials
   - Balances workload across referees

3. **Clear Career Paths**
   - Referees know their specialization
   - Can focus on specific skills
   - Transparent progression opportunities

4. **System Integrity**
   - Validates appointments
   - Prevents conflicts
   - Maintains match quality standards

## Usage Examples

### Example 1: Appointing Main Referee
```
Match: Team A vs Team B
Round: 5
Date: 2026-01-20 15:00

When selecting Main Referee:
- System shows only referees with REFEREE specialization
- Excludes referees appointed to other Round 5 matches from 13:00-17:00
- Shows: John Doe, Jane Smith, Mike Johnson (all REFEREE specialists, available)
```

### Example 2: Appointing AR1
```
When selecting AR1:
- System shows only ASSISTANT_REFEREE specialists
- Excludes those already appointed in same time window
- Shows: Sarah Williams, Tom Brown (ASSISTANT_REFEREE specialists)
```

### Example 3: Appointing AR2 (Flexible)
```
When selecting AR2:
- System shows both REFEREE and ASSISTANT_REFEREE specialists
- Provides larger pool of candidates
- Shows: John Doe (REFEREE), Sarah Williams (ASSISTANT_REFEREE), etc.
```

## Testing Checklist

✅ Registration form shows specialization dropdown
✅ Profile page allows editing specialization
✅ Appointment form filters by specialization
✅ Already-appointed referees are excluded
✅ AR2 accepts both REFEREE and ASSISTANT_REFEREE
✅ Commissioner field shows only MATCH_COMMISSIONER
✅ Backward compatibility maintained
✅ Database migration applied successfully

## Future Enhancements

1. **Specialization Statistics**
   - Track appointments by specialization
   - Generate reports on referee utilization
   - Identify gaps in specialist availability

2. **Certification Levels**
   - Link specialization to certification levels
   - Require minimum qualifications for certain roles
   - Track training and skill development

3. **Automated Suggestions**
   - AI-powered referee recommendations
   - Consider experience, ratings, location
   - Optimize appointment efficiency

## Support & Troubleshooting

### Common Issues

**Q: Can't see any referees in appointment dropdown?**
A: Check if referees have the correct specialization set for that role.

**Q: Referee has wrong specialization?**
A: They can update it in their profile settings.

**Q: Need to appoint referee to multiple matches?**
A: System prevents double-booking. Ensure match times don't overlap.

**Q: AR2 showing both types of specialists?**
A: This is by design - AR2 can be filled by either REFEREE or ASSISTANT_REFEREE.

---

**Implementation Date:** January 14, 2026  
**Status:** Completed and Tested ✅
