from datetime import date, time, datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from models import (
    Employee, LeaveRequest, LeaveBalance, LeaveType, LeaveStatus,
    AttendanceRecord, AttendanceStatus
)
from config import LEAVE_CONFIG

def validate_leave_date(date_val):
    if date_val is None:
        return False, "日期不能为空"
    
    if isinstance(date_val, str):
        try:
            date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
        except ValueError:
            return False, "日期格式错误，应为YYYY-MM-DD格式，如: 2024-04-21"
    
    return True, date_val

def calculate_leave_days(start_date, end_date, start_time=None, end_time=None):
    if start_date > end_date:
        raise ValueError("开始日期不能晚于结束日期")
    
    total_days = (end_date - start_date).days + 1
    total_hours = None
    
    if start_time and end_time:
        if start_date == end_date:
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            if end_minutes <= start_minutes:
                raise ValueError("结束时间必须晚于开始时间")
            total_hours = (end_minutes - start_minutes) / 60
            total_days = total_hours / 8
        else:
            total_hours = None
    
    return round(total_days, 2), total_hours

def get_leave_type_config(leave_type):
    leave_type_str = leave_type.name.lower() if hasattr(leave_type, 'name') else str(leave_type).lower()
    return LEAVE_CONFIG["leave_types"].get(leave_type_str, {})

def create_leave_request(
    session,
    employee_id,
    leave_type,
    start_date,
    end_date,
    reason,
    start_time=None,
    end_time=None,
    certificate_url=None
):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    is_valid, start_date_obj = validate_leave_date(start_date)
    if not is_valid:
        raise ValueError(start_date_obj)
    
    is_valid, end_date_obj = validate_leave_date(end_date)
    if not is_valid:
        raise ValueError(end_date_obj)
    
    if start_date_obj > end_date_obj:
        raise ValueError("请假开始日期不能晚于结束日期")
    
    if isinstance(leave_type, str):
        try:
            leave_type = LeaveType[leave_type.upper()]
        except KeyError:
            raise ValueError(f"无效的请假类型: {leave_type}")
    
    if not reason or len(reason.strip()) == 0:
        raise ValueError("请假原因不能为空")
    
    leave_config = get_leave_type_config(leave_type)
    if leave_config.get("certificate_required") and not certificate_url:
        raise ValueError(f"{leave_type.value}需要提供证明材料")
    
    total_days, total_hours = calculate_leave_days(
        start_date_obj, end_date_obj, start_time, end_time
    )
    
    if total_days <= 0:
        raise ValueError("请假时长必须大于0")
    
    if leave_type in [LeaveType.ANNUAL_LEAVE, LeaveType.COMPENSATORY_LEAVE]:
        current_year = date.today().year
        balance = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type == leave_type,
            LeaveBalance.year == current_year
        ).first()
        
        if balance and balance.remaining_days < total_days:
            raise ValueError(
                f"{leave_type.value}余额不足。剩余: {balance.remaining_days}天, 申请: {total_days}天"
            )
    
    leave_request = LeaveRequest(
        employee_id=employee_id,
        leave_type=leave_type,
        start_date=start_date_obj,
        end_date=end_date_obj,
        start_time=start_time,
        end_time=end_time,
        total_days=total_days,
        total_hours=total_hours,
        reason=reason,
        certificate_url=certificate_url,
        status=LeaveStatus.DRAFT
    )
    
    session.add(leave_request)
    session.commit()
    session.refresh(leave_request)
    
    return leave_request

def submit_leave_request(session, leave_request_id):
    leave_request = session.query(LeaveRequest).filter(
        LeaveRequest.id == leave_request_id
    ).first()
    
    if not leave_request:
        raise ValueError(f"请假申请 {leave_request_id} 不存在")
    
    if leave_request.status != LeaveStatus.DRAFT:
        raise ValueError(f"只有草稿状态的申请可以提交。当前状态: {leave_request.status.value}")
    
    leave_request.status = LeaveStatus.PENDING
    leave_request.submitted_at = datetime.now()
    
    session.commit()
    session.refresh(leave_request)
    
    return leave_request

def approve_leave_request(session, leave_request_id, approver_id, approval_remark=None):
    leave_request = session.query(LeaveRequest).filter(
        LeaveRequest.id == leave_request_id
    ).first()
    
    if not leave_request:
        raise ValueError(f"请假申请 {leave_request_id} 不存在")
    
    if leave_request.status != LeaveStatus.PENDING:
        raise ValueError(f"只有待审批状态的申请可以审批。当前状态: {leave_request.status.value}")
    
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    if not approver:
        raise ValueError(f"审批人 {approver_id} 不存在")
    
    try:
        if leave_request.leave_type in [LeaveType.ANNUAL_LEAVE, LeaveType.COMPENSATORY_LEAVE]:
            if leave_request.created_at:
                leave_year = leave_request.created_at.year
            else:
                leave_year = date.today().year
            
            balance = session.query(LeaveBalance).filter(
                LeaveBalance.employee_id == leave_request.employee_id,
                LeaveBalance.leave_type == leave_request.leave_type,
                LeaveBalance.year == leave_year
            ).first()
            
            if balance:
                if balance.remaining_days < leave_request.total_days:
                    raise ValueError(
                        f"{leave_request.leave_type.value}余额不足。"
                        f"剩余: {balance.remaining_days}天, 申请: {leave_request.total_days}天"
                    )
                
                balance.used_days += leave_request.total_days
                balance.remaining_days -= leave_request.total_days
            else:
                raise ValueError(
                    f"{leave_year}年{leave_request.leave_type.value}余额未初始化"
                )
            
            leave_request.leave_year = leave_year
        
        leave_request.status = LeaveStatus.APPROVED
        leave_request.approver_id = approver_id
        leave_request.approval_remark = approval_remark
        leave_request.approved_at = datetime.now()
        
        _create_leave_attendance_records(session, leave_request)
        
        session.commit()
        session.refresh(leave_request)
        
        return leave_request
        
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"审批失败，事务已回滚: {str(e)}")

def reject_leave_request(session, leave_request_id, approver_id, rejection_reason):
    leave_request = session.query(LeaveRequest).filter(
        LeaveRequest.id == leave_request_id
    ).first()
    
    if not leave_request:
        raise ValueError(f"请假申请 {leave_request_id} 不存在")
    
    if leave_request.status != LeaveStatus.PENDING:
        raise ValueError(f"只有待审批状态的申请可以拒绝。当前状态: {leave_request.status.value}")
    
    if not rejection_reason or len(rejection_reason.strip()) == 0:
        raise ValueError("拒绝原因不能为空")
    
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    if not approver:
        raise ValueError(f"审批人 {approver_id} 不存在")
    
    leave_request.status = LeaveStatus.REJECTED
    leave_request.approver_id = approver_id
    leave_request.approval_remark = rejection_reason
    leave_request.approved_at = datetime.now()
    
    session.commit()
    session.refresh(leave_request)
    
    return leave_request

def cancel_leave_request(session, leave_request_id, employee_id):
    leave_request = session.query(LeaveRequest).filter(
        LeaveRequest.id == leave_request_id
    ).first()
    
    if not leave_request:
        raise ValueError(f"请假申请 {leave_request_id} 不存在")
    
    if leave_request.employee_id != employee_id:
        raise ValueError("只能取消自己的请假申请")
    
    if leave_request.status not in [LeaveStatus.DRAFT, LeaveStatus.PENDING, LeaveStatus.APPROVED]:
        raise ValueError(f"当前状态 {leave_request.status.value} 无法取消")
    
    if leave_request.status == LeaveStatus.APPROVED and leave_request.start_date <= date.today():
        raise ValueError("请假已开始，无法取消")
    
    try:
        if leave_request.status == LeaveStatus.APPROVED:
            if leave_request.leave_type in [LeaveType.ANNUAL_LEAVE, LeaveType.COMPENSATORY_LEAVE]:
                if leave_request.leave_year:
                    restore_year = leave_request.leave_year
                elif leave_request.created_at:
                    restore_year = leave_request.created_at.year
                else:
                    restore_year = date.today().year
                
                balance = session.query(LeaveBalance).filter(
                    LeaveBalance.employee_id == leave_request.employee_id,
                    LeaveBalance.leave_type == leave_request.leave_type,
                    LeaveBalance.year == restore_year
                ).first()
                
                if balance:
                    balance.used_days -= leave_request.total_days
                    balance.remaining_days += leave_request.total_days
                else:
                    raise ValueError(
                        f"{restore_year}年{leave_request.leave_type.value}余额记录不存在，无法恢复"
                    )
            
            _delete_leave_attendance_records(session, leave_request)
        
        leave_request.status = LeaveStatus.CANCELLED
        
        session.commit()
        session.refresh(leave_request)
        
        return leave_request
        
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"取消失败，事务已回滚: {str(e)}")

def _create_leave_attendance_records(session, leave_request):
    current_date = leave_request.start_date
    end_date = leave_request.end_date
    
    while current_date <= end_date:
        existing = session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == leave_request.employee_id,
            AttendanceRecord.date == current_date
        ).first()
        
        if existing:
            existing.leave_request_id = leave_request.id
            existing.remark = f"{leave_request.leave_type.value}：{leave_request.reason}"
        else:
            record = AttendanceRecord(
                employee_id=leave_request.employee_id,
                date=current_date,
                leave_request_id=leave_request.id,
                status=AttendanceStatus.NORMAL,
                remark=f"{leave_request.leave_type.value}：{leave_request.reason}"
            )
            session.add(record)
        
        current_date += timedelta(days=1)

def _delete_leave_attendance_records(session, leave_request):
    records = session.query(AttendanceRecord).filter(
        AttendanceRecord.leave_request_id == leave_request.id
    ).all()
    
    for record in records:
        if record.clock_in is None and record.clock_out is None:
            session.delete(record)
        else:
            record.leave_request_id = None
            record.remark = None

def get_employee_leave_requests(session, employee_id, status=None):
    query = session.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id
    )
    
    if status:
        if isinstance(status, str):
            try:
                status = LeaveStatus[status.upper()]
            except KeyError:
                raise ValueError(f"无效的状态: {status}")
        query = query.filter(LeaveRequest.status == status)
    
    return query.order_by(LeaveRequest.created_at.desc()).all()

def get_pending_leave_requests(session, approver_id=None):
    query = session.query(LeaveRequest).filter(
        LeaveRequest.status == LeaveStatus.PENDING
    )
    
    if approver_id:
        query = query.join(Employee).filter(
            Employee.supervisor_id == approver_id
        )
    
    return query.order_by(LeaveRequest.submitted_at.asc()).all()

def init_leave_balance(session, employee_id, leave_type, year, total_days):
    existing = session.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.leave_type == leave_type,
        LeaveBalance.year == year
    ).first()
    
    if existing:
        raise ValueError(f"该员工{year}年的{leave_type.value}余额已初始化")
    
    balance = LeaveBalance(
        employee_id=employee_id,
        leave_type=leave_type,
        year=year,
        total_days=total_days,
        used_days=0.0,
        remaining_days=total_days,
        expired_days=0.0
    )
    
    session.add(balance)
    session.commit()
    session.refresh(balance)
    
    return balance

def get_leave_balance(session, employee_id, year=None):
    if year is None:
        year = date.today().year
    
    return session.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.year == year
    ).all()
