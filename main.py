import streamlit as st
st.set_page_config(layout="wide")

import pandas as pd
import jpholiday
from datetime import datetime
import asyncio
from database import db
from pdf_generator import generate_help_table_pdf, generate_individual_pdf
from constants import (
    SHIFT_TYPES, 
    WEEKDAY_JA, 
    AREAS, 
    SATURDAY_BG_COLOR, 
    HOLIDAY_BG_COLOR, 
    HOLIDAY_BG_COLOR2,
    SATURDAY_BG_COLOR2
)
from utils import parse_shift, format_shifts, update_session_state_shifts, highlight_weekend_and_holiday

@st.cache_data(ttl=10)  # 1分間キャッシュ
def get_active_employees():
    """有効なスタッフ一覧を取得"""
    return db.get_employees()

@st.cache_data(ttl=3600)
def get_cached_shifts(year, month):
    start_date = pd.Timestamp(year, month, 16)
    end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    return db.get_shifts(start_date, end_date)

def initialize_shift_data(year, month):
    if 'shift_data' not in st.session_state or st.session_state.current_year != year or st.session_state.current_month != month:
        start_date = pd.Timestamp(year, month, 16)
        end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
        date_range = pd.date_range(start=start_date, end=end_date)
        
        # アクティブな従業員リストを取得
        employees = get_active_employees()
        
        # シフトデータを取得
        shifts = get_cached_shifts(year, month)
        
        # 新しいDataFrameを作成
        st.session_state.shift_data = pd.DataFrame(
            index=date_range,
            columns=employees,
            data=''
        )
        
        # 既存のシフトデータがあれば更新
        if not shifts.empty:
            for emp in employees:
                if emp in shifts.columns:
                    st.session_state.shift_data[emp].update(shifts[emp])
        
        # カスタム祝日を取得
        custom_holidays = db.get_custom_holidays(year, month)
        
        # 土日、祝日、カスタム祝日に'休み'を設定
        for date in date_range:
            if (date.weekday() >= 5 or  # 5=土曜日, 6=日曜日
                jpholiday.is_holiday(date) or  # 通常の祝日
                date in custom_holidays):  # カスタム祝日
                st.session_state.shift_data.loc[date, :] = '休み'
        
        st.session_state.current_year = year
        st.session_state.current_month = month

def calculate_shift_count(shift_data):
    def count_shift(shift):
        if pd.isna(shift) or shift == '休み':
            return 0
        return 1  # 「休み」以外は全てカウント（ハイフンを含む）

    return shift_data.apply(lambda x: x.map(count_shift)).sum()


def display_shift_table(selected_year, selected_month):
    start_date = pd.Timestamp(selected_year, selected_month, 16)
    end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    
    # アクティブな従業員リストを取得
    employees = get_active_employees()
    
    # シフトデータをコピー
    display_data = st.session_state.shift_data.loc[start_date:end_date].copy()
    
    # 日付と曜日の列を追加
    display_data.insert(0, '日付', display_data.index.strftime('%Y-%m-%d'))
    display_data.insert(1, '曜日', display_data.index.strftime('%a').map(WEEKDAY_JA))
    
    # 必要な列のみを選択（日付、曜日、アクティブな従業員）
    keep_columns = ['日付', '曜日'] + [emp for emp in employees if emp in display_data.columns]
    display_data = display_data[keep_columns]
    
    # 新しい従業員の列を追加（データがない場合は空文字列を設定）
    for emp in employees:
        if emp not in display_data.columns:
            display_data[emp] = ''

    # スタイルの設定
    st.markdown("""
    <style>
    table {
        font-size: 16px;
        width: 100%;
    }
    th, td {
        text-align: center;
        padding: 10px;
        white-space: pre-line;
        vertical-align: middle;
    }
    th {
        background-color: #f0f0f0;
    }
    .shift-count {
        font-weight: bold;
        background-color: #e6f3ff;
    }
    /* シフトバッジのスタイル */
    td span.shift-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        margin: 2px;
    }
    </style>
    """, unsafe_allow_html=True)

    # カスタム祝日の管理UI
    with st.expander("カスタム祝日の管理"):
        custom_holidays = db.get_custom_holidays(selected_year, selected_month)
        
        # カスタム祝日の追加
        col1, col2 = st.columns(2)
        with col1:
            new_holiday = st.date_input(
                "祝日として設定する日付を選択",
                min_value=start_date.date(),
                max_value=end_date.date()
            )
        with col2:
            if st.button("祝日として追加"):
                if db.add_custom_holiday(pd.Timestamp(new_holiday)):
                    st.session_state.shift_data.loc[pd.Timestamp(new_holiday), :] = '休み'
                    st.success("カスタム祝日を追加しました")
                    st.rerun()
        
        # 現在のカスタム祝日一覧
        if custom_holidays:
            st.write("現在のカスタム祝日:")
            for holiday in sorted(custom_holidays):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{holiday.strftime('%Y年%m月%d日')}")
                with col2:
                    if st.button("削除", key=f"delete_{holiday}"):
                        if db.remove_custom_holiday(holiday):
                            holiday_date = pd.Timestamp(holiday)
                            if (holiday_date.weekday() < 5 and  # 平日
                                not jpholiday.is_holiday(holiday_date)):  # 通常の祝日でない
                                st.session_state.shift_data.loc[holiday_date, :] = ''
                            st.success("カスタム祝日を削除しました")
                            st.rerun()
        else:
            st.write("カスタム祝日は設定されていません")

    # ページネーション関連の設定
    items_per_page = 15
    total_pages = len(display_data) // items_per_page + (1 if len(display_data) % items_per_page > 0 else 0)
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    col1, col2, col3 = st.columns([2,3,2])
    with col1:
        if st.button('◀◀ 最初'):
            st.session_state.current_page = 1
        if st.button('◀ 前へ') and st.session_state.current_page > 1:
            st.session_state.current_page -= 1
    with col2:
        st.write(f'ページ {st.session_state.current_page} / {total_pages}')
    with col3:
        if st.button('最後 ▶▶'):
            st.session_state.current_page = total_pages
        if st.button('次へ ▶') and st.session_state.current_page < total_pages:
            st.session_state.current_page += 1

    start_idx = (st.session_state.current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_display_data = display_data.iloc[start_idx:end_idx]
    
    # 各行のフォーマット時に現在の日付情報を保存
    styled_rows = []
    for idx, row in page_display_data.iterrows():
        # 現在の日付をセッションステートに保存
        st.session_state.current_date = idx
        # 行のスタイリングを適用
        styled_rows.append(row)
    
    page_display_data = pd.DataFrame(styled_rows)
    page_display_data = page_display_data.reset_index(drop=True)

    def style_val(val, row):
        if pd.isna(val) or val not in ['休み', '有給']:
            return format_shifts(val)
            
        weekday = row['曜日']
        date = pd.to_datetime(row['日付'])
        
        is_holiday = weekday == '日' or date in custom_holidays or jpholiday.is_holiday(date)
        is_saturday = weekday == '土'
        
        if is_holiday:
            text_color = HOLIDAY_BG_COLOR2  # 日曜・祝日は赤色
            bg_color = HOLIDAY_BG_COLOR
        elif is_saturday:
            text_color = SATURDAY_BG_COLOR2  # 土曜は青色
            bg_color = SATURDAY_BG_COLOR
        else:
            text_color = "#373737"  # 平日はデフォルトの色
            bg_color = HOLIDAY_BG_COLOR
            
        return f'<div style="display: flex; align-items: center; justify-content: center;"><span style="color: {text_color}; background-color: {bg_color}; padding: 4px 8px; border-radius: 4px; display: inline-block;">{val}</span></div>'

    # スタイルを適用
    employees = get_active_employees()
    for emp in employees:
        styled_rows = []
        for idx, row in page_display_data.iterrows():
            styled_val = style_val(row[emp], row)
            styled_rows.append(styled_val)
        page_display_data[emp] = styled_rows

    # スタイリングにカスタム祝日を反映
    styled_df = page_display_data.style.apply(
        lambda row: highlight_weekend_and_holiday(row, custom_holidays),
        axis=1
    )
    
    st.write(styled_df.hide(axis="index").to_html(escape=False), unsafe_allow_html=True)
    st.markdown("### シフト日数")
    shift_counts = calculate_shift_count(display_data[employees])
    shift_count_df = pd.DataFrame([shift_counts], columns=employees)
    styled_shift_count = shift_count_df.style.format("{:.1f}")\
                                           .set_properties(**{'class': 'shift-count'})
    st.write(styled_shift_count.hide(axis="index").to_html(escape=False), unsafe_allow_html=True)

    # Add work days display
    work_days = db.get_work_days(selected_year, selected_month)
    if work_days is not None:
        st.markdown(f"### {start_date.strftime('%Y年%m月%d日')}～{end_date.strftime('%Y年%m月%d日')}の必要日数")
        st.markdown(f"<h2 style='text-align: left; color: #1E88E5; font-size: 28px;'><strong>{work_days}</strong> 日</h2>", unsafe_allow_html=True)

    # ヘルプ表PDFのダウンロードボタンを追加
    if st.button('ヘルプ表をPDFでダウンロード'):
        pdf = generate_help_table_pdf(display_data, selected_year, selected_month, custom_holidays)
        st.download_button(
            label="ヘルプ表PDFをダウンロード",
            data=pdf,
            file_name=f"かごしま北_{selected_year}_{selected_month}.pdf",
            mime="application/pdf"
        )

def display_employee_management():
    st.header("スタッフ管理")
    
    # 新しいスタッフの追加
    with st.expander("新しいスタッフを追加"):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_name = st.text_input("スタッフ名")
        with col2:
            add_clicked = st.button("追加", type="primary")
            
        if add_clicked and new_name:
            if db.add_employee(new_name):
                st.success(f"{new_name}を追加しました")
                st.rerun()
            else:
                st.error("スタッフの追加に失敗しました")

    # スタッフ一覧と管理
    employees = db.get_all_employees()
    if employees:
        st.write("### 現在のスタッフ一覧")
        st.write("↑↓ボタンで表示順序を変更できます")
        
        # スタッフ一覧を表として表示
        for i, emp in enumerate(employees):
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 1, 1])
                
                with col1:
                    st.write(f"{emp['display_order']}.")
                
                with col2:
                    st.write(f"{emp['name']}")
                
                with col3:
                    active = st.toggle('有効', value=emp['is_active'], key=f"active_{emp['id']}")
                    if active != emp['is_active']:
                        if db.update_employee(emp['id'], is_active=active):
                            st.success("状態を更新しました")
                            st.rerun()
                
                with col4:
                    # 上下移動ボタンを縦に配置
                    if i > 0:
                        if st.button("↑", key=f"up_{emp['id']}", help="上に移動"):
                            prev_emp = employees[i-1]
                            if db.reorder_employees([
                                (emp['id'], prev_emp['display_order']),
                                (prev_emp['id'], emp['display_order'])
                            ]):
                                st.rerun()
                    
                    if i < len(employees)-1:
                        if st.button("↓", key=f"down_{emp['id']}", help="下に移動"):
                            next_emp = employees[i+1]
                            if db.reorder_employees([
                                (emp['id'], next_emp['display_order']),
                                (next_emp['id'], emp['display_order'])
                            ]):
                                st.rerun()
                
                with col5:
                    # 削除ボタン
                    if st.button("🗑️", key=f"delete_{emp['id']}", help="削除"):
                        # 削除確認用のモーダル
                        if 'delete_confirm' not in st.session_state:
                            st.session_state.delete_confirm = False
                        
                        st.session_state.delete_confirm = True
                        st.session_state.delete_target = emp
                
                # 区切り線を追加
                st.divider()

        # 削除確認モーダル
        if getattr(st.session_state, 'delete_confirm', False):
            emp = st.session_state.delete_target
            st.warning(f"⚠️ {emp['name']}を削除してもよろしいですか？")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("はい、削除します"):
                    if db.delete_employee(emp['id']):
                        st.success(f"{emp['name']}を削除しました")
                        del st.session_state.delete_confirm
                        del st.session_state.delete_target
                        st.rerun()
            with col2:
                if st.button("キャンセル"):
                    del st.session_state.delete_confirm
                    del st.session_state.delete_target
                    st.rerun()
    else:
        st.info("スタッフが登録されていません")

def initialize_session_state():
    if 'editing_shift' not in st.session_state:
        st.session_state.editing_shift = False
    if 'current_shift' not in st.session_state:
        st.session_state.current_shift = None
    if 'selected_dates' not in st.session_state:
        st.session_state.selected_dates = {}

def update_shift_input(current_shift):
    initialize_session_state()
    
    if not st.session_state.editing_shift:
        st.session_state.current_shift = current_shift
        st.session_state.editing_shift = True
    
    shift_type, times, stores = parse_shift(st.session_state.current_shift)
    
    new_shift_type = st.selectbox('種類', SHIFT_TYPES, 
                                 index=SHIFT_TYPES.index(shift_type) 
                                 if shift_type in SHIFT_TYPES else 0)
    
    if new_shift_type == 'ヘルプ':
        num_shifts = st.number_input('希望店舗数', min_value=1, max_value=5, value=len(times) or 1)
        
        new_times = []
        new_stores = []
        for i in range(num_shifts):
            col1, col2, col3 = st.columns(3)
            with col1:
                area_options = [area for area in AREAS.keys() if area != 'なし']
                current_area = next((area for area, stores_list in AREAS.items() 
                                  if i < len(stores) and stores[i] in stores_list), 
                                  area_options[0])
                area = st.selectbox(f'エリア {i+1}', area_options, 
                                  index=area_options.index(current_area), 
                                  key=f'shift_area_{i}')
                
            with col2:
                store_options = AREAS[area]
                current_store = stores[i] if i < len(stores) and stores[i] in store_options else store_options[0]
                store = st.selectbox(f'店舗 {i+1}', store_options, 
                                   index=store_options.index(current_store), 
                                   key=f'shift_store_{i}')
            
            with col3:
                time = st.text_input(f'時間 {i+1}', value=times[i] if i < len(times) else '')
            
            if time and store:
                new_times.append(time)
                new_stores.append(store)
        
        if new_times and new_stores:
            new_shift_str = f"{new_shift_type},{','.join([f'{t}@{s}' for t, s in zip(new_times, new_stores)])}"
        else:
            new_shift_str = new_shift_type
    else:
        new_shift_str = new_shift_type
    
    st.session_state.current_shift = new_shift_str

    repeat_weekly = st.checkbox('繰り返し登録をする', help='同一シフトを一括登録します')
    
    selected_dates = []
    if repeat_weekly:
        period_start = pd.Timestamp(st.session_state.current_year, st.session_state.current_month, 16)
        period_end = (period_start + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
        
        dates = pd.date_range(start=period_start, end=period_end).tolist()
        
        if dates:
            st.write('登録する日付を選択:')
            
            if 'selected_dates' not in st.session_state:
                st.session_state.selected_dates = {d.strftime("%Y/%m/%d"): True for d in dates}
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button('全て選択'):
                    for d in dates:
                        st.session_state.selected_dates[d.strftime("%Y/%m/%d")] = True
                    st.rerun()
            with col2:
                if st.button('全て解除'):
                    for d in dates:
                        st.session_state.selected_dates[d.strftime("%Y/%m/%d")] = False
                    st.rerun()
            
            for d in dates:
                date_str = d.strftime("%Y/%m/%d")
                st.session_state.selected_dates[date_str] = st.checkbox(
                    f'{date_str} ({WEEKDAY_JA[d.strftime("%a")]})', 
                    value=st.session_state.selected_dates.get(date_str, True),
                    key=f'date_checkbox_{date_str}'
                )
                if st.session_state.selected_dates[date_str]:
                    selected_dates.append(d)
    
    # クリアボタンと保存ボタンの配置
    col1, col2 = st.columns(2)
    save_clicked = None
    clear_clicked = None
    
    with col1:
        save_clicked = st.button('保存')
    with col2:
        clear_clicked = st.button('シフト取り消し')
        
    if clear_clicked:
        new_shift_str = '-'
        st.session_state.current_shift = new_shift_str
        
    return new_shift_str, repeat_weekly, selected_dates, save_clicked, clear_clicked

def main():
    st.title('かごしま北シフト管理📝')

    # サイドバーにタブを追加
    with st.sidebar:
        selected_tab = st.radio(
            "メニュー",
            ["シフト管理", "スタッフ管理"],
            key="sidebar_tab"
        )

    if selected_tab == "シフト管理":
        with st.sidebar:
            st.header('設定')
            current_year = datetime.now().year
            years = range(current_year - 1, current_year + 10)
            current_year_index = years.index(current_year)
            selected_year = st.selectbox('年を選択', years, index=current_year_index, key='year_selector')
            selected_month = st.selectbox('月を選択', range(1, 13), key='month_selector')

            # Add work days registration section
            st.header('月間労働日数の登録')
            work_days = st.number_input('労働日数を記入', min_value=0, max_value=31, 
                                      value=db.get_work_days(selected_year, selected_month) or 0)
            if st.button('労働日数を保存'):
                if db.save_work_days(selected_year, selected_month, work_days):
                    st.success('労働日数を保存しました')
                else:
                    st.error('労働日数の保存に失敗しました')

            initialize_shift_data(selected_year, selected_month)
            shifts = get_cached_shifts(selected_year, selected_month)
            update_session_state_shifts(shifts)

            st.header('シフト登録/修正')
            employees = get_active_employees()
            employee = st.selectbox('従業員を選択', employees)
            
            start_date = datetime(selected_year, selected_month, 16)
            end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
            default_date = max(min(datetime.now().date(), end_date.date()), start_date.date())
            date = st.date_input('日付を選択', min_value=start_date.date(), max_value=end_date.date(), value=default_date)
            
            date = pd.Timestamp(date)
            current_shift = st.session_state.shift_data.loc[date, employee] if date in st.session_state.shift_data.index else '休み'
            if pd.isna(current_shift) or isinstance(current_shift, (int, float)):
                current_shift = '休み'
            
            new_shift_str, repeat_weekly, selected_dates, save_clicked, clear_clicked = update_shift_input(current_shift)

            if save_clicked or clear_clicked:
                action_text = 'シフト取り消し' if clear_clicked else '保存'
                try:
                    with st.spinner(f'{action_text}中...'):
                        if not repeat_weekly:
                            save_result = db.save_shift(date, employee, new_shift_str)
                        else:
                            save_result = True
                            for target_date in selected_dates:
                                result = db.save_shift(target_date, employee, new_shift_str)
                                save_result = save_result and result
                        
                        if save_result:
                            st.session_state.shift_data.loc[date, employee] = new_shift_str
                            if repeat_weekly and selected_dates:
                                for next_date in selected_dates:
                                    if next_date in st.session_state.shift_data.index:
                                        st.session_state.shift_data.loc[next_date, employee] = new_shift_str
                            st.session_state.editing_shift = False
                            st.success(f'{action_text}しました')
                            
                            # キャッシュをクリアして再読み込み
                            current_month = date.replace(day=1)
                            next_month = current_month + pd.DateOffset(months=1)
                            previous_month = current_month - pd.DateOffset(months=1)
                            get_cached_shifts.clear()
                            get_cached_shifts(current_month.year, current_month.month)
                            get_cached_shifts(next_month.year, next_month.month)
                            get_cached_shifts(previous_month.year, previous_month.month)
                            
                            st.rerun()
                        else:
                            st.error(f'{action_text}に失敗しました')
                except Exception as e:
                    st.error(f'{action_text}中にエラーが発生しました: {str(e)}')

            st.header('個別PDFのダウンロード')
            selected_employee = st.selectbox('従業員を選択', employees, key='pdf_employee_selector')
            
            if st.button('PDFを生成'):
                employee_data = st.session_state.shift_data[selected_employee]
                pdf_buffer = generate_individual_pdf(employee_data, selected_employee, selected_year, selected_month)
                start_date = pd.Timestamp(selected_year, selected_month, 16)
                end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
                file_name = f'{selected_employee}さん_{start_date.strftime("%Y年%m月%d日")}～{end_date.strftime("%Y年%m月%d日")}_シフト.pdf'
                st.download_button(
                    label=f"{selected_employee}さんのPDFをダウンロード",
                    data=pdf_buffer.getvalue(),
                    file_name=file_name,
                    mime="application/pdf"
                )

        display_shift_table(selected_year, selected_month)
    else:
        display_employee_management()

if __name__ == '__main__':
    if db.init_db():
        main()
    else:
        st.error("データベース接続に失敗しました")