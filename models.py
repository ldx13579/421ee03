from sqlalchemy import Column, Integer, String, Date, Time, DateTime, ForeignKey, Enum, UniqueConstraint, Text, Float, Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class AttendanceStatus(enum.Enum):
    NORMAL = "正常"
    LATE = "迟到"
    EARLY_LEAVE = "早退"
    ABSENT = "缺勤"

class LeaveType(enum.Enum):
    ANNUAL_LEAVE = "年假"
    SICK_LEAVE = "病假"
    PERSONAL_LEAVE = "事假"
    MATERNITY_LEAVE = "产假"
    PATERNITY_LEAVE = "陪产假"
    MARRIAGE_LEAVE = "婚假"
    COMPENSATORY_LEAVE = "调休"

class LeaveStatus(enum.Enum):
    DRAFT = "草稿"
    PENDING = "待审批"
    APPROVED = "已批准"
    REJECTED = "已拒绝"
    CANCELLED = "已取消"

class OvertimeType(enum.Enum):
    WEEKDAY = "工作日加班"
    WEEKEND = "周末加班"
    HOLIDAY = "节假日加班"

class OvertimeStatus(enum.Enum):
    DRAFT = "草稿"
    PENDING = "待审批"
    APPROVED = "已批准"
    REJECTED = "已拒绝"
    SETTLED = "已结算"

class SettlementType(enum.Enum):
    COMPENSATORY_LEAVE = "调休"
    OVERTIME_PAY = "加班费"

class NotificationType(enum.Enum):
    ATTENDANCE_ALERT = "考勤异常告警"
    LEAVE_APPROVAL = "请假审批通知"
    OVERTIME_APPROVAL = "加班审批通知"
    LEAVE_APPROVED = "请假批准通知"
    OVERTIME_APPROVED = "加班批准通知"
    LEAVE_REJECTED = "请假拒绝通知"
    OVERTIME_REJECTED = "加班拒绝通知"

class NotificationChannel(enum.Enum):
    WECHAT_WORK = "企业微信"
    EMAIL = "邮件"

class Employee(Base):
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    employee_no = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    hourly_wage = Column(Float, default=0.0)
    supervisor_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    attendance_records = relationship(
        "AttendanceRecord",
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="AttendanceRecord.employee_id"
    )
    
    leave_requests = relationship(
        "LeaveRequest",
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="LeaveRequest.employee_id"
    )
    
    overtime_requests = relationship(
        "OvertimeRequest",
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="OvertimeRequest.employee_id"
    )
    
    leave_balances = relationship(
        "LeaveBalance",
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="LeaveBalance.employee_id"
    )
    
    supervisor = relationship(
        "Employee",
        remote_side=[id],
        backref="subordinates"
    )
    
    def __repr__(self):
        return f"<Employee(id={self.id}, name={self.name}, employee_no={self.employee_no})>"

class AttendanceRecord(Base):
    __tablename__ = 'attendance_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    clock_in = Column(Time, nullable=True)
    clock_out = Column(Time, nullable=True)
    status = Column(Enum(AttendanceStatus), nullable=True)
    leave_request_id = Column(Integer, ForeignKey('leave_requests.id'), nullable=True)
    remark = Column(String(255), nullable=True)
    is_alert_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        UniqueConstraint('employee_id', 'date', name='uix_employee_date'),
    )
    
    employee = relationship("Employee", back_populates="attendance_records")
    leave_request = relationship("LeaveRequest", back_populates="attendance_records")
    
    def __repr__(self):
        return f"<AttendanceRecord(id={self.id}, employee_id={self.employee_id}, date={self.date}, status={self.status})>"

class LeaveRequest(Base):
    __tablename__ = 'leave_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    leave_type = Column(Enum(LeaveType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    total_days = Column(Float, nullable=False)
    total_hours = Column(Float, nullable=True)
    reason = Column(Text, nullable=False)
    certificate_url = Column(String(500), nullable=True)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.DRAFT, nullable=False)
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approval_remark = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    leave_year = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    employee = relationship("Employee", back_populates="leave_requests", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    attendance_records = relationship("AttendanceRecord", back_populates="leave_request")
    
    def __repr__(self):
        return f"<LeaveRequest(id={self.id}, employee_id={self.employee_id}, type={self.leave_type.value}, status={self.status.value})>"

class LeaveBalance(Base):
    __tablename__ = 'leave_balances'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    leave_type = Column(Enum(LeaveType), nullable=False)
    year = Column(Integer, nullable=False)
    total_days = Column(Float, default=0.0)
    used_days = Column(Float, default=0.0)
    remaining_days = Column(Float, default=0.0)
    expired_days = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        UniqueConstraint('employee_id', 'leave_type', 'year', name='uix_leave_balance'),
    )
    
    employee = relationship("Employee", back_populates="leave_balances")
    
    def __repr__(self):
        return f"<LeaveBalance(employee_id={self.employee_id}, type={self.leave_type.value}, year={self.year}, remaining={self.remaining_days})>"

class OvertimeRequest(Base):
    __tablename__ = 'overtime_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    overtime_type = Column(Enum(OvertimeType), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    total_hours = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(OvertimeStatus), default=OvertimeStatus.DRAFT, nullable=False)
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approval_remark = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    settlement_type = Column(Enum(SettlementType), nullable=True)
    is_settled = Column(Boolean, default=False)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    employee = relationship("Employee", back_populates="overtime_requests", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    
    def __repr__(self):
        return f"<OvertimeRequest(id={self.id}, employee_id={self.employee_id}, type={self.overtime_type.value}, hours={self.total_hours})>"

class OvertimeSettlement(Base):
    __tablename__ = 'overtime_settlements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    overtime_request_id = Column(Integer, ForeignKey('overtime_requests.id'), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    settlement_type = Column(Enum(SettlementType), nullable=False)
    overtime_hours = Column(Float, nullable=False)
    overtime_rate = Column(Float, nullable=False)
    compensatory_leave_days = Column(Float, nullable=True)
    overtime_pay_amount = Column(Float, nullable=True)
    settlement_date = Column(Date, nullable=False)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    overtime_request = relationship("OvertimeRequest")
    
    def __repr__(self):
        return f"<OvertimeSettlement(id={self.id}, type={self.settlement_type.value}, hours={self.overtime_hours})>"

class NotificationLog(Base):
    __tablename__ = 'notification_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    recipient_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    notification_type = Column(Enum(NotificationType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<NotificationLog(id={self.id}, type={self.notification_type.value}, sent={self.is_sent})>"
