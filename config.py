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
    "default_annual_leave_days": 10,
    "max_carry_over_days": 5,
    "sick_leave_require_certificate_days": 3,
    "approval_levels": {
        "1-3": "direct_supervisor",
        "4-7": "department_manager",
        "8+": "hr_director"
    },
    "auto_approve": False,
    "notify_approver_on_submit": True,
}

HR_CONFIG = {
    "hr_department": "人力资源部",
    "default_hr_employee_no": "HR001",
    "auto_detect_abnormal": True,
    "abnormal_check_time": "10:00",
    "notify_hr_on_abnormal": True,
    "notify_supervisor_on_abnormal": True,
    "notify_employee_on_abnormal": True,
}

OVERTIME_CONFIG = {
    "weekday_multiplier": 1.5,
    "weekend_multiplier": 2.0,
    "holiday_multiplier": 3.0,
    "default_hourly_rate": 50.0,
    "min_overtime_hours": 0.5,
    "max_daily_overtime_hours": 12.0,
    "settlement_options": ["TIME_OFF", "OVERTIME_PAY"],
    "time_off_conversion_rate": 1.0,
}

NOTIFICATION_CONFIG = {
    "enabled": True,
    "channels": {
        "WECHAT": {
            "enabled": True,
            "corp_id": os.environ.get("WECHAT_CORP_ID", ""),
            "agent_id": os.environ.get("WECHAT_AGENT_ID", ""),
            "secret": os.environ.get("WECHAT_SECRET", ""),
        },
        "EMAIL": {
            "enabled": True,
            "smtp_server": os.environ.get("EMAIL_SMTP_SERVER", "smtp.example.com"),
            "smtp_port": int(os.environ.get("EMAIL_SMTP_PORT", 587)),
            "sender_email": os.environ.get("EMAIL_SENDER", "noreply@example.com"),
            "sender_password": os.environ.get("EMAIL_PASSWORD", ""),
            "use_tls": True,
        },
        "SMS": {
            "enabled": False,
            "api_key": os.environ.get("SMS_API_KEY", ""),
            "api_secret": os.environ.get("SMS_API_SECRET", ""),
        }
    },
    "attendance_abnormal_notify": {
        "enabled": True,
        "notify_supervisor": True,
        "notify_hr": True,
        "notify_types": ["LATE", "EARLY_LEAVE", "ABSENT"],
        "time_window_minutes": 30,
    }
}

REPORT_CONFIG = {
    "output_dir": os.path.join(BASE_DIR, "reports"),
    "company_name": "某某科技有限公司",
    "company_address": "北京市朝阳区某某路88号",
    "company_phone": "010-88888888",
    "signature_name": "人力资源部",
    "signature_title": "人事主管",
    "report_title": "员工考勤月度报表",
    "include_charts": True,
    "include_signature": True,
    "watermark_text": "内部文件 - 仅供薪资核算使用",
}
