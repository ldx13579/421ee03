from datetime import date, time, datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError

from models import LeaveRequest, Employee, LeaveType, LeaveStatus
from validators import validate_date, parse_time
from config import LEAVE_CONFIG


def calculate_leave_days(start_date, end_date, start_time=None, end_time=None):
    if start_date > end_date:
        raise ValueError("开始日期不能晚于结束日期")
    
    start_datetime = datetime.combine(start_date, start_time or time.min)
    end_datetime = datetime.combine(end_date, end_time or time.max)
    
    total_days = (end_datetime - start_datetime).total_seconds() / (24 * 3600)
    
    if start_time and end_time and start_date == end_date:
        work_start = time(9, 0)
        work_end = time(18, 0)
        work_hours = 9.0
        
        effective_start = max(start_time, work_start)
        effective_end = min(end_time, work_end)
        
        if effective_start >= effective_end:
            return Decimal('0')
        
        hours = (datetime.combine(date.today(), effective_end) - 
                 datetime.combine(date.today(), effective_start)).total_seconds() / 3600
        total_days = hours / work_hours
    
    return Decimal(str(round(total_days, 2)))


def check_leave_balance(session, employee_id, leave_type, total_days):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    if leave_type == LeaveType.ANNUAL:
        if employee.annual_leave_balance < float(total_days):
            return False, f"年假余额不足。当前余额: {employee.annual_leave_balance}天，申请: {total_days}天"
    elif leave_type == LeaveType.COMPENSATORY:
        if employee.compensatory_leave_balance < float(total_days):
            return False, f"调休假余额不足。当前余额: {employee.compensatory_leave_balance}天，申请: {total_days}天"
    
    return True, "余额充足"


def check_date_conflict(session, employee_id, start_date, end_date, exclude_request_id=None):
    query = session.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED])
    )
    
    if exclude_request_id:
        query = query.filter(LeaveRequest.id != exclude_request_id)
    
    existing_leaves = query.all()
    
    for leave in existing_leaves:
        if not (end_date < leave.start_date or start_date > leave.end_date):
            return False, f"与现有请假冲突: {leave.leave_type.value} ({leave.start_date} 至 {leave.end_date})"
    
    return True, "无日期冲突"


def create_leave_request(
    session,
    employee_id,
    leave_type,
    start_date,
    end_date,
    reason,
    start_time=None,
    end_time=None,
    attachment_path=None,
    approver_id=None
):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    is_valid, start_date_obj = validate_date(start_date, allow_future=True)
    if not is_valid:
        raise ValueError(f"开始日期无效: {start_date_obj}")
    
    is_valid, end_date_obj = validate_date(end_date, allow_future=True)
    if not is_valid:
        raise ValueError(f"结束日期无效: {end_date_obj}")
    
    start_time_obj = parse_time(start_time) if start_time else None
    end_time_obj = parse_time(end_time) if end_time else None
    
    total_days = calculate_leave_days(
        start_date_obj, end_date_obj, start_time_obj, end_time_obj
    )
    
    if total_days <= 0:
        raise ValueError("请假天数必须大于0")
    
    has_conflict, conflict_msg = check_date_conflict(
        session, employee_id, start_date_obj, end_date_obj
    )
    if not has_conflict:
        raise ValueError(conflict_msg)
    
    if isinstance(leave_type, str):
        try:
            leave_type = LeaveType[leave_type.upper()]
        except KeyError:
            raise ValueError(f"无效的请假类型: {leave_type}")
    
    has_balance, balance_msg = check_leave_balance(
        session, employee_id, leave_type, total_days
    )
    if not has_balance:
        raise ValueError(balance_msg)
    
    if not reason or not reason.strip():
        raise ValueError("请假原因不能为空")
    
    leave_request = LeaveRequest(
        employee_id=employee_id,
        leave_type=leave_type,
        start_date=start_date_obj,
        end_date=end_date_obj,
        start_time=start_time_obj,
        end_time=end_time_obj,
        total_days=total_days,
        reason=reason.strip(),
        status=LeaveStatus.PENDING,
        attachment_path=attachment_path,
        approver_id=approver_id
    )
    
    try:
        session.add(leave_request)
        session.commit()
        session.refresh(leave_request)
        return leave_request
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"创建请假申请失败: {str(e)}")


def approve_leave_request(session, request_id, approver_id, approval_comment=None, is_approved=True):
    leave_request = session.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not leave_request:
        raise ValueError(f"请假申请 {request_id} 不存在")
    
    if leave_request.status != LeaveStatus.PENDING:
        raise ValueError(f"只能审批待审批状态的申请，当前状态: {leave_request.status.value}")
    
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    if not approver:
        raise ValueError(f"审批人 {approver_id} 不存在")
    
    if is_approved:
        employee = session.query(Employee).filter(
            Employee.id == leave_request.employee_id
        ).first()
        
        if employee:
            if leave_request.leave_type == LeaveType.ANNUAL:
                employee.annual_leave_balance -= float(leave_request.total_days)
            elif leave_request.leave_type == LeaveType.COMPENSATORY:
                employee.compensatory_leave_balance -= float(leave_request.total_days)
        
        leave_request.status = LeaveStatus.APPROVED
    else:
        leave_request.status = LeaveStatus.REJECTED
    
    leave_request.approver_id = approver_id
    leave_request.approval_comment = approval_comment
    leave_request.approved_at = datetime.now()
    
    try:
        session.commit()
        session.refresh(leave_request)
        return leave_request
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"审批请假申请失败: {str(e)}")


def cancel_leave_request(session, request_id, employee_id=None):
    leave_request = session.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not leave_request:
        raise ValueError(f"请假申请 {request_id} 不存在")
    
    if employee_id and leave_request.employee_id != employee_id:
        raise ValueError("只能取消自己的请假申请")
    
    if leave_request.status not in [LeaveStatus.PENDING, LeaveStatus.APPROVED]:
        raise ValueError(f"当前状态无法取消: {leave_request.status.value}")
    
    if leave_request.status == LeaveStatus.APPROVED:
        employee = session.query(Employee).filter(
            Employee.id == leave_request.employee_id
        ).first()
        
        if employee:
            if leave_request.leave_type == LeaveType.ANNUAL:
                employee.annual_leave_balance += float(leave_request.total_days)
            elif leave_request.leave_type == LeaveType.COMPENSATORY:
                employee.compensatory_leave_balance += float(leave_request.total_days)
    
    leave_request.status = LeaveStatus.CANCELLED
    
    try:
        session.commit()
        session.refresh(leave_request)
        return leave_request
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"取消请假申请失败: {str(e)}")


def get_employee_leaves(session, employee_id, status=None, start_date=None, end_date=None):
    query = session.query(LeaveRequest).filter(LeaveRequest.employee_id == employee_id)
    
    if status:
        if isinstance(status, str):
            try:
                status = LeaveStatus[status.upper()]
            except KeyError:
                raise ValueError(f"无效的状态: {status}")
        query = query.filter(LeaveRequest.status == status)
    
    if start_date:
        is_valid, start_date_obj = validate_date(start_date)
        if is_valid:
            query = query.filter(LeaveRequest.start_date >= start_date_obj)
    
    if end_date:
        is_valid, end_date_obj = validate_date(end_date)
        if is_valid:
            query = query.filter(LeaveRequest.end_date <= end_date_obj)
    
    return query.order_by(LeaveRequest.created_at.desc()).all()


def get_pending_leaves(session, department=None):
    query = session.query(LeaveRequest).filter(LeaveRequest.status == LeaveStatus.PENDING)
    
    if department:
        query = query.join(Employee).filter(Employee.department == department)
    
    return query.order_by(LeaveRequest.created_at.asc()).all()


def get_leave_balance(session, employee_id):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "annual_leave_balance": employee.annual_leave_balance,
        "compensatory_leave_balance": float(employee.compensatory_leave_balance),
    }
