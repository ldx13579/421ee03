from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError

from models import (
    Employee, LeaveRequest, OvertimeRequest, 
    DepartmentSupervisor, ApprovalRecord, 
    ApprovalType, ApprovalResult, LeaveStatus, 
    OvertimeStatus, ApprovalRole
)
from config import LEAVE_CONFIG, HR_CONFIG


def get_approval_level(total_days):
    approval_levels = LEAVE_CONFIG.get("approval_levels", {})
    
    total_days_float = float(total_days)
    
    for level_range, role in approval_levels.items():
        if "-" in level_range:
            min_days, max_days = map(float, level_range.split("-"))
            if min_days <= total_days_float <= max_days:
                role_map = {
                    "direct_supervisor": 1,
                    "department_manager": 2,
                    "hr_director": 3
                }
                return role_map.get(role, 1)
        elif "+" in level_range:
            min_days = float(level_range.replace("+", ""))
            if total_days_float >= min_days:
                role_map = {
                    "direct_supervisor": 1,
                    "department_manager": 2,
                    "hr_director": 3
                }
                return role_map.get(role, 1)
    
    return 1


def get_approval_role_name(approval_level):
    role_names = {
        1: "直属主管",
        2: "部门经理",
        3: "人力资源总监"
    }
    return role_names.get(approval_level, "直属主管")


def find_direct_supervisor(session, employee):
    if employee.supervisor_id:
        supervisor = session.query(Employee).filter(
            Employee.id == employee.supervisor_id
        ).first()
        if supervisor:
            return supervisor
    
    if employee.department:
        dept_supervisor = session.query(DepartmentSupervisor).filter(
            DepartmentSupervisor.department == employee.department,
            DepartmentSupervisor.role_type == ApprovalRole.DIRECT_SUPERVISOR,
            DepartmentSupervisor.is_active == True
        ).first()
        
        if dept_supervisor:
            return dept_supervisor.supervisor
    
    all_supervisors = session.query(Employee).filter(
        Employee.approval_role == ApprovalRole.DIRECT_SUPERVISOR
    ).all()
    
    if all_supervisors:
        for sup in all_supervisors:
            if sup.department == employee.department:
                return sup
        return all_supervisors[0]
    
    return None


def find_department_manager(session, employee):
    if employee.department:
        dept_manager = session.query(DepartmentSupervisor).filter(
            DepartmentSupervisor.department == employee.department,
            DepartmentSupervisor.role_type == ApprovalRole.DEPARTMENT_MANAGER,
            DepartmentSupervisor.is_active == True
        ).first()
        
        if dept_manager:
            return dept_manager.supervisor
    
    all_managers = session.query(Employee).filter(
        Employee.approval_role == ApprovalRole.DEPARTMENT_MANAGER
    ).all()
    
    if all_managers:
        for mgr in all_managers:
            if mgr.department == employee.department:
                return mgr
        return all_managers[0]
    
    return None


def find_hr_director(session):
    hr_director = session.query(DepartmentSupervisor).filter(
        DepartmentSupervisor.role_type == ApprovalRole.HR_DIRECTOR,
        DepartmentSupervisor.is_active == True
    ).first()
    
    if hr_director:
        return hr_director.supervisor
    
    hr_employees = session.query(Employee).filter(
        Employee.approval_role == ApprovalRole.HR_DIRECTOR
    ).first()
    
    if hr_employees:
        return hr_employees
    
    hr_dept_emp = session.query(Employee).filter(
        Employee.department == HR_CONFIG.get("hr_department", "人力资源部"),
        Employee.is_hr == True
    ).first()
    
    return hr_dept_emp


def get_approver_for_leave(session, leave_request):
    employee = session.query(Employee).filter(
        Employee.id == leave_request.employee_id
    ).first()
    
    if not employee:
        return None
    
    approval_level = get_approval_level(leave_request.total_days)
    
    approver = None
    
    if approval_level == 1:
        approver = find_direct_supervisor(session, employee)
        if not approver:
            approver = find_department_manager(session, employee)
    
    elif approval_level == 2:
        approver = find_department_manager(session, employee)
        if not approver:
            approver = find_hr_director(session)
    
    elif approval_level == 3:
        approver = find_hr_director(session)
    
    return approver, approval_level


def get_approver_for_overtime(session, overtime_request):
    employee = session.query(Employee).filter(
        Employee.id == overtime_request.employee_id
    ).first()
    
    if not employee:
        return None
    
    approval_level = 1
    
    approver = find_direct_supervisor(session, employee)
    if not approver:
        approver = find_department_manager(session, employee)
    
    return approver, approval_level


def create_approval_record(
    session,
    approval_type,
    request_id,
    approver_id,
    approval_result,
    approval_level=1,
    comment=None
):
    if isinstance(approval_type, str):
        try:
            approval_type = ApprovalType[approval_type.upper()]
        except KeyError:
            raise ValueError(f"无效的审批类型: {approval_type}")
    
    if isinstance(approval_result, str):
        try:
            approval_result = ApprovalResult[approval_result.upper()]
        except KeyError:
            raise ValueError(f"无效的审批结果: {approval_result}")
    
    approval_record = ApprovalRecord(
        approval_type=approval_type,
        request_id=request_id,
        approver_id=approver_id,
        approval_level=approval_level,
        approval_result=approval_result,
        comment=comment,
        approval_time=datetime.now()
    )
    
    try:
        session.add(approval_record)
        session.commit()
        session.refresh(approval_record)
        return approval_record
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"创建审批记录失败: {str(e)}")


def get_pending_approvals(session, approver_id):
    pending_leaves = session.query(LeaveRequest).filter(
        LeaveRequest.status == LeaveStatus.PENDING
    ).all()
    
    pending_overtimes = session.query(OvertimeRequest).filter(
        OvertimeRequest.status == OvertimeStatus.PENDING
    ).all()
    
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    if not approver:
        return {"leaves": [], "overtimes": []}
    
    eligible_leaves = []
    for leave in pending_leaves:
        _, level = get_approver_for_leave(session, leave)
        
        if approver.approval_role == ApprovalRole.DIRECT_SUPERVISOR and level >= 1:
            eligible_leaves.append(leave)
        elif approver.approval_role == ApprovalRole.DEPARTMENT_MANAGER and level >= 2:
            eligible_leaves.append(leave)
        elif approver.approval_role == ApprovalRole.HR_DIRECTOR and level >= 3:
            eligible_leaves.append(leave)
        elif approver.is_hr:
            eligible_leaves.append(leave)
    
    eligible_overtimes = []
    for overtime in pending_overtimes:
        if approver.approval_role in [ApprovalRole.DIRECT_SUPERVISOR, ApprovalRole.DEPARTMENT_MANAGER]:
            eligible_overtimes.append(overtime)
        elif approver.is_hr:
            eligible_overtimes.append(overtime)
    
    return {
        "leaves": eligible_leaves,
        "overtimes": eligible_overtimes
    }


def get_approval_history(session, request_id, approval_type):
    if isinstance(approval_type, str):
        try:
            approval_type = ApprovalType[approval_type.upper()]
        except KeyError:
            return []
    
    records = session.query(ApprovalRecord).filter(
        ApprovalRecord.request_id == request_id,
        ApprovalRecord.approval_type == approval_type
    ).order_by(ApprovalRecord.approval_time.asc()).all()
    
    return [
        {
            "id": r.id,
            "approver_name": r.approver.name if r.approver else "未知",
            "approval_level": r.approval_level,
            "approval_level_name": get_approval_role_name(r.approval_level),
            "result": r.approval_result.value,
            "comment": r.comment,
            "time": r.approval_time.strftime("%Y-%m-%d %H:%M:%S") if r.approval_time else None
        }
        for r in records
    ]


def can_approve(session, approver_id, request_id, approval_type):
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    if not approver:
        return False, "审批人不存在"
    
    if approval_type == ApprovalType.LEAVE:
        leave_request = session.query(LeaveRequest).filter(
            LeaveRequest.id == request_id
        ).first()
        
        if not leave_request:
            return False, "请假申请不存在"
        
        if leave_request.status != LeaveStatus.PENDING:
            return False, f"申请状态不是待审批，当前状态: {leave_request.status.value}"
        
        expected_approver, level = get_approver_for_leave(session, leave_request)
        
        if approver.is_hr:
            return True, f"HR有权审批，当前需要{get_approval_role_name(level)}审批"
        
        if expected_approver and expected_approver.id == approver.id:
            return True, f"有权审批，当前需要{get_approval_role_name(level)}审批"
        
        if approver.approval_role == ApprovalRole.DEPARTMENT_MANAGER and level >= 2:
            return True, f"部门经理有权审批，当前需要{get_approval_role_name(level)}审批"
        
        if approver.approval_role == ApprovalRole.HR_DIRECTOR and level >= 3:
            return True, f"HR总监有权审批，当前需要{get_approval_role_name(level)}审批"
        
        return False, f"当前申请需要{get_approval_role_name(level)}审批"
    
    elif approval_type == ApprovalType.OVERTIME:
        overtime_request = session.query(OvertimeRequest).filter(
            OvertimeRequest.id == request_id
        ).first()
        
        if not overtime_request:
            return False, "加班申请不存在"
        
        if overtime_request.status != OvertimeStatus.PENDING:
            return False, f"申请状态不是待审批，当前状态: {overtime_request.status.value}"
        
        if approver.is_hr:
            return True, "HR有权审批"
        
        if approver.approval_role in [ApprovalRole.DIRECT_SUPERVISOR, ApprovalRole.DEPARTMENT_MANAGER]:
            return True, "主管/经理有权审批"
        
        return False, "无权限审批"
    
    return False, "无效的审批类型"


def process_approval(
    session,
    approver_id,
    request_id,
    approval_type,
    result,
    comment=None
):
    if isinstance(approval_type, str):
        approval_type = ApprovalType[approval_type.upper()]
    
    if isinstance(result, str):
        result = ApprovalResult[result.upper()]
    
    can_approve_flag, msg = can_approve(session, approver_id, request_id, approval_type)
    if not can_approve_flag:
        raise ValueError(f"无审批权限: {msg}")
    
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    
    approval_level = 1
    
    try:
        if approval_type == ApprovalType.LEAVE:
            leave_request = session.query(LeaveRequest).filter(
                LeaveRequest.id == request_id
            ).first()
            
            if not leave_request:
                raise ValueError("请假申请不存在")
            
            _, approval_level = get_approver_for_leave(session, leave_request)
            
            if result == ApprovalResult.APPROVED:
                leave_request.status = LeaveStatus.APPROVED
                leave_request.approver_id = approver_id
                leave_request.approved_at = datetime.now()
                leave_request.comment = comment or leave_request.comment
            else:
                leave_request.status = LeaveStatus.REJECTED
                leave_request.approver_id = approver_id
                leave_request.rejected_at = datetime.now()
                leave_request.comment = comment or leave_request.comment
        
        elif approval_type == ApprovalType.OVERTIME:
            overtime_request = session.query(OvertimeRequest).filter(
                OvertimeRequest.id == request_id
            ).first()
            
            if not overtime_request:
                raise ValueError("加班申请不存在")
            
            _, approval_level = get_approver_for_overtime(session, overtime_request)
            
            if result == ApprovalResult.APPROVED:
                overtime_request.status = OvertimeStatus.APPROVED
                overtime_request.approver_id = approver_id
                overtime_request.approved_at = datetime.now()
                overtime_request.comment = comment or overtime_request.comment
            else:
                overtime_request.status = OvertimeStatus.REJECTED
                overtime_request.approver_id = approver_id
                overtime_request.rejected_at = datetime.now()
                overtime_request.comment = comment or overtime_request.comment
        
        approval_record = create_approval_record(
            session,
            approval_type=approval_type,
            request_id=request_id,
            approver_id=approver_id,
            approval_result=result,
            approval_level=approval_level,
            comment=comment
        )
        
        session.commit()
        
        return True, approval_record
        
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"处理审批失败: {str(e)}")


def get_approval_records(session, request_id, approval_type):
    if isinstance(approval_type, str):
        approval_type = ApprovalType[approval_type.upper()]
    
    records = session.query(ApprovalRecord).filter(
        ApprovalRecord.request_id == request_id,
        ApprovalRecord.approval_type == approval_type
    ).order_by(ApprovalRecord.approval_time.asc()).all()
    
    return records


def create_dept_supervisor(
    session,
    department,
    supervisor_id,
    role_type,
    is_active=True
):
    return set_department_supervisor(
        session,
        department=department,
        supervisor_id=supervisor_id,
        role_type=role_type,
        is_active=is_active
    )


def set_department_supervisor(
    session,
    department,
    supervisor_id,
    role_type,
    is_active=True
):
    if isinstance(role_type, str):
        try:
            role_type = ApprovalRole[role_type.upper()]
        except KeyError:
            raise ValueError(f"无效的角色类型: {role_type}")
    
    supervisor = session.query(Employee).filter(
        Employee.id == supervisor_id
    ).first()
    
    if not supervisor:
        raise ValueError(f"主管 {supervisor_id} 不存在")
    
    existing = session.query(DepartmentSupervisor).filter(
        DepartmentSupervisor.department == department,
        DepartmentSupervisor.role_type == role_type
    ).first()
    
    if existing:
        existing.supervisor_id = supervisor_id
        existing.is_active = is_active
    else:
        dept_supervisor = DepartmentSupervisor(
            department=department,
            supervisor_id=supervisor_id,
            role_type=role_type,
            is_active=is_active
        )
        session.add(dept_supervisor)
    
    supervisor.approval_role = role_type
    
    try:
        session.commit()
        return True
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"设置部门主管失败: {str(e)}")
