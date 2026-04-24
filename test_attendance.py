#!/usr/bin/env python
# -*- coding: utf-8 -*-

from database import init_db, get_session
from models import Employee, AttendanceRecord, AttendanceStatus
from employee_service import create_employee, delete_employee, get_employee, get_all_employees
from attendance_service import create_attendance_record, update_attendance_record, calculate_attendance_status
from statistics import calculate_employee_monthly_stats, get_attendance_summary
from validators import validate_time_format, validate_clock_times, validate_date
from datetime import date, time

def test_time_validators():
    print("=" * 60)
    print("测试1: 时间格式校验")
    print("=" * 60)
    
    test_cases = [
        ("09:30", True),
        ("13:00", True),
        ("18:00", True),
        ("25:00", False),
        ("09:61", False),
        ("9:30", True),
        ("09-30", False),
        ("abc", False),
    ]
    
    for time_str, expected in test_cases:
        is_valid, msg = validate_time_format(time_str)
        status = "✓ 通过" if is_valid == expected else "✗ 失败"
        print(f"  {time_str}: {status} - {msg}")
    
    print("\n测试2: 上班时间合法性校验")
    print("-" * 40)
    
    clock_in_cases = [
        ("08:59", False, "早于上班时间"),
        ("09:00", True, "正常上班时间"),
        ("10:00", True, "晚于上班时间但在有效范围内"),
        ("18:01", False, "晚于下班时间"),
    ]
    
    for time_str, expected, desc in clock_in_cases:
        is_valid, msg = validate_clock_times(time_str, None)
        status = "✓ 通过" if is_valid == expected else "✗ 失败"
        print(f"  {desc} ({time_str}): {status}")
    
    print("\n测试3: 下班时间合法性校验")
    print("-" * 40)
    
    clock_out_cases = [
        ("08:59", False, "早于上班时间"),
        ("12:00", True, "中午时间"),
        ("18:00", True, "正常下班时间"),
        ("18:01", False, "晚于下班时间"),
    ]
    
    for time_str, expected, desc in clock_out_cases:
        is_valid, msg = validate_clock_times(None, time_str)
        status = "✓ 通过" if is_valid == expected else "✗ 失败"
        print(f"  {desc} ({time_str}): {status}")
    
    print("\n测试4: 上下班时间关系校验")
    print("-" * 40)
    
    time_pairs = [
        ("09:00", "18:00", True, "正常上下班"),
        ("10:00", "17:00", True, "迟到且早退"),
        ("18:00", "09:00", False, "下班早于上班"),
        ("09:00", "09:00", False, "上下班时间相同"),
    ]
    
    for in_time, out_time, expected, desc in time_pairs:
        is_valid, msg = validate_clock_times(in_time, out_time)
        status = "✓ 通过" if is_valid == expected else "✗ 失败"
        print(f"  {desc} ({in_time}-{out_time}): {status}")

def test_attendance_status():
    print("\n" + "=" * 60)
    print("测试5: 考勤状态自动判定")
    print("=" * 60)
    
    test_cases = [
        ("09:00", "18:00", AttendanceStatus.NORMAL, "正常上下班"),
        ("09:10", "18:00", AttendanceStatus.NORMAL, "10分钟内迟到（宽限15分钟）"),
        ("09:20", "18:00", AttendanceStatus.LATE, "20分钟迟到（超过宽限）"),
        ("09:00", "17:50", AttendanceStatus.NORMAL, "10分钟内早退（宽限15分钟）"),
        ("09:00", "17:40", AttendanceStatus.EARLY_LEAVE, "20分钟早退（超过宽限）"),
        ("09:20", "17:40", AttendanceStatus.EARLY_LEAVE, "同时迟到早退"),
        (None, None, AttendanceStatus.ABSENT, "无打卡记录"),
        ("09:00", None, AttendanceStatus.NORMAL, "只有上班打卡"),
        (None, "18:00", AttendanceStatus.NORMAL, "只有下班打卡"),
    ]
    
    for in_time, out_time, expected_status, desc in test_cases:
        status = calculate_attendance_status(in_time, out_time)
        status_str = "✓ 通过" if status == expected_status else "✗ 失败"
        in_str = in_time if in_time else "无"
        out_str = out_time if out_time else "无"
        print(f"  {desc}: {status_str}")
        print(f"    上班: {in_str}, 下班: {out_str}")
        print(f"    判定结果: {status.value}, 期望: {expected_status.value}")

def test_database_operations():
    print("\n" + "=" * 60)
    print("测试6: 数据库操作测试")
    print("=" * 60)
    
    init_db()
    session = get_session()
    
    try:
        print("\n  步骤1: 创建测试员工")
        print("  " + "-" * 40)
        
        try:
            employee1 = create_employee(
                session,
                name="张三",
                employee_no="EMP001",
                department="技术部",
                position="工程师",
                email="zhangsan@example.com",
                phone="13800138001"
            )
            print(f"  ✓ 员工创建成功: {employee1.name} (工号: {employee1.employee_no})")
        except Exception as e:
            print(f"  ✗ 员工创建失败: {e}")
            employee1 = get_employee(session, 1)
        
        try:
            employee2 = create_employee(
                session,
                name="李四",
                employee_no="EMP002",
                department="技术部",
                position="设计师"
            )
            print(f"  ✓ 员工创建成功: {employee2.name} (工号: {employee2.employee_no})")
        except Exception as e:
            print(f"  员工创建失败或已存在: {e}")
            employee2 = get_employee(session, 2)
        
        print("\n  步骤2: 创建考勤记录")
        print("  " + "-" * 40)
        
        today = date.today()
        test_date1 = today
        test_date2 = date(today.year, today.month, today.day - 1) if today.day > 1 else today
        
        record1 = create_attendance_record(
            session,
            employee_id=employee1.id,
            date=test_date1,
            clock_in="09:00",
            clock_out="18:00",
            remark="正常出勤"
        )
        print(f"  ✓ 考勤记录创建成功: {record1.date} - 状态: {record1.status.value}")
        
        record2 = create_attendance_record(
            session,
            employee_id=employee1.id,
            date=test_date2,
            clock_in="09:30",
            clock_out="17:30",
            remark="迟到早退测试"
        )
        print(f"  ✓ 考勤记录创建成功: {record2.date} - 状态: {record2.status.value}")
        
        record3 = create_attendance_record(
            session,
            employee_id=employee2.id,
            date=test_date1,
            clock_in="08:50",
            clock_out="18:10"
        )
        print(f"  ✓ 考勤记录创建成功: {record3.date} - 状态: {record3.status.value}")
        
        print("\n  步骤3: 更新考勤记录")
        print("  " + "-" * 40)
        
        updated_record = update_attendance_record(
            session,
            record_id=record1.id,
            clock_out="17:40",
            remark="提前下班"
        )
        print(f"  ✓ 考勤记录更新成功: 新状态 - {updated_record.status.value}")
        
        print("\n  步骤4: 月度考勤统计")
        print("  " + "-" * 40)
        
        stats = calculate_employee_monthly_stats(
            session,
            employee_id=employee1.id,
            year=today.year,
            month=today.month
        )
        print(f"  员工: {stats['employee_name']}")
        print(f"  出勤天数: {stats['actual_attendance_days']}")
        print(f"  正常天数: {stats['normal_days']}")
        print(f"  迟到天数: {stats['late_days']}")
        print(f"  早退天数: {stats['early_leave_days']}")
        print(f"  缺勤天数: {stats['absent_days']}")
        print(f"  出勤率: {stats['attendance_rate']}%")
        
        summary = get_attendance_summary(session, today.year, today.month)
        print(f"\n  本月汇总:")
        print(f"  总记录数: {summary['total_records']}")
        for status, count in summary['status_counts'].items():
            print(f"  {status}: {count} 天")
        
        print("\n  步骤5: 测试无效时间录入")
        print("  " + "-" * 40)
        
        try:
            create_attendance_record(
                session,
                employee_id=employee1.id,
                date=test_date1,
                clock_in="25:00",
                clock_out="18:00"
            )
            print("  ✗ 应该拒绝无效时间")
        except ValueError as e:
            print(f"  ✓ 正确拒绝无效时间: {e}")
        
        try:
            create_attendance_record(
                session,
                employee_id=employee1.id,
                date=test_date1,
                clock_in="18:00",
                clock_out="09:00"
            )
            print("  ✗ 应该拒绝下班早于上班的时间")
        except ValueError as e:
            print(f"  ✓ 正确拒绝无效时间顺序: {e}")
        
        print("\n  步骤6: 测试员工删除（事务同步清理）")
        print("  " + "-" * 40)
        
        employees_before = get_all_employees(session)
        print(f"  删除前员工数量: {len(employees_before)}")
        
        attendance_before = session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == employee2.id
        ).count()
        print(f"  员工 {employee2.name} 的考勤记录数: {attendance_before}")
        
        result = delete_employee(session, employee2.id)
        print(f"  ✓ 删除结果: {result}")
        
        employees_after = get_all_employees(session)
        print(f"  删除后员工数量: {len(employees_after)}")
        
        attendance_after = session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == employee2.id
        ).count()
        print(f"  员工 {employee2.name} 的考勤记录数: {attendance_after}")
        
        if attendance_after == 0 and result["deleted_attendance_records"] == attendance_before:
            print("  ✓ 事务同步清理验证通过")
        else:
            print("  ✗ 事务同步清理验证失败")
        
        print("\n" + "=" * 60)
        print("所有测试完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"  测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

def main():
    print("\n" + "=" * 60)
    print("员工考勤系统功能测试")
    print("=" * 60)
    
    test_time_validators()
    test_attendance_status()
    test_database_operations()

if __name__ == "__main__":
    main()
