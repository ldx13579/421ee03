from datetime import time, datetime, timedelta
from models import AttendanceRecord, Employee, AttendanceStatus
from validators import validate_clock_times, parse_time, validate_date
from config import WORK_TIME_CONFIG

def time_to_minutes(t):
    return t.hour * 60 + t.minute

def calculate_attendance_status(clock_in_time, clock_out_time):
    config = WORK_TIME_CONFIG
    
    if clock_in_time is None and clock_out_time is None:
        return AttendanceStatus.ABSENT
    
    morning_start = parse_time(config["morning_start"])
    afternoon_end = parse_time(config["afternoon_end"])
    grace_late = config["lateness_grace_minutes"]
    grace_early = config["early_leave_grace_minutes"]
    
    if clock_in_time is not None:
        if isinstance(clock_in_time, str):
            clock_in_time = parse_time(clock_in_time)
    if clock_out_time is not None:
        if isinstance(clock_out_time, str):
            clock_out_time = parse_time(clock_out_time)
    
    is_late = False
    is_early_leave = False
    
    if clock_in_time is not None:
        in_minutes = time_to_minutes(clock_in_time)
        start_minutes = time_to_minutes(morning_start)
        if in_minutes > start_minutes + grace_late:
            is_late = True
    
    if clock_out_time is not None:
        out_minutes = time_to_minutes(clock_out_time)
        end_minutes = time_to_minutes(afternoon_end)
        if out_minutes < end_minutes - grace_early:
            is_early_leave = True
    
    if is_late and is_early_leave:
        return AttendanceStatus.EARLY_LEAVE
    elif is_late:
        return AttendanceStatus.LATE
    elif is_early_leave:
        return AttendanceStatus.EARLY_LEAVE
    else:
        return AttendanceStatus.NORMAL

def create_attendance_record(session, employee_id, date, clock_in=None, clock_out=None, remark=None):
    is_valid, date_obj = validate_date(date)
    if not is_valid:
        raise ValueError(date_obj)
    
    is_valid, msg = validate_clock_times(clock_in, clock_out)
    if not is_valid:
        raise ValueError(msg)
    
    existing = session.query(AttendanceRecord).filter(
        AttendanceRecord.employee_id == employee_id,
        AttendanceRecord.date == date_obj
    ).first()
    
    if existing:
        raise ValueError(f"员工 {employee_id} 在 {date_obj} 已有考勤记录")
    
    status = calculate_attendance_status(clock_in, clock_out)
    
    record = AttendanceRecord(
        employee_id=employee_id,
        date=date_obj,
        clock_in=parse_time(clock_in) if clock_in else None,
        clock_out=parse_time(clock_out) if clock_out else None,
        status=status,
        remark=remark
    )
    
    session.add(record)
    session.commit()
    session.refresh(record)
    
    return record

def update_attendance_record(session, record_id, clock_in=None, clock_out=None, remark=None):
    record = session.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
    
    if not record:
        raise ValueError(f"考勤记录 {record_id} 不存在")
    
    new_clock_in = clock_in if clock_in is not None else record.clock_in
    new_clock_out = clock_out if clock_out is not None else record.clock_out
    
    is_valid, msg = validate_clock_times(new_clock_in, new_clock_out)
    if not is_valid:
        raise ValueError(msg)
    
    if clock_in is not None:
        record.clock_in = parse_time(clock_in)
    if clock_out is not None:
        record.clock_out = parse_time(clock_out)
    if remark is not None:
        record.remark = remark
    
    record.status = calculate_attendance_status(record.clock_in, record.clock_out)
    
    session.commit()
    session.refresh(record)
    
    return record

def get_employee_attendance(session, employee_id, start_date=None, end_date=None):
    query = session.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id)
    
    if start_date:
        is_valid, start_date_obj = validate_date(start_date)
        if not is_valid:
            raise ValueError(start_date_obj)
        query = query.filter(AttendanceRecord.date >= start_date_obj)
    
    if end_date:
        is_valid, end_date_obj = validate_date(end_date)
        if not is_valid:
            raise ValueError(end_date_obj)
        query = query.filter(AttendanceRecord.date <= end_date_obj)
    
    return query.order_by(AttendanceRecord.date).all()
