import pandas as pd
import streamlit as st
import jpholiday
from constants import SHIFT_TYPES, STORE_COLORS, FILLED_HELP_BG_COLOR, SATURDAY_BG_COLOR, HOLIDAY_BG_COLOR, KAGOKITA_BG_COLOR, RECRUIT_BG_COLOR, AREAS,HOLIDAY_BG_COLOR2,SATURDAY_BG_COLOR2

def parse_shift(shift_str):
    if pd.isna(shift_str) or shift_str in ['', '-', '休み', 'かご北', 'リクルート'] or isinstance(shift_str, (int, float)):  # 空文字列のチェックを追加
        return shift_str, [], []
    try:
        parts = str(shift_str).split(',')
        shift_type = parts[0] if parts[0] in ['ヘルプ', '有給', '休み', 'かご北', 'リクルート'] else ''
        times_stores = []
        for part in parts[1:]:
            if '@' in part:
                time, store = part.strip().split('@')
                times_stores.append((time, store))
            else:
                times_stores.append((part.strip(), ''))
        times, stores = zip(*times_stores) if times_stores else ([], [])
        return shift_type, list(times), list(stores)
    except:
        return '-', [], []

def format_shifts(val):
    if pd.isna(val) or val == '-' or isinstance(val, (int, float)):
        return val
        
    # かご北とリクルートの処理
    if val == 'かご北':
        return f'<div style="display: flex; align-items: center; justify-content: center;"><span style="background-color: {KAGOKITA_BG_COLOR}; padding: 4px 8px; border-radius: 4px; display: inline-block;">{val}</span></div>'
    
    if val == 'リクルート':
        return f'<div style="display: flex; align-items: center; justify-content: center;"><span style="background-color: {RECRUIT_BG_COLOR}; padding: 4px 8px; border-radius: 4px; display: inline-block;">{val}</span></div>'
    
    try:
        parts = str(val).split(',')
        shift_type = parts[0]
        formatted_shifts = []
        
        for part in parts[1:]:
            if '@' in part:
                time, store = part.strip().split('@')
                if store == 'かご北':
                    formatted_shifts.append(f'<span style="background-color: {KAGOKITA_BG_COLOR}; padding: 2px 4px; border-radius: 4px; display: inline-block; margin: 2px;">{time}@{store}</span>')
                else:
                    color = STORE_COLORS.get(store, "#000000")
                    formatted_shifts.append(f'<span style="color: {color}">{time}@{store}</span>')
            else:
                formatted_shifts.append(part.strip())
        
        if shift_type == 'ヘルプ':
            if formatted_shifts:
                return f'<div style="white-space: pre-line">{shift_type}\n{chr(10).join(formatted_shifts)}</div>'
            else:
                return shift_type
        else:
            return f'<div style="white-space: pre-line">{chr(10).join(formatted_shifts)}</div>' if formatted_shifts else '-'
    except Exception as e:
        print(f"Error formatting shift: {val}. Error: {e}")
        return str(val)
    

def update_session_state_shifts(shifts):
    for date, row in shifts.iterrows():
        if date in st.session_state.shift_data.index:
            for employee, shift in row.items():
                if pd.notna(shift):
                    st.session_state.shift_data.loc[date, employee] = str(shift)
                else:
                    st.session_state.shift_data.loc[date, employee] = ''

# utils.py に追加
def is_holiday(date, custom_holidays=None):
    """祝日判定（カスタム祝日を含む）"""
    if custom_holidays is None:
        custom_holidays = []
    return jpholiday.is_holiday(date) or date in custom_holidays

def highlight_weekend_and_holiday(row, custom_holidays=None):
    """週末と祝日のハイライト（カスタム祝日対応）"""
    weekday = row['曜日']
    date = pd.to_datetime(row['日付'])
    if weekday == '日' or is_holiday(date, custom_holidays):
        return ['background-color: ' + HOLIDAY_BG_COLOR] * len(row)
    elif weekday == '土':
        return ['background-color: ' + SATURDAY_BG_COLOR] * len(row)
    return [''] * len(row)

def get_shift_type_index(shift_type):
    return SHIFT_TYPES.index(shift_type) if shift_type in SHIFT_TYPES else 0

def is_shift_filled(shift):
    if pd.isna(shift) or shift == '' or shift == '-':  # 空文字列のチェックを追加
        return False, []
    shift_type, times, stores = parse_shift(shift)
    return bool(times and stores), stores

def highlight_filled_shifts(row, shift_data):
    styles = [''] * len(row)
    date = pd.to_datetime(row['日付'])
    if date not in shift_data.index:
        return styles
    
    all_stores = [store for stores in AREAS.values() for store in stores]
    for i, store in enumerate(all_stores):
        if store in row.index:
            store_shifts = shift_data.loc[date]
            if any(is_shift_filled(shift)[0] and store in is_shift_filled(shift)[1] for shift in store_shifts if pd.notna(shift)):
                styles[row.index.get_loc(store)] = FILLED_HELP_BG_COLOR
    return styles