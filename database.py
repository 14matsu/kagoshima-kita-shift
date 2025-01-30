import os
from datetime import datetime
import pandas as pd
from supabase import create_client, Client
import streamlit as st
from dotenv import load_dotenv

if not os.environ.get('STREAMLIT_CLOUD'):
    load_dotenv()

class SupabaseDB:
    def __init__(self):
        try:
            # First try loading from .env file
            load_dotenv()
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            
            # If .env values are not available, try streamlit secrets
            if not supabase_url or not supabase_key:
                try:
                    supabase_url = st.secrets["database"]["supabase_url"]
                    supabase_key = st.secrets["database"]["supabase_key"]
                except Exception:
                    pass

            if not supabase_url or not supabase_key:
                st.error("データベース接続情報が見つかりません")
                st.write("Current values:", {
                    "url_exists": bool(supabase_url),
                    "key_exists": bool(supabase_key)
                })
                raise Exception("Supabase の認証情報が設定されていません")
                
            self.supabase: Client = create_client(supabase_url, supabase_key)
            
        except Exception as e:
            st.error(f"データベース接続エラー: {str(e)}")
            raise

    def get_work_days(self, year, month):
        try:
            start_date = f"{year}-{month:02d}-16"
            response = self.supabase.table('work_days')\
                .select("days")\
                .eq('year', year)\
                .eq('month', month)\
                .execute()
            
            return response.data[0]['days'] if response.data else None
            
        except Exception as e:
            st.error(f"労働日数の取得エラー: {e}")
            return None

    def save_work_days(self, year, month, days):
        try:
            # Delete existing record if exists
            self.supabase.table('work_days')\
                .delete()\
                .eq('year', year)\
                .eq('month', month)\
                .execute()
            
            # Insert new record
            data = {
                'year': year,
                'month': month,
                'days': days
            }
            
            self.supabase.table('work_days')\
                .insert(data)\
                .execute()
                
            return True
            
        except Exception as e:
            st.error(f"労働日数の保存エラー: {e}")
            return False
            
    def init_db(self):
        try:
            self.supabase.table('shifts').select("*").limit(1).execute()
            return True
        except Exception as e:
            st.error(f"データベース接続エラー: {e}")
            return False

    def get_shifts(self, start_date, end_date):
        try:
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            response = self.supabase.table('shifts')\
                .select("*")\
                .gte('date', start_date_str)\
                .lte('date', end_date_str)\
                .execute()
            
            if not response.data:
                return pd.DataFrame()
            
            df = pd.DataFrame(response.data)
            df['date'] = pd.to_datetime(df['date'])
            
            pivot_df = df.pivot(index='date', columns='employee', values='shift')
            return pivot_df
            
        except Exception as e:
            st.error(f"シフトデータの取得エラー: {e}")
            return pd.DataFrame()

    def save_shift(self, date, employee, shift_str):
        try:
            date_str = date.strftime('%Y-%m-%d')
            
            # 既存のレコードを削除
            self.supabase.table('shifts')\
                .delete()\
                .match({'date': date_str, 'employee': employee})\
                .execute()
                
            # シフトが'-'の場合は削除のみ行い、新規レコードは作成しない
            if shift_str == '-':
                return True
                
            # データの形式を確認
            data = {
                'date': date_str,
                'employee': employee,
                'shift': shift_str
            }
            
            # Supabaseへの保存を試行
            response = self.supabase.table('shifts')\
                .insert(data)\
                .execute()
            
            return True
        except Exception as e:
            st.error(f"シフトの保存エラー: {e}")
            return False

    def get_custom_holidays(self, year, month):
        """カスタム祝日を取得"""
        try:
            start_date = f"{year}-{month:02d}-16"
            next_month = pd.Timestamp(year, month, 16) + pd.DateOffset(months=1)
            end_date = f"{next_month.year}-{next_month.month:02d}-15"
            
            response = self.supabase.table('custom_holidays')\
                .select("date")\
                .gte('date', start_date)\
                .lte('date', end_date)\
                .execute()
            
            return [pd.Timestamp(item['date']) for item in response.data]
        except Exception as e:
            st.error(f"カスタム祝日の取得エラー: {e}")
            return []

    def add_custom_holiday(self, date):
        """カスタム祝日を追加"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            self.supabase.table('custom_holidays')\
                .insert({'date': date_str})\
                .execute()
            return True
        except Exception as e:
            st.error(f"カスタム祝日の追加エラー: {e}")
            return False

    def remove_custom_holiday(self, date):
        """カスタム祝日を削除"""
        try:
            date_str = date.strftime('%Y-%m-%d')
            self.supabase.table('custom_holidays')\
                .delete()\
                .eq('date', date_str)\
                .execute()
            return True
        except Exception as e:
            st.error(f"カスタム祝日の削除エラー: {e}")
            return False    
        
    def get_employees(self):
        """スタッフ一覧を取得"""
        try:
            response = self.supabase.table('employees')\
                .select("*")\
                .eq('is_active', True)\
                .order('display_order')\
                .execute()
            
            return [item['name'] for item in response.data]
        except Exception as e:
            st.error(f"スタッフ情報の取得エラー: {e}")
            return []

    def get_all_employees(self):
        """全てのスタッフ情報を取得（管理用）"""
        try:
            response = self.supabase.table('employees')\
                .select("*")\
                .order('display_order')\
                .execute()
            
            return response.data
        except Exception as e:
            st.error(f"スタッフ情報の取得エラー: {e}")
            return []

    def add_employee(self, name):
        """新しいスタッフを追加"""
        try:
            # 現在の最大display_orderを取得
            response = self.supabase.table('employees')\
                .select("display_order")\
                .order('display_order', desc=True)\
                .limit(1)\
                .execute()
            
            max_order = response.data[0]['display_order'] if response.data else 0
            
            # 新しいスタッフを追加
            self.supabase.table('employees')\
                .insert({
                    'name': name,
                    'display_order': max_order + 1,
                    'is_active': True
                })\
                .execute()
            return True
        except Exception as e:
            st.error(f"スタッフの追加エラー: {e}")
            return False

    def update_employee(self, id, name=None, display_order=None, is_active=None):
        """スタッフ情報を更新"""
        try:
            update_data = {}
            if name is not None:
                update_data['name'] = name
            if display_order is not None:
                update_data['display_order'] = display_order
            if is_active is not None:
                update_data['is_active'] = is_active

            if update_data:
                self.supabase.table('employees')\
                    .update(update_data)\
                    .eq('id', id)\
                    .execute()
            return True
        except Exception as e:
            st.error(f"スタッフ情報の更新エラー: {e}")
            return False

    def reorder_employees(self, id_order_pairs):
        """スタッフの表示順序を更新"""
        try:
            # 一時的な大きな数値を使用して更新
            temp_order = 10000
            
            for emp_id, new_order in id_order_pairs:
                # まず一時的な値に更新
                self.supabase.table('employees')\
                    .update({'display_order': temp_order + new_order})\
                    .eq('id', emp_id)\
                    .execute()
            
            # 次に実際の値に更新
            for emp_id, new_order in id_order_pairs:
                self.supabase.table('employees')\
                    .update({'display_order': new_order})\
                    .eq('id', emp_id)\
                    .execute()
                
            return True
        except Exception as e:
            st.error(f"表示順序の更新エラー: {e}")
            return False
        
    def delete_employee(self, id):
        """スタッフを完全に削除"""
        try:
            self.supabase.table('employees')\
                .delete()\
                .eq('id', id)\
                .execute()
            
            # 残りのスタッフの表示順序を整理
            response = self.supabase.table('employees')\
                .select("*")\
                .order('display_order')\
                .execute()
            
            # 表示順序を1から振り直し
            for i, emp in enumerate(response.data, 1):
                self.supabase.table('employees')\
                    .update({'display_order': i})\
                    .eq('id', emp['id'])\
                    .execute()
            
            return True
        except Exception as e:
            st.error(f"スタッフの削除エラー: {e}")
            return False
# データベースのシングルトンインスタンスを作成
db = SupabaseDB()