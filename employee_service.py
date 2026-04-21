from sqlalchemy.exc import SQLAlchemyError
from models import Employee, AttendanceRecord
from datetime import datetime

def create_employee(session, name, employee_no, department=None, position=None, email=None, phone=None):
    if not name or not employee_no:
        raise ValueError("员工姓名和工号不能为空")
    
    existing = session.query(Employee).filter(Employee.employee_no == employee_no).first()
    if existing:
        raise ValueError(f"工号 {employee_no} 已存在")
    
    employee = Employee(
        name=name,
        employee_no=employee_no,
        department=department,
        position=position,
        email=email,
        phone=phone
    )
    
    session.add(employee)
    session.commit()
    session.refresh(employee)
    
    return employee

def get_employee(session, employee_id):
    return session.query(Employee).filter(Employee.id == employee_id).first()

def get_employee_by_no(session, employee_no):
    return session.query(Employee).filter(Employee.employee_no == employee_no).first()

def update_employee(session, employee_id, name=None, department=None, position=None, email=None, phone=None):
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
    
    employee.updated_at = datetime.now()
    
    session.commit()
    session.refresh(employee)
    
    return employee

def delete_employee(session, employee_id):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    try:
        attendance_count = session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == employee_id
        ).count()
        
        session.delete(employee)
        session.commit()
        
        return {
            "success": True,
            "employee_id": employee_id,
            "employee_name": employee.name,
            "deleted_attendance_records": attendance_count
        }
        
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"删除员工失败: {str(e)}")

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
