import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'attendance.db')}")

WORK_TIME_CONFIG = {
    "morning_start": "09:00",
    "morning_end": "12:00",
    "afternoon_start": "13:00",
    "afternoon_end": "18:00",
    "lateness_grace_minutes": 15,
    "early_leave_grace_minutes": 15,
}

LEAVE_CONFIG = {
    "leave_types": {
        "annual_leave": {"name": "年假", "paid": True},
        "sick_leave": {"name": "病假", "paid": True, "certificate_required": True},
        "personal_leave": {"name": "事假", "paid": False},
        "maternity_leave": {"name": "产假", "paid": True},
        "paternity_leave": {"name": "陪产假", "paid": True},
        "marriage_leave": {"name": "婚假", "paid": True},
        "compensatory_leave": {"name": "调休", "paid": True},
    },
    "approval_levels": ["team_leader", "department_manager", "hr"],
}

HOLIDAY_CONFIG = {
    2024: {
        "new_year": ["2024-01-01"],
        "spring_festival": ["2024-02-10", "2024-02-11", "2024-02-12", "2024-02-13", "2024-02-14", "2024-02-15", "2024-02-16", "2024-02-17"],
        "qingming": ["2024-04-04", "2024-04-05", "2024-04-06"],
        "labor_day": ["2024-05-01", "2024-05-02", "2024-05-03", "2024-05-04", "2024-05-05"],
        "dragon_boat": ["2024-06-08", "2024-06-09", "2024-06-10"],
        "mid_autumn": ["2024-09-15", "2024-09-16", "2024-09-17"],
        "national_day": ["2024-10-01", "2024-10-02", "2024-10-03", "2024-10-04", "2024-10-05", "2024-10-06", "2024-10-07"],
    },
    2025: {
        "new_year": ["2025-01-01"],
        "spring_festival": ["2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", "2025-02-01", "2025-02-02", "2025-02-03", "2025-02-04"],
        "qingming": ["2025-04-04", "2025-04-05", "2025-04-06"],
        "labor_day": ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05"],
        "dragon_boat": ["2025-05-31", "2025-06-01", "2025-06-02"],
        "mid_autumn": ["2025-10-06", "2025-10-07", "2025-10-08"],
        "national_day": ["2025-10-01", "2025-10-02", "2025-10-03", "2025-10-04", "2025-10-05", "2025-10-06", "2025-10-07"],
    },
    2026: {
        "new_year": ["2026-01-01"],
        "spring_festival": ["2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24"],
        "qingming": ["2026-04-05", "2026-04-06", "2026-04-07"],
        "labor_day": ["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05"],
        "dragon_boat": ["2026-06-19", "2026-06-20", "2026-06-21"],
        "mid_autumn": ["2026-09-25", "2026-09-26", "2026-09-27"],
        "national_day": ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07"],
    },
}

def is_legal_holiday(check_date):
    if isinstance(check_date, str):
        from datetime import datetime
        check_date = datetime.strptime(check_date, '%Y-%m-%d').date()
    
    year = check_date.year
    date_str = check_date.strftime('%Y-%m-%d')
    
    if year in HOLIDAY_CONFIG:
        for holiday_name, holiday_dates in HOLIDAY_CONFIG[year].items():
            if date_str in holiday_dates:
                return True, holiday_name
    
    return False, None

OVERTIME_CONFIG = {
    "weekday_overtime_rate": 1.5,
    "weekend_overtime_rate": 2.0,
    "holiday_overtime_rate": 3.0,
    "min_overtime_hours": 0.5,
    "max_daily_overtime_hours": 4,
    "max_monthly_overtime_hours": 36,
    "compensatory_leave_ratio": 1.0,
    "overtime_pay_basis": "hourly_wage",
}

NOTIFICATION_CONFIG = {
    "wechat_work": {
        "enabled": False,
        "webhook_url": "",
        "secret": "",
        "agent_id": "",
    },
    "email": {
        "enabled": False,
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "sender_email": "",
        "sender_password": "",
        "use_tls": True,
    },
    "alert_channels": ["wechat_work", "email"],
    "alert_time": "10:00",
}

REPORT_CONFIG = {
    "company_name": "示例科技有限公司",
    "company_logo": None,
    "report_title": "员工月度考勤报表",
    "output_dir": os.path.join(BASE_DIR, "reports"),
    "default_signature": "人力资源部",
}
