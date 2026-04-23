#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from models import Base, Employee, AttendanceRecord, AttendanceStatus
from employee_service import create_employee, delete_employee, get_employee
from attendance_service import create_attendance_record, update_attendance_record

def get_test_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session(), engine

def test_duplicate_prevention():
    print("\n" + "=" * 60)
    print("测试1: 防止重复插入考勤记录")
    print("=" * 60)
    
    session, engine = get_test_session()
    
    try:
        print("\n  步骤1: 创建测试员工")
        employee = create_employee(
            session,
            name="测试员工",
            employee_no="TEST001",
            department="测试部"
        )
        print(f"  ✓ 员工创建成功: {employee.name}")
        
        test_date = date.today()
        
        print("\n  步骤2: 第一次插入考勤记录")
        record1 = create_attendance_record(
            session,
            employee_id=employee.id,
            date=test_date,
            clock_in="09:00",
            clock_out="18:00"
        )
        print(f"  ✓ 第一次插入成功: 状态={record1.status.value}")
        
        print("\n  步骤3: 尝试重复插入同一天的考勤记录")
        try:
            create_attendance_record(
                session,
                employee_id=employee.id,
                date=test_date,
                clock_in="10:00",
                clock_out="17:00"
            )
            print("  ✗ 失败: 应该拒绝重复插入")
            return False
        except ValueError as e:
            print(f"  ✓ 正确拒绝重复插入: {e}")
        
        print("\n  步骤4: 验证数据库中只有一条记录")
        count = session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == employee.id,
            AttendanceRecord.date == test_date
        ).count()
        
        if count == 1:
            print(f"  ✓ 验证通过: 只有 {count} 条记录")
        else:
            print(f"  ✗ 验证失败: 有 {count} 条记录（期望1条）")
            return False
        
        print("\n  步骤5: 测试唯一约束（模拟并发场景）")
        try:
            Session2 = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            new_session = Session2()
            duplicate_record = AttendanceRecord(
                employee_id=employee.id,
                date=test_date,
                clock_in=None,
                clock_out=None,
                status=AttendanceStatus.ABSENT
            )
            new_session.add(duplicate_record)
            new_session.commit()
            new_session.close()
            print("  ✗ 失败: 唯一约束应该阻止重复插入")
            return False
        except IntegrityError as e:
            print(f"  ✓ 数据库唯一约束正确阻止重复插入")
        
        return True
        
    except Exception as e:
        print(f"  测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def test_status_recalculation_on_update():
    print("\n" + "=" * 60)
    print("测试2: 更新考勤记录时状态重新计算")
    print("=" * 60)
    
    session, engine = get_test_session()
    
    try:
        print("\n  步骤1: 创建测试员工和初始考勤记录")
        employee = create_employee(
            session,
            name="状态测试员工",
            employee_no="STATUS001",
            department="测试部"
        )
        
        test_date = date.today()
        
        print("\n  步骤2: 创建正常出勤记录")
        record = create_attendance_record(
            session,
            employee_id=employee.id,
            date=test_date,
            clock_in="09:00",
            clock_out="18:00",
            remark="正常出勤"
        )
        print(f"  初始状态: {record.status.value}")
        assert record.status == AttendanceStatus.NORMAL, f"期望正常，实际: {record.status.value}"
        print("  ✓ 初始状态正确: 正常")
        
        print("\n  步骤3: 只更新下班时间为早退时间")
        updated_record = update_attendance_record(
            session,
            record_id=record.id,
            clock_out="17:30",
            remark="提前30分钟下班"
        )
        print(f"  更新后下班时间: 17:30")
        print(f"  更新后状态: {updated_record.status.value}")
        
        if updated_record.status == AttendanceStatus.EARLY_LEAVE:
            print("  ✓ 状态正确重新计算: 早退")
        else:
            print(f"  ✗ 状态未正确重新计算: 期望早退，实际 {updated_record.status.value}")
            return False
        
        print("\n  步骤4: 只更新上班时间为迟到时间")
        updated_record2 = update_attendance_record(
            session,
            record_id=record.id,
            clock_in="09:30",
            remark="迟到30分钟+早退"
        )
        print(f"  更新后上班时间: 09:30")
        print(f"  更新后状态: {updated_record2.status.value}")
        
        if updated_record2.status == AttendanceStatus.EARLY_LEAVE:
            print("  ✓ 状态正确重新计算: 同时迟到早退（按早退处理）")
        else:
            print(f"  ✗ 状态未正确重新计算: 期望早退，实际 {updated_record2.status.value}")
            return False
        
        print("\n  步骤5: 只更新备注，验证状态保持不变")
        session.refresh(updated_record2)
        original_status = updated_record2.status
        
        updated_record3 = update_attendance_record(
            session,
            record_id=record.id,
            remark="只更新备注"
        )
        print(f"  只更新备注后状态: {updated_record3.status.value}")
        
        if updated_record3.status == original_status:
            print("  ✓ 只更新备注时状态保持不变")
        else:
            print(f"  ✗ 状态意外改变: 期望 {original_status.value}，实际 {updated_record3.status.value}")
            return False
        
        print("\n  步骤6: 恢复为正常时间，验证状态恢复")
        updated_record4 = update_attendance_record(
            session,
            record_id=record.id,
            clock_in="09:00",
            clock_out="18:00",
            remark="恢复正常"
        )
        print(f"  恢复正常时间后状态: {updated_record4.status.value}")
        
        if updated_record4.status == AttendanceStatus.NORMAL:
            print("  ✓ 状态正确恢复为正常")
        else:
            print(f"  ✗ 状态未正确恢复: 期望正常，实际 {updated_record4.status.value}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def test_transaction_rollback():
    print("\n" + "=" * 60)
    print("测试3: 事务回滚测试")
    print("=" * 60)
    
    session, engine = get_test_session()
    
    try:
        print("\n  场景1: 测试删除员工时的事务原子性")
        print("  " + "-" * 40)
        
        print("\n  步骤1: 创建测试员工和多条考勤记录")
        employee = create_employee(
            session,
            name="事务测试员工",
            employee_no="TRANS001",
            department="测试部"
        )
        
        today = date.today()
        for i in range(3):
            test_date = today - timedelta(days=i)
            create_attendance_record(
                session,
                employee_id=employee.id,
                date=test_date,
                clock_in="09:00",
                clock_out="18:00"
            )
        
        attendance_count = session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == employee.id
        ).count()
        print(f"  员工 {employee.name} 有 {attendance_count} 条考勤记录")
        
        employee_id = employee.id
        employee_name = employee.name
        
        print("\n  步骤2: 验证删除前数据存在")
        assert session.query(Employee).filter(Employee.id == employee_id).first() is not None
        assert session.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id).count() == 3
        print("  ✓ 删除前数据验证通过")
        
        print("\n  步骤3: 执行删除操作")
        result = delete_employee(session, employee_id)
        print(f"  删除结果: {result}")
        
        print("\n  步骤4: 验证删除后数据不存在")
        employee_after = session.query(Employee).filter(Employee.id == employee_id).first()
        attendance_after = session.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id).count()
        
        if employee_after is None and attendance_after == 0:
            print("  ✓ 员工和关联考勤记录已成功删除")
        else:
            print(f"  ✗ 删除不完整: 员工存在={employee_after is not None}, 考勤记录数={attendance_after}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def test_manual_transaction_rollback():
    print("\n" + "=" * 60)
    print("测试4: 手动模拟事务失败回滚")
    print("=" * 60)
    
    session, engine = get_test_session()
    
    try:
        print("\n  步骤1: 创建测试员工")
        employee = Employee(
            name="回滚测试员工",
            employee_no="ROLLBACK001",
            department="测试部"
        )
        session.add(employee)
        session.flush()
        
        employee_id = employee.id
        print(f"  创建员工 ID: {employee_id}")
        
        print("\n  步骤2: 添加考勤记录（不提交）")
        record = AttendanceRecord(
            employee_id=employee_id,
            date=date.today(),
            clock_in=None,
            clock_out=None,
            status=AttendanceStatus.ABSENT
        )
        session.add(record)
        session.flush()
        
        record_id = record.id
        print(f"  创建考勤记录 ID: {record_id}")
        
        print("\n  步骤3: 验证未提交前数据在会话中存在")
        employee_in_session = session.query(Employee).filter(Employee.id == employee_id).first()
        record_in_session = session.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
        
        assert employee_in_session is not None
        assert record_in_session is not None
        print("  ✓ 会话中数据存在")
        
        print("\n  步骤4: 执行回滚")
        session.rollback()
        print("  ✓ 已执行回滚")
        
        print("\n  步骤5: 验证回滚后数据不存在")
        employee_after = session.query(Employee).filter(Employee.id == employee_id).first()
        record_after = session.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
        
        if employee_after is None and record_after is None:
            print("  ✓ 回滚验证通过: 数据已被撤销")
            return True
        else:
            print(f"  ✗ 回滚验证失败: 员工存在={employee_after is not None}, 记录存在={record_after is not None}")
            return False
        
    except Exception as e:
        print(f"  测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def main():
    print("\n" + "=" * 60)
    print("员工考勤系统修复验证测试")
    print("=" * 60)
    
    results = []
    
    results.append(("防止重复插入", test_duplicate_prevention()))
    results.append(("状态重新计算", test_status_recalculation_on_update()))
    results.append(("事务原子性", test_transaction_rollback()))
    results.append(("手动回滚", test_manual_transaction_rollback()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "-" * 60)
    if all_passed:
        print("所有测试通过! ✓")
    else:
        print("部分测试失败，请检查代码! ✗")
    print("-" * 60)

if __name__ == "__main__":
    main()
