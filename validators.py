import re
from datetime import time, datetime, timedelta
from config import WORK_TIME_CONFIG

def validate_time_format(time_str):
    time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    if not re.match(time_pattern, time_str):
        return False, f"时间格式错误，应为HH:MM格式，如: 09:30"
    return True, "格式正确"

def parse_time(time_str):
    is_valid, msg = validate_time_format(time_str)
    if not is_valid:
        raise ValueError(msg)
    hours, minutes = map(int, time_str.split(':'))
    return time(hours, minutes)

def validate_clock_in_time(clock_in_time):
    if clock_in_time is None:
        return True, None
    
    if isinstance(clock_in_time, str):
        clock_in_time = parse_time(clock_in_time)
    
    config = WORK_TIME_CONFIG
    morning_start = parse_time(config["morning_start"])
    afternoon_end = parse_time(config["afternoon_end"])
    
    if clock_in_time > afternoon_end:
        return False, f"上班时间不能晚于下午下班时间 {config['afternoon_end']}"
    
    if clock_in_time < morning_start:
        return False, f"上班时间不能早于早上上班时间 {config['morning_start']}"
    
    return True, None

def validate_clock_out_time(clock_out_time):
    if clock_out_time is None:
        return True, None
    
    if isinstance(clock_out_time, str):
        clock_out_time = parse_time(clock_out_time)
    
    config = WORK_TIME_CONFIG
    morning_start = parse_time(config["morning_start"])
    afternoon_end = parse_time(config["afternoon_end"])
    
    if clock_out_time < morning_start:
        return False, f"下班时间不能早于早上上班时间 {config['morning_start']}"
    
    if clock_out_time > afternoon_end:
        return False, f"下班时间不能晚于下午下班时间 {config['afternoon_end']}"
    
    return True, None

def validate_clock_times(clock_in_time, clock_out_time):
    if clock_in_time is None and clock_out_time is None:
        return True, "无打卡记录"
    
    in_valid, in_msg = validate_clock_in_time(clock_in_time)
    if not in_valid:
        return False, in_msg
    
    out_valid, out_msg = validate_clock_out_time(clock_out_time)
    if not out_valid:
        return False, out_msg
    
    if clock_in_time is not None and clock_out_time is not None:
        if isinstance(clock_in_time, str):
            clock_in_time = parse_time(clock_in_time)
        if isinstance(clock_out_time, str):
            clock_out_time = parse_time(clock_out_time)
        
        if clock_out_time <= clock_in_time:
            return False, "下班时间必须晚于上班时间"
    
    return True, "时间校验通过"

def validate_date(date_val, allow_future=False):
    if date_val is None:
        return False, "日期不能为空"
    
    if isinstance(date_val, str):
        try:
            date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
        except ValueError:
            return False, "日期格式错误，应为YYYY-MM-DD格式，如: 2024-04-21"
    
    if not allow_future and date_val > datetime.now().date():
        return False, "日期不能是未来时间"
    
    return True, date_val


def validate_future_date(date_val, max_days_ahead=365):
    if date_val is None:
        return False, "日期不能为空"
    
    if isinstance(date_val, str):
        try:
            date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
        except ValueError:
            return False, "日期格式错误，应为YYYY-MM-DD格式，如: 2024-04-21"
    
    today = datetime.now().date()
    max_date = today + timedelta(days=max_days_ahead)
    
    if date_val > max_date:
        return False, f"日期不能超过 {max_days_ahead} 天后"
    
    return True, date_val
