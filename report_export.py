import os
from datetime import date, datetime
from calendar import monthrange
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models import Employee, AttendanceRecord, AttendanceStatus, LeaveRequest, OvertimeRequest, OvertimeSettlement, SettlementType
from statistics import calculate_employee_monthly_stats, get_attendance_summary
from overtime_service import calculate_overtime_statistics
from leave_service import get_leave_balance
from config import REPORT_CONFIG

try:
    font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'SimHei.ttf')
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('SimHei', font_path))
        FONT_NAME = 'SimHei'
    else:
        FONT_NAME = 'Helvetica'
except:
    FONT_NAME = 'Helvetica'


def ensure_output_dir():
    output_dir = REPORT_CONFIG.get("output_dir", "reports")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir


def get_styles():
    styles = getSampleStyleSheet()
    
    if 'ReportTitle' not in styles:
        styles.add(ParagraphStyle(
            name='ReportTitle',
            fontName=FONT_NAME,
            fontSize=18,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor('#333333')
        ))
    
    if 'SubTitle' not in styles:
        styles.add(ParagraphStyle(
            name='SubTitle',
            fontName=FONT_NAME,
            fontSize=12,
            spaceAfter=10,
            alignment=1,
            textColor=colors.HexColor('#666666')
        ))
    
    if 'SectionTitle' not in styles:
        styles.add(ParagraphStyle(
            name='SectionTitle',
            fontName=FONT_NAME,
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor('#333333'),
            borderPadding=(5, 5, 5, 5),
            backColor=colors.HexColor('#F5F5F5')
        ))
    
    if 'ReportNormal' not in styles:
        styles.add(ParagraphStyle(
            name='ReportNormal',
            fontName=FONT_NAME,
            fontSize=10,
            spaceAfter=5,
            textColor=colors.HexColor('#333333')
        ))
    
    if 'ReportSmall' not in styles:
        styles.add(ParagraphStyle(
            name='ReportSmall',
            fontName=FONT_NAME,
            fontSize=8,
            textColor=colors.HexColor('#999999')
        ))
    
    styles.add(ParagraphStyle(
        name='Small',
        fontName=FONT_NAME,
        fontSize=8,
        textColor=colors.HexColor('#999999')
    ))
    
    return styles


def create_company_header(styles):
    elements = []
    
    company_name = REPORT_CONFIG.get("company_name", "某某科技有限公司")
    report_title = REPORT_CONFIG.get("report_title", "员工考勤月度报表")
    
    elements.append(Paragraph(company_name, styles['ReportTitle']))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(report_title, styles['SubTitle']))
    elements.append(Spacer(1, 20))
    
    return elements


def create_employee_info_table(employee, year, month, styles):
    data = [
        ['员工信息', '', '', ''],
        ['姓名', employee.name, '工号', employee.employee_no],
        ['部门', employee.department or '未分配', '职位', employee.position or '未指定'],
        ['统计周期', f'{year}年{month}月', '生成时间', datetime.now().strftime('%Y-%m-%d %H:%M')]
    ]
    
    table = Table(data, colWidths=[3*cm, 5*cm, 3*cm, 5*cm])
    table.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#F0F0F0')),
        ('BACKGROUND', (2, 1), (2, -1), colors.HexColor('#F0F0F0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    return table


def create_attendance_summary_table(stats, styles):
    data = [
        ['考勤统计', '', ''],
        ['项目', '天数/次数', '状态'],
        ['实际出勤天数', str(stats['actual_attendance_days']), '✓'],
        ['正常出勤', str(stats['normal_days']), '✓'],
        ['迟到天数', str(stats['late_days']), '⚠' if stats['late_days'] > 0 else '-'],
        ['早退天数', str(stats['early_leave_days']), '⚠' if stats['early_leave_days'] > 0 else '-'],
        ['缺勤天数', str(stats['absent_days']), '✗' if stats['absent_days'] > 0 else '-'],
        ['迟到次数', str(stats['late_count']), '⚠' if stats['late_count'] > 0 else '-'],
        ['出勤率', f"{stats['attendance_rate']}%", '✓' if stats['attendance_rate'] >= 95 else '⚠'],
    ]
    
    table = Table(data, colWidths=[5*cm, 4*cm, 3*cm])
    table.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5CB85C')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F0F0F0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
    ]))
    
    return table


def create_overtime_summary_table(overtime_stats, styles):
    data = [
        ['加班统计', '', ''],
        ['项目', '数值', '备注'],
        ['总加班时长', f"{overtime_stats['total_hours']} 小时", ''],
        ['工作日加班', f"{overtime_stats['weekday_hours']} 小时", '1.5倍'],
        ['周末加班', f"{overtime_stats['weekend_hours']} 小时", '2倍'],
        ['节假日加班', f"{overtime_stats['holiday_hours']} 小时", '3倍'],
        ['已结算时长', f"{overtime_stats['total_settled_hours']} 小时", ''],
        ['未结算时长', f"{overtime_stats['total_unsettled_hours']} 小时", ''],
        ['加班费合计', f"¥ {overtime_stats['total_overtime_pay']:.2f}", ''],
        ['调休天数', f"{overtime_stats['total_time_off_days']} 天", ''],
    ]
    
    table = Table(data, colWidths=[4*cm, 5*cm, 3*cm])
    table.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0AD4E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F0F0F0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
    ]))
    
    return table


def create_leave_balance_table(leave_balance, styles):
    data = [
        ['假期余额', '', ''],
        ['假期类型', '余额', '状态'],
        ['年假', f"{leave_balance['annual_leave_balance']} 天", '✓'],
        ['调休假', f"{leave_balance['compensatory_leave_balance']} 天", '✓'],
    ]
    
    table = Table(data, colWidths=[5*cm, 4*cm, 3*cm])
    table.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5BC0DE')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F0F0F0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
    ]))
    
    return table


def create_signature_section(styles):
    data = [
        ['员工确认', '部门主管', '人力资源部'],
        ['', '', ''],
        ['', '', REPORT_CONFIG.get('signature_name', '人力资源部')],
        ['日期: ____________', '日期: ____________', f"日期: {date.today().strftime('%Y年%m月%d日')}"],
    ]
    
    table = Table(data, colWidths=[6*cm, 6*cm, 6*cm])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEABOVE', (0, 2), (-1, 2), 1, colors.black),
        ('TOPPADDING', (0, 2), (-1, 2), 5),
        ('BOTTOMPADDING', (0, 3), (-1, 3), 5),
    ]))
    
    return table


def create_watermark(canvas, doc):
    watermark_text = REPORT_CONFIG.get("watermark_text", "")
    if not watermark_text:
        return
    
    canvas.saveState()
    canvas.setFont(FONT_NAME, 60)
    canvas.setFillColor(colors.HexColor('#EEEEEE'))
    canvas.translate(A4[0]/2, A4[1]/2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, watermark_text)
    canvas.restoreState()


def generate_employee_monthly_report(session, employee_id, year, month):
    employee = session.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise ValueError(f"员工 {employee_id} 不存在")
    
    output_dir = ensure_output_dir()
    output_file = os.path.join(output_dir, f"考勤报表_{employee.employee_no}_{year}年{month}月.pdf")
    
    doc = SimpleDocTemplate(
        output_file,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = get_styles()
    elements = []
    
    elements.extend(create_company_header(styles))
    elements.append(create_employee_info_table(employee, year, month, styles))
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("一、考勤统计", styles['SectionTitle']))
    try:
        stats = calculate_employee_monthly_stats(session, employee_id, year, month)
        elements.append(create_attendance_summary_table(stats, styles))
    except Exception as e:
        elements.append(Paragraph(f"考勤统计获取失败: {str(e)}", styles['ReportNormal']))
    elements.append(Spacer(1, 10))
    
    elements.append(Paragraph("二、加班统计", styles['SectionTitle']))
    try:
        overtime_stats = calculate_overtime_statistics(session, employee_id, year, month)
        elements.append(create_overtime_summary_table(overtime_stats, styles))
    except Exception as e:
        elements.append(Paragraph(f"加班统计获取失败: {str(e)}", styles['ReportNormal']))
    elements.append(Spacer(1, 10))
    
    elements.append(Paragraph("三、假期余额", styles['SectionTitle']))
    try:
        leave_balance = get_leave_balance(session, employee_id)
        elements.append(create_leave_balance_table(leave_balance, styles))
    except Exception as e:
        elements.append(Paragraph(f"假期余额获取失败: {str(e)}", styles['ReportNormal']))
    elements.append(Spacer(1, 20))
    
    if REPORT_CONFIG.get("include_signature", True):
        elements.append(Paragraph("四、签字确认", styles['SectionTitle']))
        elements.append(create_signature_section(styles))
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(f"注：本报表由系统自动生成，仅供薪资核算使用。如有疑问，请联系人力资源部。", styles['ReportSmall']))
    
    doc.build(elements, onFirstPage=create_watermark, onLaterPages=create_watermark)
    
    return output_file


def generate_department_monthly_report(session, department, year, month):
    from statistics import calculate_department_monthly_stats
    
    output_dir = ensure_output_dir()
    output_file = os.path.join(output_dir, f"部门考勤报表_{department}_{year}年{month}月.pdf")
    
    doc = SimpleDocTemplate(
        output_file,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = get_styles()
    elements = []
    
    elements.extend(create_company_header(styles))
    
    elements.append(Paragraph(f"部门: {department}", styles['SubTitle']))
    elements.append(Paragraph(f"统计周期: {year}年{month}月", styles['SubTitle']))
    elements.append(Spacer(1, 15))
    
    try:
        dept_stats = calculate_department_monthly_stats(session, department, year, month)
        
        data = [
            ['部门汇总统计', '', ''],
            ['项目', '数值', ''],
            ['员工总数', str(dept_stats['total_employees']), ''],
            ['迟到总次数', str(dept_stats['total_late_count']), ''],
            ['早退总次数', str(dept_stats['total_early_leave_count']), ''],
            ['平均出勤率', f"{dept_stats['avg_attendance_rate']}%", ''],
        ]
        
        table = Table(data, colWidths=[5*cm, 4*cm, 3*cm])
        table.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        elements.append(Paragraph("员工明细", styles['SectionTitle']))
        
        for emp_stats in dept_stats['employee_stats']:
            emp_data = [
                [f"员工: {emp_stats['employee_name']} ({emp_stats['employee_no']})", '', '', ''],
                ['出勤天数', str(emp_stats['actual_attendance_days']), '迟到次数', str(emp_stats['late_count'])],
                ['正常天数', str(emp_stats['normal_days']), '早退次数', str(emp_stats['early_leave_count'])],
                ['缺勤天数', str(emp_stats['absent_days']), '出勤率', f"{emp_stats['attendance_rate']}%"],
            ]
            
            emp_table = Table(emp_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm])
            emp_table.setStyle(TableStyle([
                ('SPAN', (0, 0), (-1, 0)),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F0F0')),
                ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ]))
            
            elements.append(emp_table)
            elements.append(Spacer(1, 10))
            
    except Exception as e:
        elements.append(Paragraph(f"部门统计获取失败: {str(e)}", styles['ReportNormal']))
    
    if REPORT_CONFIG.get("include_signature", True):
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("签字确认", styles['SectionTitle']))
        elements.append(create_signature_section(styles))
    
    doc.build(elements, onFirstPage=create_watermark, onLaterPages=create_watermark)
    
    return output_file
