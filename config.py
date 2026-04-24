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
