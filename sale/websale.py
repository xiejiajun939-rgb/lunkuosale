# -*- coding: utf-8 -*-
"""
订单业绩统计工具 - 完整版（维度切换 + 向量化重构）
管理员账号：admin / 1234567890
子账号存储在 Supabase 的 sub_accounts 表中
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io
import hashlib
import time
import re
import numpy as np
from supabase import create_client
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI

st.set_page_config(page_title="业绩统计工具", layout="wide", page_icon="📊")

# ========== 预编译正则表达式 ==========
ANCHOR_PATTERN = re.compile(r'主播[：:]([^_]+)')
PRODUCT_CODE_PATTERN = re.compile(r'_([A-Za-z0-9]{14,})')

# ========== 常量映射 ==========
SEASON_MAP = {"1": "春", "2": "夏", "3": "秋", "4": "冬"}
SIZE_MAP = {"001": "S", "002": "M", "003": "L", "004": "XL", "008": "均码"}

# ========== 自定义CSS（保留原有，仅注释掉selectbox标签隐藏） ==========
st.markdown("""
<style>
    .custom-main-title { font-size: 28px !important; font-weight: 600 !important; margin-top: -0.5rem !important; margin-bottom: 0.25rem !important; padding-bottom: 0 !important; color: #1e293b !important; }
    .welcome-text { font-size: 14px !important; color: #475569 !important; margin-top: 0 !important; margin-bottom: 0.5rem !important; }
    h1 { font-size: 28px !important; margin-top: -0.5rem !important; margin-bottom: 0.25rem !important; color: #1e293b !important; }
    h2 { font-size: 24px !important; margin-top: 0.5rem !important; margin-bottom: 0.25rem !important; font-weight: 500 !important; color: #1e293b !important; }
    h3 { font-size: 20px !important; margin-top: 0.5rem !important; margin-bottom: 0.25rem !important; font-weight: 500 !important; color: #1e293b !important; }
    h4 { font-size: 18px !important; margin-top: 0.5rem !important; margin-bottom: 0.25rem !important; font-weight: 500 !important; color: #1e293b !important; }
    h5, h6 { font-size: 16px !important; margin-top: 0.25rem !important; margin-bottom: 0.25rem !important; color: #1e293b !important; }
    hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; border-color: #e2e8f0 !important; }
    .css-1d391kg h1, .css-1d391kg h2, .css-1d391kg h3 { font-size: 1.2rem !important; }
    div[data-testid="stButton"] button {
        padding: 4px 12px !important;
        font-size: 13px !important;
        border-radius: 6px !important;
        background-color: #f8fafc !important;
        border: 1px solid #d1d5db !important;
        color: #1f2937 !important;
        white-space: nowrap !important;
    }
    div[data-testid="stButton"] button:hover {
        background-color: #e2e8f0 !important;
    }
    /* 不隐藏 selectbox 标签，保留可见 */
    div[data-testid="stDateInput"] label { display: none !important; }
    .date-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .css-1d391kg, .css-1d391kg .st-emotion-cache-1v0mbdj { background: #f1f5f9 !important; }
    .stDataFrame, .stTable, .stMarkdown table { color: #1e293b !important; }
    .stMarkdown td, .stMarkdown th { color: #1e293b !important; }
    /* KPI卡片样式 */
    .glass-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.9), rgba(245,247,250,0.9));
        border-radius: 16px;
        padding: 22px 24px;
        border: 1px solid rgba(0,0,0,0.06);
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        margin-bottom: 8px;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 48px rgba(0,0,0,0.12);
    }
    .kpi-number {
        font-size: 38px;
        font-weight: 700;
        letter-spacing: -0.5px;
        background: linear-gradient(135deg, #0f172a 60%, #475569);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .kpi-label { color: #475569; font-size: 13px; font-weight: 500; letter-spacing: 0.3px; text-transform: uppercase; }
    .change-up { color: #16a34a; font-weight: 600; }
    .change-down { color: #dc2626; font-weight: 600; }
    .change-neutral { color: #64748b; }
    .progress-track { width: 100%; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; margin: 8px 0 4px 0; }
    .progress-fill { height: 100%; border-radius: 3px; transition: width 0.8s ease; }
    .rank-item { display: flex; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
    .rank-item:last-child { border-bottom: none; }
    .rank-emoji { font-size: 22px; width: 36px; }
    .rank-name { flex: 1; color: #1e293b; font-size: 14px; }
    .rank-value { color: #16a34a; font-weight: 600; font-size: 14px; width: 80px; text-align: right; }
    .rank-bar-bg { width: 100px; height: 6px; background: #e2e8f0; border-radius: 3px; }
    .rank-bar-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #22c55e, #14b8a6); }
    .section-title { color: #1e293b; font-size: 16px; font-weight: 600; margin-bottom: 12px; letter-spacing: 0.2px; display: flex; align-items: center; gap: 8px; }
    .section-title .badge { background: rgba(34,197,94,0.15); color: #16a34a; font-size: 11px; padding: 2px 10px; border-radius: 12px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ========== Supabase 连接 ==========
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase 连接失败：{e}")
        return None

supabase = init_supabase()

def get_table_name(base_name, suffix=None):
    if suffix is None:
        suffix = st.session_state.get("table_suffix", "")
    return f"{base_name}{suffix}"

# ========== 映射表加载与关联（向量化） ==========
@st.cache_data(ttl=600)
def load_mapping(supabase_client) -> pd.DataFrame:
    if supabase_client is None:
        return pd.DataFrame()
    try:
        resp = supabase_client.table("mapping").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df['anchor_name'] = df['anchor_name'].fillna('NONE')
            df['shop_name'] = df['shop_name'].fillna('')
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载映射表失败: {e}")
        return pd.DataFrame()

def add_mapping_columns(df: pd.DataFrame, mapping_df: pd.DataFrame,
                        shop_col: str = 'shop_name',
                        anchor_col: str = 'anchor') -> pd.DataFrame:
    if df.empty or mapping_df.empty:
        df['org_name'] = None
        df['dept'] = None
        return df
    df = df.copy()
    if anchor_col not in df.columns:
        df[anchor_col] = 'NONE'
    else:
        df[anchor_col] = df[anchor_col].fillna('NONE')
    mapping_df['key'] = mapping_df['shop_name'] + '||' + mapping_df['anchor_name']
    mapping_shop_only = mapping_df[mapping_df['anchor_name'] == 'NONE'].copy()
    map_exact = mapping_df.set_index('key')[['org_name', 'dept']].to_dict('index')
    map_shop = mapping_shop_only.set_index('shop_name')[['org_name', 'dept']].to_dict('index')
    df['key'] = df[shop_col] + '||' + df[anchor_col]
    df['org_name'] = df['key'].map(lambda k: map_exact.get(k, {}).get('org_name'))
    df['dept'] = df['key'].map(lambda k: map_exact.get(k, {}).get('dept'))
    unmatched = df['org_name'].isna()
    if unmatched.any():
        df.loc[unmatched, 'org_name'] = df.loc[unmatched, shop_col].map(
            lambda s: map_shop.get(s, {}).get('org_name') if s in map_shop else None
        )
        df.loc[unmatched, 'dept'] = df.loc[unmatched, shop_col].map(
            lambda s: map_shop.get(s, {}).get('dept') if s in map_shop else None
        )
    df.drop(columns=['key'], inplace=True)
    return df

# ========== 向量化解析函数 ==========
def extract_anchor_vectorized(remarks: pd.Series) -> pd.Series:
    return remarks.astype(str).str.extract(r'主播[：:]([^_]+)', expand=False)

def parse_product_code_vectorized(remarks: pd.Series) -> pd.DataFrame:
    product_codes = remarks.astype(str).str.extract(r'_([A-Za-z0-9]{14,})', expand=False)
    result = pd.DataFrame(index=remarks.index)
    result['product_code'] = product_codes
    result['style_code'] = product_codes.str[:8]
    result['brand'] = product_codes.str[0]
    result['year'] = product_codes.str[1:3]
    result['season_code'] = product_codes.str[3:4]
    result['season'] = result['season_code'].map(SEASON_MAP)
    result['product_category'] = product_codes.str[4:5]
    result['style'] = product_codes.str[5:8]
    result['color_code'] = product_codes.str[8:11]
    result['size_code'] = product_codes.str[11:14].map(SIZE_MAP)
    return result

def process_orders_vectorized(df_orders: pd.DataFrame, master_df: pd.DataFrame) -> pd.DataFrame:
    if df_orders.empty:
        return pd.DataFrame()
    df = df_orders.copy()
    parsed = parse_product_code_vectorized(df['备注'])
    df = pd.concat([df, parsed], axis=1)
    df['amount'] = pd.to_numeric(df['金额/时间'], errors='coerce').fillna(0)
    df['ship_amount'] = df['amount'].clip(lower=0)
    df['return_amount'] = (-df['amount']).clip(lower=0)
    df['net_amount'] = df['amount']
    df['sale_date'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
    df['shop_name'] = df['备注'].astype(str).str.split('_').str[-1]
    df['shop_name'] = df['shop_name'].str.replace(r'^商店[：:]', '', regex=True).str.strip()
    if not master_df.empty and 'style_code' in master_df.columns:
        master_subset = master_df[['style_code', 'image_url', 'category', 'has_newbie_coupon']].copy()
        master_subset = master_subset.rename(columns={'category': 'master_category'})
        master_subset = master_subset.drop_duplicates(subset='style_code', keep='first')
        df = df.merge(master_subset, on='style_code', how='left')
    else:
        df['image_url'] = None
        df['master_category'] = None
        df['has_newbie_coupon'] = False
    agg_cols = ['ship_amount', 'return_amount', 'net_amount']
    agg_rules = {col: 'sum' for col in agg_cols}
    other_cols = ['sale_date', 'shop_name', 'product_code', 'style_code', 'brand',
                  'year', 'season', 'product_category', 'style', 'color_code',
                  'size_code', 'image_url', 'master_category']
    for col in other_cols:
        agg_rules[col] = 'first'
    grouped = df.groupby('remark', as_index=False).agg(agg_rules)
    return grouped

def rebuild_daily_from_product_vectorized(df_product: pd.DataFrame, suffix: str = "") -> tuple:
    if df_product.empty:
        return True, "商品销售表无数据", []
    df = df_product.copy()
    df['sale_date'] = pd.to_datetime(df['sale_date'])
    if suffix == "_all":
        df['anchor'] = extract_anchor_vectorized(df['remark'].astype(str))
        group_col = 'anchor'
    else:
        group_col = 'shop_name'
    daily_agg = df.groupby(['sale_date', group_col], as_index=False)['net_amount'].sum()
    daily_agg.rename(columns={'net_amount': 'amount', group_col: '店铺名称'}, inplace=True)
    daily_agg = daily_agg.sort_values(['店铺名称', 'sale_date'])
    daily_agg['cumulative_amount'] = daily_agg.groupby('店铺名称')['amount'].cumsum().round(2)
    records = daily_agg.to_dict(orient='records')
    return True, f"成功聚合 {len(records)} 条每日记录", records

def extract_anchor(remark):
    if not isinstance(remark, str):
        return None
    match = ANCHOR_PATTERN.search(remark)
    return match.group(1).strip() if match else None

# ========== 子账号数据库操作（保留原有） ==========
def load_sub_accounts_from_db():
    if supabase is None:
        return {}
    try:
        resp = supabase.table("sub_accounts").select("*").execute()
        if resp.data:
            sub_users = {}
            for row in resp.data:
                perms = row.get("permissions", {})
                if not perms and "allowed_tabs" in row:
                    perms = {"": row["allowed_tabs"], "_live": row["allowed_tabs"], "_all": row["allowed_tabs"]}
                sub_users[row["username"]] = {
                    "password": row["password"],
                    "role": row.get("role", "viewer"),
                    "default_suffix": row.get("default_suffix", ""),
                    "permissions": perms,
                    "filter_platform": row.get("filter_platform", "all"),
                    "filter_shop_names": row.get("filter_shop_names", [])
                }
            return sub_users
        else:
            return {}
    except Exception as e:
        st.error(f"加载子账号失败：{e}")
        return {}

def save_sub_account_to_db(username, info):
    if supabase is None:
        return False, "Supabase 未连接"
    try:
        data = {
            "username": username,
            "password": info["password"],
            "role": info["role"],
            "default_suffix": info["default_suffix"],
            "permissions": info.get("permissions", {}),
            "filter_platform": info.get("filter_platform", "all"),
            "filter_shop_names": info.get("filter_shop_names", [])
        }
        supabase.table("sub_accounts").upsert(data, on_conflict="username").execute()
        return True, "保存成功"
    except Exception as e:
        return False, str(e)

def delete_sub_account_from_db(username):
    if supabase is None:
        return False, "Supabase 未连接"
    try:
        supabase.table("sub_accounts").delete().eq("username", username).execute()
        return True, "删除成功"
    except Exception as e:
        return False, str(e)

def get_all_users():
    users = {
        "admin": {"password": "1234567890", "role": "admin", "default_suffix": ""},
        "XDZ01": {"password": "94949468", "role": "user", "default_suffix": ""},
        "ZBZ01": {"password": "123456", "role": "user", "default_suffix": "_live"}
    }
    if "sub_users" in st.session_state:
        for username, info in st.session_state.sub_users.items():
            users[username] = info
    return users

def login():
    st.title("🔐 数据罗盘 - 登录")
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")
        if submitted:
            users = get_all_users()
            if username in users and users[username]["password"] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = users[username]["role"]
                st.session_state.table_suffix = users[username]["default_suffix"]
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("用户名或密码错误")

# ========== 硅基流动 AI 调用 ==========
@st.cache_resource
def get_siliconflow_client():
    try:
        api_key = st.secrets["SILICONFLOW_API_KEY"]
        client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
        return client
    except Exception as e:
        st.error(f"硅基流动客户端初始化失败: {e}")
        return None

@st.cache_data(ttl=3600)
def get_ai_summary(prompt: str, context: str, model: str) -> str:
    client = get_siliconflow_client()
    if not client:
        return "⚠️ AI 服务暂不可用，请稍后再试。"
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": context}]
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(model=model, messages=messages, stream=False)
            return response.choices[0].message.content
        except Exception as e:
            if attempt == max_retries - 1:
                return f"❌ AI 总结失败，请稍后再试。错误: {str(e)}"
            time.sleep(1 * (2 ** attempt))
    return "⚠️ AI 服务暂时无法响应。"

# ========== 初始化 session_state ==========
if "sub_users" not in st.session_state:
    st.session_state.sub_users = load_sub_accounts_from_db()
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    login()
    st.stop()

# ========== 主页面 ==========
st.markdown('<div class="custom-main-title">📊 抖音&视频号商品销售分析罗盘</div>', unsafe_allow_html=True)
st.markdown(f'<div class="welcome-text">欢迎，**{st.session_state.username}** ({"管理员" if st.session_state.role == "admin" else ("子账号" if st.session_state.role == "viewer" else "成员")})</div>', unsafe_allow_html=True)
st.markdown("---")

if "df_all_daily" not in st.session_state:
    st.session_state.df_all_daily = None
if "target_dict" not in st.session_state:
    st.session_state.target_dict = {}
if "latest_date" not in st.session_state:
    st.session_state.latest_date = None
if "uploaded_file_hash" not in st.session_state:
    st.session_state.uploaded_file_hash = None
if "daily_latest" not in st.session_state:
    st.session_state.daily_latest = None
if "monthly_actual" not in st.session_state:
    st.session_state.monthly_actual = None
if "processing_upload" not in st.session_state:
    st.session_state.processing_upload = False
if "mapping_df" not in st.session_state:
    st.session_state.mapping_df = load_mapping(supabase)

# ========== 数据权限过滤 ==========
def apply_data_permission(df, username=None, role=None):
    if username is None:
        username = st.session_state.get("username", "")
    if role is None:
        role = st.session_state.get("role", "")
    if role == "admin" or username == "admin":
        return df
    user_info = st.session_state.sub_users.get(username)
    if not user_info:
        return df
    filter_platform = user_info.get("filter_platform", "all")
    filter_shop_names = user_info.get("filter_shop_names", [])
    if filter_platform != "all":
        if "shop_name" in df.columns:
            if filter_platform == "抖音":
                df = df[df["shop_name"].str.contains("抖音", case=False, na=False)]
            elif filter_platform == "视频号":
                df = df[df["shop_name"].str.contains("视频号", case=False, na=False)]
    if filter_shop_names:
        if "shop_name" in df.columns:
            df = df[df["shop_name"].isin(filter_shop_names)]
        elif "anchor" in df.columns:
            df = df[df["anchor"].isin(filter_shop_names)]
    return df

# ========== 日期快捷按钮（修改：昨日、近7天、上周） ==========
def date_quick_buttons(start_key, end_key, default_start=None, default_end=None, min_date=None, max_date=None):
    if start_key not in st.session_state:
        st.session_state[start_key] = default_start or date.today().replace(day=1)
    if end_key not in st.session_state:
        st.session_state[end_key] = default_end or date.today()
    def clamp(d):
        if min_date and d < min_date:
            return min_date
        if max_date and d > max_date:
            return max_date
        return d
    cols = st.columns([1, 1, 1, 1, 1, 1.5])
    with cols[0]:
        if st.button("📅 昨日", key=f"{start_key}_yesterday", use_container_width=True):
            yesterday = date.today() - timedelta(days=1)
            st.session_state[start_key] = clamp(yesterday)
            st.session_state[end_key] = clamp(yesterday)
            st.rerun()
    with cols[1]:
        if st.button("📊 近7天", key=f"{start_key}_7days", use_container_width=True):
            yesterday = date.today() - timedelta(days=1)
            start = yesterday - timedelta(days=6)
            st.session_state[start_key] = clamp(start)
            st.session_state[end_key] = clamp(yesterday)
            st.rerun()
    with cols[2]:
        if st.button("📆 上周", key=f"{start_key}_last_week", use_container_width=True):
            today = date.today()
            last_monday = today - timedelta(days=today.weekday() + 7)
            last_sunday = last_monday + timedelta(days=6)
            st.session_state[start_key] = clamp(last_monday)
            st.session_state[end_key] = clamp(last_sunday)
            st.rerun()
    with cols[3]:
        if st.button("📆 本周", key=f"{start_key}_week", use_container_width=True):
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            if end_of_week > today:
                end_of_week = today
            st.session_state[start_key] = clamp(start_of_week)
            st.session_state[end_key] = clamp(end_of_week)
            st.rerun()
    with cols[4]:
        if st.button("📆 本月", key=f"{start_key}_month", use_container_width=True):
            today = date.today()
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month+1, day=1) - timedelta(days=1)
            if end_of_month > today:
                end_of_month = today - timedelta(days=1)
            st.session_state[start_key] = clamp(start_of_month)
            st.session_state[end_key] = clamp(end_of_month)
            st.rerun()
    with cols[5]:
        more_options = ["更多 ▼", "自然月", "自然年", "自定义月"]
        selected_more = st.selectbox("", options=more_options, index=0, key=f"{start_key}_more", label_visibility="collapsed")
        if selected_more != "更多 ▼":
            if selected_more == "自然月":
                col_y, col_m = st.columns(2)
                with col_y:
                    year = st.number_input("年", min_value=2020, max_value=2030, value=date.today().year, key=f"{start_key}_year", label_visibility="collapsed")
                with col_m:
                    month = st.number_input("月", min_value=1, max_value=12, value=date.today().month, key=f"{start_key}_month_num", label_visibility="collapsed")
                if st.button("确定", key=f"{start_key}_month_apply"):
                    start_d = date(year, month, 1)
                    if month == 12:
                        end_d = date(year+1, 1, 1) - timedelta(days=1)
                    else:
                        end_d = date(year, month+1, 1) - timedelta(days=1)
                    today = date.today()
                    if end_d > today:
                        end_d = today - timedelta(days=1)
                    st.session_state[start_key] = clamp(start_d)
                    st.session_state[end_key] = clamp(end_d)
                    st.rerun()
            elif selected_more == "自然年":
                year = st.number_input("年份", min_value=2020, max_value=2030, value=date.today().year, key=f"{start_key}_year_only", label_visibility="collapsed")
                if st.button("确定", key=f"{start_key}_year_apply"):
                    start_d = date(year, 1, 1)
                    end_d = date(year, 12, 31)
                    today = date.today()
                    if end_d > today:
                        end_d = today - timedelta(days=1)
                    st.session_state[start_key] = clamp(start_d)
                    st.session_state[end_key] = clamp(end_d)
                    st.rerun()
            elif selected_more == "自定义月":
                st.info("可自行扩展更多功能")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_val = st.session_state.get(start_key, default_start or date.today())
        if min_date and start_val < min_date:
            start_val = min_date
        if max_date and start_val > max_date:
            start_val = max_date
        st.date_input("开始日期", value=start_val, key=start_key, min_value=min_date, max_value=max_date, label_visibility="collapsed")
    with col_d2:
        end_val = st.session_state.get(end_key, default_end or date.today())
        if min_date and end_val < min_date:
            end_val = min_date
        if max_date and end_val > max_date:
            end_val = max_date
        st.date_input("结束日期", value=end_val, key=end_key, min_value=min_date, max_value=max_date, label_visibility="collapsed")

# ========== 辅助函数（加载数据，注入映射） ==========
@st.cache_data(ttl=300)
def load_daily_sales(suffix=None, apply_filter=True):
    if supabase is None:
        return pd.DataFrame()
    try:
        table_name = get_table_name("daily_sales", suffix)
        all_data = []
        page = 0
        page_size = 1000
        while True:
            resp = supabase.table(table_name)\
                           .select("id, sale_date, shop_name, amount, cumulative_amount")\
                           .range(page*page_size, (page+1)*page_size-1).execute()
            if not resp.data:
                break
            all_data.extend(resp.data)
            if len(resp.data) < page_size:
                break
            page += 1
        if all_data:
            df = pd.DataFrame(all_data)
            df["sale_date"] = pd.to_datetime(df["sale_date"])
            mapping_df = st.session_state.get("mapping_df")
            if mapping_df is not None and not mapping_df.empty:
                df['anchor'] = 'NONE'
                df = add_mapping_columns(df, mapping_df, shop_col='shop_name', anchor_col='anchor')
            else:
                df['org_name'] = None
                df['dept'] = None
            if apply_filter:
                df = apply_data_permission(df)
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载每日业绩失败：{e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_product_sales(suffix=None, apply_filter=True):
    if supabase is None:
        return pd.DataFrame()
    try:
        table_name = get_table_name("product_sales", suffix)
        all_data = []
        page = 0
        page_size = 1000
        needed_cols = "sale_date, shop_name, product_code, style_code, brand, year, season, product_category, style, color_code, size_code, ship_amount, return_amount, net_amount, remark"
        while True:
            resp = supabase.table(table_name)\
                           .select(needed_cols)\
                           .range(page*page_size, (page+1)*page_size-1).execute()
            if not resp.data:
                break
            all_data.extend(resp.data)
            if len(resp.data) < page_size:
                break
            page += 1
        if all_data:
            df = pd.DataFrame(all_data)
            df["sale_date"] = pd.to_datetime(df["sale_date"])
            df["style_code"] = df["style_code"].fillna(df["product_code"].str[:8])
            for col in ["ship_amount", "return_amount", "net_amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            if suffix in ["_live", "_all"]:
                df["anchor"] = df["remark"].apply(extract_anchor)
            mapping_df = st.session_state.get("mapping_df")
            if mapping_df is not None and not mapping_df.empty:
                if "anchor" not in df.columns:
                    df['anchor'] = 'NONE'
                df = add_mapping_columns(df, mapping_df, shop_col='shop_name', anchor_col='anchor')
            else:
                df['org_name'] = None
                df['dept'] = None
            if apply_filter:
                df = apply_data_permission(df)
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载商品销售数据失败：{e}")
        return pd.DataFrame()

def save_daily_sales(records, suffix=None):
    if supabase is None or not records:
        return
    table_name = get_table_name("daily_sales", suffix)
    supabase.table(table_name).upsert(records, on_conflict="sale_date,shop_name").execute()

def save_product_sales(df_orders, suffix=None):
    if supabase is None or df_orders.empty:
        return
    master_df = load_product_master()
    grouped = process_orders_vectorized(df_orders, master_df)
    if grouped.empty:
        return
    records = grouped.to_dict(orient='records')
    table_name = get_table_name("product_sales", suffix)
    batch_size = 500
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        supabase.table(table_name).upsert(batch, on_conflict="remark").execute()

def rebuild_daily_data(suffix=None):
    df = load_daily_sales(suffix, apply_filter=False)
    if df.empty:
        st.session_state.df_all_daily = None
        st.session_state.daily_latest = None
        st.session_state.monthly_actual = None
        st.session_state.latest_date = None
        return
    df = df.rename(columns={"sale_date": "日期", "shop_name": "店铺名称",
                            "amount": "当日金额", "cumulative_amount": "月累计金额"})
    df_all = df.sort_values(["店铺名称", "日期"])
    latest_date = df_all["日期"].max()
    daily_latest = df_all.loc[df_all.groupby("店铺名称")["日期"].idxmax()].copy()
    monthly_actual = df_all.groupby("店铺名称")["当日金额"].sum().reset_index()
    monthly_actual["月累计金额"] = monthly_actual["当日金额"].round(2)
    monthly_actual = monthly_actual[["店铺名称", "月累计金额"]].sort_values("店铺名称")
    st.session_state.df_all_daily = df_all
    st.session_state.daily_latest = daily_latest
    st.session_state.monthly_actual = monthly_actual
    st.session_state.latest_date = latest_date

def rebuild_daily_from_product(suffix=None):
    if supabase is None:
        return False, "Supabase 未连接"
    try:
        product_table = get_table_name("product_sales", suffix)
        resp = supabase.table(product_table).select("sale_date, shop_name, net_amount, remark").execute()
        df_product = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
        ok, msg, records = rebuild_daily_from_product_vectorized(df_product, suffix)
        if not ok:
            return False, msg
        daily_table = get_table_name("daily_sales", suffix)
        supabase.table(daily_table).delete().neq("id", 0).execute()
        if records:
            batch_size = 1000
            for i in range(0, len(records), batch_size):
                batch = records[i:i+batch_size]
                supabase.table(daily_table).insert(batch).execute()
        return True, f"成功重建每日业绩，共 {len(records)} 条记录"
    except Exception as e:
        return False, str(e)

def load_targets(suffix=None):
    if supabase is None:
        return {}
    try:
        table_name = get_table_name("shop_targets", suffix)
        resp = supabase.table(table_name).select("*").execute()
        if resp.data:
            return {row["shop_name"]: row["target_amount"] for row in resp.data}
        else:
            return {}
    except:
        return {}

def save_targets(target_dict, suffix=None):
    if supabase is None:
        return
    records = [{"shop_name": k, "target_amount": v} for k, v in target_dict.items()]
    if records:
        table_name = get_table_name("shop_targets", suffix)
        supabase.table(table_name).upsert(records, on_conflict="shop_name").execute()

def clear_targets(suffix=None):
    if supabase:
        table_name = get_table_name("shop_targets", suffix)
        supabase.table(table_name).delete().neq("id", 0).execute()
    st.session_state.target_dict = {}
    st.rerun()

def load_product_master():
    if supabase is None:
        return pd.DataFrame()
    try:
        all_data = []
        page = 0
        page_size = 1000
        while True:
            resp = supabase.table("product_master").select("*").range(page*page_size, (page+1)*page_size-1).execute()
            if not resp.data:
                break
            all_data.extend(resp.data)
            if len(resp.data) < page_size:
                break
            page += 1
        if all_data:
            df = pd.DataFrame(all_data)
            if "has_newbie_coupon" not in df.columns:
                df["has_newbie_coupon"] = False
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载商品库失败：{e}")
        return pd.DataFrame()

def update_product_master_flag(style_code, flag_value):
    if supabase is None:
        return False, "Supabase 未连接"
    try:
        supabase.table("product_master").update({"has_newbie_coupon": flag_value}).eq("style_code", style_code).execute()
        return True, "更新成功"
    except Exception as e:
        return False, str(e)

def validate_order_data(df):
    try:
        required = ["日期", "金额/时间", "备注"]
        missing_cols = [col for col in required if col not in df.columns]
        if missing_cols:
            return False, f"缺少必要列: {', '.join(missing_cols)}。", None
        df_valid = df.copy()
        df_valid["日期"] = pd.to_datetime(df_valid["日期"], errors='coerce')
        if df_valid["日期"].isnull().any():
            return False, "日期列包含无效日期，请检查格式（如 2026-06-01）。", None
        df_valid["店铺名称"] = df_valid["备注"].astype(str).str.split("_").str[-1]
        df_valid["店铺名称"] = df_valid["店铺名称"].str.replace(r'^商店[：:]', '', regex=True).str.strip()
        df_valid = df_valid[df_valid["店铺名称"].notna() & (df_valid["店铺名称"] != "")].copy()
        if df_valid.empty:
            return False, "未提取到有效的店铺名称，请检查备注格式。", None
        df_valid["金额/时间"] = pd.to_numeric(df_valid["金额/时间"], errors='coerce')
        if df_valid["金额/时间"].isnull().any():
            return False, "金额/时间列包含非数值内容，请检查。", None
        return True, "验证通过", df_valid
    except Exception as e:
        return False, f"验证过程发生异常: {str(e)}", None

def process_uploaded_file(uploaded_file, suffix):
    try:
        try:
            df = pd.read_excel(uploaded_file, header=1)
        except Exception as e:
            return False, f"文件读取失败：{str(e)}。"
        is_valid, err_msg, df_valid = validate_order_data(df)
        if not is_valid:
            return False, err_msg
        try:
            save_product_sales(df_valid, suffix)
        except Exception as e:
            if "duplicate key" in str(e).lower():
                return False, "数据重复：该文件中的订单备注与已存在数据冲突。"
            return False, f"保存商品销售明细失败：{str(e)}。"
        ok, msg = rebuild_daily_from_product(suffix)
        if not ok:
            return False, msg
        if suffix == st.session_state.get("table_suffix", ""):
            rebuild_daily_data(suffix)
            st.session_state.target_dict = load_targets(suffix)
        return True, f"处理完成！"
    except Exception as e:
        return False, f"未预料的错误：{str(e)}"

def load_target_file(uploaded_file, suffix):
    try:
        df_target = pd.read_excel(uploaded_file, header=None)
        first_cell = str(df_target.iloc[0, 0]) if len(df_target) > 0 else ""
        if "月目标" in first_cell or "目标" in first_cell:
            df_target = df_target.iloc[1:].reset_index(drop=True)
        if df_target.shape[1] < 2:
            raise ValueError("需要两列：店铺名称、目标金额")
        shop_names = df_target.iloc[:, 0].astype(str).str.strip()
        target_vals = pd.to_numeric(df_target.iloc[:, 1], errors='coerce')
        target_dict = {}
        for name, val in zip(shop_names, target_vals):
            if pd.notna(val) and name not in ["", "nan", "None"]:
                target_dict[name] = val
        save_targets(target_dict, suffix)
        if suffix == st.session_state.get("table_suffix", ""):
            st.session_state.target_dict = target_dict
        return True, f"成功加载 {len(target_dict)} 个店铺目标"
    except Exception as e:
        return False, str(e)

def manage_newbie_coupon():
    # 与原代码相同，略（保持功能）
    st.subheader("🏷️ 单商品礼金标签管理")
    master_df = load_product_master()
    if master_df.empty:
        st.info("暂无商品数据")
        return
    if "has_newbie_coupon" not in master_df.columns:
        st.warning("数据库表中缺少 has_newbie_coupon 字段，请先执行 ALTER TABLE product_master ADD COLUMN has_newbie_coupon BOOLEAN DEFAULT FALSE;")
        return
    search = st.text_input("搜索货号", key="coupon_search")
    style_codes = master_df["style_code"].dropna().unique()
    if search:
        style_codes = [code for code in style_codes if search.upper() in code.upper()]
    selected_style = st.selectbox("选择商品货号", options=sorted(style_codes), key="coupon_style")
    current_flag = master_df[master_df["style_code"] == selected_style]["has_newbie_coupon"].values[0] if not master_df[master_df["style_code"] == selected_style].empty else False
    new_flag = st.checkbox("参与新人礼金", value=bool(current_flag), key="coupon_flag")
    if st.button("更新标签", key="coupon_update"):
        ok, msg = update_product_master_flag(selected_style, new_flag)
        if ok:
            st.success(msg)
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(msg)

def batch_manage_newbie_coupon():
    # 与原代码相同，略
    st.subheader("📦 批量礼金标签管理")
    master_df = load_product_master()
    if master_df.empty:
        st.warning("暂无商品数据")
        return
    if "has_newbie_coupon" not in master_df.columns:
        st.warning("数据库表中缺少 has_newbie_coupon 字段，请先执行 ALTER TABLE product_master ADD COLUMN has_newbie_coupon BOOLEAN DEFAULT FALSE;")
        return
    current_coupon_codes = master_df[master_df["has_newbie_coupon"] == True]["style_code"].tolist()
    st.info(f"当前共有 **{len(current_coupon_codes)}** 个商品参与新人礼金活动。")
    operation = st.radio("选择操作模式", ["批量新增", "批量删除", "整体替换"], horizontal=True, key="batch_op")
    input_method = st.radio("输入方式", ["文本框（每行一个货号）", "上传文件（每行一个货号）"], horizontal=True, key="input_method")
    style_codes_input = []
    if input_method == "文本框（每行一个货号）":
        text_area = st.text_area("请输入货号，每行一个", height=200, key="batch_codes_text")
        if text_area:
            style_codes_input = [line.strip().upper() for line in text_area.splitlines() if line.strip()]
    else:
        uploaded_file = st.file_uploader("上传文本文件（每行一个货号）", type=["txt", "csv"], key="batch_file")
        if uploaded_file is not None:
            content = uploaded_file.read().decode("utf-8")
            style_codes_input = [line.strip().upper() for line in content.splitlines() if line.strip()]
    if style_codes_input:
        st.write(f"共识别 **{len(style_codes_input)}** 个货号：")
        st.text(", ".join(style_codes_input[:20]) + ("..." if len(style_codes_input) > 20 else ""))
    if st.button("确认执行", key="batch_execute"):
        if not style_codes_input:
            st.error("请至少输入一个货号")
            return
        existing_codes = master_df["style_code"].tolist()
        invalid_codes = [code for code in style_codes_input if code not in existing_codes]
        if invalid_codes:
            st.warning(f"以下货号不存在于商品库中：{', '.join(invalid_codes[:10])}{'...' if len(invalid_codes) > 10 else ''}")
            if st.button("仍要执行（忽略不存在货号）", key="ignore_invalid"):
                valid_codes = [code for code in style_codes_input if code in existing_codes]
                if not valid_codes:
                    st.error("没有有效的货号")
                    return
                style_codes_input = valid_codes
            else:
                st.stop()
        with st.spinner("正在更新数据库，请稍候..."):
            try:
                if operation == "批量新增":
                    for code in style_codes_input:
                        update_product_master_flag(code, True)
                    st.success(f"成功为 {len(style_codes_input)} 个商品启用新人礼金标签")
                elif operation == "批量删除":
                    for code in style_codes_input:
                        update_product_master_flag(code, False)
                    st.success(f"成功为 {len(style_codes_input)} 个商品停用新人礼金标签")
                else:
                    all_codes = master_df["style_code"].tolist()
                    for code in all_codes:
                        update_product_master_flag(code, False)
                    for code in style_codes_input:
                        update_product_master_flag(code, True)
                    st.success(f"整体替换完成，现有 {len(style_codes_input)} 个商品启用新人礼金标签")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"操作失败：{e}")

# ========== 页面初始化 ==========
rebuild_daily_data(st.session_state.table_suffix)
if st.session_state.target_dict == {}:
    st.session_state.target_dict = load_targets(st.session_state.table_suffix)

# ========== 侧边栏（保留原有，未改动） ==========
with st.sidebar:
    st.header("📂 数据加载")
    st.subheader("🔄 数据源切换")
    suffix_names = {"": "非直播数据", "_live": "直播数据", "_all": "全部数据"}
    current_source_name = suffix_names.get(st.session_state.table_suffix, "未知")
    st.info(f"📌 当前正在查看：**{current_source_name}**")

    if st.session_state.role == "admin":
        available_suffixes = {"非直播数据": "", "直播数据": "_live", "全部数据": "_all"}
    else:
        user_info = st.session_state.sub_users.get(st.session_state.username, {})
        default_suffix = user_info.get("default_suffix", "")
        perms = user_info.get("permissions", {})
        available = {}
        for name, suf in [("非直播数据", ""), ("直播数据", "_live"), ("全部数据", "_all")]:
            if suf in perms and perms[suf]:
                available[name] = suf
        if not available:
            available = {suffix_names.get(default_suffix, "非直播数据"): default_suffix}
        available_suffixes = available

    options = list(available_suffixes.keys())
    if current_source_name in options:
        default_index = options.index(current_source_name)
    else:
        default_index = 0
    selected_source = st.selectbox("选择数据源", options=options, index=default_index, key="source_selectbox_sidebar")
    if st.button("✅ 确认切换", key="confirm_switch_sidebar"):
        new_suffix = available_suffixes[selected_source]
        if new_suffix != st.session_state.table_suffix:
            st.session_state.table_suffix = new_suffix
            st.cache_data.clear()
            st.rerun()
    st.markdown("---")

    if st.session_state.role == "admin":
        current_display_suffix = st.session_state.table_suffix
        def handle_upload(uploaded_file, suffix, file_type="order"):
            if st.session_state.processing_upload:
                st.warning("上一个文件正在处理中，请稍后...")
                return
            if uploaded_file is None:
                st.warning("请先选择文件")
                return
            file_content = uploaded_file.getvalue()
            file_hash = hashlib.md5(file_content).hexdigest()
            if file_type == "order" and st.session_state.get("uploaded_file_hash") == file_hash:
                st.info("该文件内容已上传过，无需重复处理")
                return
            st.session_state.processing_upload = True
            with st.spinner("正在处理文件，请稍候..."):
                file_bytes = io.BytesIO(file_content)
                if file_type == "order":
                    ok, msg = process_uploaded_file(file_bytes, suffix)
                else:
                    ok, msg = load_target_file(file_bytes, suffix)
            if ok:
                st.success(msg)
                if file_type == "order":
                    st.session_state.uploaded_file_hash = file_hash
                st.cache_data.clear()
                st.session_state.processing_upload = False
                time.sleep(0.3)
                st.rerun()
            else:
                st.error(msg)
                st.session_state.processing_upload = False

        if current_display_suffix == "":
            st.subheader("📁 非直播数据上传")
            uploaded_order = st.file_uploader("选择订单文件 (Excel)", type=["xlsx", "xls"], key="order_uploader_normal_final")
            if st.button("📤 确认上传", key="confirm_upload_normal_final"):
                handle_upload(uploaded_order, "", "order")
            target_file = st.file_uploader("选择目标文件 (Excel)", type=["xlsx", "xls"], key="target_upload_normal_final")
            if st.button("📤 确认上传目标", key="confirm_target_normal_final"):
                handle_upload(target_file, "", "target")
        elif current_display_suffix == "_live":
            st.subheader("🎥 直播数据上传")
            uploaded_order = st.file_uploader("选择订单文件 (Excel)", type=["xlsx", "xls"], key="order_uploader_live_final")
            if st.button("📤 确认上传", key="confirm_upload_live_final"):
                handle_upload(uploaded_order, "_live", "order")
            target_file = st.file_uploader("选择目标文件 (Excel)", type=["xlsx", "xls"], key="target_upload_live_final")
            if st.button("📤 确认上传目标", key="confirm_target_live_final"):
                handle_upload(target_file, "_live", "target")
        else:
            st.subheader("📊 全部数据上传")
            uploaded_order = st.file_uploader("选择订单文件 (Excel)", type=["xlsx", "xls"], key="order_uploader_all_final")
            if st.button("📤 确认上传", key="confirm_upload_all_final"):
                handle_upload(uploaded_order, "_all", "order")
            target_file = st.file_uploader("选择目标文件 (Excel)", type=["xlsx", "xls"], key="target_upload_all_final")
            if st.button("📤 确认上传目标", key="confirm_target_all_final"):
                handle_upload(target_file, "_all", "target")
        st.markdown("---")
        st.header("⚙️ 工具")
        template_df = pd.DataFrame({"店铺名称": ["示例店铺A", "示例店铺B"], "目标金额": [100000, 200000]})
        template_bytes = io.BytesIO()
        with pd.ExcelWriter(template_bytes, engine='openpyxl') as writer:
            template_df.to_excel(writer, index=False)
        st.download_button("📄 下载目标模板", data=template_bytes.getvalue(), file_name="目标模板.xlsx", key="download_template_final")
        if st.button("🗑️ 清除当前用户的目标记忆", key="clear_targets_final"):
            clear_targets(st.session_state.table_suffix)
        if st.button("🔄 强制刷新所有数据", key="force_refresh_final"):
            st.cache_data.clear()
            st.rerun()
        if st.button("🔁 重置为非直播数据", key="reset_to_normal_final"):
            st.session_state.table_suffix = ""
            st.cache_data.clear()
            st.rerun()
        if st.button("🔄 从商品明细重建每日业绩", key="rebuild_daily_final"):
            ok, msg = rebuild_daily_from_product(st.session_state.table_suffix)
            if ok:
                st.success(msg)
                rebuild_daily_data(st.session_state.table_suffix)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(msg)
        st.markdown("---")
        with st.expander("🏷️ 单商品礼金标签管理"):
            manage_newbie_coupon()
        with st.expander("📦 批量礼金标签管理"):
            batch_manage_newbie_coupon()
    else:
        st.info("您只有查看权限，无法上传文件。如需上传，请联系管理员。")
    st.markdown("---")
    if st.button("🚪 退出登录", key="logout_final"):
        st.session_state.authenticated = False
        for key in ["username", "role", "table_suffix"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# ========== 动态创建选项卡 ==========
base_tabs = [
    "📊 经营驾驶舱",
    "🏪 店铺分析",
    "📦 商品分析",
    "🎤 组织分析",
    "📈 趋势分析",
    "📂 数据管理",
    "📈 销售分布与品牌",
    "⚠️ 异常预警"
]
admin_extra_tabs = [ "🔧 调试", "📚 商品库导出", "⚙️ 系统设置"]

if st.session_state.role == "admin":
    tab_labels = base_tabs + admin_extra_tabs
else:
    current_suffix = st.session_state.table_suffix
    user_info = st.session_state.sub_users.get(st.session_state.username, {})
    perms = user_info.get("permissions", {})
    allowed = perms.get(current_suffix, [])
    if not allowed and "" in perms:
        allowed = perms[""]
    if not allowed:
        allowed = base_tabs
    valid_tabs = [tab for tab in allowed if tab in base_tabs]
    tab_labels = valid_tabs if valid_tabs else base_tabs

tabs = st.tabs(tab_labels, key="main_tabs")

def get_tab_index(label):
    return tab_labels.index(label) if label in tab_labels else None

idx_dashboard = get_tab_index("📊 经营驾驶舱")
idx_shop = get_tab_index("🏪 店铺分析")
idx_product = get_tab_index("📦 商品分析")
idx_anchor = get_tab_index("🎤 组织分析")
idx_trend = get_tab_index("📈 趋势分析")
idx_data = get_tab_index("📂 数据管理")
idx_distribution = get_tab_index("📈 销售分布与品牌")
idx_alert = get_tab_index("⚠️ 异常预警")
idx_debug = get_tab_index("🔧 调试")
idx_export = get_tab_index("📚 商品库导出")
idx_system = get_tab_index("⚙️ 系统设置")

idx_latest = idx_shop
idx_range = idx_trend
idx_query = idx_shop
idx_ship_return = idx_data
idx_history = idx_data
idx_anchor_compare = idx_anchor

# ========== 经营驾驶舱（核心改动：增加维度切换） ==========
if idx_dashboard is not None:
    with tabs[idx_dashboard]:
        # ---------- 维度选择 ----------
        col_dim1, col_dim2, col_dim3 = st.columns([1, 2, 1])
        with col_dim1:
            dimension = st.selectbox(
                "📌 聚合维度",
                options=["店铺", "主播", "组织", "部门"],
                index=0,
                key="dashboard_dimension"
            )
        with col_dim2:
            mapping_df = st.session_state.get("mapping_df")
            if dimension in ["组织", "部门"] and mapping_df is not None and not mapping_df.empty:
                if dimension == "组织":
                    options = sorted(mapping_df['org_name'].dropna().unique())
                    selected = st.multiselect("筛选组织", options=options, default=[], key="dashboard_org_filter")
                else:
                    options = sorted(mapping_df['dept'].dropna().unique())
                    selected = st.multiselect("筛选部门", options=options, default=[], key="dashboard_dept_filter")
            else:
                selected = []
        with col_dim3:
            if st.button("🔄 刷新数据", key="dashboard_refresh"):
                st.cache_data.clear()
                st.rerun()

        # ---------- 加载数据 ----------
        with st.spinner("加载数据..."):
            daily_df = load_daily_sales(st.session_state.table_suffix)
            prod_df = load_product_sales(st.session_state.table_suffix)

        if daily_df.empty or prod_df.empty:
            st.info("📌 暂无数据，请先上传订单文件。")
            st.stop()

        latest_date = daily_df["sale_date"].max().date()
        st.caption(f"📅 数据更新至：{latest_date.strftime('%Y年%m月%d日')}")

        # ---------- 应用维度筛选 ----------
        dim_col_map = {
            "店铺": "shop_name",
            "主播": "anchor",
            "组织": "org_name",
            "部门": "dept"
        }
        group_col = dim_col_map[dimension]
        if group_col not in daily_df.columns:
            st.error(f"数据中缺少 {dimension} 列，请检查映射表是否完整。")
            st.stop()

        if selected:
            daily_df = daily_df[daily_df[group_col].isin(selected)]

        if daily_df.empty:
            st.warning("当前筛选条件下无数据")
            st.stop()

        # ---------- 按维度聚合 ----------
        mask_latest = daily_df["sale_date"].dt.date == latest_date
        latest_grouped = daily_df[mask_latest].groupby(group_col)['amount'].sum().reset_index(name='昨日销售')
        month_start = latest_date.replace(day=1)
        mask_month = (daily_df["sale_date"].dt.date >= month_start) & (daily_df["sale_date"].dt.date <= latest_date)
        month_grouped = daily_df[mask_month].groupby(group_col)['amount'].sum().reset_index(name='月累计')
        merged = pd.merge(latest_grouped, month_grouped, on=group_col, how='outer').fillna(0)

        latest_sales = merged['昨日销售'].sum()
        month_sales = merged['月累计'].sum()

        prev_date = latest_date - timedelta(days=1)
        mask_prev = daily_df["sale_date"].dt.date == prev_date
        prev_sales = daily_df[mask_prev]['amount'].sum()

        # 目标处理
        target_dict = st.session_state.target_dict
        if target_dict:
            target_df = pd.DataFrame(list(target_dict.items()), columns=['shop_name', 'target'])
            if dimension in ["组织", "部门"]:
                mapping_df = st.session_state.get("mapping_df")
                if mapping_df is not None and not mapping_df.empty:
                    shop_org = mapping_df[['shop_name', 'org_name', 'dept']].drop_duplicates()
                    target_mapped = target_df.merge(shop_org, on='shop_name', how='left')
                    if dimension == "组织":
                        target_agg = target_mapped.groupby('org_name')['target'].sum()
                        total_target = target_agg.sum()
                        merged['target'] = merged[group_col].map(target_agg).fillna(0)
                    else:
                        target_agg = target_mapped.groupby('dept')['target'].sum()
                        total_target = target_agg.sum()
                        merged['target'] = merged[group_col].map(target_agg).fillna(0)
                else:
                    total_target = 0
                    merged['target'] = 0
            else:
                if dimension == "店铺":
                    merged['target'] = merged[group_col].map(target_dict).fillna(0)
                    total_target = sum(target_dict.values())
                else:
                    merged['target'] = 0
                    total_target = 0
        else:
            total_target = 0
            merged['target'] = 0

        merged['达成率'] = merged.apply(lambda r: r['月累计'] / r['target'] * 100 if r['target'] > 0 else 0, axis=1)
        target_rate = (month_sales / total_target * 100) if total_target > 0 else 0

        prod_latest = prod_df[prod_df["sale_date"].dt.date == latest_date]
        ship_latest = prod_latest['ship_amount'].sum()
        return_latest = prod_latest['return_amount'].sum()
        return_rate = (return_latest / ship_latest * 100) if ship_latest > 0 else 0

        health_score = 70
        if target_rate > 80:
            health_score += 15
        elif target_rate > 50:
            health_score += 5
        if return_rate < 5:
            health_score += 10
        elif return_rate < 10:
            health_score += 5
        if latest_sales > prev_sales:
            health_score += 5
        health_score = min(100, health_score)

        if prev_sales != 0:
            change = ((latest_sales - prev_sales) / prev_sales) * 100
        else:
            change = 0

        # ---------- KPI 卡片 ----------
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if prev_sales < 0:
                abs_increase = latest_sales - prev_sales
                change_text = f"▲ 由负转正 (+{abs_increase:,.0f})"
                change_class = "change-up"
            elif prev_sales == 0:
                change_text = "无前日数据"
                change_class = "change-neutral"
            else:
                change_text = f"{'▲' if change >= 0 else '▼'} {abs(change):.1f}%" if change != 0 else "持平"
                change_class = "change-up" if change >= 0 else "change-down"
            st.markdown(f"""
            <div class="glass-card">
                <div class="kpi-label">昨日销售</div>
                <div class="kpi-number">¥{latest_sales:,.0f}</div>
                <div style="margin-top:6px;">
                    <span class="{change_class}">{change_text}</span>
                    <span style="color:#64748b;font-size:13px;margin-left:8px;">前日 ¥{prev_sales:,.0f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            bar_color = "#4ade80" if target_rate >= 80 else "#fbbf24" if target_rate >= 50 else "#f87171"
            st.markdown(f"""
            <div class="glass-card">
                <div class="kpi-label">月目标完成率</div>
                <div style="font-size:38px;font-weight:700;color:#0f172a;letter-spacing:-0.5px;">{target_rate:.0f}%</div>
                <div class="progress-track">
                    <div class="progress-fill" style="width:{min(target_rate,100)}%;background:{bar_color};"></div>
                </div>
                <div style="color:#475569;font-size:12px;">¥{month_sales:,.0f} / ¥{total_target:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            return_color = "#f87171" if return_rate > 10 else "#fbbf24" if return_rate > 5 else "#4ade80"
            status_text = "正常" if return_rate < 5 else "偏高" if return_rate < 10 else "异常"
            st.markdown(f"""
            <div class="glass-card">
                <div class="kpi-label">退货率</div>
                <div style="font-size:38px;font-weight:700;color:#0f172a;letter-spacing:-0.5px;">{return_rate:.1f}%</div>
                <div style="margin-top:4px;">
                    <span style="color:{return_color};font-weight:500;">● {status_text}</span>
                    <span style="color:#64748b;font-size:13px;margin-left:8px;">退货 ¥{return_latest:,.0f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            health_color = "#4ade80" if health_score >= 80 else "#fbbf24" if health_score >= 60 else "#f87171"
            health_text = "良好" if health_score >= 80 else "一般" if health_score >= 60 else "需关注"
            st.markdown(f"""
            <div class="glass-card">
                <div class="kpi-label">经营健康度</div>
                <div style="font-size:38px;font-weight:700;color:#0f172a;letter-spacing:-0.5px;">{health_score}分</div>
                <div class="progress-track">
                    <div class="progress-fill" style="width:{health_score}%;background:{health_color};"></div>
                </div>
                <div style="color:{health_color};font-size:13px;font-weight:500;">● {health_text}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # ---------- 排行 ----------
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.markdown(f'<div class="section-title">🏆 {dimension}排行</div>', unsafe_allow_html=True)
            top = merged.sort_values('昨日销售', ascending=False).head(5)
            if not top.empty:
                max_val = top['昨日销售'].iloc[0]
                rank_html = ""
                emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                for i, (_, r) in enumerate(top.iterrows()):
                    pct = (r['昨日销售'] / max_val * 100) if max_val > 0 else 0
                    rank_html += f"""
                    <div class="rank-item">
                        <div class="rank-emoji">{emojis[i]}</div>
                        <div class="rank-name">{r[group_col]}</div>
                        <div class="rank-value">¥{r['昨日销售']/10000:.1f}万</div>
                        <div class="rank-bar-bg">
                            <div class="rank-bar-fill" style="width:{pct}%;"></div>
                        </div>
                    </div>
                    """
                st.markdown(rank_html, unsafe_allow_html=True)
            else:
                st.info("暂无数据")

        with col_right:
            st.markdown("📈 近7日销售趋势")
            last_7 = daily_df[daily_df["sale_date"].dt.date >= (latest_date - timedelta(days=6))]
            trend = last_7.groupby("sale_date")['amount'].sum().reset_index()
            if not trend.empty:
                fig = px.line(trend, x="sale_date", y="amount", markers=True, template="plotly_white")
                fig.update_layout(height=240, margin=dict(l=0,r=0,t=10,b=0), hovermode="x unified")
                fig.update_traces(line=dict(color="#22c55e", width=2.5), marker=dict(color="#22c55e", size=6))
                st.plotly_chart(fig, use_container_width=True)

        # AI 智能总结（保留原逻辑，略）
        # ... 可自行添加 AI 部分 ...

# ========== 店铺分析（支持维度切换） ==========
if idx_shop is not None:
    with tabs[idx_shop]:
        st.info("📌 按维度查看最新日明细")
        dim = st.selectbox("选择维度", ["店铺", "主播", "组织", "部门"], key="shop_dim")
        dim_col = {"店铺":"shop_name", "主播":"anchor", "组织":"org_name", "部门":"dept"}[dim]
        dim_label = {"店铺":"店铺名称", "主播":"主播名称", "组织":"组织名称", "部门":"部门"}[dim]
        df_all = st.session_state.df_all_daily
        if df_all is not None and not df_all.empty:
            latest = df_all['日期'].max()
            df_latest = df_all[df_all['日期'] == latest].copy()
            if dim_col not in df_latest.columns:
                st.error(f"数据中缺少 {dim_col} 列，请检查映射。")
            else:
                grouped = df_latest.groupby(dim_col).agg(当日金额=('当日金额', 'sum')).reset_index()
                month_start = latest.replace(day=1)
                df_month = df_all[(df_all['日期'] >= month_start) & (df_all['日期'] <= latest)]
                month_agg = df_month.groupby(dim_col)['当日金额'].sum().reset_index(name='月累计金额')
                grouped = grouped.merge(month_agg, on=dim_col, how='outer').fillna(0)
                target_dict = st.session_state.target_dict
                if dim in ["组织", "部门"]:
                    mapping_df = st.session_state.get("mapping_df")
                    if mapping_df is not None and not mapping_df.empty:
                        shop_org = mapping_df[['shop_name', 'org_name', 'dept']].drop_duplicates()
                        target_df = pd.DataFrame(list(target_dict.items()), columns=['shop_name', 'target'])
                        target_mapped = target_df.merge(shop_org, on='shop_name', how='left')
                        if dim == "组织":
                            target_agg = target_mapped.groupby('org_name')['target'].sum()
                        else:
                            target_agg = target_mapped.groupby('dept')['target'].sum()
                        grouped['目标金额'] = grouped[dim_col].map(target_agg).fillna(0)
                    else:
                        grouped['目标金额'] = 0
                elif dim == "店铺":
                    grouped['目标金额'] = grouped[dim_col].map(target_dict).fillna(0)
                else:
                    grouped['目标金额'] = 0
                grouped['达成率'] = grouped.apply(lambda r: f"{r['月累计金额']/r['目标金额']*100:.2f}%" if r['目标金额']>0 else "-", axis=1)
                st.dataframe(grouped, column_config={dim_col: dim_label, "当日金额": "当日销售", "月累计金额": "月累计", "目标金额": "月目标", "达成率": "达成率"}, hide_index=True, use_container_width=True)
        else:
            st.info("暂无数据")
# ========== 组织分析（原主播分析，改为组织维度） ==========
if idx_anchor is not None:
    with tabs[idx_anchor]:
        st.subheader("🎤 组织分析")
        st.info("按组织维度查看销售表现，支持筛选部门")
        mapping_df = st.session_state.get("mapping_df")
        if mapping_df is None or mapping_df.empty:
            st.warning("无映射表数据，请先导入阿米巴映射表。")
        else:
            depts = sorted(mapping_df['dept'].dropna().unique())
            selected_dept = st.multiselect("筛选部门", options=depts, default=[], key="org_dept_filter")
            prod_df = load_product_sales(st.session_state.table_suffix)
            if prod_df.empty:
                st.info("无商品数据")
            else:
                if selected_dept:
                    prod_df = prod_df[prod_df['dept'].isin(selected_dept)]
                if prod_df.empty:
                    st.warning("当前筛选条件下无数据")
                else:
                    org_agg = prod_df.groupby('org_name').agg(
                        发货金额=('ship_amount', 'sum'),
                        退货金额=('return_amount', 'sum'),
                        净销售金额=('net_amount', 'sum')
                    ).reset_index()
                    org_agg['退货率'] = (org_agg['退货金额'] / org_agg['发货金额'] * 100).fillna(0).map("{:.2f}%".format)
                    st.dataframe(org_agg, use_container_width=True, hide_index=True)

# ========== 商品分析 ==========
if idx_product is not None:
    with tabs[idx_product]:
        if st.session_state.get("detail_clicked", False):
            st.session_state.detail_clicked = False
        else:
            st.session_state.show_dialog = False
            st.session_state.dialog_style_code = None
            st.session_state.cached_detail_data = None
        if st.session_state.get("trend_clicked", False):
            st.session_state.trend_clicked = False
        else:
            st.session_state.show_trend_dialog = False
            st.session_state.trend_style_code = None
            st.session_state.trend_data = None

        col_btn, _ = st.columns([1, 5])
        with col_btn:
            if st.button("🔄 刷新数据", key="refresh_analysis_final"):
                st.session_state.show_dialog = False
                st.session_state.dialog_style_code = None
                st.session_state.cached_detail_data = None
                st.session_state.detail_clicked = False
                st.session_state.show_trend_dialog = False
                st.session_state.trend_style_code = None
                st.session_state.trend_data = None
                st.session_state.trend_clicked = False
                st.cache_data.clear()
                st.rerun()
        
        if "dialog_style_code" not in st.session_state:
            st.session_state.dialog_style_code = None
        if "show_dialog" not in st.session_state:
            st.session_state.show_dialog = False
        if "cached_detail_data" not in st.session_state:
            st.session_state.cached_detail_data = None
        if "detail_clicked" not in st.session_state:
            st.session_state.detail_clicked = False
        if "trend_style_code" not in st.session_state:
            st.session_state.trend_style_code = None
        if "show_trend_dialog" not in st.session_state:
            st.session_state.show_trend_dialog = False
        if "trend_data" not in st.session_state:
            st.session_state.trend_data = None
        if "trend_clicked" not in st.session_state:
            st.session_state.trend_clicked = False
        if "product_page_num" not in st.session_state:
            st.session_state.product_page_num = 1
        if "product_page_size" not in st.session_state:
            st.session_state.product_page_size = 10
        if "sort_by" not in st.session_state:
            st.session_state.sort_by = "净销售金额"
        if "sort_ascending" not in st.session_state:
            st.session_state.sort_ascending = False
        
        with st.spinner("正在加载商品销售数据，请稍候..."):
            prod_df = load_product_sales(st.session_state.table_suffix)
        
        if prod_df.empty:
            st.warning("暂无商品销售数据，请先上传订单文件。")
        else:
            if "style_code" in prod_df.columns:
                prod_df["style_code"] = prod_df["style_code"].astype(str).str.strip().str.upper()
            else:
                prod_df["style_code"] = prod_df["product_code"].str[:8].str.strip().str.upper()
            
            if st.session_state.table_suffix in ["_live", "_all"]:
                if "anchor" not in prod_df.columns:
                    prod_df["anchor"] = prod_df["remark"].astype(str).apply(extract_anchor)
            
            min_date = prod_df["sale_date"].min().date()
            max_date = prod_df["sale_date"].max().date()
            
            date_quick_buttons("prod_start_final", "prod_end_final",
                               default_start=min_date,
                               default_end=max_date,
                               min_date=min_date,
                               max_date=max_date)
            start_date = st.session_state.get("prod_start_final", min_date)
            end_date = st.session_state.get("prod_end_final", max_date)
            
            st.subheader("🔍 筛选条件")
            col_platform, col_shop = st.columns(2)
            with col_platform:
                platform_options = ["全部", "抖音", "视频号"]
                selected_platform = st.selectbox("平台", platform_options, key="platform_filter_final")
            with col_shop:
                all_shops_all = prod_df["shop_name"].unique()
                if selected_platform == "抖音":
                    shop_options = [shop for shop in all_shops_all if "抖音" in shop]
                elif selected_platform == "视频号":
                    shop_options = [shop for shop in all_shops_all if "视频号" in shop]
                else:
                    shop_options = list(all_shops_all)
                selected_shops = st.multiselect("店铺（可多选）", options=sorted(shop_options), default=[], key="shop_filter_final")
            
            col_code, col_brand = st.columns(2)
            with col_code:
                style_codes_input = st.text_input("货号筛选（多个用英文逗号分隔）", placeholder="例如: L262Y050, G262Y030", key="style_code_filter_final")
            with col_brand:
                brands_all = ["全部"] + sorted(prod_df["brand"].dropna().unique())
                selected_brand = st.selectbox("品牌", brands_all, key="brand_filter_final")
            
            coupon_filter_options = ["全部", "仅首单礼金", "非首单礼金"]
            selected_coupon_filter = st.selectbox("是否首单礼金款式", coupon_filter_options, key="coupon_filter_final")
            
            selected_anchors = []
            if st.session_state.table_suffix in ["_live", "_all"]:
                if "anchor" not in prod_df.columns:
                    prod_df["anchor"] = prod_df["remark"].astype(str).apply(extract_anchor)
                all_anchors = prod_df["anchor"].dropna().unique().tolist()
                if all_anchors:
                    selected_anchors = st.multiselect("主播（可多选）", options=sorted(all_anchors), default=[], key="anchor_filter_final")
                else:
                    st.info("当前数据中未识别到任何主播信息，请检查备注字段是否包含“主播：xxx”格式。")
            
            mask_date = (prod_df["sale_date"] >= pd.to_datetime(start_date)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))
            filtered = prod_df[mask_date].copy()
            
            if selected_platform == "抖音":
                filtered = filtered[filtered["shop_name"].str.contains("抖音", case=False, na=False)]
            elif selected_platform == "视频号":
                filtered = filtered[filtered["shop_name"].str.contains("视频号", case=False, na=False)]
            if selected_shops:
                filtered = filtered[filtered["shop_name"].isin(selected_shops)]
            if style_codes_input.strip():
                target_codes = [code.strip().upper() for code in style_codes_input.split(",") if code.strip()]
                if target_codes:
                    filtered = filtered[filtered["style_code"].isin(target_codes)]
            if selected_brand != "全部":
                filtered = filtered[filtered["brand"] == selected_brand]
            if selected_anchors:
                filtered = filtered[filtered["anchor"].isin(selected_anchors)]
            
            master_df = load_product_master()
            coupon_map = {}
            if not master_df.empty and "style_code" in master_df.columns:
                master_df["style_code"] = master_df["style_code"].astype(str).str.strip().str.upper()
                coupon_map = master_df.set_index("style_code")["has_newbie_coupon"].to_dict()
            filtered["has_newbie_coupon"] = filtered["style_code"].map(coupon_map).fillna(False)
            if selected_coupon_filter == "仅首单礼金":
                filtered = filtered[filtered["has_newbie_coupon"] == True]
            elif selected_coupon_filter == "非首单礼金":
                filtered = filtered[filtered["has_newbie_coupon"] == False]
            
            if filtered.empty:
                st.warning("所选条件下无销售数据")
            else:
                grouped = filtered.groupby("style_code").agg(
                    发货金额=("ship_amount", "sum"),
                    退货金额=("return_amount", "sum"),
                    净销售金额=("net_amount", "sum")
                ).reset_index().rename(columns={"style_code": "货号"})
                
                if not master_df.empty and "style_code" in master_df.columns:
                    master_df = master_df.drop_duplicates(subset="style_code", keep="first")
                    img_map = master_df.set_index("style_code")["image_url"].to_dict()
                    cat_map = master_df.set_index("style_code")["category"].to_dict()
                    coupon_map = master_df.set_index("style_code")["has_newbie_coupon"].to_dict()
                    grouped["image_url"] = grouped["货号"].map(img_map).fillna(None)
                    grouped["has_newbie_coupon"] = grouped["货号"].map(coupon_map).fillna(False)
                    if "master_category" not in filtered.columns:
                        filtered["master_category"] = None
                    cat_series = filtered.groupby("style_code")["master_category"].first()
                    grouped["master_category"] = grouped["货号"].map(cat_series).fillna(grouped["货号"].map(cat_map))
                else:
                    grouped["master_category"] = None
                    grouped["image_url"] = None
                    grouped["has_newbie_coupon"] = False
                
                grouped["退款率"] = np.where(
                    grouped["发货金额"] != 0,
                    ((grouped["退货金额"] / grouped["发货金额"].replace(0, np.nan)) * 100).map("{:.2f}%".format),
                    "-"
                )
                
                st.markdown("#### 货号汇总表")
                
                col_sort1, col_sort2, col_sort3 = st.columns([1, 1, 2])
                with col_sort1:
                    sort_options = ["货号", "发货金额", "退货金额", "净销售金额", "退款率"]
                    selected_sort = st.selectbox("排序字段", sort_options, index=sort_options.index(st.session_state.sort_by) if st.session_state.sort_by in sort_options else 3, key="sort_by_selector")
                with col_sort2:
                    sort_order = st.radio("排序顺序", ["降序", "升序"], horizontal=True, index=0 if not st.session_state.sort_ascending else 1, key="sort_order_radio")
                with col_sort3:
                    page_size_options = [10, 20, 50, 100]
                    selected_page_size = st.selectbox(
                        "每页显示行数",
                        options=page_size_options,
                        index=page_size_options.index(st.session_state.product_page_size),
                        key="page_size_selector"
                    )
                    if selected_page_size != st.session_state.product_page_size:
                        st.session_state.product_page_size = selected_page_size
                        st.session_state.product_page_num = 1
                        st.rerun()
                
                if selected_sort != st.session_state.sort_by or (sort_order == "降序" and st.session_state.sort_ascending) or (sort_order == "升序" and not st.session_state.sort_ascending):
                    st.session_state.show_dialog = False
                    st.session_state.dialog_style_code = None
                    st.session_state.cached_detail_data = None
                    st.session_state.detail_clicked = False
                    st.session_state.show_trend_dialog = False
                    st.session_state.trend_style_code = None
                    st.session_state.trend_data = None
                    st.session_state.trend_clicked = False
                    st.session_state.sort_by = selected_sort
                    st.session_state.sort_ascending = (sort_order == "升序")
                    st.session_state.product_page_num = 1
                    st.rerun()
                
                if st.session_state.sort_by == "货号":
                    grouped = grouped.sort_values("货号", ascending=st.session_state.sort_ascending)
                elif st.session_state.sort_by == "发货金额":
                    grouped = grouped.sort_values("发货金额", ascending=st.session_state.sort_ascending)
                elif st.session_state.sort_by == "退货金额":
                    grouped = grouped.sort_values("退货金额", ascending=st.session_state.sort_ascending)
                elif st.session_state.sort_by == "净销售金额":
                    grouped = grouped.sort_values("净销售金额", ascending=st.session_state.sort_ascending)
                elif st.session_state.sort_by == "退款率":
                    grouped["退款率_num"] = grouped["退款率"].str.rstrip("%").astype(float)
                    grouped = grouped.sort_values("退款率_num", ascending=st.session_state.sort_ascending)
                    grouped = grouped.drop(columns=["退款率_num"])
                
                page_size = st.session_state.product_page_size
                total_rows = len(grouped)
                total_pages = (total_rows + page_size - 1) // page_size if total_rows > 0 else 1
                if st.session_state.product_page_num > total_pages:
                    st.session_state.product_page_num = 1
                
                col_prev, col_page, col_next, col_export = st.columns([1, 2, 1, 1.5])
                with col_prev:
                    if st.button("◀ 上一页", key="product_prev_page"):
                        st.session_state.show_dialog = False
                        st.session_state.dialog_style_code = None
                        st.session_state.cached_detail_data = None
                        st.session_state.detail_clicked = False
                        st.session_state.show_trend_dialog = False
                        st.session_state.trend_style_code = None
                        st.session_state.trend_data = None
                        st.session_state.trend_clicked = False
                        if st.session_state.product_page_num > 1:
                            st.session_state.product_page_num -= 1
                            st.rerun()
                with col_page:
                    st.write(f"第 {st.session_state.product_page_num} / {total_pages} 页")
                with col_next:
                    if st.button("下一页 ▶", key="product_next_page"):
                        st.session_state.show_dialog = False
                        st.session_state.dialog_style_code = None
                        st.session_state.cached_detail_data = None
                        st.session_state.detail_clicked = False
                        st.session_state.show_trend_dialog = False
                        st.session_state.trend_style_code = None
                        st.session_state.trend_data = None
                        st.session_state.trend_clicked = False
                        if st.session_state.product_page_num < total_pages:
                            st.session_state.product_page_num += 1
                            st.rerun()
                with col_export:
                    is_live_or_all = st.session_state.table_suffix in ["_live", "_all"]
                    if is_live_or_all:
                        detail_type_name = "明细（货号+主播）"
                    else:
                        detail_type_name = "明细（货号+店铺）"
                    
                    export_type = st.radio(
                        "导出类型",
                        ["汇总（货号级别）", detail_type_name],
                        horizontal=True,
                        key="export_type_radio"
                    )
                    
                    if st.button("📥 下载数据", key="export_filtered_data"):
                        if export_type == "汇总（货号级别）":
                            export_df = grouped.copy()
                            if "image_url" in export_df.columns:
                                export_df = export_df.drop(columns=["image_url"])
                            cols_order = ["货号", "master_category", "发货金额", "退货金额", "净销售金额", "退款率", "has_newbie_coupon"]
                            export_cols = [c for c in cols_order if c in export_df.columns]
                            export_df = export_df[export_cols]
                            export_df.rename(columns={
                                "master_category": "商品分类",
                                "has_newbie_coupon": "是否新人礼金"
                            }, inplace=True)
                            export_df["是否新人礼金"] = export_df["是否新人礼金"].map({True: "是", False: "否"})
                            sheet_name = "货号汇总"
                            file_suffix = "货号汇总"
                        else:
                            if is_live_or_all:
                                group_col = "anchor"
                                group_name = "主播"
                            else:
                                group_col = "shop_name"
                                group_name = "店铺"
                            
                            if group_col not in filtered.columns:
                                st.error(f"数据中缺少 {group_name} 信息，无法导出明细。")
                                st.stop()
                            
                            detail_agg = filtered.groupby(["style_code", group_col]).agg(
                                明细发货金额=("ship_amount", "sum"),
                                明细退货金额=("return_amount", "sum"),
                                明细净销售金额=("net_amount", "sum")
                            ).reset_index()
                            
                            detail_agg["明细退款率"] = np.where(
                                detail_agg["明细发货金额"] != 0,
                                (detail_agg["明细退货金额"] / detail_agg["明细发货金额"] * 100).map("{:.2f}%".format),
                                "-"
                            )
                            
                            master_cols = grouped[["货号", "master_category", "发货金额", "退货金额", "净销售金额", "退款率", "has_newbie_coupon"]].copy()
                            export_df = pd.merge(
                                detail_agg,
                                master_cols,
                                left_on="style_code",
                                right_on="货号",
                                how="left"
                            )
                            export_df.drop(columns=["style_code"], inplace=True)
                            export_df.rename(columns={
                                group_col: group_name,
                                "master_category": "商品分类",
                                "has_newbie_coupon": "是否新人礼金"
                            }, inplace=True)
                            export_df["是否新人礼金"] = export_df["是否新人礼金"].map({True: "是", False: "否"})
                            
                            final_cols = [
                                "货号", "商品分类", "发货金额", "退货金额", "净销售金额", "退款率", "是否新人礼金",
                                group_name, "明细发货金额", "明细退货金额", "明细净销售金额", "明细退款率"
                            ]
                            export_df = export_df[final_cols]
                            sheet_name = f"货号{group_name}明细"
                            file_suffix = f"货号{group_name}明细"
                        
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            export_df.to_excel(writer, index=False, sheet_name=sheet_name)
                        st.success("导出成功！点击下方按钮下载")
                        st.download_button(
                            label="💾 点击下载 Excel",
                            data=output.getvalue(),
                            file_name=f"{file_suffix}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
                            key="download_export",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                
                start_idx = (st.session_state.product_page_num - 1) * page_size
                end_idx = min(start_idx + page_size, total_rows)
                page_df = grouped.iloc[start_idx:end_idx]
                
                cols = st.columns([2, 0.5, 1.5, 1.2, 1.2, 1.2, 1, 0.8, 0.8, 0.8])
                headers = ["货号", "图片", "商品分类", "发货金额(¥)", "退货金额(¥)", "净销售金额(¥)", "退款率", "新人礼金", "详情", "趋势"]
                for col, header in zip(cols, headers):
                    col.markdown(f"**{header}**")
                
                for idx, row in page_df.iterrows():
                    col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([2, 0.5, 1.5, 1.2, 1.2, 1.2, 1, 0.8, 0.8, 0.8])
                    col1.write(row["货号"])
                    if row.get("image_url") and pd.notna(row["image_url"]):
                        col2.image(row["image_url"], width=50)
                    else:
                        col2.write("-")
                    col3.write(row["master_category"] if pd.notna(row["master_category"]) else "-")
                    col4.write(f"{row['发货金额']:,.2f}")
                    col5.write(f"{row['退货金额']:,.2f}")
                    col6.write(f"{row['净销售金额']:,.2f}")
                    col7.write(row["退款率"])
                    col8.write("✅" if row.get("has_newbie_coupon") else "❌")
                    if col9.button("📊", key=f"detail_btn_{row['货号']}_{idx}"):
                        style_code = row["货号"]
                        detail_df = filtered[filtered["style_code"] == style_code].copy()
                        if not detail_df.empty:
                            suffix = st.session_state.table_suffix
                            def extract_anchor_fn(remark):
                                match = re.search(r'主播[：:]([^_]+)', remark)
                                return match.group(1).strip() if match else None
                            if suffix in ["_live", "_all"]:
                                detail_df["anchor"] = detail_df["remark"].apply(extract_anchor_fn)
                                detail_df = detail_df[detail_df["anchor"].notna()]
                                if not detail_df.empty:
                                    shop_detail = detail_df.groupby("anchor").agg(
                                        发货金额=("ship_amount", "sum"),
                                        退货金额=("return_amount", "sum"),
                                        净销售金额=("net_amount", "sum")
                                    ).reset_index().rename(columns={"anchor": "主播"})
                                    shop_detail["退款率"] = shop_detail.apply(
                                        lambda r: f"{(r['退货金额']/r['发货金额']*100):.2f}%" if r['发货金额']!=0 else "-", axis=1
                                    )
                                    detail_type = "anchor"
                                else:
                                    shop_detail = pd.DataFrame()
                                    detail_type = "anchor"
                            else:
                                shop_detail = detail_df.groupby("shop_name").agg(
                                    发货金额=("ship_amount", "sum"),
                                    退货金额=("return_amount", "sum"),
                                    净销售金额=("net_amount", "sum")
                                ).reset_index()
                                shop_detail["退款率"] = shop_detail.apply(
                                    lambda r: f"{(r['退货金额']/r['发货金额']*100):.2f}%" if r['发货金额']!=0 else "-", axis=1
                                )
                                detail_type = "shop"
                            st.session_state.cached_detail_data = {"style_code": style_code, "shop_detail": shop_detail, "type": detail_type}
                        else:
                            st.session_state.cached_detail_data = None
                        st.session_state.show_trend_dialog = False
                        st.session_state.trend_style_code = None
                        st.session_state.trend_data = None
                        st.session_state.trend_clicked = False
                        st.session_state.dialog_style_code = style_code
                        st.session_state.show_dialog = True
                        st.session_state.detail_clicked = True
                        st.rerun()
                    if col10.button("📈", key=f"trend_btn_{row['货号']}_{idx}"):
                        style_code = row["货号"]
                        trend_data = filtered[filtered["style_code"] == style_code].copy()
                        if not trend_data.empty:
                            daily = trend_data.groupby("sale_date").agg(
                                ship_amount=("ship_amount", "sum"),
                                return_amount=("return_amount", "sum"),
                                net_amount=("net_amount", "sum")
                            ).reset_index().sort_values("sale_date")
                            st.session_state.trend_data = daily
                        else:
                            st.session_state.trend_data = None
                        st.session_state.show_dialog = False
                        st.session_state.dialog_style_code = None
                        st.session_state.cached_detail_data = None
                        st.session_state.detail_clicked = False
                        st.session_state.trend_style_code = style_code
                        st.session_state.show_trend_dialog = True
                        st.session_state.trend_clicked = True
                        st.rerun()
        
        if st.session_state.show_dialog and st.session_state.dialog_style_code:
            style_code = st.session_state.dialog_style_code
            cached = st.session_state.cached_detail_data
            @st.dialog(f"📋 货号 {style_code} 销售明细", width="large")
            def show_style_detail():
                if cached and cached.get("style_code") == style_code:
                    shop_detail = cached["shop_detail"]
                    if cached.get("type") == "anchor":
                        st.markdown("#### 主播销售汇总")
                    else:
                        st.markdown("#### 店铺销售汇总")
                    if not shop_detail.empty:
                        st.dataframe(shop_detail, column_config={
                            "主播" if cached.get("type") == "anchor" else "shop_name": st.column_config.TextColumn("主播" if cached.get("type") == "anchor" else "店铺"),
                            "发货金额": st.column_config.NumberColumn("发货金额(¥)", format="%.2f"),
                            "退货金额": st.column_config.NumberColumn("退货金额(¥)", format="%.2f"),
                            "净销售金额": st.column_config.NumberColumn("净销售金额(¥)", format="%.2f"),
                            "退款率": st.column_config.TextColumn("退款率")
                        }, hide_index=True, use_container_width=True)
                    else:
                        st.info("无有效数据")
                else:
                    st.info("该货号无销售数据")
                if st.button("关闭", key="close_dialog"):
                    st.session_state.show_dialog = False
                    st.session_state.dialog_style_code = None
                    st.session_state.cached_detail_data = None
                    st.session_state.detail_clicked = False
                    st.rerun()
            show_style_detail()
        
        if st.session_state.show_trend_dialog and st.session_state.trend_style_code:
            style_code = st.session_state.trend_style_code
            @st.dialog(f"📈 货号 {style_code} 销售趋势", width="large")
            def show_trend():
                st.subheader(f"货号：{style_code}")
                daily = st.session_state.trend_data
                if daily is None or daily.empty:
                    st.info("当前筛选条件下该货号无销售数据")
                else:
                    show_ship = st.checkbox("显示发货金额", value=True, key="trend_ship")
                    show_return = st.checkbox("显示退货金额", value=True, key="trend_return")
                    show_net = st.checkbox("显示净销售金额", value=True, key="trend_net")
                    lines = []
                    if show_ship and "ship_amount" in daily.columns:
                        lines.append(go.Scatter(x=daily["sale_date"], y=daily["ship_amount"], name="发货金额", mode="lines+markers"))
                    if show_return and "return_amount" in daily.columns:
                        lines.append(go.Scatter(x=daily["sale_date"], y=daily["return_amount"], name="退货金额", mode="lines+markers"))
                    if show_net and "net_amount" in daily.columns:
                        lines.append(go.Scatter(x=daily["sale_date"], y=daily["net_amount"], name="净销售金额", mode="lines+markers"))
                    if not lines:
                        st.info("请至少勾选一项")
                    else:
                        fig = go.Figure(data=lines)
                        fig.update_layout(title="每日销售趋势", xaxis_title="日期", yaxis_title="金额(¥)", legend_title="指标", hovermode="x unified")
                        st.plotly_chart(fig, use_container_width=True)
                if st.button("关闭", key="close_trend"):
                    st.session_state.show_trend_dialog = False
                    st.session_state.trend_style_code = None
                    st.session_state.trend_data = None
                    st.session_state.trend_clicked = False
                    st.rerun()
            show_trend()

# ========== 趋势分析（日期范围累计） ==========
if idx_trend is not None:
    with tabs[idx_trend]:
        if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
            date_quick_buttons("range_start_final", "range_end_final",
                               default_start=date.today().replace(day=1),
                               default_end=date.today())
            start = st.session_state.get("range_start_final", date.today().replace(day=1))
            end = st.session_state.get("range_end_final", date.today())

            with st.spinner("加载数据..."):
                prod_df = load_product_sales(st.session_state.table_suffix)
            if prod_df.empty:
                st.warning("无商品数据，无法计算发货/退货")
            else:
                if st.session_state.table_suffix == "_all":
                    if "anchor" not in prod_df.columns:
                        prod_df["anchor"] = prod_df["remark"].astype(str).apply(extract_anchor)
                    group_col = "anchor"
                    name_col = "主播名称"
                else:
                    group_col = "shop_name"
                    name_col = "店铺名称"
                all_values = prod_df[group_col].dropna().unique().tolist()
                all_values = sorted([v for v in all_values if v != "" and v is not None])
                selected_values = st.multiselect(
                    f"筛选 {name_col}（不选则显示全部）",
                    options=all_values,
                    default=[]
                )
                if st.button("计算累计", key="calc_range_final"):
                    if start > end:
                        st.error("开始日期不能晚于结束日期")
                    else:
                        mask = (prod_df["sale_date"] >= pd.to_datetime(start)) & (prod_df["sale_date"] <= pd.to_datetime(end))
                        range_data = prod_df[mask].copy()
                        if range_data.empty:
                            st.warning("所选日期范围内无数据")
                        else:
                            if selected_values:
                                range_data = range_data[range_data[group_col].isin(selected_values)]
                            if range_data.empty:
                                st.warning("所选维度在日期范围内无数据")
                                summary = pd.DataFrame(columns=[name_col, "发货金额", "退货金额", "净销售金额"])
                                st.dataframe(summary, use_container_width=True, hide_index=True)
                            else:
                                summary = range_data.groupby(group_col).agg(
                                    发货金额=("ship_amount", "sum"),
                                    退货金额=("return_amount", "sum"),
                                    净销售金额=("net_amount", "sum")
                                ).reset_index().rename(columns={group_col: name_col})
                                summary["发货金额"] = summary["发货金额"].round(2)
                                summary["退货金额"] = summary["退货金额"].round(2)
                                summary["净销售金额"] = summary["净销售金额"].round(2)
                                st.dataframe(summary, use_container_width=True, hide_index=True)
                                total_ship = summary["发货金额"].sum()
                                total_return = summary["退货金额"].sum()
                                total_net = summary["净销售金额"].sum()
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("📦 总发货", f"{total_ship:,.2f}")
                                with col2:
                                    st.metric("📦 总退货", f"{total_return:,.2f}")
                                with col3:
                                    st.metric("📊 净销售额", f"{total_net:,.2f}")
                                output = io.BytesIO()
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    summary.to_excel(writer, index=False)
                                st.download_button("💾 导出", data=output.getvalue(), file_name=f"累计_{start}_{end}.xlsx", key="export_range_summary")
        else:
            st.info("暂无数据，请先上传订单文件")

# ========== 数据管理（日期查询、发货退货明细、历史业绩） ==========
if idx_data is not None:
    with tabs[idx_data]:
        # 子选项卡：日期查询
        st.markdown("#### 日期查询")
        if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
            if st.button("📅 昨日", key="query_yesterday"):
                st.session_state["query_date_final"] = date.today() - timedelta(days=1)
                st.rerun()
            query_date = st.date_input("查询日期",
                                       value=st.session_state.get("query_date_final", date.today()),
                                       key="query_date_final")
            if st.button("查询", key="query_btn_final"):
                res = st.session_state.df_all_daily[st.session_state.df_all_daily["日期"] == pd.to_datetime(query_date)].copy()
                if res.empty:
                    st.warning("无数据")
                else:
                    res = res.sort_values("店铺名称")
                    res["当日金额"] = res["当日金额"].round(2)
                    res["月累计金额"] = res["月累计金额"].round(2)
                    col_name = "主播名称" if st.session_state.table_suffix == "_all" else "店铺名称"
                    cols = ["日期", col_name, "当日金额", "月累计金额"]
                    if st.session_state.table_suffix == "_all":
                        res = res.rename(columns={"店铺名称": "主播名称"})
                    st.dataframe(res[cols], use_container_width=True, hide_index=True)
                    if st.session_state.table_suffix == "_all":
                        st.metric("📊 总业绩合计", f"当日: {res['当日金额'].sum():,.2f}", delta=f"月累: {res['月累计金额'].sum():,.2f}")
                    else:
                        douyin_df = res[res["店铺名称"].str.contains("抖音", case=False, na=False)]
                        video_df = res[res["店铺名称"].str.contains("视频号", case=False, na=False)]
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("📱 抖音合计", f"当日: {douyin_df['当日金额'].sum():,.2f}", delta=f"月累: {douyin_df['月累计金额'].sum():,.2f}")
                        with col2:
                            st.metric("📺 视频号合计", f"当日: {video_df['当日金额'].sum():,.2f}", delta=f"月累: {video_df['月累计金额'].sum():,.2f}")
                        with col3:
                            st.metric("📊 总业绩合计", f"当日: {res['当日金额'].sum():,.2f}", delta=f"月累: {res['月累计金额'].sum():,.2f}")
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        res[cols].to_excel(writer, index=False)
                    st.download_button("💾 导出", data=output.getvalue(), file_name=f"查询_{query_date}.xlsx", key="export_query_result")
        else:
            st.info("暂无数据")

        # 发货退货明细
        st.markdown("---")
        st.markdown("#### 发货退货明细")
        with st.spinner("正在加载商品数据，请稍候..."):
            prod_df = load_product_sales(st.session_state.table_suffix)
        if prod_df.empty:
            st.info("暂无商品数据，请先上传订单文件")
        else:
            dates = sorted(prod_df["sale_date"].unique(), reverse=True)
            if dates:
                if st.button("📅 昨日", key="ship_yesterday"):
                    max_date = prod_df["sale_date"].max().date()
                    st.session_state["ship_return_date_final"] = max_date
                    st.rerun()
                selected_date = st.selectbox("选择日期", dates, format_func=lambda x: x.strftime("%Y-%m-%d"), key="ship_return_date_final")
                filtered = prod_df[prod_df["sale_date"] == selected_date]
                if st.session_state.table_suffix == "_all":
                    filtered["anchor"] = filtered["remark"].apply(extract_anchor)
                    summary = filtered.groupby("anchor").agg(当日发货=("ship_amount", "sum"), 当日退货=("return_amount", "sum")).reset_index().rename(columns={"anchor": "主播"})
                else:
                    summary = filtered.groupby("shop_name").agg(当日发货=("ship_amount", "sum"), 当日退货=("return_amount", "sum")).reset_index()
                st.dataframe(summary, use_container_width=True, hide_index=True)
                if st.session_state.table_suffix == "_all":
                    st.metric("📊 总合计", f"发货: {summary['当日发货'].sum():,.2f}", delta=f"退货: {summary['当日退货'].sum():,.2f}")
                else:
                    douyin_df = summary[summary["shop_name"].str.contains("抖音", case=False, na=False)]
                    video_df = summary[summary["shop_name"].str.contains("视频号", case=False, na=False)]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📱 抖音合计", f"发货: {douyin_df['当日发货'].sum():,.2f}", delta=f"退货: {douyin_df['当日退货'].sum():,.2f}")
                    with col2:
                        st.metric("📺 视频号合计", f"发货: {video_df['当日发货'].sum():,.2f}", delta=f"退货: {video_df['当日退货'].sum():,.2f}")
                    with col3:
                        st.metric("📊 总业绩合计", f"发货: {summary['当日发货'].sum():,.2f}", delta=f"退货: {summary['当日退货'].sum():,.2f}")
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary.to_excel(writer, index=False)
                st.download_button("💾 导出", data=output.getvalue(), file_name=f"发货退货_{selected_date.strftime('%Y%m%d')}.xlsx", key="export_ship_return")
            else:
                st.info("无日期数据")

        # 历史业绩
        st.markdown("---")
        st.markdown("#### 历史业绩（全部数据）")
        with st.spinner("正在加载历史数据，请稍候..."):
            daily_df = load_daily_sales(st.session_state.table_suffix)
        if not daily_df.empty:
            if st.session_state.table_suffix == "_all":
                daily_df = daily_df.rename(columns={"shop_name": "主播名称"})
            st.dataframe(daily_df, use_container_width=True, hide_index=True)
            if st.session_state.table_suffix == "_all":
                st.metric("📊 总业绩合计", f"{daily_df['amount'].sum():,.2f}")
            else:
                douyin_df = daily_df[daily_df["shop_name"].str.contains("抖音", case=False, na=False)]
                video_df = daily_df[daily_df["shop_name"].str.contains("视频号", case=False, na=False)]
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📱 抖音合计", f"{douyin_df['amount'].sum():,.2f}")
                with col2:
                    st.metric("📺 视频号合计", f"{video_df['amount'].sum():,.2f}")
                with col3:
                    st.metric("📊 总业绩合计", f"{daily_df['amount'].sum():,.2f}")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                daily_df.to_excel(writer, index=False)
            st.download_button("💾 导出全部", data=output.getvalue(), file_name="历史业绩.xlsx", key="export_history_all")
        else:
            st.info("暂无历史数据")

# ========== 销售分布与品牌 ==========
if idx_distribution is not None:
    with tabs[idx_distribution]:
        with st.spinner("正在加载数据，请稍候..."):
            prod_df = load_product_sales(st.session_state.table_suffix)
        if prod_df.empty:
            st.warning("暂无商品销售数据，请先上传订单文件。")
        else:
            if "style_code" in prod_df.columns:
                prod_df["style_code"] = prod_df["style_code"].astype(str).str.strip().str.upper()
            else:
                prod_df["style_code"] = prod_df["product_code"].str[:8].str.strip().str.upper()
            if st.session_state.table_suffix in ["_live", "_all"]:
                if "anchor" not in prod_df.columns:
                    prod_df["anchor"] = prod_df["remark"].astype(str).apply(extract_anchor)
            
            st.markdown("#### 筛选条件")
            min_date = prod_df["sale_date"].min().date()
            max_date = prod_df["sale_date"].max().date()
            
            date_quick_buttons("dist_start_v2", "dist_end_v2",
                               default_start=min_date,
                               default_end=max_date,
                               min_date=min_date,
                               max_date=max_date)
            start_date = st.session_state.get("dist_start_v2", min_date)
            end_date = st.session_state.get("dist_end_v2", max_date)
            
            col_platform, col_shop = st.columns(2)
            with col_platform:
                platform_options = ["全部", "抖音", "视频号"]
                selected_platform = st.selectbox("平台", platform_options, key="dist_platform_v2")
            with col_shop:
                all_shops_all = prod_df["shop_name"].unique()
                if selected_platform == "抖音":
                    shop_options = [shop for shop in all_shops_all if "抖音" in shop]
                elif selected_platform == "视频号":
                    shop_options = [shop for shop in all_shops_all if "视频号" in shop]
                else:
                    shop_options = list(all_shops_all)
                selected_shops = st.multiselect("店铺（可多选）", options=sorted(shop_options), default=[], key="dist_shop_v2")
            
            col_brand, col_anchor = st.columns(2)
            with col_brand:
                brands_all = ["全部"] + sorted(prod_df["brand"].dropna().unique())
                selected_brand = st.selectbox("品牌", brands_all, key="dist_brand_v2")
            with col_anchor:
                selected_anchors = []
                if st.session_state.table_suffix in ["_live", "_all"]:
                    if "anchor" not in prod_df.columns:
                        prod_df["anchor"] = prod_df["remark"].astype(str).apply(extract_anchor)
                    all_anchors = prod_df["anchor"].dropna().unique().tolist()
                    if all_anchors:
                        selected_anchors = st.multiselect("主播（可多选）", options=sorted(all_anchors), default=[], key="dist_anchor_v2")
                    else:
                        st.info("当前数据中未识别到任何主播信息，请检查备注字段是否包含“主播：xxx”格式。")
            
            mask_date = (prod_df["sale_date"] >= pd.to_datetime(start_date)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))
            filtered = prod_df[mask_date].copy()
            if selected_platform == "抖音":
                filtered = filtered[filtered["shop_name"].str.contains("抖音", case=False, na=False)]
            elif selected_platform == "视频号":
                filtered = filtered[filtered["shop_name"].str.contains("视频号", case=False, na=False)]
            if selected_shops:
                filtered = filtered[filtered["shop_name"].isin(selected_shops)]
            if selected_brand != "全部":
                filtered = filtered[filtered["brand"] == selected_brand]
            if selected_anchors:
                filtered = filtered[filtered["anchor"].isin(selected_anchors)]
            
            if filtered.empty:
                st.warning("所选条件下无销售数据")
            else:
                metric_options = ["净销售金额", "发货金额", "退货金额"]
                selected_metric = st.radio("金额指标", metric_options, horizontal=True, key="dist_metric_v2")
                metric_col = {"净销售金额": "net_amount", "发货金额": "ship_amount", "退货金额": "return_amount"}[selected_metric]
                metric_name = selected_metric
                
                if "master_category" not in filtered.columns:
                    master_df = load_product_master()
                    if not master_df.empty and "style_code" in master_df.columns:
                        master_df["style_code"] = master_df["style_code"].astype(str).str.strip().str.upper()
                        cat_map = master_df.set_index("style_code")["category"].to_dict()
                        filtered["master_category"] = filtered["style_code"].map(cat_map).fillna("未分类")
                    else:
                        filtered["master_category"] = "未分类"
                else:
                    filtered["master_category"] = filtered["master_category"].fillna("未分类")
                cat_data = filtered.groupby("master_category")[metric_col].sum().reset_index()
                
                if "year" in filtered.columns and not filtered["year"].isnull().all():
                    year_data = filtered.groupby("year")[metric_col].sum().reset_index()
                    year_data = year_data[year_data["year"].notna()]
                else:
                    total_val = filtered[metric_col].sum()
                    year_data = pd.DataFrame({"year": ["无年份信息"], metric_col: [total_val]}) if total_val > 0 else None
                
                if "season" in filtered.columns and not filtered["season"].isnull().all():
                    season_data = filtered.groupby("season")[metric_col].sum().reset_index()
                    season_data = season_data[season_data["season"].notna()]
                else:
                    total_val = filtered[metric_col].sum()
                    season_data = pd.DataFrame({"season": ["无季节信息"], metric_col: [total_val]}) if total_val > 0 else None
                
                def create_pie_chart(data, name_col, value_col, title, key):
                    if data is None:
                        return None
                    total = data[value_col].sum()
                    if total == 0 or total < 0 and metric_col == "net_amount":
                        return None
                    chart_data = data[data[value_col] != 0].copy()
                    if chart_data.empty:
                        return None
                    fig = px.pie(chart_data, names=name_col, values=value_col, title=title, hole=0.3, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True, key=key)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if cat_data is not None and not cat_data.empty:
                        create_pie_chart(cat_data, "master_category", metric_col, f"分类{metric_name}占比", "pie_category_v2")
                    else:
                        st.info("无分类数据")
                with col2:
                    if year_data is not None and not year_data.empty:
                        create_pie_chart(year_data, "year", metric_col, f"年份{metric_name}占比", "pie_year_v2")
                    else:
                        st.info("无年份数据")
                with col3:
                    if season_data is not None and not season_data.empty:
                        create_pie_chart(season_data, "season", metric_col, f"季节{metric_name}占比", "pie_season_v2")
                    else:
                        st.info("无季节数据")
                
                master_df = load_product_master()
                if "has_newbie_coupon" not in filtered.columns:
                    if not master_df.empty and "style_code" in master_df.columns:
                        master_df["style_code"] = master_df["style_code"].astype(str).str.strip().str.upper()
                        coupon_map = master_df.set_index("style_code")["has_newbie_coupon"].to_dict()
                        filtered["has_newbie_coupon"] = filtered["style_code"].map(coupon_map).fillna(False)
                    else:
                        filtered["has_newbie_coupon"] = False
                else:
                    filtered["has_newbie_coupon"] = filtered["has_newbie_coupon"].fillna(False)
                
                coupon_filtered = filtered[filtered["has_newbie_coupon"] == True].copy()
                non_coupon_filtered = filtered[filtered["has_newbie_coupon"] == False].copy()
                
                st.markdown(f"#### 首单礼金销售分析")
                col_left, col_right = st.columns(2)
                with col_left:
                    coupon_total = coupon_filtered[metric_col].sum()
                    non_coupon_total = non_coupon_filtered[metric_col].sum()
                    if coupon_total > 0 or non_coupon_total > 0:
                        coupon_pie_data = pd.DataFrame({
                            "类型": ["参与首单礼金", "未参与首单礼金"],
                            metric_name: [coupon_total, non_coupon_total]
                        })
                        coupon_pie_data = coupon_pie_data[coupon_pie_data[metric_name] > 0]
                        fig_coupon_total = px.pie(coupon_pie_data, names="类型", values=metric_name,
                                                  title=f"首单礼金商品{metric_name}占比", hole=0.3,
                                                  color_discrete_sequence=["#FF6B6B", "#4ECDC4"])
                        fig_coupon_total.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_coupon_total, use_container_width=True, key="pie_coupon_total_v2")
                    else:
                        st.info("无首单礼金数据")
                with col_right:
                    if not coupon_filtered.empty:
                        coupon_brand_data = coupon_filtered.groupby("brand")[metric_col].sum().reset_index()
                        coupon_brand_data = coupon_brand_data[coupon_brand_data[metric_col] != 0]
                        if not coupon_brand_data.empty:
                            if len(coupon_brand_data) > 8:
                                top8 = coupon_brand_data.nlargest(8, metric_col)
                                other_sum = coupon_brand_data[~coupon_brand_data["brand"].isin(top8["brand"])][metric_col].sum()
                                other_row = pd.DataFrame({"brand": ["其他"], metric_col: [other_sum]})
                                coupon_brand_data = pd.concat([top8, other_row], ignore_index=True)
                            fig_coupon_brand = px.pie(coupon_brand_data, names="brand", values=metric_col,
                                                      title=f"首单礼金商品{metric_name}品牌占比", hole=0.3,
                                                      color_discrete_sequence=px.colors.qualitative.Set2)
                            fig_coupon_brand.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig_coupon_brand, use_container_width=True, key="pie_coupon_brand_v2")
                        else:
                            st.info("无礼金品牌数据")
                    else:
                        st.info("无礼金商品数据")
                
                if not coupon_filtered.empty:
                    st.markdown(f"#### 首单礼金商品销售明细（按货号汇总）")
                    coupon_detail = coupon_filtered.groupby("style_code").agg(
                        发货金额=("ship_amount", "sum"),
                        退货金额=("return_amount", "sum"),
                        净销售金额=("net_amount", "sum")
                    ).reset_index()
                    coupon_detail.rename(columns={"style_code": "货号"}, inplace=True)
                    master_df = load_product_master()
                    if not master_df.empty and "style_code" in master_df.columns:
                        master_df["style_code"] = master_df["style_code"].astype(str).str.strip().str.upper()
                        img_map = master_df.set_index("style_code")["image_url"].to_dict()
                        coupon_detail["图片"] = coupon_detail["货号"].map(img_map).fillna(None)
                    else:
                        coupon_detail["图片"] = None
                    coupon_detail["退款率"] = coupon_detail.apply(
                        lambda r: f"{(r['退货金额']/r['发货金额']*100):.2f}%" if r['发货金额'] != 0 else "-", axis=1
                    )
                    col_order = ["货号", "图片", "发货金额", "退货金额", "净销售金额", "退款率"]
                    coupon_detail = coupon_detail[col_order]
                    st.dataframe(
                        coupon_detail,
                        column_config={
                            "货号": st.column_config.TextColumn("货号"),
                            "图片": st.column_config.ImageColumn("商品图片", help="点击放大"),
                            "发货金额": st.column_config.NumberColumn("发货金额(¥)", format="%.2f"),
                            "退货金额": st.column_config.NumberColumn("退货金额(¥)", format="%.2f"),
                            "净销售金额": st.column_config.NumberColumn("净销售金额(¥)", format="%.2f"),
                            "退款率": st.column_config.TextColumn("退款率")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        export_df = coupon_detail.drop(columns=["图片"], errors='ignore')
                        export_df.to_excel(writer, index=False)
                    st.download_button(
                        "💾 导出首单礼金商品明细",
                        data=output.getvalue(),
                        file_name=f"首单礼金明细_{start_date}_{end_date}.xlsx",
                        key="export_coupon_detail_v2"
                    )
                else:
                    st.info("当前筛选条件下无首单礼金商品")

# ========== 异常预警 ==========
if idx_alert is not None:
    with tabs[idx_alert]:
        st.subheader("⚠️ 异常预警监控")
        st.info("监控近7天业绩下滑明显的店铺，以及退货率激增的商品。可调整敏感度阈值。")
        
        with st.spinner("加载数据..."):
            daily_df = load_daily_sales(st.session_state.table_suffix)
            prod_df = load_product_sales(st.session_state.table_suffix)
        
        if daily_df.empty or prod_df.empty:
            st.warning("数据不足，请先上传订单文件。")
        else:
            if "shop_name" not in daily_df.columns or "amount" not in daily_df.columns:
                st.error("daily_sales 表中缺少 shop_name 或 amount 列，请检查数据结构。")
                st.stop()
            
            today = date.today()
            end_date = today - timedelta(days=1)
            start_date_recent = end_date - timedelta(days=6)
            start_date_previous = start_date_recent - timedelta(days=7)
            end_date_previous = start_date_recent - timedelta(days=1)
            
            min_data_date = daily_df["sale_date"].min().date()
            max_data_date = daily_df["sale_date"].max().date()
            if start_date_recent < min_data_date:
                st.warning("数据不足以覆盖近7天，请检查数据日期范围。")
                st.stop()
            
            # 业绩下滑店铺
            st.markdown("### 📉 业绩下滑店铺（近7天 vs 前7天日均）")
            col1, col2 = st.columns([2, 1])
            with col1:
                decline_threshold = st.slider("下滑幅度阈值（%）", min_value=0, max_value=100, value=20, key="decline_threshold")
            with col2:
                min_days = st.number_input("至少需要最近7天有销售天数", min_value=1, max_value=7, value=3, key="min_days")
            
            mask_recent = (daily_df["sale_date"] >= pd.to_datetime(start_date_recent)) & (daily_df["sale_date"] <= pd.to_datetime(end_date))
            mask_previous = (daily_df["sale_date"] >= pd.to_datetime(start_date_previous)) & (daily_df["sale_date"] <= pd.to_datetime(end_date_previous))
            
            recent_data = daily_df[mask_recent].copy()
            previous_data = daily_df[mask_previous].copy()
            
            recent_agg = recent_data.groupby("shop_name").agg(
                近7天总额=("amount", "sum"),
                近7天天数=("amount", "count")
            ).reset_index()
            previous_agg = previous_data.groupby("shop_name").agg(
                前7天总额=("amount", "sum"),
                前7天天数=("amount", "count")
            ).reset_index()
            
            merged = pd.merge(recent_agg, previous_agg, on="shop_name", how="inner")
            merged["近7天日均"] = merged["近7天总额"] / merged["近7天天数"]
            merged["前7天日均"] = merged["前7天总额"] / merged["前7天天数"]
            merged = merged[merged["近7天天数"] >= min_days]
            merged["下滑幅度"] = ((merged["前7天日均"] - merged["近7天日均"]) / merged["前7天日均"] * 100).round(2)
            decline_df = merged[merged["下滑幅度"] >= decline_threshold].sort_values("下滑幅度", ascending=False)
            
            if decline_df.empty:
                st.success("🎉 近7天没有业绩下滑明显的店铺。")
            else:
                st.dataframe(
                    decline_df[["shop_name", "近7天日均", "前7天日均", "下滑幅度"]],
                    column_config={
                        "shop_name": "店铺",
                        "近7天日均": st.column_config.NumberColumn("近7天日均(¥)", format="%.2f"),
                        "前7天日均": st.column_config.NumberColumn("前7天日均(¥)", format="%.2f"),
                        "下滑幅度": st.column_config.NumberColumn("下滑幅度(%)", format="%.2f%%"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
                worst = decline_df.iloc[0]
                st.metric("⚠️ 下滑最严重店铺", worst["shop_name"], delta=f"{worst['下滑幅度']:.2f}%", delta_color="inverse")
            
            # 退货率激增商品
            st.markdown("### 📈 退货率激增商品（近7天 vs 前7天退货率）")
            col3, col4 = st.columns(2)
            with col3:
                return_rate_threshold = st.slider("退货率上升阈值（百分点）", min_value=0, max_value=50, value=10, key="return_rate_threshold")
            with col4:
                min_ship_recent = st.number_input("近7天发货金额至少", min_value=0, value=1000, step=100, key="min_ship")
            
            prod_recent = prod_df[(prod_df["sale_date"] >= pd.to_datetime(start_date_recent)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))]
            prod_previous = prod_df[(prod_df["sale_date"] >= pd.to_datetime(start_date_previous)) & (prod_df["sale_date"] <= pd.to_datetime(end_date_previous))]
            
            def agg_ship_return(df):
                return df.groupby("style_code").agg(
                    发货金额=("ship_amount", "sum"),
                    退货金额=("return_amount", "sum")
                ).reset_index()
            
            recent_prod = agg_ship_return(prod_recent)
            previous_prod = agg_ship_return(prod_previous)
            
            merged_prod = pd.merge(recent_prod, previous_prod, on="style_code", suffixes=("_近7天", "_前7天"), how="inner")
            merged_prod = merged_prod[merged_prod["发货金额_近7天"] >= min_ship_recent]
            merged_prod["退货率_近7天"] = (merged_prod["退货金额_近7天"] / merged_prod["发货金额_近7天"] * 100).round(2)
            merged_prod["退货率_前7天"] = (merged_prod["退货金额_前7天"] / merged_prod["发货金额_前7天"] * 100).round(2)
            merged_prod["退货率_前7天"] = merged_prod["退货率_前7天"].fillna(0)
            merged_prod["退货率变化"] = (merged_prod["退货率_近7天"] - merged_prod["退货率_前7天"]).round(2)
            return_spike = merged_prod[merged_prod["退货率变化"] >= return_rate_threshold].sort_values("退货率变化", ascending=False)
            
            if return_spike.empty:
                st.success("🎉 近7天没有退货率激增的商品。")
            else:
                master_df = load_product_master()
                if not master_df.empty and "style_code" in master_df.columns:
                    master_df["style_code"] = master_df["style_code"].astype(str).str.strip().str.upper()
                    return_spike = return_spike.merge(master_df[["style_code", "category"]], on="style_code", how="left")
                    return_spike.rename(columns={"category": "分类"}, inplace=True)
                else:
                    return_spike["分类"] = "-"
                
                st.dataframe(
                    return_spike[["style_code", "分类", "发货金额_近7天", "退货率_近7天", "退货率_前7天", "退货率变化"]],
                    column_config={
                        "style_code": "货号",
                        "分类": "分类",
                        "发货金额_近7天": st.column_config.NumberColumn("近7天发货(¥)", format="%.2f"),
                        "退货率_近7天": st.column_config.NumberColumn("近7天退货率(%)", format="%.2f%%"),
                        "退货率_前7天": st.column_config.NumberColumn("前7天退货率(%)", format="%.2f%%"),
                        "退货率变化": st.column_config.NumberColumn("变化(百分点)", format="%.2f"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
                worst_prod = return_spike.iloc[0]
                st.metric("⚠️ 退货率激增最严重商品", worst_prod["style_code"], delta=f"{worst_prod['退货率变化']:.2f} 百分点", delta_color="inverse")

# ========== 调试 ==========
if idx_debug is not None:
    with tabs[idx_debug]:
        st.subheader("🔧 调试信息")
        st.json({
            "当前数据源后缀": st.session_state.table_suffix,
            "每日业绩数据行数": len(st.session_state.df_all_daily) if st.session_state.df_all_daily is not None else 0,
            "目标字典": st.session_state.target_dict,
            "子账号数": len(st.session_state.sub_users)
        })

# ========== 商品库导出 ==========
if idx_export is not None:
    with tabs[idx_export]:
        st.subheader("📚 导出商品库数据（product_master）")
        master_df = load_product_master()
        if master_df.empty:
            st.warning("商品库（product_master）为空，无法导出。")
        else:
            st.write(f"当前商品库共有 **{len(master_df)}** 条记录。")
            with st.expander("点击预览商品库数据"):
                st.dataframe(master_df.head(10), use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                master_df.to_excel(writer, index=False)
            st.download_button(
                label="📥 导出全部商品库数据 (Excel)",
                data=output.getvalue(),
                file_name=f"product_master_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ========== 系统设置 ==========
if idx_system is not None:
    with tabs[idx_system]:
        st.subheader("👥 账号管理与权限设置（按数据源分别设置）")
        st.info("对每个子账号，可分别配置其在“非直播数据”、“直播数据”、“全部数据”下能看到的选项卡。")

        if st.button("🔄 重新从数据库加载账号"):
            st.session_state.sub_users = load_sub_accounts_from_db()
            st.success("已重新加载")
            st.rerun()

        if st.session_state.sub_users:
            for username, info in list(st.session_state.sub_users.items()):
                with st.expander(f"账号：{username}"):
                    st.markdown(f"**{username}** 的权限配置")
                    perms = info.get("permissions", {})
                    for suf in ["", "_live", "_all"]:
                        if suf not in perms:
                            perms[suf] = []
                    suffix_display = {"": "非直播数据", "_live": "直播数据", "_all": "全部数据"}
                    new_perms = {}
                    for suf, display_name in suffix_display.items():
                        current_allowed = perms.get(suf, [])
                        all_options = base_tabs
                        default = [tab for tab in current_allowed if tab in all_options]
                        selected = st.multiselect(
                            f"{display_name} 允许的选项卡",
                            options=all_options,
                            default=default,
                            key=f"perm_{username}_{suf}"
                        )
                        new_perms[suf] = selected
                    
                    current_default = info.get("default_suffix", "")
                    default_options = {"非直播数据": "", "直播数据": "_live", "全部数据": "_all"}
                    default_display = [k for k, v in default_options.items() if v == current_default]
                    default_display = default_display[0] if default_display else "非直播数据"
                    new_default_display = st.selectbox(
                        "默认数据源",
                        options=list(default_options.keys()),
                        index=list(default_options.keys()).index(default_display),
                        key=f"default_suffix_{username}"
                    )
                    new_default = default_options[new_default_display]

                    st.markdown("**数据过滤权限**")
                    platform_options = ["all", "抖音", "视频号"]
                    current_platform = info.get("filter_platform", "all")
                    new_platform = st.selectbox(
                        "限制平台（all=全部）",
                        options=platform_options,
                        index=platform_options.index(current_platform) if current_platform in platform_options else 0,
                        key=f"platform_{username}"
                    )
                    @st.cache_data(ttl=600)
                    def get_all_shop_names():
                        df = load_product_sales(apply_filter=False)
                        if df.empty:
                            return []
                        if st.session_state.table_suffix == "_all":
                            if "anchor" in df.columns:
                                return sorted(df["anchor"].dropna().unique().tolist())
                            else:
                                return []
                        else:
                            if "shop_name" in df.columns:
                                return sorted(df["shop_name"].dropna().unique().tolist())
                            else:
                                return []
                    all_shop_names = get_all_shop_names()
                    current_shop_names = info.get("filter_shop_names", [])
                    current_shop_names = [name for name in current_shop_names if name in all_shop_names]
                    new_shop_names = st.multiselect(
                        "限制店铺/主播（空表示全部）",
                        options=all_shop_names,
                        default=current_shop_names,
                        key=f"shops_{username}"
                    )

                    if st.button(f"保存全部权限", key=f"save_perm_{username}"):
                        st.session_state.sub_users[username]["permissions"] = new_perms
                        st.session_state.sub_users[username]["default_suffix"] = new_default
                        st.session_state.sub_users[username]["filter_platform"] = new_platform
                        st.session_state.sub_users[username]["filter_shop_names"] = new_shop_names
                        ok, msg = save_sub_account_to_db(username, st.session_state.sub_users[username])
                        if ok:
                            st.success(f"权限已保存到数据库")
                            st.rerun()
                        else:
                            st.error(f"保存失败：{msg}")
                    
                    if st.button(f"删除账号", key=f"del_{username}"):
                        ok, msg = delete_sub_account_from_db(username)
                        if ok:
                            del st.session_state.sub_users[username]
                            st.success(f"账号 {username} 已删除")
                            st.rerun()
                        else:
                            st.error(f"删除失败：{msg}")
        else:
            st.info("暂无子账号")
        
        with st.expander("➕ 创建新子账号"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("用户名", key="new_username_sys")
                new_password = st.text_input("密码", type="password", key="new_password_sys")
            with col2:
                default_suffix = st.selectbox("默认数据源", ["非直播数据", "直播数据", "全部数据"], key="new_default_suffix_sys")
                suffix_map = {"非直播数据": "", "直播数据": "_live", "全部数据": "_all"}
                default_perms = {suf: base_tabs for suf in ["", "_live", "_all"]}
                default_platform = "all"
            if st.button("创建子账号", key="create_sys"):
                if new_username and new_password:
                    if new_username in st.session_state.sub_users:
                        st.error("用户名已存在")
                    else:
                        new_info = {
                            "password": new_password,
                            "role": "viewer",
                            "default_suffix": suffix_map[default_suffix],
                            "permissions": default_perms,
                            "filter_platform": default_platform,
                            "filter_shop_names": []
                        }
                        ok, msg = save_sub_account_to_db(new_username, new_info)
                        if ok:
                            st.session_state.sub_users[new_username] = new_info
                            st.success(f"子账号 {new_username} 创建成功（已保存到数据库）")
                            st.rerun()
                        else:
                            st.error(f"创建失败：{msg}")
                else:
                    st.error("请填写用户名和密码")
