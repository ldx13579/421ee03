from datetime import date, time, datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

from models import OvertimeRequest, OvertimeSettlement, Employee, OvertimeType, OvertimeStatus, SettlementType
from validators import validate_date, parse_time
from config import OVERTIME_CONFIG


def calculate_overtime_hours(start_time, end_time):
    if start_time >= end_time:
        raise ValueError("开始时间不能晚于结束时间")
    
    start_dt = datetime.combine(date.today(), start_time)
    end_dt = datetime.combine(date.today(), end_time)
    
    total_hours = (end_dt - start_dt).total_seconds() / 3600
    
    min_hours = OVERTIME_CONFIG.get("min_overtime_hours", 0.5)
    max_hours = OVERTIME_CONFIG.get("max_daily_overtime_hours", 4.0)
    
    if total_hours < min_hours:
        raise ValueError(f"加班时长不能少于 {min_hours} 小时")
    
    if total_hours > max_hours:
        raise ValueError(f"每日加班时长不能超过 {max_hours} 小时")
    
    return Decimal(str(round(total_hours, 2)))


def get_overtime_multiplier(overtime_type):
    if overtime_type == OvertimeType.WEEKDAY:
        return OVERTIME_CONFIG.get("weekday_multiplier", 1.5)
    elif overtime_type == OvertimeType.WEEKEND:
        return OVERTIME_CONFIG.get("weekend_multiplier", 2.0)
    elif overtime_type == OvertimeType.HOLIDAY:
        return OVERTIME_CONFIG.get("holiday_multiplier", 3.0)
    return 1.0


def calculate_settlement_value(overtime_hours, overtime_type, settlement_type, hourly_rate=None):
    multiplier = get_overtime_multiplier(overtime_type)
    
    if settlement_type == SettlementType.OVERTIME_PAY:
        if hourly_rate is None:
            hourly_rate = OVERTIME_CONFIG.get("default_hourly_rate", 50.0)
        overtime_pay = float(overtime_hours) * multiplier * hourly_rate
        return Decimal(str(round(overtime_pay, 2)))
    else:
        conversion_rate = OVERTIME_CONFIG.get("time_off_conversion_rate", 1.0)
        time_off_days = float(overtime_hours) * multiplier * conversion_rate / 8
        return Decimal(str(round(time_off_days, 2)))


def check_overtime_conflict(session, employee_id, overtime_date, exclude_request_id=None):
    query = session.query(OvertimeRequest).filter(
        OvertimeRequest.employee_id == employee_id,
        OvertimeRequest.date == overtime_date,
        OvertimeRequest.status.in_([OvertimeStatus.PENDING, OvertimeStatus.APPROVED])
    )
    
    if exclude_request_id:
        query = query.filter(OvertimeRequest.id != exclude_request_id)
    
    existing = query.first()
    
    if existing:
        return False, f"该日期已有加班申请: {existing.overtime_type.value} ({existing.start_time} - {existing.end_time})"
    
    return True, "无日期冲突"


def create_overtime_request(
    session,
    employee_id,
    overtime_type,
    overtime_date=None,
    start_time=None,
    end_time=None,
    reason=None,
    settlement_type=None,
    approver_id=None,
    date=None
):
    actual_date = overtime_date if overtime_date is not None else date
    
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    is_valid, date_obj = validate_date(actual_date, allow_future=True)
    if not is_valid:
        raise ValueError(f"日期无效: {date_obj}")
    
    start_time_obj = parse_time(start_time)
    end_time_obj = parse_time(end_time)
    
    total_hours = calculate_overtime_hours(start_time_obj, end_time_obj)
    
    has_conflict, conflict_msg = check_overtime_conflict(
        session, employee_id, date_obj
    )
    if not has_conflict:
        raise ValueError(conflict_msg)
    
    if isinstance(overtime_type, str):
        try:
            overtime_type = OvertimeType[overtime_type.upper()]
        except KeyError:
            raise ValueError(f"无效的加班类型: {overtime_type}")
    
    if settlement_type:
        if isinstance(settlement_type, str):
            try:
                settlement_type = SettlementType[settlement_type.upper()]
            except KeyError:
                raise ValueError(f"无效的结算类型: {settlement_type}")
    
    if not reason or not reason.strip():
        raise ValueError("加班原因不能为空")
    
    overtime_request = OvertimeRequest(
        employee_id=employee_id,
        overtime_type=overtime_type,
        date=date_obj,
        start_time=start_time_obj,
        end_time=end_time_obj,
        total_hours=total_hours,
        reason=reason.strip(),
        status=OvertimeStatus.PENDING,
        settlement_type=settlement_type,
        approver_id=approver_id
    )
    
    try:
        session.add(overtime_request)
        session.commit()
        session.refresh(overtime_request)
        return overtime_request
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"创建加班申请失败: {str(e)}")


def approve_overtime_request(
    session,
    request_id,
    approver_id,
    approval_comment=None,
    is_approved=True,
    settlement_type=None
):
    overtime_request = session.query(OvertimeRequest).filter(OvertimeRequest.id == request_id).first()
    if not overtime_request:
        raise ValueError(f"加班申请 {request_id} 不存在")
    
    if overtime_request.status != OvertimeStatus.PENDING:
        raise ValueError(f"只能审批待审批状态的申请，当前状态: {overtime_request.status.value}")
    
    approver = session.query(Employee).filter(Employee.id == approver_id).first()
    if not approver:
        raise ValueError(f"审批人 {approver_id} 不存在")
    
    if is_approved:
        overtime_request.status = OvertimeStatus.APPROVED
        if settlement_type:
            if isinstance(settlement_type, str):
                settlement_type = SettlementType[settlement_type.upper()]
            overtime_request.settlement_type = settlement_type
    else:
        overtime_request.status = OvertimeStatus.REJECTED
    
    overtime_request.approver_id = approver_id
    overtime_request.approval_comment = approval_comment
    overtime_request.approved_at = datetime.now()
    
    try:
        session.commit()
        session.refresh(overtime_request)
        return overtime_request
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"审批加班申请失败: {str(e)}")


def settle_overtime_request(session, request_id, settlement_type=None, hourly_rate=None):
    overtime_request = session.query(OvertimeRequest).filter(OvertimeRequest.id == request_id).first()
    if not overtime_request:
        raise ValueError(f"加班申请 {request_id} 不存在")
    
    if overtime_request.status != OvertimeStatus.APPROVED:
        raise ValueError(f"只能结算已批准的加班申请，当前状态: {overtime_request.status.value}")
    
    if overtime_request.is_settled:
        raise ValueError(f"该加班申请已结算")
    
    if settlement_type is None:
        settlement_type = overtime_request.settlement_type
    
    if settlement_type is None:
        raise ValueError("请指定结算类型（调休或加班费）")
    
    if isinstance(settlement_type, str):
        settlement_type = SettlementType[settlement_type.upper()]
    
    multiplier = get_overtime_multiplier(overtime_request.overtime_type)
    overtime_hours = overtime_request.total_hours
    settlement_value = calculate_settlement_value(
        overtime_hours,
        overtime_request.overtime_type,
        settlement_type,
        hourly_rate
    )
    
    if hourly_rate is None:
        hourly_rate = OVERTIME_CONFIG.get("default_hourly_rate", 50.0)
    
    overtime_pay_amount = None
    time_off_days = None
    
    if settlement_type == SettlementType.OVERTIME_PAY:
        overtime_pay_amount = settlement_value
    else:
        time_off_days = settlement_value
        employee = session.query(Employee).filter(
            Employee.id == overtime_request.employee_id
        ).first()
        if employee:
            if isinstance(time_off_days, Decimal):
                employee.compensatory_leave_balance += time_off_days
            else:
                employee.compensatory_leave_balance += Decimal(str(time_off_days))
    
    settlement = OvertimeSettlement(
        overtime_request_id=overtime_request.id,
        employee_id=overtime_request.employee_id,
        settlement_type=settlement_type,
        overtime_hours=overtime_hours,
        settlement_value=settlement_value,
        hourly_rate=Decimal(str(hourly_rate)) if hourly_rate else None,
        overtime_pay_amount=overtime_pay_amount,
        time_off_days=time_off_days,
        settlement_date=date.today()
    )
    
    overtime_request.is_settled = True
    
    try:
        session.add(settlement)
        session.commit()
        session.refresh(settlement)
        return settlement
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"结算加班申请失败: {str(e)}")


def get_employee_overtime(session, employee_id, status=None, start_date=None, end_date=None):
    query = session.query(OvertimeRequest).filter(OvertimeRequest.employee_id == employee_id)
    
    if status:
        if isinstance(status, str):
            try:
                status = OvertimeStatus[status.upper()]
            except KeyError:
                raise ValueError(f"无效的状态: {status}")
        query = query.filter(OvertimeRequest.status == status)
    
    if start_date:
        is_valid, start_date_obj = validate_date(start_date)
        if is_valid:
            query = query.filter(OvertimeRequest.date >= start_date_obj)
    
    if end_date:
        is_valid, end_date_obj = validate_date(end_date)
        if is_valid:
            query = query.filter(OvertimeRequest.date <= end_date_obj)
    
    return query.order_by(OvertimeRequest.created_at.desc()).all()


def get_pending_overtime(session, department=None):
    query = session.query(OvertimeRequest).filter(OvertimeRequest.status == OvertimeStatus.PENDING)
    
    if department:
        query = query.join(Employee).filter(Employee.department == department)
    
    return query.order_by(OvertimeRequest.created_at.asc()).all()


def calculate_overtime_statistics(session, employee_id, year, month):
    from calendar import monthrange
    
    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    
    overtime_requests = session.query(OvertimeRequest).filter(
        OvertimeRequest.employee_id == employee_id,
        OvertimeRequest.status == OvertimeStatus.APPROVED,
        OvertimeRequest.date >= start_date,
        OvertimeRequest.date <= end_date
    ).all()
    
    total_hours = Decimal('0')
    total_settled_hours = Decimal('0')
    total_unsettled_hours = Decimal('0')
    
    weekday_hours = Decimal('0')
    weekend_hours = Decimal('0')
    holiday_hours = Decimal('0')
    
    for request in overtime_requests:
        total_hours += request.total_hours
        
        if request.is_settled:
            total_settled_hours += request.total_hours
        else:
            total_unsettled_hours += request.total_hours
        
        if request.overtime_type == OvertimeType.WEEKDAY:
            weekday_hours += request.total_hours
        elif request.overtime_type == OvertimeType.WEEKEND:
            weekend_hours += request.total_hours
        elif request.overtime_type == OvertimeType.HOLIDAY:
            holiday_hours += request.total_hours
    
    settlements = session.query(OvertimeSettlement).filter(
        OvertimeSettlement.employee_id == employee_id,
        OvertimeSettlement.settlement_date >= start_date,
        OvertimeSettlement.settlement_date <= end_date
    ).all()
    
    total_overtime_pay = Decimal('0')
    total_time_off = Decimal('0')
    
    for s in settlements:
        if s.settlement_type == SettlementType.OVERTIME_PAY:
            total_overtime_pay += s.settlement_value
        else:
            total_time_off += s.settlement_value
    
    return {
        "year": year,
        "month": month,
        "total_hours": float(total_hours),
        "total_settled_hours": float(total_settled_hours),
        "total_unsettled_hours": float(total_unsettled_hours),
        "weekday_hours": float(weekday_hours),
        "weekend_hours": float(weekend_hours),
        "holiday_hours": float(holiday_hours),
        "total_overtime_pay": float(total_overtime_pay),
        "total_time_off_days": float(total_time_off)
    }
