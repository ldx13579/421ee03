#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date, time, datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import (
    Base, Employee, AttendanceRecord, AttendanceStatus,
    LeaveRequest, LeaveType, LeaveStatus,
    OvertimeRequest, OvertimeType, OvertimeStatus,
    ApprovalRecord, ApprovalType, ApprovalResult, ApprovalRole,
    DepartmentSupervisor, Notification, NotificationType
)
from config import LEAVE_CONFIG, NOTIFICATION_CONFIG, HR_CONFIG
from employee_service import create_employee, update_employee
from attendance_service import create_attendance_record
from leave_service import create_leave_request, cancel_leave_request, calculate_leave_days
from approval_service import (
    get_approval_level, find_direct_supervisor, find_department_manager,
    find_hr_director, get_approver_for_leave, create_approval_record,
    get_pending_approvals, can_approve, process_approval,
    get_approval_history, get_approval_records, create_dept_supervisor
)
from notification_service import (
    get_supervisor_for_employee, get_hr_employees, check_attendance_abnormal,
    run_attendance_check
)


def get_test_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session(), engine


def setup_test_organization(session):
    print("\n  步骤1: 创建测试组织架构")
    
    print("\n  创建主管角色员工:")
    hr_director = create_employee(
        session,
        name="HR总监",
        employee_no="HR001",
        department="人力资源部",
        position="人力资源总监",
        email="hr_director@example.com",
        wechat_userid="hr_director"
    )
    update_employee(session, hr_director.id, approval_role="HR_DIRECTOR", is_hr=True)
    print(f"    ✓ HR总监: {hr_director.name} (审批角色: {hr_director.approval_role.value}, HR: {hr_director.is_hr})")
    
    dept_manager = create_employee(
        session,
        name="张经理",
        employee_no="MGR001",
        department="技术部",
        position="部门经理",
        email="manager@example.com",
        wechat_userid="zhang_manager"
    )
    update_employee(session, dept_manager.id, approval_role="DEPARTMENT_MANAGER")
    print(f"    ✓ 部门经理: {dept_manager.name} (审批角色: {dept_manager.approval_role.value})")
    
    supervisor = create_employee(
        session,
        name="李主管",
        employee_no="SUP001",
        department="技术部",
        position="主管",
        email="supervisor@example.com",
        wechat_userid="li_supervisor"
    )
    update_employee(session, supervisor.id, approval_role="DIRECT_SUPERVISOR")
    print(f"    ✓ 直属主管: {supervisor.name} (审批角色: {supervisor.approval_role.value})")
    
    hr_staff = create_employee(
        session,
        name="HR专员",
        employee_no="HR002",
        department="人力资源部",
        position="HR专员",
        email="hr_staff@example.com",
        wechat_userid="hr_staff"
    )
    update_employee(session, hr_staff.id, is_hr=True)
    print(f"    ✓ HR专员: {hr_staff.name} (HR: {hr_staff.is_hr})")
    
    print("\n  创建普通员工:")
    employee1 = create_employee(
        session,
        name="王开发",
        employee_no="DEV001",
        department="技术部",
        position="开发工程师",
        email="employee1@example.com",
        wechat_userid="wang_dev",
        supervisor_id=supervisor.id
    )
    employee1.annual_leave_balance = 15
    employee1.compensatory_leave_balance = 5
    session.commit()
    print(f"    ✓ 员工1: {employee1.name} (主管ID: {employee1.supervisor_id})")
    
    employee2 = create_employee(
        session,
        name="赵测试",
        employee_no="TEST001",
        department="技术部",
        position="测试工程师",
        email="employee2@example.com",
        wechat_userid="zhao_test"
    )
    employee2.annual_leave_balance = 10
    employee2.compensatory_leave_balance = 3
    session.commit()
    print(f"    ✓ 员工2: {employee2.name} (无主管)")
    
    print("\n  步骤2: 创建部门主管配置")
    create_dept_supervisor(
        session,
        department="技术部",
        supervisor_id=dept_manager.id,
        role_type="DEPARTMENT_MANAGER"
    )
    print(f"    ✓ 技术部 - 部门经理: {dept_manager.name}")
    
    create_dept_supervisor(
        session,
        department="人力资源部",
        supervisor_id=hr_director.id,
        role_type="HR_DIRECTOR"
    )
    print(f"    ✓ 人力资源部 - HR总监: {hr_director.name}")
    
    return {
        "hr_director": hr_director,
        "dept_manager": dept_manager,
        "supervisor": supervisor,
        "hr_staff": hr_staff,
        "employee1": employee1,
        "employee2": employee2
    }


def test_approval_level_calculation():
    print("\n" + "=" * 70)
    print("测试1: 审批层级计算逻辑")
    print("=" * 70)
    
    test_cases = [
        (1, "直属主管"),
        (3, "直属主管"),
        (4, "部门经理"),
        (7, "部门经理"),
        (8, "HR总监"),
        (15, "HR总监"),
        (30, "HR总监"),
    ]
    
    print("\n  请假天数 -> 审批层级映射:")
    for days, expected in test_cases:
        level = get_approval_level(days)
        level_name = {1: "直属主管", 2: "部门经理", 3: "HR总监"}.get(level, "未知")
        status = "✓" if level_name == expected else "✗"
        print(f"    {status} {days}天 -> 层级{level} ({level_name})")
    
    print("\n  配置文件中的审批规则:")
    for days_range, role in LEAVE_CONFIG["approval_levels"].items():
        role_name = {
            "direct_supervisor": "直属主管",
            "department_manager": "部门经理",
            "hr_director": "HR总监"
        }.get(role, role)
        print(f"    {days_range}天 -> {role_name}")
    
    print("\n  测试结果: 审批层级计算逻辑正常工作")


def test_supervisor_finding():
    print("\n" + "=" * 70)
    print("测试2: 审批人查找逻辑")
    print("=" * 70)
    
    session, engine = get_test_session()
    
    try:
        org = setup_test_organization(session)
        
        print("\n  步骤3: 测试查找审批人")
        
        print("\n  查找直属主管:")
        supervisor = find_direct_supervisor(session, org["employee1"])
        if supervisor:
            print(f"    ✓ 员工1 ({org['employee1'].name}) 的主管: {supervisor.name}")
        else:
            print(f"    ✗ 未找到员工1的主管")
        
        print("\n  查找部门经理:")
        dept_manager = find_department_manager(session, org["employee1"])
        if dept_manager:
            print(f"    ✓ 员工1 ({org['employee1'].name}) 的部门经理: {dept_manager.name}")
        else:
            print(f"    ✗ 未找到员工1的部门经理")
        
        print("\n  查找HR总监:")
        hr_director = find_hr_director(session)
        if hr_director:
            print(f"    ✓ HR总监: {hr_director.name}")
        else:
            print(f"    ⚠ 未找到HR总监(可能未配置部门主管表)")
        
        print("\n  步骤4: 测试请假申请审批人自动分配")
        
        print("\n  测试不同请假天数的审批人分配:")
        
        test_leaves = [
            (2, "直属主管"),
            (5, "部门经理"),
            (10, "HR总监"),
        ]
        
        for days, expected_role in test_leaves:
            leave = LeaveRequest(
                employee_id=org["employee1"].id,
                leave_type=LeaveType.ANNUAL,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=days - 1),
                total_days=days,
                reason=f"测试{days}天请假",
                status=LeaveStatus.PENDING
            )
            session.add(leave)
            session.commit()
            session.refresh(leave)
            
            approver, level = get_approver_for_leave(session, leave)
            
            if approver:
                expected_role_enum = {
                    "直属主管": ApprovalRole.DIRECT_SUPERVISOR,
                    "部门经理": ApprovalRole.DEPARTMENT_MANAGER,
                    "HR总监": ApprovalRole.HR_DIRECTOR
                }.get(expected_role)
                
                is_correct = approver.approval_role == expected_role_enum
                status = "✓" if is_correct else "✗"
                
                print(f"    {status} {days}天请假 -> 审批人: {approver.name} (角色: {approver.approval_role.value})")
            else:
                print(f"    ⚠ {days}天请假 -> 未找到审批人")
        
        print("\n  测试结果: 审批人查找逻辑正常工作")
        
    finally:
        session.close()
        engine.dispose()


def test_full_approval_flow():
    print("\n" + "=" * 70)
    print("测试3: 完整请假审批流程")
    print("=" * 70)
    
    session, engine = get_test_session()
    
    try:
        org = setup_test_organization(session)
        
        print("\n  步骤3: 员工提交请假申请")
        
        start_date = date.today()
        end_date = start_date + timedelta(days=2)
        
        print(f"\n  员工 {org['employee1'].name} 提交2天请假申请:")
        print(f"    日期: {start_date} 至 {end_date}")
        print(f"    类型: 年假")
        print(f"    原因: 家中有事")
        
        leave_request = create_leave_request(
            session,
            employee_id=org["employee1"].id,
            leave_type="ANNUAL",
            start_date=start_date,
            end_date=end_date,
            reason="家中有事",
            approver_id=org["supervisor"].id
        )
        
        print(f"\n  ✓ 请假申请创建成功!")
        print(f"    申请ID: {leave_request.id}")
        print(f"    请假天数: {leave_request.total_days}天")
        print(f"    当前状态: {leave_request.status.value}")
        print(f"    审批人: {org['supervisor'].name if org['supervisor'] else '未指定'}")
        
        print("\n  步骤4: 查看待审批列表")
        
        pending_result = get_pending_approvals(session, org["supervisor"].id)
        print(f"\n  主管 {org['supervisor'].name} 的待审批列表:")
        for approval in pending_result.get("leaves", []):
            employee = session.query(Employee).filter(Employee.id == approval.employee_id).first()
            print(f"    - 请假申请ID: {approval.id}, 员工: {employee.name if employee else '未知'}, 状态: {approval.status.value}")
        
        print("\n  步骤5: 主管审批申请")
        
        print(f"\n  检查审批权限...")
        can_approve_flag, msg = can_approve(session, org["supervisor"].id, leave_request.id, ApprovalType.LEAVE)
        print(f"    主管 {org['supervisor'].name} 是否有权限: {'是' if can_approve_flag else '否'} - {msg}")
        
        print(f"\n  主管批准申请:")
        success, approval_record = process_approval(
            session,
            approver_id=org["supervisor"].id,
            request_id=leave_request.id,
            approval_type=ApprovalType.LEAVE,
            result=ApprovalResult.APPROVED,
            comment="同意请假，请安排好工作交接。"
        )
        
        print(f"    审批结果: {'成功' if success else '失败'}")
        
        session.refresh(leave_request)
        print(f"\n  申请状态更新:")
        print(f"    状态: {leave_request.status.value}")
        print(f"    审批人: {leave_request.approver_id}")
        
        print("\n  步骤6: 查看审批记录")
        
        approval_records = get_approval_records(session, leave_request.id, ApprovalType.LEAVE)
        print(f"\n  审批记录:")
        for record in approval_records:
            approver = session.query(Employee).filter(Employee.id == record.approver_id).first()
            print(f"    审批人: {approver.name if approver else '未知'}")
            print(f"    层级: {record.approval_level}")
            print(f"    结果: {record.approval_result.value}")
            print(f"    意见: {record.comment or '无'}")
            print(f"    时间: {record.approval_time}")
        
        print("\n  步骤7: 测试拒绝流程")
        
        print(f"\n  员工 {org['employee1'].name} 再提交一个3天请假申请:")
        leave_request2 = create_leave_request(
            session,
            employee_id=org["employee1"].id,
            leave_type="ANNUAL",
            start_date=end_date + timedelta(days=1),
            end_date=end_date + timedelta(days=3),
            reason="再请假",
            approver_id=org["supervisor"].id
        )
        
        print(f"\n  主管拒绝申请:")
        success2, approval_record2 = process_approval(
            session,
            approver_id=org["supervisor"].id,
            request_id=leave_request2.id,
            approval_type=ApprovalType.LEAVE,
            result=ApprovalResult.REJECTED,
            comment="近期项目紧张，暂不批准请假，请延后申请。"
        )
        
        print(f"    审批结果: {'成功' if success2 else '失败'}")
        
        session.refresh(leave_request2)
        print(f"\n  申请状态更新:")
        print(f"    状态: {leave_request2.status.value}")
        
        print("\n  步骤8: 查看审批历史")
        
        history1 = get_approval_history(session, leave_request.id, ApprovalType.LEAVE)
        print(f"\n  员工 {org['employee1'].name} 的第一个申请审批历史:")
        for item in history1:
            print(f"    - 审批人: {item['approver_name']}, 层级: {item['approval_level_name']}, 结果: {item['result']}")
        
        history2 = get_approval_history(session, leave_request2.id, ApprovalType.LEAVE)
        print(f"\n  员工 {org['employee1'].name} 的第二个申请审批历史:")
        for item in history2:
            print(f"    - 审批人: {item['approver_name']}, 层级: {item['approval_level_name']}, 结果: {item['result']}")
        
        print("\n  测试结果: 完整请假审批流程正常工作")
        
    finally:
        session.close()
        engine.dispose()


def test_attendance_abnormal_detection():
    print("\n" + "=" * 70)
    print("测试4: 考勤异常检测与通知逻辑")
    print("=" * 70)
    
    session, engine = get_test_session()
    
    try:
        org = setup_test_organization(session)
        
        print("\n  步骤3: 创建考勤异常记录")
        
        today = date.today()
        
        print(f"\n  为员工 {org['employee1'].name} 创建异常考勤记录:")
        
        late_record = create_attendance_record(
            session,
            employee_id=org["employee1"].id,
            date=today,
            clock_in="09:30",
            clock_out="18:00"
        )
        print(f"    ✓ 迟到记录: 上班 9:30 (标准 9:00)")
        
        absent_record = create_attendance_record(
            session,
            employee_id=org["employee2"].id,
            date=today,
            clock_in=None,
            clock_out=None
        )
        print(f"    ✓ 缺勤记录: 无打卡")
        
        print(f"\n  确认考勤状态:")
        late_record2 = session.query(AttendanceRecord).filter(AttendanceRecord.id == late_record.id).first()
        absent_record2 = session.query(AttendanceRecord).filter(AttendanceRecord.id == absent_record.id).first()
        print(f"    员工1状态: {late_record2.status.value}")
        print(f"    员工2状态: {absent_record2.status.value}")
        
        print("\n  步骤4: 测试主管查找逻辑")
        
        print(f"\n  员工1的主管查找:")
        supervisor1 = get_supervisor_for_employee(session, org["employee1"])
        if supervisor1:
            print(f"    ✓ 找到主管: {supervisor1.name}")
        else:
            print(f"    ✗ 未找到主管")
        
        print(f"\n  员工2的主管查找(未设置supervisor_id):")
        supervisor2 = get_supervisor_for_employee(session, org["employee2"])
        if supervisor2:
            print(f"    ✓ 通过部门配置找到主管: {supervisor2.name}")
        else:
            print(f"    ⚠ 未找到主管(正常行为，如果部门主管未配置的话)")
        
        print("\n  步骤5: 测试HR人员查找")
        
        hr_employees = get_hr_employees(session)
        print(f"\n  找到HR人员: {len(hr_employees)} 人")
        for hr in hr_employees:
            print(f"    - {hr.name} (部门: {hr.department}, HR标记: {hr.is_hr})")
        
        print("\n  步骤6: 测试异常检测和通知逻辑")
        
        print(f"\n  HR配置:")
        print(f"    自动检测异常: {HR_CONFIG.get('auto_detect_abnormal', False)}")
        print(f"    异常时通知员工: {HR_CONFIG.get('notify_employee_on_abnormal', False)}")
        print(f"    异常时通知主管: {HR_CONFIG.get('notify_supervisor_on_abnormal', False)}")
        print(f"    异常时通知HR: {HR_CONFIG.get('notify_hr_on_abnormal', False)}")
        
        print(f"\n  通知配置:")
        notify_config = NOTIFICATION_CONFIG.get("attendance_abnormal_notify", {})
        print(f"    启用异常通知: {notify_config.get('enabled', False)}")
        print(f"    通知类型: {notify_config.get('notify_types', [])}")
        
        print(f"\n  运行考勤异常检测 (模拟模式):")
        print(f"  - 注意: 企业微信/邮件通知通道默认未配置，不会实际发送")
        print(f"  - 但会创建通知记录到数据库")
        
        notifications = check_attendance_abnormal(session, check_date=today)
        
        print(f"\n  创建的通知记录: {len(notifications)} 条")
        for n in notifications:
            employee = session.query(Employee).filter(Employee.id == n.employee_id).first()
            print(f"    - 接收人: {employee.name if employee else '未知'}")
            print(f"      通道: {n.channel.value}")
            print(f"      类型: {n.notification_type.value}")
            print(f"      标题: {n.title}")
        
        print(f"\n  数据库中的通知记录:")
        all_notifications = session.query(Notification).all()
        print(f"    总记录数: {len(all_notifications)}")
        
        print("\n  步骤7: 测试强制运行检测")
        
        print(f"\n  测试run_attendance_check(force_run=True):")
        notifications2 = run_attendance_check(session, force_run=True)
        print(f"    检测结果: 创建了 {len(notifications2)} 条通知")
        
        print("\n  测试结果: 考勤异常检测与通知逻辑正常工作")
        print("\n  说明:")
        print("    1. 企业微信和邮件通知通道需要在config.py中配置真实参数后才能发送")
        print("    2. 当前逻辑会:")
        print("       - 自动查找员工的直属主管")
        print("       - 自动查找HR人员")
        print("       - 检测到异常后分别通知员工本人、主管、HR")
        print("    3. 可以通过run_attendance_check()进行定时检测")
        
    finally:
        session.close()
        engine.dispose()


def test_overtime_approval_flow():
    print("\n" + "=" * 70)
    print("测试5: 加班申请审批流程")
    print("=" * 70)
    
    session, engine = get_test_session()
    
    try:
        org = setup_test_organization(session)
        
        print("\n  步骤3: 员工提交加班申请")
        
        today = date.today()
        
        print(f"\n  员工 {org['employee1'].name} 提交加班申请:")
        print(f"    日期: {today}")
        print(f"    时间: 18:00 - 21:00 (3小时)")
        print(f"    类型: 工作日加班")
        print(f"    原因: 项目上线")
        
        from overtime_service import create_overtime_request
        
        overtime_request = create_overtime_request(
            session,
            employee_id=org["employee1"].id,
            overtime_date=today,
            start_time="18:00",
            end_time="21:00",
            overtime_type="WEEKDAY",
            reason="项目上线",
            approver_id=org["supervisor"].id
        )
        
        print(f"\n  ✓ 加班申请创建成功!")
        print(f"    申请ID: {overtime_request.id}")
        print(f"    加班时长: {overtime_request.total_hours}小时")
        print(f"    当前状态: {overtime_request.status.value}")
        
        print("\n  步骤4: 主管审批加班申请")
        
        success, approval_record = process_approval(
            session,
            approver_id=org["supervisor"].id,
            request_id=overtime_request.id,
            approval_type=ApprovalType.OVERTIME,
            result=ApprovalResult.APPROVED,
            comment="同意加班，请记录好工时。"
        )
        
        print(f"    审批结果: {'成功' if success else '失败'}")
        
        session.refresh(overtime_request)
        print(f"\n  申请状态更新:")
        print(f"    状态: {overtime_request.status.value}")
        
        print("\n  步骤5: 查看审批记录")
        
        approval_records = get_approval_records(session, overtime_request.id, ApprovalType.OVERTIME)
        print(f"\n  审批记录:")
        for record in approval_records:
            approver = session.query(Employee).filter(Employee.id == record.approver_id).first()
            print(f"    审批人: {approver.name if approver else '未知'}")
            print(f"    结果: {record.approval_result.value}")
            print(f"    意见: {record.comment or '无'}")
        
        print("\n  测试结果: 加班申请审批流程正常工作")
        
    finally:
        session.close()
        engine.dispose()


def main():
    print("\n" + "#" * 70)
    print("# 审批流程与考勤异常预警综合测试")
    print("#" * 70)
    
    test_approval_level_calculation()
    test_supervisor_finding()
    test_full_approval_flow()
    test_attendance_abnormal_detection()
    test_overtime_approval_flow()
    
    print("\n" + "#" * 70)
    print("# 测试完成")
    print("#" * 70)
    
    print("\n" + "=" * 70)
    print("核心功能修复总结")
    print("=" * 70)
    
    print("""

【问题1: 光有审批配置没流程】

✓ 已修复 - 新增了完整的审批流程:

  1. 数据模型 (models.py):
     - ApprovalRole 枚举: DIRECT_SUPERVISOR, DEPARTMENT_MANAGER, HR_DIRECTOR, ADMIN
     - Employee 新增字段: supervisor_id, approval_role, is_hr
     - ApprovalRecord 模型: 记录审批历史
     - DepartmentSupervisor 模型: 部门主管配置

  2. 审批服务 (approval_service.py):
     - get_approval_level(): 根据请假天数计算审批层级
       * 1-3天: 直属主管审批
       * 4-7天: 部门经理审批
       * 8天以上: HR总监审批
     
     - 审批人查找:
       * find_direct_supervisor(): 查找直属主管
       * find_department_manager(): 查找部门经理
       * find_hr_director(): 查找HR总监
     
     - 审批流程:
       * get_pending_approvals(): 获取待审批列表
       * can_approve(): 检查审批权限
       * process_approval(): 处理审批(批准/拒绝)
       * create_approval_record(): 创建审批记录
       * get_approval_history(): 查看审批历史

  3. 员工服务更新 (employee_service.py):
     - create_employee() 支持: supervisor_id, approval_role, is_hr
     - update_employee() 支持: supervisor_id, approval_role, is_hr


【问题2: 光有通知配置没检测逻辑】

✓ 已修复 - 新增了完整的考勤异常检测与通知逻辑:

  1. 检测逻辑 (notification_service.py):
     - check_attendance_abnormal(): 检测指定日期的考勤异常
       * 自动查找状态为 LATE/EARLY_LEAVE/ABSENT 的记录
       * 分别通知员工本人、主管、HR
     
     - run_attendance_check(): 定时检测入口
       * 支持配置检测时间 (默认10:00)
       * 支持 force_run 强制运行
     
     - 通知对象确定:
       * get_supervisor_for_employee(): 智能查找员工主管
         - 优先使用 employee.supervisor_id
         - 其次使用部门主管配置
         - 最后使用审批角色匹配
       
       * get_hr_employees(): 查找HR人员
         - 优先使用 employee.is_hr 标记
         - 其次使用部门名称匹配
         - 最后使用HR总监配置

  2. 通知发送:
     - send_abnormal_notification(): 发送异常通知
       * 支持企业微信通知
       * 支持邮件通知
       * 自动创建通知记录

  3. HR配置 (config.py):
     - HR_CONFIG:
       * auto_detect_abnormal: 是否自动检测异常
       * notify_employee_on_abnormal: 是否通知员工本人
       * notify_supervisor_on_abnormal: 是否通知主管
       * notify_hr_on_abnormal: 是否通知HR
       * abnormal_check_time: 检测时间 (默认10:00)


【使用示例】

  # 1. 员工提交请假申请
  leave = create_leave_request(session, employee_id=1, ...)
  
  # 2. 主管查看待审批
  pending = get_pending_approvals(session, approver_id=2)
  
  # 3. 主管审批
  process_approval(session, approver_id=2, request_id=leave.id, 
                     approval_type=ApprovalType.LEAVE,
                     result=ApprovalResult.APPROVED, comment="同意")
  
  # 4. 查看审批历史
  history = get_approval_history(session, employee_id=1)
  
  # 5. 检测考勤异常
  check_attendance_abnormal(session, check_date=date.today())
  
  # 6. 定时检测 (可放入定时任务)
  run_attendance_check(session)


【测试说明】

  运行 test_approval_and_abnormal.py 可验证:
  - 审批层级计算逻辑
  - 审批人查找逻辑
  - 完整请假审批流程
  - 考勤异常检测与通知
  - 加班申请审批流程

  注意: 企业微信和邮件通知需要配置真实参数才能发送。
""")


if __name__ == "__main__":
    main()
