from sqlalchemy import Column, Integer, String, Date, Time, DateTime, ForeignKey, Enum, UniqueConstraint, Text, Boolean, Numeric
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
    ANNUAL = "年假"
    SICK = "病假"
    PERSONAL = "事假"
    MARRIAGE = "婚假"
    MATERNITY = "产假"
    PATERNITY = "陪产假"
    COMPENSATORY = "调休假"

class LeaveStatus(enum.Enum):
    PENDING = "待审批"
    APPROVED = "已批准"
    REJECTED = "已拒绝"
    CANCELLED = "已取消"

class OvertimeType(enum.Enum):
    WEEKDAY = "工作日加班"
    WEEKEND = "周末加班"
    HOLIDAY = "节假日加班"

class OvertimeStatus(enum.Enum):
    PENDING = "待审批"
    APPROVED = "已批准"
    REJECTED = "已拒绝"

class SettlementType(enum.Enum):
    TIME_OFF = "调休"
    OVERTIME_PAY = "加班费"

class NotificationType(enum.Enum):
    ATTENDANCE_ABNORMAL = "考勤异常"
    LEAVE_APPROVAL = "请假审批"
    OVERTIME_APPROVAL = "加班审批"
    SYSTEM = "系统通知"

class NotificationChannel(enum.Enum):
    WECHAT = "企业微信"
    EMAIL = "邮件"
    SMS = "短信"

class Employee(Base):
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    employee_no = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    wechat_userid = Column(String(100), nullable=True)
    annual_leave_balance = Column(Integer, default=0)
    compensatory_leave_balance = Column(Numeric(10, 2), default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    attendance_records = relationship(
        "AttendanceRecord",
        back_populates="employee",
        cascade="all, delete-orphan"
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
    settlements = relationship(
        "OvertimeSettlement",
        back_populates="employee",
        cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification",
        back_populates="employee",
        cascade="all, delete-orphan"
    )
    approved_leaves = relationship(
        "LeaveRequest",
        foreign_keys="LeaveRequest.approver_id",
        overlaps="approver"
    )
    approved_overtimes = relationship(
        "OvertimeRequest",
        foreign_keys="OvertimeRequest.approver_id",
        overlaps="approver"
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
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        UniqueConstraint('employee_id', 'date', name='uix_employee_date'),
    )
    
    employee = relationship("Employee", back_populates="attendance_records")
    
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
    total_days = Column(Numeric(10, 2), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING)
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approval_comment = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    attachment_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    employee = relationship("Employee", back_populates="leave_requests", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    
    def __repr__(self):
        return f"<LeaveRequest(id={self.id}, employee_id={self.employee_id}, status={self.status})>"

class OvertimeRequest(Base):
    __tablename__ = 'overtime_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    overtime_type = Column(Enum(OvertimeType), nullable=False)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    total_hours = Column(Numeric(10, 2), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(OvertimeStatus), default=OvertimeStatus.PENDING)
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approval_comment = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    settlement_type = Column(Enum(SettlementType), nullable=True)
    is_settled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    employee = relationship("Employee", back_populates="overtime_requests", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    settlement = relationship("OvertimeSettlement", back_populates="overtime_request", uselist=False)
    
    def __repr__(self):
        return f"<OvertimeRequest(id={self.id}, employee_id={self.employee_id}, hours={self.total_hours})>"

class OvertimeSettlement(Base):
    __tablename__ = 'overtime_settlements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    overtime_request_id = Column(Integer, ForeignKey('overtime_requests.id'), nullable=False, unique=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    settlement_type = Column(Enum(SettlementType), nullable=False)
    overtime_hours = Column(Numeric(10, 2), nullable=False)
    settlement_value = Column(Numeric(10, 2), nullable=False)
    hourly_rate = Column(Numeric(10, 2), nullable=True)
    overtime_pay_amount = Column(Numeric(10, 2), nullable=True)
    time_off_days = Column(Numeric(10, 2), nullable=True)
    settlement_date = Column(Date, nullable=False)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    overtime_request = relationship("OvertimeRequest", back_populates="settlement")
    employee = relationship("Employee", back_populates="settlements")
    
    def __repr__(self):
        return f"<OvertimeSettlement(id={self.id}, type={self.settlement_type}, value={self.settlement_value})>"

class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    notification_type = Column(Enum(NotificationType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    recipient = Column(String(200), nullable=False)
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    
    employee = relationship("Employee", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, type={self.notification_type}, channel={self.channel})>"
