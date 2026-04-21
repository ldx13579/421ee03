from datetime import datetime, date, timedelta
from calendar import monthrange
from sqlalchemy import func
from models import AttendanceRecord, Employee, AttendanceStatus
from validators import validate_date

def get_month_range(year, month):
    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    return start_date, end_date

def calculate_employee_monthly_stats(session, employee_id, year, month):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    start_date, end_date = get_month_range(year, month)
    
    records = session.query(AttendanceRecord).filter(
        AttendanceRecord.employee_id == employee_id,
        AttendanceRecord.date >= start_date,
        AttendanceRecord.date <= end_date
    ).all()
    
    total_work_days = len(records)
    normal_days = 0
    late_days = 0
    early_leave_days = 0
    absent_days = 0
    late_count = 0
    early_leave_count = 0
    
    for record in records:
        if record.status == AttendanceStatus.NORMAL:
            normal_days += 1
        elif record.status == AttendanceStatus.LATE:
            late_days += 1
            late_count += 1
        elif record.status == AttendanceStatus.EARLY_LEAVE:
            early_leave_days += 1
            early_leave_count += 1
        elif record.status == AttendanceStatus.ABSENT:
            absent_days += 1
    
    actual_attendance_days = total_work_days - absent_days
    
    attendance_rate = 0.0
    if total_work_days > 0:
        attendance_rate = round((actual_attendance_days / total_work_days) * 100, 2)
    
    return {
        "employee_id": employee_id,
        "employee_name": employee.name,
        "employee_no": employee.employee_no,
        "year": year,
        "month": month,
        "total_days": total_work_days,
        "actual_attendance_days": actual_attendance_days,
        "normal_days": normal_days,
        "late_days": late_days,
        "early_leave_days": early_leave_days,
        "absent_days": absent_days,
        "late_count": late_count,
        "early_leave_count": early_leave_count,
        "attendance_rate": attendance_rate
    }

def calculate_department_monthly_stats(session, department, year, month):
    employees = session.query(Employee).filter(Employee.department == department).all()
    
    if not employees:
        raise ValueError(f"部门 {department} 没有员工")
    
    stats_list = []
    for employee in employees:
        try:
            stats = calculate_employee_monthly_stats(session, employee.id, year, month)
            stats_list.append(stats)
        except Exception as e:
            continue
    
    total_employees = len(stats_list)
    total_late_count = sum(stat["late_count"] for stat in stats_list)
    total_early_leave_count = sum(stat["early_leave_count"] for stat in stats_list)
    avg_attendance_rate = round(sum(stat["attendance_rate"] for stat in stats_list) / total_employees, 2) if total_employees > 0 else 0.0
    
    return {
        "department": department,
        "year": year,
        "month": month,
        "total_employees": total_employees,
        "total_late_count": total_late_count,
        "total_early_leave_count": total_early_leave_count,
        "avg_attendance_rate": avg_attendance_rate,
        "employee_stats": stats_list
    }

def get_attendance_summary(session, year, month):
    start_date, end_date = get_month_range(year, month)
    
    total_records = session.query(func.count(AttendanceRecord.id)).filter(
        AttendanceRecord.date >= start_date,
        AttendanceRecord.date <= end_date
    ).scalar() or 0
    
    status_counts = session.query(
        AttendanceRecord.status,
        func.count(AttendanceRecord.id)
    ).filter(
        AttendanceRecord.date >= start_date,
        AttendanceRecord.date <= end_date
    ).group_by(AttendanceRecord.status).all()
    
    counts = {
        AttendanceStatus.NORMAL.value: 0,
        AttendanceStatus.LATE.value: 0,
        AttendanceStatus.EARLY_LEAVE.value: 0,
        AttendanceStatus.ABSENT.value: 0
    }
    
    for status, count in status_counts:
        if status:
            counts[status.value] = count
    
    return {
        "year": year,
        "month": month,
        "total_records": total_records,
        "status_counts": counts
    }
