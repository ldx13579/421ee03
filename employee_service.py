from sqlalchemy.exc import SQLAlchemyError
from models import Employee, AttendanceRecord, ApprovalRole
from datetime import datetime

def create_employee(
    session, 
    name, 
    employee_no, 
    department=None, 
    position=None, 
    email=None, 
    phone=None,
    wechat_userid=None,
    annual_leave_balance=None,
    compensatory_leave_balance=None,
    supervisor_id=None,
    approval_role=None,
    is_hr=False
):
    if not name or not employee_no:
        raise ValueError("员工姓名和工号不能为空")
    
    existing = session.query(Employee).filter(Employee.employee_no == employee_no).first()
    if existing:
        raise ValueError(f"工号 {employee_no} 已存在")
    
    from config import LEAVE_CONFIG
    default_annual = LEAVE_CONFIG.get("default_annual_leave_days", 10)
    
    if approval_role and isinstance(approval_role, str):
        try:
            approval_role = ApprovalRole[approval_role.upper()]
        except KeyError:
            raise ValueError(f"无效的审批角色: {approval_role}")
    
    employee = Employee(
        name=name,
        employee_no=employee_no,
        department=department,
        position=position,
        email=email,
        phone=phone,
        wechat_userid=wechat_userid,
        annual_leave_balance=annual_leave_balance if annual_leave_balance is not None else default_annual,
        compensatory_leave_balance=compensatory_leave_balance if compensatory_leave_balance is not None else 0,
        supervisor_id=supervisor_id,
        approval_role=approval_role,
        is_hr=is_hr
    )
    
    session.add(employee)
    session.commit()
    session.refresh(employee)
    
    return employee

def get_employee(session, employee_id):
    return session.query(Employee).filter(Employee.id == employee_id).first()

def get_employee_by_no(session, employee_no):
    return session.query(Employee).filter(Employee.employee_no == employee_no).first()

def update_employee(
    session, 
    employee_id, 
    name=None, 
    department=None, 
    position=None, 
    email=None, 
    phone=None,
    wechat_userid=None,
    annual_leave_balance=None,
    compensatory_leave_balance=None,
    supervisor_id=None,
    approval_role=None,
    is_hr=None
):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    if name is not None:
        employee.name = name
    if department is not None:
        employee.department = department
    if position is not None:
        employee.position = position
    if email is not None:
        employee.email = email
    if phone is not None:
        employee.phone = phone
    if wechat_userid is not None:
        employee.wechat_userid = wechat_userid
    if annual_leave_balance is not None:
        employee.annual_leave_balance = annual_leave_balance
    if compensatory_leave_balance is not None:
        employee.compensatory_leave_balance = compensatory_leave_balance
    if supervisor_id is not None:
        employee.supervisor_id = supervisor_id
    if approval_role is not None:
        if isinstance(approval_role, str):
            approval_role = ApprovalRole[approval_role.upper()]
        employee.approval_role = approval_role
    if is_hr is not None:
        employee.is_hr = is_hr
    
    employee.updated_at = datetime.now()
    
    session.commit()
    session.refresh(employee)
    
    return employee

def delete_employee(session, employee_id):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    employee_name = employee.name
    
    try:
        attendance_count = session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == employee_id
        ).count()
        
        session.delete(employee)
        session.flush()
        
        after_delete_count = session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == employee_id
        ).count()
        
        if after_delete_count != 0:
            raise Exception(f"考勤记录未完全清理，剩余 {after_delete_count} 条")
        
        session.commit()
        
        return {
            "success": True,
            "employee_id": employee_id,
            "employee_name": employee_name,
            "deleted_attendance_records": attendance_count
        }
        
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"删除员工失败，事务已回滚: {str(e)}")
    except Exception as e:
        session.rollback()
        raise

def get_all_employees(session, department=None):
    query = session.query(Employee)
    
    if department:
        query = query.filter(Employee.department == department)
    
    return query.order_by(Employee.created_at.desc()).all()

def get_departments(session):
    departments = session.query(Employee.department).filter(
        Employee.department.isnot(None)
    ).distinct().all()
    
    return [dept[0] for dept in departments if dept[0]]
