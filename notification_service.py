from datetime import date, datetime, time
from sqlalchemy.exc import SQLAlchemyError
from models import (
    Employee, AttendanceRecord, NotificationLog,
    AttendanceStatus, NotificationType, NotificationChannel
)
from config import NOTIFICATION_CONFIG

class NotificationSender:
    def __init__(self):
        self.config = NOTIFICATION_CONFIG
    
    def send_wechat_work(self, webhook_url, title, content):
        if not self.config["wechat_work"]["enabled"]:
            return False, "企业微信通知未启用"
        
        if not webhook_url:
            webhook_url = self.config["wechat_work"].get("webhook_url")
        
        if not webhook_url:
            return False, "未配置企业微信Webhook URL"
        
        try:
            import json
            import urllib.request
            
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"**{title}**\n\n{content}"
                }
            }
            
            data = json.dumps(message).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('errcode') == 0:
                    return True, "发送成功"
                else:
                    return False, f"企业微信返回错误: {result.get('errmsg')}"
                    
        except Exception as e:
            return False, f"发送失败: {str(e)}"
    
    def send_email(self, to_email, title, content):
        if not self.config["email"]["enabled"]:
            return False, "邮件通知未启用"
        
        email_config = self.config["email"]
        
        if not to_email:
            return False, "收件人邮箱为空"
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.header import Header
            
            msg = MIMEText(content, 'plain', 'utf-8')
            msg['From'] = email_config["sender_email"]
            msg['To'] = to_email
            msg['Subject'] = Header(title, 'utf-8')
            
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            
            if email_config["use_tls"]:
                server.starttls()
            
            server.login(email_config["sender_email"], email_config["sender_password"])
            server.sendmail(email_config["sender_email"], [to_email], msg.as_string())
            server.quit()
            
            return True, "发送成功"
            
        except Exception as e:
            return False, f"邮件发送失败: {str(e)}"
    
    def send(self, channel, recipient, title, content, webhook_url=None):
        if channel == NotificationChannel.WECHAT_WORK:
            return self.send_wechat_work(webhook_url, title, content)
        elif channel == NotificationChannel.EMAIL:
            return self.send_email(recipient, title, content)
        else:
            return False, f"不支持的通知渠道: {channel}"

def get_abnormal_attendance_records(session, check_date=None):
    if check_date is None:
        check_date = date.today()
    
    abnormal_statuses = [AttendanceStatus.LATE, AttendanceStatus.ABSENT, AttendanceStatus.EARLY_LEAVE]
    
    records = session.query(AttendanceRecord).filter(
        AttendanceRecord.date == check_date,
        AttendanceRecord.status.in_(abnormal_statuses),
        AttendanceRecord.is_alert_sent == False
    ).all()
    
    return records

def get_employee_supervisor(session, employee):
    if employee.supervisor_id:
        return session.query(Employee).filter(
            Employee.id == employee.supervisor_id
        ).first()
    
    department_employees = session.query(Employee).filter(
        Employee.department == employee.department,
        Employee.position.like('%主管%') | Employee.position.like('%经理%')
    ).first()
    
    return department_employees

def generate_alert_content(employee, record):
    status_messages = {
        AttendanceStatus.LATE: "迟到",
        AttendanceStatus.ABSENT: "缺勤",
        AttendanceStatus.EARLY_LEAVE: "早退"
    }
    
    status_text = status_messages.get(record.status, "异常")
    
    clock_in_str = record.clock_in.strftime("%H:%M") if record.clock_in else "未打卡"
    clock_out_str = record.clock_out.strftime("%H:%M") if record.clock_out else "未打卡"
    
    content = f"""
【考勤异常告警】

员工信息：
- 姓名：{employee.name}
- 工号：{employee.employee_no}
- 部门：{employee.department or '未分配'}
- 职位：{employee.position or '未分配'}

异常详情：
- 日期：{record.date}
- 异常类型：{status_text}
- 上班打卡：{clock_in_str}
- 下班打卡：{clock_out_str}
- 备注：{record.remark or '无'}

请及时关注并处理。

---
系统自动发送
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return content.strip()

def send_attendance_alert(session, employee, record, sender=None):
    if sender is None:
        sender = NotificationSender()
    
    supervisor = get_employee_supervisor(session, employee)
    
    if not supervisor:
        return False, "未找到该员工的主管"
    
    title = f"【考勤异常】{employee.name} - {record.status.value}"
    content = generate_alert_content(employee, record)
    
    channels = NOTIFICATION_CONFIG["alert_channels"]
    results = []
    
    for channel_name in channels:
        try:
            if channel_name == "wechat_work":
                channel = NotificationChannel.WECHAT_WORK
                webhook_url = None
                
                success, msg = sender.send(channel, None, title, content, webhook_url)
                
                log = NotificationLog(
                    employee_id=employee.id,
                    recipient_id=supervisor.id,
                    notification_type=NotificationType.ATTENDANCE_ALERT,
                    channel=channel,
                    title=title,
                    content=content,
                    is_sent=success,
                    error_message=None if success else msg,
                    sent_at=datetime.now() if success else None
                )
                session.add(log)
                results.append((channel.value, success, msg))
                
            elif channel_name == "email":
                channel = NotificationChannel.EMAIL
                recipient_email = supervisor.email
                
                if recipient_email:
                    success, msg = sender.send(channel, recipient_email, title, content)
                    
                    log = NotificationLog(
                        employee_id=employee.id,
                        recipient_id=supervisor.id,
                        notification_type=NotificationType.ATTENDANCE_ALERT,
                        channel=channel,
                        title=title,
                        content=content,
                        is_sent=success,
                        error_message=None if success else msg,
                        sent_at=datetime.now() if success else None
                    )
                    session.add(log)
                    results.append((channel.value, success, msg))
                else:
                    results.append((channel.value, False, "主管未配置邮箱"))
                    
        except Exception as e:
            results.append((channel_name, False, str(e)))
    
    try:
        record.is_alert_sent = True
        session.commit()
    except SQLAlchemyError:
        session.rollback()
    
    return True, results

def run_daily_alert_check(session, check_date=None):
    if check_date is None:
        check_date = date.today()
    
    abnormal_records = get_abnormal_attendance_records(session, check_date)
    
    if not abnormal_records:
        return {
            "check_date": check_date,
            "total_abnormal": 0,
            "alerts_sent": 0,
            "details": []
        }
    
    sender = NotificationSender()
    results = []
    alerts_sent = 0
    
    for record in abnormal_records:
        employee = record.employee
        
        if not employee:
            continue
        
        try:
            success, detail = send_attendance_alert(session, employee, record, sender)
            results.append({
                "employee_id": employee.id,
                "employee_name": employee.name,
                "record_id": record.id,
                "status": record.status.value,
                "success": success,
                "detail": detail
            })
            
            if success:
                alerts_sent += 1
                
        except Exception as e:
            results.append({
                "employee_id": employee.id,
                "employee_name": employee.name,
                "record_id": record.id,
                "status": record.status.value,
                "success": False,
                "error": str(e)
            })
    
    return {
        "check_date": check_date,
        "total_abnormal": len(abnormal_records),
        "alerts_sent": alerts_sent,
        "details": results
    }

def send_approval_notification(session, notification_type, applicant, approver, request_info, sender=None):
    if sender is None:
        sender = NotificationSender()
    
    titles = {
        NotificationType.LEAVE_APPROVAL: "【请假审批】新的请假申请待审批",
        NotificationType.OVERTIME_APPROVAL: "【加班审批】新的加班申请待审批",
        NotificationType.LEAVE_APPROVED: "【请假通知】您的请假申请已批准",
        NotificationType.OVERTIME_APPROVED: "【加班通知】您的加班申请已批准",
        NotificationType.LEAVE_REJECTED: "【请假通知】您的请假申请被拒绝",
        NotificationType.OVERTIME_REJECTED: "【加班通知】您的加班申请被拒绝",
    }
    
    title = titles.get(notification_type, "审批通知")
    
    if notification_type in [NotificationType.LEAVE_APPROVAL, NotificationType.OVERTIME_APPROVAL]:
        recipient = approver
        content = f"""
【审批通知】

您有新的{notification_type.value.replace('审批', '')}申请待审批：

申请人：{applicant.name}（{applicant.employee_no}）
申请详情：
{request_info}

请及时登录系统处理。

---
系统自动发送
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    else:
        recipient = applicant
        content = f"""
【通知】

您的{notification_type.value.replace('通知', '')}：

申请详情：
{request_info}

---
系统自动发送
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    channels = NOTIFICATION_CONFIG["alert_channels"]
    results = []
    
    for channel_name in channels:
        try:
            if channel_name == "wechat_work":
                channel = NotificationChannel.WECHAT_WORK
                success, msg = sender.send(channel, None, title, content.strip())
                
                log = NotificationLog(
                    employee_id=applicant.id,
                    recipient_id=recipient.id,
                    notification_type=notification_type,
                    channel=channel,
                    title=title,
                    content=content.strip(),
                    is_sent=success,
                    error_message=None if success else msg,
                    sent_at=datetime.now() if success else None
                )
                session.add(log)
                results.append((channel.value, success, msg))
                
            elif channel_name == "email":
                channel = NotificationChannel.EMAIL
                recipient_email = recipient.email
                
                if recipient_email:
                    success, msg = sender.send(channel, recipient_email, title, content.strip())
                    
                    log = NotificationLog(
                        employee_id=applicant.id,
                        recipient_id=recipient.id,
                        notification_type=notification_type,
                        channel=channel,
                        title=title,
                        content=content.strip(),
                        is_sent=success,
                        error_message=None if success else msg,
                        sent_at=datetime.now() if success else None
                    )
                    session.add(log)
                    results.append((channel.value, success, msg))
                    
        except Exception as e:
            results.append((channel_name, False, str(e)))
    
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
    
    return results
