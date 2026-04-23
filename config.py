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
