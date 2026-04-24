from datetime import date, datetime, timedelta, time as dt_time
from decimal import Decimal
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

import requests

from models import (
    Notification, Employee, AttendanceRecord, 
    AttendanceStatus, NotificationType, NotificationChannel,
    DepartmentSupervisor, ApprovalRole
)
from config import NOTIFICATION_CONFIG, HR_CONFIG


class WeChatNotification:
    def __init__(self, corp_id=None, agent_id=None, secret=None):
        config = NOTIFICATION_CONFIG.get("channels", {}).get("WECHAT", {})
        self.corp_id = corp_id or config.get("corp_id", "")
        self.agent_id = agent_id or config.get("agent_id", "")
        self.secret = secret or config.get("secret", "")
        self._access_token = None
        self._token_expiry = None
    
    def get_access_token(self):
        if self._access_token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._access_token
        
        if not self.corp_id or not self.secret:
            raise ValueError("企业微信配置不完整")
        
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.secret}"
        response = requests.get(url, timeout=10)
        result = response.json()
        
        if result.get("errcode") == 0:
            self._access_token = result.get("access_token")
            self._token_expiry = datetime.now() + timedelta(seconds=result.get("expires_in", 7200) - 300)
            return self._access_token
        else:
            raise Exception(f"获取企业微信Token失败: {result.get('errmsg')}")
    
    def send_message(self, userid, content, title=None):
        access_token = self.get_access_token()
        
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        
        message = {
            "touser": userid,
            "msgtype": "text",
            "agentid": int(self.agent_id) if self.agent_id else 0,
            "text": {
                "content": content
            }
        }
        
        if title:
            message = {
                "touser": userid,
                "msgtype": "markdown",
                "agentid": int(self.agent_id) if self.agent_id else 0,
                "markdown": {
                    "content": f"## {title}\n\n{content}"
                }
            }
        
        response = requests.post(url, json=message, timeout=10)
        result = response.json()
        
        if result.get("errcode") != 0:
            raise Exception(f"发送企业微信消息失败: {result.get('errmsg')}")
        
        return True


class EmailNotification:
    def __init__(self, smtp_server=None, smtp_port=None, sender_email=None, sender_password=None, use_tls=True):
        config = NOTIFICATION_CONFIG.get("channels", {}).get("EMAIL", {})
        self.smtp_server = smtp_server or config.get("smtp_server", "smtp.example.com")
        self.smtp_port = smtp_port or config.get("smtp_port", 587)
        self.sender_email = sender_email or config.get("sender_email", "noreply@example.com")
        self.sender_password = sender_password or config.get("sender_password", "")
        self.use_tls = use_tls if use_tls is not None else config.get("use_tls", True)
    
    def send_message(self, recipient_email, content, title=None):
        if not self.smtp_server or not self.sender_email or not self.sender_password:
            raise ValueError("邮件配置不完整")
        
        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = recipient_email
        msg['Subject'] = Header(title or "考勤通知", 'utf-8')
        
        msg.attach(MIMEText(content, 'plain', 'utf-8'))
        
        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, recipient_email, msg.as_string())
            server.quit()
            
            return True
        except smtplib.SMTPException as e:
            raise Exception(f"发送邮件失败: {str(e)}")


def create_notification(
    session,
    notification_type,
    channel,
    title,
    content,
    recipient,
    employee_id=None
):
    if isinstance(notification_type, str):
        notification_type = NotificationType[notification_type.upper()]
    
    if isinstance(channel, str):
        channel = NotificationChannel[channel.upper()]
    
    notification = Notification(
        employee_id=employee_id,
        notification_type=notification_type,
        channel=channel,
        title=title,
        content=content,
        recipient=recipient
    )
    
    session.add(notification)
    session.commit()
    session.refresh(notification)
    
    return notification


def send_notification(session, notification):
    if notification.is_sent:
        return True, "消息已发送"
    
    try:
        if notification.channel == NotificationChannel.WECHAT:
            wechat_config = NOTIFICATION_CONFIG.get("channels", {}).get("WECHAT", {})
            if not wechat_config.get("enabled", False):
                raise ValueError("企业微信通知通道未启用")
            
            wechat = WeChatNotification()
            wechat.send_message(notification.recipient, notification.content, notification.title)
        
        elif notification.channel == NotificationChannel.EMAIL:
            email_config = NOTIFICATION_CONFIG.get("channels", {}).get("EMAIL", {})
            if not email_config.get("enabled", False):
                raise ValueError("邮件通知通道未启用")
            
            email = EmailNotification()
            email.send_message(notification.recipient, notification.content, notification.title)
        
        notification.is_sent = True
        notification.sent_at = datetime.now()
        session.commit()
        
        return True, "发送成功"
        
    except Exception as e:
        notification.retry_count = (notification.retry_count or 0) + 1
        notification.error_message = str(e)
        session.commit()
        
        return False, str(e)


def get_supervisor_for_employee(session, employee):
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
        
        dept_manager = session.query(DepartmentSupervisor).filter(
            DepartmentSupervisor.department == employee.department,
            DepartmentSupervisor.role_type == ApprovalRole.DEPARTMENT_MANAGER,
            DepartmentSupervisor.is_active == True
        ).first()
        
        if dept_manager:
            return dept_manager.supervisor
    
    all_supervisors = session.query(Employee).filter(
        Employee.approval_role == ApprovalRole.DIRECT_SUPERVISOR
    ).all()
    
    if all_supervisors:
        for sup in all_supervisors:
            if sup.department == employee.department:
                return sup
        return all_supervisors[0]
    
    return None


def get_hr_employees(session):
    hr_dept = HR_CONFIG.get("hr_department", "人力资源部")
    
    hr_employees = session.query(Employee).filter(
        Employee.is_hr == True
    ).all()
    
    if hr_employees:
        return hr_employees
    
    hr_employees = session.query(Employee).filter(
        Employee.department == hr_dept
    ).all()
    
    if hr_employees:
        return hr_employees
    
    hr_director = session.query(DepartmentSupervisor).filter(
        DepartmentSupervisor.role_type == ApprovalRole.HR_DIRECTOR,
        DepartmentSupervisor.is_active == True
    ).first()
    
    if hr_director and hr_director.supervisor:
        return [hr_director.supervisor]
    
    return []


def send_abnormal_notification(session, recipient_employee, title, content, target_type="员工"):
    notifications = []
    channels_config = NOTIFICATION_CONFIG.get("channels", {})
    
    if channels_config.get("WECHAT", {}).get("enabled", False) and recipient_employee.wechat_userid:
        notification = create_notification(
            session,
            notification_type=NotificationType.ATTENDANCE_ABNORMAL,
            channel=NotificationChannel.WECHAT,
            title=title,
            content=content,
            recipient=recipient_employee.wechat_userid,
            employee_id=recipient_employee.id
        )
        notifications.append(notification)
        
        success, msg = send_notification(session, notification)
        if success:
            print(f"  ✓ 企业微信通知已发送至{target_type}: {recipient_employee.name}")
        else:
            print(f"  ✗ 企业微信通知发送失败({target_type}): {msg}")
    
    if channels_config.get("EMAIL", {}).get("enabled", False) and recipient_employee.email:
        notification = create_notification(
            session,
            notification_type=NotificationType.ATTENDANCE_ABNORMAL,
            channel=NotificationChannel.EMAIL,
            title=title,
            content=content,
            recipient=recipient_employee.email,
            employee_id=recipient_employee.id
        )
        notifications.append(notification)
        
        success, msg = send_notification(session, notification)
        if success:
            print(f"  ✓ 邮件通知已发送至{target_type}: {recipient_employee.name}")
        else:
            print(f"  ✗ 邮件通知发送失败({target_type}): {msg}")
    
    return notifications


def check_attendance_abnormal(session, check_date=None):
    if check_date is None:
        check_date = date.today()
    
    config = NOTIFICATION_CONFIG.get("attendance_abnormal_notify", {})
    if not config.get("enabled", False):
        print("  考勤异常通知功能未启用")
        return []
    
    notify_employee = HR_CONFIG.get("notify_employee_on_abnormal", True)
    notify_supervisor = HR_CONFIG.get("notify_supervisor_on_abnormal", True)
    notify_hr = HR_CONFIG.get("notify_hr_on_abnormal", True)
    
    notify_types = config.get("notify_types", ["LATE", "EARLY_LEAVE", "ABSENT"])
    status_map = {
        "LATE": AttendanceStatus.LATE,
        "EARLY_LEAVE": AttendanceStatus.EARLY_LEAVE,
        "ABSENT": AttendanceStatus.ABSENT
    }
    
    target_statuses = [status_map[t] for t in notify_types if t in status_map]
    
    abnormal_records = session.query(AttendanceRecord).filter(
        AttendanceRecord.date == check_date,
        AttendanceRecord.status.in_(target_statuses)
    ).all()
    
    all_notifications = []
    
    print(f"\n  开始检测 {check_date} 的考勤异常...")
    print(f"  发现 {len(abnormal_records)} 条异常记录")
    
    hr_employees = []
    if notify_hr:
        hr_employees = get_hr_employees(session)
        print(f"  HR人员数量: {len(hr_employees)}")
    
    for record in abnormal_records:
        employee = session.query(Employee).filter(Employee.id == record.employee_id).first()
        if not employee:
            continue
        
        status_desc = {
            AttendanceStatus.LATE: "迟到",
            AttendanceStatus.EARLY_LEAVE: "早退",
            AttendanceStatus.ABSENT: "缺勤"
        }.get(record.status, "异常")
        
        employee_title = f"考勤异常通知 - {employee.name}"
        supervisor_title = f"下属考勤异常通知 - {employee.name}"
        hr_title = f"考勤异常通知 - {employee.department or '未知部门'} - {employee.name}"
        
        employee_content = f"""【考勤异常提醒】

员工: {employee.name} ({employee.employee_no})
部门: {employee.department or '未分配'}
日期: {check_date}
状态: {status_desc}
"""
        
        if record.clock_in:
            employee_content += f"上班打卡: {record.clock_in}\n"
        if record.clock_out:
            employee_content += f"下班打卡: {record.clock_out}\n"
        
        employee_content += f"\n如有疑问，请及时联系主管或HR。"
        
        supervisor_content = f"""【下属考勤异常提醒】

员工: {employee.name} ({employee.employee_no})
部门: {employee.department or '未分配'}
日期: {check_date}
状态: {status_desc}
"""
        
        if record.clock_in:
            supervisor_content += f"上班打卡: {record.clock_in}\n"
        if record.clock_out:
            supervisor_content += f"下班打卡: {record.clock_out}\n"
        
        supervisor_content += f"\n请及时关注并了解情况。"
        
        hr_content = f"""【考勤异常通知】

员工: {employee.name} ({employee.employee_no})
部门: {employee.department or '未分配'}
日期: {check_date}
状态: {status_desc}
"""
        
        if record.clock_in:
            hr_content += f"上班打卡: {record.clock_in}\n"
        if record.clock_out:
            hr_content += f"下班打卡: {record.clock_out}\n"
        
        hr_content += f"\n请跟进处理。"
        
        print(f"\n  处理异常记录: {employee.name} - {status_desc}")
        
        if notify_employee:
            print(f"  通知员工本人...")
            notifications = send_abnormal_notification(
                session, employee, employee_title, employee_content, "员工"
            )
            all_notifications.extend(notifications)
        
        if notify_supervisor:
            print(f"  通知主管...")
            supervisor = get_supervisor_for_employee(session, employee)
            if supervisor:
                notifications = send_abnormal_notification(
                    session, supervisor, supervisor_title, supervisor_content, "主管"
                )
                all_notifications.extend(notifications)
            else:
                print(f"  ⚠ 未找到主管: {employee.name}")
        
        if notify_hr and hr_employees:
            print(f"  通知HR...")
            for hr_emp in hr_employees:
                notifications = send_abnormal_notification(
                    session, hr_emp, hr_title, hr_content, "HR"
                )
                all_notifications.extend(notifications)
    
    print(f"\n  异常检测完成，共发送 {len(all_notifications)} 条通知")
    return all_notifications


def run_attendance_check(session, force_run=False):
    auto_detect = HR_CONFIG.get("auto_detect_abnormal", True)
    if not auto_detect and not force_run:
        print("自动检测未启用，跳过考勤检查")
        return []
    
    check_time_str = HR_CONFIG.get("abnormal_check_time", "10:00")
    try:
        check_hour, check_minute = map(int, check_time_str.split(":"))
    except:
        check_hour, check_minute = 10, 0
    
    now = datetime.now()
    current_time = dt_time(now.hour, now.minute)
    check_time = dt_time(check_hour, check_minute)
    
    if not force_run and current_time < check_time:
        print(f"当前时间 {current_time} 早于检查时间 {check_time}，跳过")
        return []
    
    return check_attendance_abnormal(session, check_date=date.today())


def get_pending_notifications(session):
    return session.query(Notification).filter(
        Notification.is_sent == False
    ).order_by(Notification.created_at.asc()).all()


def retry_failed_notifications(session, max_retries=3):
    pending = session.query(Notification).filter(
        Notification.is_sent == False,
        Notification.retry_count < max_retries
    ).all()
    
    results = []
    for notification in pending:
        success, msg = send_notification(session, notification)
        results.append({
            "id": notification.id,
            "success": success,
            "message": msg
        })
    
    return results
