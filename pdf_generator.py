import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER
from constants import (
    HOLIDAY_BG_COLOR, KAGOKITA_BG_COLOR, WEEKDAY_JA, SATURDAY_BG_COLOR,
    RECRUIT_BG_COLOR, SATURDAY_BG_COLOR2, SUNDAY_BG_COLOR2, HOLIDAY_BG_COLOR2,
    STORE_COLORS
)
import jpholiday

def calculate_shift_count(data, employee=None):
    """シフト日数を計算する関数"""
    def count_shift(shift):
        if pd.isna(shift) or shift == '休み':
            return 0
        return 1  # 「休み」以外は全てカウント（ハイフンを含む）

    if employee:
        # 個別従業員のシフト日数を計算
        return sum(count_shift(shift) for shift in data)
    else:
        # 全従業員のシフト日数を計算
        counts = {}
        for emp in data.columns:
            if emp not in ['日付', '曜日']:
                counts[emp] = sum(count_shift(shift) for shift in data[emp])
        return counts

def count_shift(shift):
    if pd.isna(shift) or shift == '休み':
        return 0
    return 1  # 「休み」以外は全てカウント（ハイフンを含む）

def get_shift_paragraph(shift, row, bold_style, custom_holidays=None):
    """シフトのパラグラフスタイルを決定する補助関数"""
    if custom_holidays is None:
        custom_holidays = []
        
    if pd.isna(shift) or shift == '' or shift == '-':
        return Paragraph('', bold_style)
        
    shift_parts = str(shift).split(',')
    shift_type = shift_parts[0]
    
    if shift_type in ['休み', '有給']:
        date = pd.to_datetime(row['日付'])
        is_holiday = row['曜日'] == '日' or date in custom_holidays or jpholiday.is_holiday(date)
        is_saturday = row['曜日'] == '土'
        
        if is_holiday:
            text_color = HOLIDAY_BG_COLOR2
            bg_color = HOLIDAY_BG_COLOR
        elif is_saturday:
            text_color = SATURDAY_BG_COLOR2
            bg_color = SATURDAY_BG_COLOR
        else:
            text_color = "#373737"
            bg_color = HOLIDAY_BG_COLOR
            
        return Paragraph(f'<font color="{text_color}"><b>{shift_type}</b></font>', 
                        ParagraphStyle('Holiday', parent=bold_style, backColor=colors.HexColor(bg_color)))
    
    if shift_type == 'かご北':
        return Paragraph(f'<b>{shift_type}</b>', 
                        ParagraphStyle('Store', parent=bold_style, 
                                     textColor=colors.HexColor("#373737"),
                                     backColor=colors.HexColor(KAGOKITA_BG_COLOR)))
    elif shift_type == 'リクルート':
        return Paragraph(f'<b>{shift_type}</b>', 
                        ParagraphStyle('Store', parent=bold_style, 
                                     textColor=colors.HexColor("#373737"),
                                     backColor=colors.HexColor(RECRUIT_BG_COLOR)))
    
    formatted_parts = []
    formatted_parts.append(Paragraph(f'<b>{shift_type}</b>', bold_style))
    
    for part in shift_parts[1:]:
        if '@' in part:
            time, store = part.split('@')
            store_color = STORE_COLORS.get(store, "#373737")
            formatted_parts.append(
                Paragraph(f'<font color="{store_color}"><b>{time}@{store}</b></font>', bold_style)
            )
        else:
            formatted_parts.append(Paragraph(f'<b>{part}</b>', bold_style))
    
    return formatted_parts

def generate_help_table_pdf(data, year, month, custom_holidays=None):
    """ヘルプ表PDFを生成する関数"""
    if custom_holidays is None:
        custom_holidays = []
        
    buffer = io.BytesIO()
    custom_page_size = (landscape(A4)[0] * 1.2, landscape(A4)[1] * 1.15)
    doc = SimpleDocTemplate(buffer, pagesize=custom_page_size, rightMargin=5*mm, leftMargin=5*mm, topMargin=8*mm, bottomMargin=8*mm)
    elements = []

    pdfmetrics.registerFont(TTFont('NotoSansJP', 'NotoSansJP-VariableFont_wght.ttf'))
    pdfmetrics.registerFont(TTFont('NotoSansJP-Bold', 'NotoSansJP-Bold.ttf'))

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontName='NotoSansJP-Bold',
        fontSize=16,
        textColor=colors.HexColor("#373737")
    )

    bold_style = ParagraphStyle(
        'Bold',
        parent=styles['Normal'],
        fontSize=9,
        fontName='NotoSansJP-Bold',
        alignment=TA_CENTER,
        textColor=colors.HexColor("#373737")
    )

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontName='NotoSansJP-Bold',
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.white
    )

    start_date = pd.Timestamp(year, month, 16)
    next_month = start_date + pd.DateOffset(months=1)
    end_date = next_month.replace(day=15)

    title = Paragraph(f"{start_date.strftime('%Y年%m月%d日')}～{end_date.strftime('%Y年%m月%d日')} ヘルプ表", title_style)
    elements.append(title)
    elements.append(Spacer(1, 3*mm))

    # シフト日数の計算
    shift_counts = calculate_shift_count(data)

    table_data = [
        [
            Paragraph('<font color="white"><b>日付</b></font>', header_style),
            Paragraph('<font color="white"><b>曜日</b></font>', header_style)
        ] + [Paragraph(f'<font color="white"><b>{emp}</b></font>', header_style) 
             for emp in data.columns if emp not in ['日付', '曜日']]
    ]

    for _, row in data.iterrows():
        table_row = [
            Paragraph(f'<b>{row["日付"]}</b>', bold_style),
            Paragraph(f'<b>{row["曜日"]}</b>', bold_style)
        ]
        
        for emp in data.columns:
            if emp not in ['日付', '曜日']:
                shift = row[emp]
                formatted_shift = get_shift_paragraph(shift, row, bold_style, custom_holidays)
                if isinstance(formatted_shift, list):
                    table_row.append(formatted_shift)
                else:
                    table_row.append(formatted_shift)
        
        table_data.append(table_row)

    # シフト日数行を追加
    table_data.append([''] * len(table_data[0]))  # 空行
    count_row = ['シフト日数', ''] + [Paragraph(f'<b>{shift_counts[emp]}</b>', bold_style) 
                                  for emp in data.columns if emp not in ['日付', '曜日']]
    table_data.append(count_row)

    available_width = custom_page_size[0] - 10*mm
    date_width = 45*mm
    weekday_width = 25*mm
    remaining_width = available_width - date_width - weekday_width - 10*mm
    employee_width = remaining_width / (len(data.columns) - 2)
    col_widths = [date_width, weekday_width] + [employee_width] * (len(data.columns) - 2)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'NotoSansJP-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.HexColor("#373737")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#e6f3ff"))  # シフト日数行の背景色
    ])

    for i, (_, row) in enumerate(data.iterrows(), start=1):
        date = pd.to_datetime(row['日付'])
        if row['曜日'] == '日' or date in custom_holidays or jpholiday.is_holiday(date):
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(HOLIDAY_BG_COLOR))
        elif row['曜日'] == '土':
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(SATURDAY_BG_COLOR))

    table.setStyle(table_style)
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_individual_pdf(data, employee, year, month, custom_holidays=None):
    """個別シフト表PDFを生成する関数"""
    if custom_holidays is None:
        custom_holidays = []
        
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=10*mm, leftMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
    elements = []

    pdfmetrics.registerFont(TTFont('NotoSansJP', 'NotoSansJP-VariableFont_wght.ttf'))
    pdfmetrics.registerFont(TTFont('NotoSansJP-Bold', 'NotoSansJP-Bold.ttf'))

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontName='NotoSansJP-Bold',
        fontSize=16,
        textColor=colors.HexColor("#373737")
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontName='NotoSansJP',
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#373737")
    )

    bold_style = ParagraphStyle(
        'Bold',
        parent=normal_style,
        fontName='NotoSansJP-Bold',
        fontSize=9
    )

    header_style = ParagraphStyle(
        'Header',
        parent=bold_style,
        fontSize=10,
        textColor=colors.white
    )

    # 日付範囲の設定
    start_date = pd.Timestamp(year, month, 16)
    next_month = start_date + pd.DateOffset(months=1)
    end_date = next_month.replace(day=15)
    
    # シフト日数を計算してタイトルに追加
    # データを日付でフィルタリング
    filtered_data = pd.DataFrame(data)
    filtered_data.index = pd.date_range(start=start_date, end=end_date)
    filtered_data = filtered_data.loc[start_date:end_date]
    
    # シフト日数を計算
    shift_count = int(filtered_data.apply(lambda x: x.map(count_shift)).sum())
    title = Paragraph(f"{employee}さん {year}年{month}月 シフト表 (シフト日数: {shift_count}日)", title_style)
    elements.append(title)
    elements.append(Spacer(1, 10))

    max_shifts = 1
    for shift in filtered_data[employee]:
        if pd.notna(shift) and shift != '-':
            shift_parts = str(shift).split(',')
            max_shifts = max(max_shifts, len(shift_parts))

    col_widths = [20*mm, 15*mm] + [30*mm] * max_shifts
    table_data = [['日付', '曜日'] + [f'シフト{i+1}' for i in range(max_shifts)]]
    
    for date, row in filtered_data.iterrows():
        weekday = WEEKDAY_JA[date.strftime('%a')]
        shift = row[employee]
        
        if pd.isna(shift) or shift == '' or shift == '-':  # 空文字列のチェックを追加
            row_data = [date.strftime('%m/%d'), weekday] + [Paragraph('', normal_style)] + [''] * (max_shifts - 1)
        else:
            shift_parts = str(shift).split(',')
            shift_type = shift_parts[0]
            
            if shift_type in ['休み', '有給']:
                is_holiday = weekday == '日' or date in custom_holidays or jpholiday.is_holiday(date)
                is_saturday = weekday == '土'
                
                if is_holiday:
                    text_color = HOLIDAY_BG_COLOR2
                    bg_color = HOLIDAY_BG_COLOR
                elif is_saturday:
                    text_color = SATURDAY_BG_COLOR2
                    bg_color = SATURDAY_BG_COLOR
                else:
                    text_color = "#373737"
                    bg_color = HOLIDAY_BG_COLOR
                    
                shift_paragraph = Paragraph(f'<font color="{text_color}"><b>{shift_type}</b></font>', 
                                         ParagraphStyle('Holiday', parent=bold_style, 
                                                      backColor=colors.HexColor(bg_color)))
                row_data = [date.strftime('%m/%d'), weekday, shift_paragraph] + [''] * (max_shifts - 1)
            else:
                formatted_shifts = []
                formatted_shifts.append(Paragraph(f'<b>{shift_type}</b>', bold_style))
                
                for part in shift_parts[1:]:
                    if '@' in part:
                        time, store = part.split('@')
                        store_color = STORE_COLORS.get(store, "#373737")
                        formatted_shifts.append(
                            Paragraph(f'<font color="{store_color}"><b>{time}@{store}</b></font>', bold_style)
                        )
                    else:
                        formatted_shifts.append(Paragraph(f'<b>{part}</b>', bold_style))
                
                formatted_shifts.extend([''] * (max_shifts - len(formatted_shifts)))
                row_data = [date.strftime('%m/%d'), weekday] + formatted_shifts
                
        table_data.append(row_data)

    # シフト日数の表示行を追加
    table_data.append([''] * len(table_data[0]))  # 空行
    count_row = ['シフト日数', '', Paragraph(f'<b>{shift_count}</b>', bold_style)] + [''] * (max_shifts - 1)
    table_data.append(count_row)

    table = Table(table_data, colWidths=col_widths)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'NotoSansJP'),
        ('FONTNAME', (0, 0), (-1, 0), 'NotoSansJP-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#e6f3ff"))  # シフト日数行の背景色
    ])

    for i, row in enumerate(table_data[1:-2], start=1):  # 最後の2行（空行とシフト日数）を除外
        try:
            date = pd.to_datetime(filtered_data.index[i-1])
            if '日' in row[1] or date in custom_holidays or jpholiday.is_holiday(date):
                style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(HOLIDAY_BG_COLOR))
            elif '土' in row[1]:
                style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(SATURDAY_BG_COLOR))
        except IndexError:
            pass

    table.setStyle(style)
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
