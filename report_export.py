import os
from datetime import date, datetime
from calendar import monthrange

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models import Employee, AttendanceRecord, LeaveRequest, OvertimeRequest
from statistics import calculate_employee_monthly_stats
from overtime_service import calculate_monthly_overtime_stats
from config import REPORT_CONFIG

CHINESE_FONT_PATHS = [
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/System/Library/Fonts/PingFang.ttc",
]

def register_chinese_font():
    for font_path in CHINESE_FONT_PATHS:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                return True
            except:
                continue
    return False

FONT_REGISTERED = register_chinese_font()

def get_base_styles():
    styles = getSampleStyleSheet()
    
    if FONT_REGISTERED:
        styles.add(ParagraphStyle(
            name='ChineseTitle',
            parent=styles['Title'],
            fontName='ChineseFont',
            fontSize=18,
            spaceAfter=20
        ))
        
        styles.add(ParagraphStyle(
            name='ChineseHeading1',
            parent=styles['Heading1'],
            fontName='ChineseFont',
            fontSize=14,
            spaceAfter=12
        ))
        
        styles.add(ParagraphStyle(
            name='ChineseHeading2',
            parent=styles['Heading2'],
            fontName='ChineseFont',
            fontSize=12,
            spaceAfter=10
        ))
        
        styles.add(ParagraphStyle(
            name='ChineseNormal',
            parent=styles['Normal'],
            fontName='ChineseFont',
            fontSize=10,
            spaceAfter=6
        ))
        
        styles.add(ParagraphStyle(
            name='ChineseSmall',
            parent=styles['Normal'],
            fontName='ChineseFont',
            fontSize=8,
            textColor=colors.gray
        ))
    else:
        styles.add(ParagraphStyle(
            name='ChineseTitle',
            parent=styles['Title'],
            fontSize=18,
            spaceAfter=20
        ))
        styles.add(ParagraphStyle(
            name='ChineseHeading1',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='ChineseHeading2',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10
        ))
        styles.add(ParagraphStyle(
            name='ChineseNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        ))
        styles.add(ParagraphStyle(
            name='ChineseSmall',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.gray
        ))
    
    return styles

def create_header(company_name, report_title, year, month):
    styles = get_base_styles()
    elements = []
    
    title_text = f"{company_name}"
    elements.append(Paragraph(title_text, styles['ChineseTitle']))
    
    subtitle_text = f"{report_title} - {year}年{month}月"
    elements.append(Paragraph(subtitle_text, styles['ChineseHeading1']))
    
    elements.append(Spacer(1, 0.5*cm))
    
    return elements

def create_employee_summary_table(employee, attendance_stats, overtime_stats):
    styles = get_base_styles()
    
    employee_info = [
        ["员工信息", "", "", ""],
        ["姓名", employee.name, "工号", employee.employee_no],
        ["部门", employee.department or "未分配", "职位", employee.position or "未分配"],
        ["邮箱", employee.email or "未设置", "电话", employee.phone or "未设置"],
    ]
    
    employee_table = Table(employee_info, colWidths=[3*cm, 4*cm, 3*cm, 4*cm])
    employee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('SPAN', (0, 0), (-1, 0)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 1), (2, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    attendance_data = [
        ["考勤统计", "", "", ""],
        ["出勤天数", attendance_stats['actual_attendance_days'], "正常天数", attendance_stats['normal_days']],
        ["迟到天数", attendance_stats['late_days'], "早退天数", attendance_stats['early_leave_days']],
        ["缺勤天数", attendance_stats['absent_days'], "出勤率", f"{attendance_stats['attendance_rate']}%"],
        ["迟到次数", attendance_stats['late_count'], "早退次数", attendance_stats['early_leave_count']],
    ]
    
    attendance_table = Table(attendance_data, colWidths=[3*cm, 4*cm, 3*cm, 4*cm])
    attendance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('SPAN', (0, 0), (-1, 0)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 1), (2, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    overtime_data = [
        ["加班统计", "", "", ""],
        ["已批准加班", f"{overtime_stats['approved_hours']}小时", "待审批", f"{overtime_stats['pending_hours']}小时"],
        ["已结算", f"{overtime_stats['settled_hours']}小时", "剩余可加班", f"{overtime_stats['remaining_allowance']}小时"],
        ["调休天数", f"{overtime_stats['total_compensatory_days']}天", "加班费", f"{overtime_stats['total_overtime_pay']}元"],
    ]
    
    overtime_table = Table(overtime_data, colWidths=[3*cm, 4*cm, 3*cm, 4*cm])
    overtime_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('SPAN', (0, 0), (-1, 0)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 1), (2, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    return employee_table, attendance_table, overtime_table

def create_attendance_detail_table(records):
    if not records:
        return None
    
    data = [["日期", "上班打卡", "下班打卡", "状态", "备注"]]
    
    for record in records:
        clock_in = record.clock_in.strftime("%H:%M") if record.clock_in else "-"
        clock_out = record.clock_out.strftime("%H:%M") if record.clock_out else "-"
        status = record.status.value if record.status else "-"
        remark = record.remark or "-"
        
        data.append([
            str(record.date),
            clock_in,
            clock_out,
            status,
            remark
        ])
    
    table = Table(data, colWidths=[2.5*cm, 2.5*cm, 2.5*cm, 2*cm, 4.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    
    return table

def create_overtime_detail_table(settlements):
    if not settlements:
        return None
    
    data = [["日期", "加班类型", "时长", "倍率", "结算类型", "调休/加班费"]]
    
    for s in settlements:
        overtime_type = s.overtime_request.overtime_type.value if s.overtime_request else "-"
        settlement_type = s.settlement_type.value
        
        if s.compensatory_leave_days:
            settlement_detail = f"调休 {s.compensatory_leave_days} 天"
        elif s.overtime_pay_amount:
            settlement_detail = f"加班费 {s.overtime_pay_amount} 元"
        else:
            settlement_detail = "-"
        
        data.append([
            str(s.overtime_request.date) if s.overtime_request else "-",
            overtime_type,
            f"{s.overtime_hours}小时",
            f"{s.overtime_rate}倍",
            settlement_type,
            settlement_detail
        ])
    
    table = Table(data, colWidths=[2.5*cm, 2.5*cm, 2*cm, 1.5*cm, 2.5*cm, 3*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    
    return table

def create_signature_section(signature_name=None):
    styles = get_base_styles()
    elements = []
    
    elements.append(Spacer(1, 2*cm))
    
    signature_data = [
        ["员工确认", "", "主管确认", "", "HR确认", ""],
        ["签字：___________", "", "签字：___________", "", "签字：___________", ""],
        ["日期：___________", "", "日期：___________", "", "日期：___________", ""],
    ]
    
    signature_table = Table(signature_data, colWidths=[2.5*cm, 0.5*cm, 2.5*cm, 0.5*cm, 2.5*cm, 0.5*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(signature_table)
    elements.append(Spacer(1, 1*cm))
    
    if signature_name:
        footer_text = f"本报表由 {signature_name} 于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 生成"
        elements.append(Paragraph(footer_text, styles['ChineseSmall']))
    
    return elements

def generate_employee_monthly_report(session, employee_id, year, month, output_path=None):
    styles = get_base_styles()
    
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    attendance_stats = calculate_employee_monthly_stats(session, employee_id, year, month)
    overtime_stats = calculate_monthly_overtime_stats(session, employee_id, year, month)
    
    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    
    attendance_records = session.query(AttendanceRecord).filter(
        AttendanceRecord.employee_id == employee_id,
        AttendanceRecord.date >= start_date,
        AttendanceRecord.date <= end_date
    ).order_by(AttendanceRecord.date).all()
    
    from overtime_service import get_settlement_history
    settlements = get_settlement_history(session, employee_id, year, month)
    
    if output_path is None:
        output_dir = REPORT_CONFIG["output_dir"]
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"考勤报表_{employee.employee_no}_{year}年{month}月.pdf"
        )
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    elements = []
    
    elements.extend(create_header(
        REPORT_CONFIG["company_name"],
        REPORT_CONFIG["report_title"],
        year,
        month
    ))
    
    employee_table, attendance_table, overtime_table = create_employee_summary_table(
        employee, attendance_stats, overtime_stats
    )
    
    elements.append(employee_table)
    elements.append(Spacer(1, 0.3*cm))
    elements.append(attendance_table)
    elements.append(Spacer(1, 0.3*cm))
    elements.append(overtime_table)
    elements.append(Spacer(1, 0.5*cm))
    
    elements.append(Paragraph("考勤明细", styles['ChineseHeading2']))
    attendance_detail_table = create_attendance_detail_table(attendance_records)
    if attendance_detail_table:
        elements.append(attendance_detail_table)
    else:
        elements.append(Paragraph("本月暂无考勤记录", styles['ChineseNormal']))
    
    elements.append(Spacer(1, 0.5*cm))
    
    elements.append(Paragraph("加班结算明细", styles['ChineseHeading2']))
    overtime_detail_table = create_overtime_detail_table(settlements)
    if overtime_detail_table:
        elements.append(overtime_detail_table)
    else:
        elements.append(Paragraph("本月暂无加班结算记录", styles['ChineseNormal']))
    
    elements.extend(create_signature_section(REPORT_CONFIG["default_signature"]))
    
    doc.build(elements)
    
    return {
        "success": True,
        "employee_id": employee_id,
        "employee_name": employee.name,
        "year": year,
        "month": month,
        "output_path": output_path,
        "generated_at": datetime.now().isoformat()
    }

def generate_department_monthly_report(session, department, year, month, output_path=None):
    styles = get_base_styles()
    
    employees = session.query(Employee).filter(Employee.department == department).all()
    if not employees:
        raise ValueError(f"部门 {department} 没有员工")
    
    if output_path is None:
        output_dir = REPORT_CONFIG["output_dir"]
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"部门考勤报表_{department}_{year}年{month}月.pdf"
        )
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    elements = []
    
    elements.extend(create_header(
        REPORT_CONFIG["company_name"],
        f"部门{REPORT_CONFIG['report_title']}",
        year,
        month
    ))
    
    summary_data = [
        ["部门汇总", "", "", "", "", ""],
        ["部门", department, "员工人数", len(employees), "月份", f"{year}年{month}月"],
    ]
    
    summary_table = Table(summary_data, colWidths=[2*cm, 3*cm, 2*cm, 2*cm, 2*cm, 3*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('SPAN', (0, 0), (-1, 0)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*cm))
    
    department_stats = []
    total_late = 0
    total_early_leave = 0
    total_absent = 0
    total_overtime_hours = 0.0
    
    for employee in employees:
        try:
            attendance_stats = calculate_employee_monthly_stats(session, employee.id, year, month)
            overtime_stats = calculate_monthly_overtime_stats(session, employee.id, year, month)
            
            total_late += attendance_stats['late_count']
            total_early_leave += attendance_stats['early_leave_count']
            total_absent += attendance_stats['absent_days']
            total_overtime_hours += overtime_stats['approved_hours']
            
            department_stats.append({
                "employee": employee,
                "attendance": attendance_stats,
                "overtime": overtime_stats
            })
        except:
            continue
    
    elements.append(Paragraph("员工考勤汇总", styles['ChineseHeading2']))
    
    employee_summary_data = [
        ["工号", "姓名", "出勤天数", "迟到次数", "早退次数", "缺勤天数", "加班时长", "出勤率"]
    ]
    
    for stat in department_stats:
        employee = stat["employee"]
        att = stat["attendance"]
        ot = stat["overtime"]
        
        employee_summary_data.append([
            employee.employee_no,
            employee.name,
            str(att['actual_attendance_days']),
            str(att['late_count']),
            str(att['early_leave_count']),
            str(att['absent_days']),
            f"{ot['approved_hours']}h",
            f"{att['attendance_rate']}%"
        ])
    
    employee_table = Table(
        employee_summary_data,
        colWidths=[1.8*cm, 1.8*cm, 1.8*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.8*cm, 1.8*cm]
    )
    employee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    elements.append(employee_table)
    
    elements.append(Spacer(1, 0.5*cm))
    
    summary_stats_data = [
        ["部门统计", "", "", ""],
        ["总迟到次数", total_late, "总早退次数", total_early_leave],
        ["总缺勤天数", total_absent, "总加班时长", f"{round(total_overtime_hours, 1)}小时"],
    ]
    
    summary_stats_table = Table(summary_stats_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm])
    summary_stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('SPAN', (0, 0), (-1, 0)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont' if FONT_REGISTERED else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(summary_stats_table)
    
    elements.extend(create_signature_section(REPORT_CONFIG["default_signature"]))
    
    doc.build(elements)
    
    return {
        "success": True,
        "department": department,
        "employee_count": len(employees),
        "year": year,
        "month": month,
        "output_path": output_path,
        "generated_at": datetime.now().isoformat()
    }
