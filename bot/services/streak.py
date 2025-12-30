"""
Streak calculation service for habits.

Rules:
- Daily: streak increases if today is done. If yesterday was not_done — reset. Skipped doesn't break streak.
- Weekly N: week is successful if done >= N. streak = consecutive successful weeks. Skipped doesn't count as done.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Sequence, Optional

from bot.models import HabitLog, LogStatus, ScheduleType


@dataclass
class HabitStats:
    """Statistics for a habit."""
    current_streak: int
    best_streak: int
    done_7_days: int
    done_30_days: int
    total_done: int


def calculate_daily_streak(logs: Sequence[HabitLog], today: date) -> tuple:
    """
    Calculate current and best streak for daily habit.
    
    Args:
        logs: List of habit logs (sorted by date)
        today: Current date in user's timezone
    
    Returns:
        (current_streak, best_streak)
    """
    if not logs:
        return 0, 0
    
    # Convert to dict for quick access
    log_by_date: Dict[date, LogStatus] = {}
    for log in logs:
        if log.log_date:
            log_by_date[log.log_date] = log.status
    
    current_streak = 0
    best_streak = 0
    streak = 0
    
    # Go from today backwards
    check_date = today
    
    # Check current streak
    while True:
        status = log_by_date.get(check_date)
        
        if status == LogStatus.DONE:
            streak += 1
            check_date -= timedelta(days=1)
        elif status == LogStatus.SKIPPED:
            # Skipped doesn't break streak, continue checking
            check_date -= timedelta(days=1)
        elif status == LogStatus.NOT_DONE:
            # Not done — reset
            break
        else:
            # No record — if not today, consider as not done
            if check_date < today:
                break
            # Today not marked yet — check yesterday
            check_date -= timedelta(days=1)
    
    current_streak = streak
    
    # Calculate best streak from all logs
    sorted_logs = sorted([l for l in logs if l.log_date], key=lambda x: x.log_date)
    streak = 0
    prev_date = None
    
    for log in sorted_logs:
        if log.status == LogStatus.DONE:
            if prev_date is None:
                streak = 1
            elif log.log_date == prev_date + timedelta(days=1):
                streak += 1
            elif log.log_date == prev_date:
                pass  # Same date
            else:
                # Check if skipped days were only skipped status
                gap_ok = True
                for i in range(1, (log.log_date - prev_date).days):
                    gap_date = prev_date + timedelta(days=i)
                    gap_status = log_by_date.get(gap_date)
                    if gap_status != LogStatus.SKIPPED:
                        gap_ok = False
                        break
                
                if gap_ok:
                    streak += 1
                else:
                    streak = 1
            
            prev_date = log.log_date
            best_streak = max(best_streak, streak)
        elif log.status == LogStatus.SKIPPED:
            # Skipped doesn't break series, but doesn't increase
            if prev_date is not None:
                prev_date = log.log_date
        else:  # NOT_DONE
            streak = 0
            prev_date = None
    
    return current_streak, best_streak


def calculate_weekly_streak(
    logs: Sequence[HabitLog],
    weekly_target: int,
    today: date,
) -> tuple:
    """
    Calculate current and best streak for weekly habit.
    
    Args:
        logs: List of habit logs
        weekly_target: How many times per week needed
        today: Current date in user's timezone
    
    Returns:
        (current_streak, best_streak)
    """
    if not logs:
        return 0, 0
    
    # Group by weeks (ISO week)
    weeks: Dict[tuple, List[LogStatus]] = {}
    
    for log in logs:
        if not log.log_date:
            continue
        week_key = (log.log_date.isocalendar()[0], log.log_date.isocalendar()[1])
        if week_key not in weeks:
            weeks[week_key] = []
        weeks[week_key].append(log.status)
    
    # Check if week is successful
    def is_week_success(statuses: List[LogStatus]) -> bool:
        done_count = sum(1 for s in statuses if s == LogStatus.DONE)
        return done_count >= weekly_target
    
    # Get all weeks in order
    sorted_weeks = sorted(weeks.keys())
    
    if not sorted_weeks:
        return 0, 0
    
    # Calculate current streak (go from current week backwards)
    current_streak = 0
    current_week = (today.isocalendar()[0], today.isocalendar()[1])
    
    check_week = current_week
    while check_week in weeks:
        if is_week_success(weeks[check_week]):
            current_streak += 1
            check_week = get_previous_week(check_week)
        else:
            break
    
    # Calculate best streak (consecutive successful weeks)
    best_streak = 0
    streak = 0
    
    for i, week in enumerate(sorted_weeks):
        if is_week_success(weeks[week]):
            if i == 0:
                streak = 1
            else:
                prev_week = sorted_weeks[i - 1]
                expected_prev = get_previous_week(week)
                if prev_week == expected_prev and is_week_success(weeks[prev_week]):
                    streak += 1
                else:
                    streak = 1
            best_streak = max(best_streak, streak)
        else:
            streak = 0
    
    return current_streak, best_streak


def get_previous_week(week: tuple) -> tuple:
    """Get previous ISO week."""
    year, week_num = week
    if week_num == 1:
        # Last week of previous year
        prev_year = year - 1
        last_day = date(prev_year, 12, 31)
        return (prev_year, last_day.isocalendar()[1])
    return (year, week_num - 1)


def get_next_week(week: tuple) -> tuple:
    """Get next ISO week."""
    year, week_num = week
    # Get last week of year
    last_day = date(year, 12, 31)
    max_week = last_day.isocalendar()[1]
    
    if week_num >= max_week:
        return (year + 1, 1)
    return (year, week_num + 1)


def get_habit_stats(
    logs: Sequence[HabitLog],
    schedule_type: ScheduleType,
    weekly_target: int,
    today: date,
) -> HabitStats:
    """
    Get full statistics for a habit.
    
    Args:
        logs: List of habit logs
        schedule_type: Type of schedule (daily/weekly)
        weekly_target: Target for weekly (ignored for daily)
        today: Current date in user's timezone
    
    Returns:
        HabitStats with current streak, best streak, done in 7/30 days
    """
    if schedule_type == ScheduleType.DAILY:
        current_streak, best_streak = calculate_daily_streak(logs, today)
    else:
        current_streak, best_streak = calculate_weekly_streak(logs, weekly_target, today)
    
    # Count done in 7 and 30 days
    done_7_days = 0
    done_30_days = 0
    total_done = 0
    
    for log in logs:
        if log.status == LogStatus.DONE:
            total_done += 1
            if log.log_date:
                days_ago = (today - log.log_date).days
                if days_ago <= 7:
                    done_7_days += 1
                if days_ago <= 30:
                    done_30_days += 1
    
    return HabitStats(
        current_streak=current_streak,
        best_streak=best_streak,
        done_7_days=done_7_days,
        done_30_days=done_30_days,
        total_done=total_done,
    )
