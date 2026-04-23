from datetime import date, time, datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from models import (
    Employee, OvertimeRequest, OvertimeSettlement, LeaveBalance,
    OvertimeType, OvertimeStatus, SettlementType, LeaveType
)
from config import OVERTIME_CONFIG, is_legal_holiday
from validators import validate_date

def calculate_overtime_hours(start_time, end_time):
    if end_time <= start_time:
        raise ValueError("结束时间必须晚于开始时间")
    
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    
    total_minutes = end_minutes - start_minutes
    total_hours = total_minutes / 60
    
    min_hours = OVERTIME_CONFIG["min_overtime_hours"]
    if total_hours < min_hours:
        raise ValueError(f"加班时长不能少于 {min_hours} 小时")
    
    max_daily_hours = OVERTIME_CONFIG["max_daily_overtime_hours"]
    if total_hours > max_daily_hours:
        raise ValueError(f"每日加班时长不能超过 {max_daily_hours} 小时")
    
    return round(total_hours, 2)

def determine_overtime_type(overtime_date):
    if isinstance(overtime_date, str):
        is_valid, overtime_date = validate_date(overtime_date)
        if not is_valid:
            raise ValueError(overtime_date)
    
    is_holiday, holiday_name = is_legal_holiday(overtime_date)
    if is_holiday:
        return OvertimeType.HOLIDAY
    
    weekday = overtime_date.weekday()
    
    if weekday >= 5:
        return OvertimeType.WEEKEND
    
    return OvertimeType.WEEKDAY

def get_overtime_rate(overtime_type):
    if overtime_type == OvertimeType.WEEKDAY:
        return OVERTIME_CONFIG["weekday_overtime_rate"]
    elif overtime_type == OvertimeType.WEEKEND:
        return OVERTIME_CONFIG["weekend_overtime_rate"]
    elif overtime_type == OvertimeType.HOLIDAY:
        return OVERTIME_CONFIG["holiday_overtime_rate"]
    return 1.0

def check_monthly_overtime_limit(session, employee_id, overtime_date, new_hours):
    year = overtime_date.year
    month = overtime_date.month
    
    approved_hours = session.query(func.sum(OvertimeRequest.total_hours)).filter(
        OvertimeRequest.employee_id == employee_id,
        func.strftime('%Y', OvertimeRequest.date) == str(year),
        func.strftime('%m', OvertimeRequest.date) == f"{month:02d}",
        OvertimeRequest.status.in_([OvertimeStatus.APPROVED, OvertimeStatus.SETTLED])
    ).scalar() or 0.0
    
    pending_hours = session.query(func.sum(OvertimeRequest.total_hours)).filter(
        OvertimeRequest.employee_id == employee_id,
        func.strftime('%Y', OvertimeRequest.date) == str(year),
        func.strftime('%m', OvertimeRequest.date) == f"{month:02d}",
        OvertimeRequest.status == OvertimeStatus.PENDING
    ).scalar() or 0.0
    
    total_hours = approved_hours + pending_hours + new_hours
    max_monthly = OVERTIME_CONFIG["max_monthly_overtime_hours"]
    
    if total_hours > max_monthly:
        raise ValueError(
            f"月度加班时长将超过限制。"
            f"当前已批准: {approved_hours}小时, "
            f"待审批: {pending_hours}小时, "
            f"申请新增: {new_hours}小时, "
            f"限制: {max_monthly}小时"
        )
    
    return True

def create_overtime_request(
    session,
    employee_id,
    overtime_date,
    start_time,
    end_time,
    reason,
    overtime_type=None
):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    is_valid, overtime_date_obj = validate_date(overtime_date)
    if not is_valid:
        raise ValueError(overtime_date_obj)
    
    if overtime_date_obj > date.today():
        raise ValueError("加班日期不能是未来时间")
    
    if not reason or len(reason.strip()) == 0:
        raise ValueError("加班原因不能为空")
    
    total_hours = calculate_overtime_hours(start_time, end_time)
    
    if overtime_type is None:
        overtime_type = determine_overtime_type(overtime_date_obj)
    elif isinstance(overtime_type, str):
        try:
            overtime_type = OvertimeType[overtime_type.upper()]
        except KeyError:
            raise ValueError(f"无效的加班类型: {overtime_type}")
    
    check_monthly_overtime_limit(session, employee_id, overtime_date_obj, total_hours)
    
    overtime_request = OvertimeRequest(
        employee_id=employee_id,
        overtime_type=overtime_type,
        date=overtime_date_obj,
        start_time=start_time,
        end_time=end_time,
        total_hours=total_hours,
        reason=reason,
        status=OvertimeStatus.DRAFT
    )
    
    session.add(overtime_request)
    session.commit()
    session.refresh(overtime_request)
    
    return overtime_request

def submit_overtime_request(session, overtime_request_id):
    overtime_request = session.query(OvertimeRequest).filter(
        OvertimeRequest.id == overtime_request_id
    ).first()
    
    if not overtime_request:
        raise ValueError(f"加班申请 {overtime_request_id} 不存在")
    
    if overtime_request.status != OvertimeStatus.DRAFT:
        raise ValueError(f"只有草稿状态的申请可以提交。当前状态: {overtime_request.status.value}")
    
    overtime_request.status = OvertimeStatus.PENDING
    overtime_request.submitted_at = datetime.now()
    
    session.commit()
    session.refresh(overtime_request)
    
    return overtime_request

def approve_overtime_request(session, overtime_request_id, approver_id, approval_remark=None):
    overtime_request = session.query(OvertimeRequest).filter(
        OvertimeRequest.id == overtime_request_id
    ).first()
    
    if not overtime_request:
        raise ValueError(f"加班申请 {overtime_request_id} 不存在")
    
    if overtime_request.status != OvertimeStatus.PENDING:
        raise ValueError(f"只有待审批状态的申请可以审批。当前状态: {overtime_request.status.value}")
    
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    if not approver:
        raise ValueError(f"审批人 {approver_id} 不存在")
    
    try:
        overtime_request.status = OvertimeStatus.APPROVED
        overtime_request.approver_id = approver_id
        overtime_request.approval_remark = approval_remark
        overtime_request.approved_at = datetime.now()
        
        session.commit()
        session.refresh(overtime_request)
        
        return overtime_request
        
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"审批失败，事务已回滚: {str(e)}")

def reject_overtime_request(session, overtime_request_id, approver_id, rejection_reason):
    overtime_request = session.query(OvertimeRequest).filter(
        OvertimeRequest.id == overtime_request_id
    ).first()
    
    if not overtime_request:
        raise ValueError(f"加班申请 {overtime_request_id} 不存在")
    
    if overtime_request.status != OvertimeStatus.PENDING:
        raise ValueError(f"只有待审批状态的申请可以拒绝。当前状态: {overtime_request.status.value}")
    
    if not rejection_reason or len(rejection_reason.strip()) == 0:
        raise ValueError("拒绝原因不能为空")
    
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    if not approver:
        raise ValueError(f"审批人 {approver_id} 不存在")
    
    overtime_request.status = OvertimeStatus.REJECTED
    overtime_request.approver_id = approver_id
    overtime_request.approval_remark = rejection_reason
    overtime_request.approved_at = datetime.now()
    
    session.commit()
    session.refresh(overtime_request)
    
    return overtime_request

def settle_overtime_request(session, overtime_request_id, settlement_type):
    overtime_request = session.query(OvertimeRequest).filter(
        OvertimeRequest.id == overtime_request_id
    ).first()
    
    if not overtime_request:
        raise ValueError(f"加班申请 {overtime_request_id} 不存在")
    
    if overtime_request.status != OvertimeStatus.APPROVED:
        raise ValueError(f"只有已批准状态的申请可以结算。当前状态: {overtime_request.status.value}")
    
    if overtime_request.is_settled:
        raise ValueError("该加班申请已结算")
    
    if isinstance(settlement_type, str):
        try:
            settlement_type = SettlementType[settlement_type.upper()]
        except KeyError:
            raise ValueError(f"无效的结算类型: {settlement_type}")
    
    overtime_rate = get_overtime_rate(overtime_request.overtime_type)
    employee = session.query(Employee).filter(Employee.id == overtime_request.employee_id).first()
    
    try:
        settlement = OvertimeSettlement(
            overtime_request_id=overtime_request.id,
            employee_id=overtime_request.employee_id,
            settlement_type=settlement_type,
            overtime_hours=overtime_request.total_hours,
            overtime_rate=overtime_rate,
            settlement_date=date.today()
        )
        
        if settlement_type == SettlementType.COMPENSATORY_LEAVE:
            ratio = OVERTIME_CONFIG["compensatory_leave_ratio"]
            compensatory_days = round(overtime_request.total_hours * overtime_rate * ratio / 8, 2)
            settlement.compensatory_leave_days = compensatory_days
            
            current_year = date.today().year
            balance = session.query(LeaveBalance).filter(
                LeaveBalance.employee_id == overtime_request.employee_id,
                LeaveBalance.leave_type == LeaveType.COMPENSATORY_LEAVE,
                LeaveBalance.year == current_year
            ).first()
            
            if balance:
                balance.total_days += compensatory_days
                balance.remaining_days += compensatory_days
            else:
                balance = LeaveBalance(
                    employee_id=overtime_request.employee_id,
                    leave_type=LeaveType.COMPENSATORY_LEAVE,
                    year=current_year,
                    total_days=compensatory_days,
                    used_days=0.0,
                    remaining_days=compensatory_days,
                    expired_days=0.0
                )
                session.add(balance)
        
        elif settlement_type == SettlementType.OVERTIME_PAY:
            if employee.hourly_wage <= 0:
                raise ValueError(f"员工 {employee.name} 的时薪未设置，无法计算加班费")
            
            overtime_pay = round(
                overtime_request.total_hours * overtime_rate * employee.hourly_wage, 2
            )
            settlement.overtime_pay_amount = overtime_pay
            settlement.remark = f"时薪: {employee.hourly_wage}元, 倍率: {overtime_rate}倍"
        
        session.add(settlement)
        
        overtime_request.status = OvertimeStatus.SETTLED
        overtime_request.settlement_type = settlement_type
        overtime_request.is_settled = True
        overtime_request.settled_at = datetime.now()
        
        session.commit()
        session.refresh(overtime_request)
        session.refresh(settlement)
        
        return {
            "overtime_request": overtime_request,
            "settlement": settlement
        }
        
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"结算失败，事务已回滚: {str(e)}")

def get_employee_overtime_requests(session, employee_id, status=None):
    query = session.query(OvertimeRequest).filter(
        OvertimeRequest.employee_id == employee_id
    )
    
    if status:
        if isinstance(status, str):
            try:
                status = OvertimeStatus[status.upper()]
            except KeyError:
                raise ValueError(f"无效的状态: {status}")
        query = query.filter(OvertimeRequest.status == status)
    
    return query.order_by(OvertimeRequest.created_at.desc()).all()

def get_pending_overtime_requests(session, approver_id=None):
    query = session.query(OvertimeRequest).filter(
        OvertimeRequest.status == OvertimeStatus.PENDING
    )
    
    if approver_id:
        query = query.join(Employee).filter(
            Employee.supervisor_id == approver_id
        )
    
    return query.order_by(OvertimeRequest.submitted_at.asc()).all()

def calculate_monthly_overtime_stats(session, employee_id, year, month):
    approved_hours = session.query(func.sum(OvertimeRequest.total_hours)).filter(
        OvertimeRequest.employee_id == employee_id,
        func.strftime('%Y', OvertimeRequest.date) == str(year),
        func.strftime('%m', OvertimeRequest.date) == f"{month:02d}",
        OvertimeRequest.status.in_([OvertimeStatus.APPROVED, OvertimeStatus.SETTLED])
    ).scalar() or 0.0
    
    pending_hours = session.query(func.sum(OvertimeRequest.total_hours)).filter(
        OvertimeRequest.employee_id == employee_id,
        func.strftime('%Y', OvertimeRequest.date) == str(year),
        func.strftime('%m', OvertimeRequest.date) == f"{month:02d}",
        OvertimeRequest.status == OvertimeStatus.PENDING
    ).scalar() or 0.0
    
    settled_hours = session.query(func.sum(OvertimeRequest.total_hours)).filter(
        OvertimeRequest.employee_id == employee_id,
        func.strftime('%Y', OvertimeRequest.date) == str(year),
        func.strftime('%m', OvertimeRequest.date) == f"{month:02d}",
        OvertimeRequest.status == OvertimeStatus.SETTLED
    ).scalar() or 0.0
    
    settlement_details = []
    settlements = session.query(OvertimeSettlement).join(OvertimeRequest).filter(
        OvertimeSettlement.employee_id == employee_id,
        func.strftime('%Y', OvertimeRequest.date) == str(year),
        func.strftime('%m', OvertimeRequest.date) == f"{month:02d}"
    ).all()
    
    total_compensatory_days = 0.0
    total_overtime_pay = 0.0
    
    for s in settlements:
        detail = {
            "date": s.overtime_request.date,
            "hours": s.overtime_hours,
            "rate": s.overtime_rate,
            "type": s.settlement_type.value
        }
        
        if s.compensatory_leave_days:
            detail["compensatory_days"] = s.compensatory_leave_days
            total_compensatory_days += s.compensatory_leave_days
        
        if s.overtime_pay_amount:
            detail["overtime_pay"] = s.overtime_pay_amount
            total_overtime_pay += s.overtime_pay_amount
        
        settlement_details.append(detail)
    
    return {
        "employee_id": employee_id,
        "year": year,
        "month": month,
        "approved_hours": round(approved_hours, 2),
        "pending_hours": round(pending_hours, 2),
        "settled_hours": round(settled_hours, 2),
        "total_compensatory_days": round(total_compensatory_days, 2),
        "total_overtime_pay": round(total_overtime_pay, 2),
        "settlement_details": settlement_details,
        "monthly_limit": OVERTIME_CONFIG["max_monthly_overtime_hours"],
        "remaining_allowance": round(OVERTIME_CONFIG["max_monthly_overtime_hours"] - approved_hours - pending_hours, 2)
    }

def get_settlement_history(session, employee_id, year=None, month=None):
    query = session.query(OvertimeSettlement).filter(
        OvertimeSettlement.employee_id == employee_id
    )
    
    if year:
        query = query.join(OvertimeRequest).filter(
            func.strftime('%Y', OvertimeRequest.date) == str(year)
        )
        if month:
            query = query.filter(
                func.strftime('%m', OvertimeRequest.date) == f"{month:02d}"
            )
    
    return query.order_by(OvertimeSettlement.created_at.desc()).all()
