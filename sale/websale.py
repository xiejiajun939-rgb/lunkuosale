# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import date
import io
from supabase import create_client
import plotly.express as px
import re

# ========== 页面配置 ==========
st.set_page_config(page_title="业绩统计工具", layout="wide", page_icon="📊")

# ========== 密码验证 ==========
PASSWORD = "94949468"

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated:
        return True
    st.title("🔒 请输入访问密码")
    with st.form("password_form"):
        pwd = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")
        if submitted:
            if pwd == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("密码错误")
    return False

if not check_password():
    st.stop()

st.title("📊 店铺业绩汇总分析")
st.markdown("---")

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

# ========== 初始化 session_state ==========
if "df_all_daily" not in st.session_state: st.session_state.df_all_daily = None
if "target_dict" not in st.session_state: st.session_state.target_dict = {}
if "latest_date" not in st.session_state: st.session_state.latest_date = None
if "uploaded_order_hash" not in st.session_state: st.session_state.uploaded_order_hash = None

# ========== 核心逻辑函数 ==========
def load_daily_sales():
    if supabase is None: return pd.DataFrame()
    try:
        resp = supabase.table("daily_sales").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df["sale_date"] = pd.to_datetime(df["sale_date"])
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

def save_daily_sales(records):
    if supabase and records:
        supabase.table("daily_sales").upsert(records, on_conflict="sale_date,shop_name").execute()

def rebuild_daily_data():
    df = load_daily_sales()
    if df.empty:
        st.session_state.df_all_daily = None
        return
    df = df.rename(columns={"sale_date": "日期", "shop_name": "店铺名称", "amount": "当日金额", "cumulative_amount": "月累计金额"})
    st.session_state.df_all_daily = df.sort_values(["店铺名称", "日期"])
    st.session_state.daily_latest = df.loc[df.groupby("店铺名称")["日期"].idxmax()].copy()
    st.session_state.latest_date = df["日期"].max()

def load_targets():
    if supabase is None: return {}
    try:
        resp = supabase.table("shop_targets").select("*").execute()
        return {row["shop_name"]: row["target_amount"] for row in resp.data} if resp.data else {}
    except: return {}

def save_targets(target_dict):
    if supabase and target_dict:
        records = [{"shop_name": k, "target_amount": v} for k, v in target_dict.items()]
        supabase.table("shop_targets").upsert(records, on_conflict="shop_name").execute()

def clear_targets():
    if supabase: supabase.table("shop_targets").delete().neq("id", 0).execute()
    st.session_state.target_dict = {}
    st.rerun()

# ========== 商品相关函数 ==========
SEASON_MAP = {"1": "春", "2": "夏", "3": "秋", "4": "冬"}
SIZE_MAP = {"001": "S", "002": "M", "003": "L", "004": "XL", "008": "均码"}

def parse_product_code(remark):
    try:
        parts = remark.split('_')
        if len(parts) < 2: return None
        product_code = parts[1]
        if len(product_code) < 14: return None
        return {
            "product_code": product_code,
            "style_code": product_code[:8],
            "brand": product_code[0],
            "year": product_code[1:3],
            "season": SEASON_MAP.get(product_code[3], product_code[3]),
            "category": product_code[4],
            "style": product_code[5:8],
            "color_code": product_code[8:11],
            "size": SIZE_MAP.get(product_code[11:14], product_code[11:14])
        }
    except: return None

@st.cache_data(ttl=600)
def load_product_master():
    if supabase is None: return pd.DataFrame()
    resp = supabase.table("product_master").select("*").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

def save_product_sales(df_orders):
    if supabase is None: return
    records = []
    for _, row in df_orders.iterrows():
        parsed = parse_product_code(str(row["备注"]))
        if not parsed: continue
        amount = float(row["金额/时间"])
        records.append({
            "remark": row["备注"],
            "sale_date": row["日期"].strftime("%Y-%m-%d"),
            "shop_name": row["店铺名称"],
            "product_code": parsed["product_code"],
            "style_code": parsed["style_code"],
            "ship_amount": max(amount, 0),
            "return_amount": max(-amount, 0),
            "net_amount": amount
        })
    if records:
        supabase.table("product_sales").upsert(records, on_conflict="remark").execute()

@st.cache_data(ttl=600)
def load_product_sales():
    if supabase is None: return pd.DataFrame()
    resp = supabase.table("product_sales").select("*").execute()
    if not resp.data: return pd.DataFrame()
    df = pd.DataFrame(resp.data)
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df

# ========== 订单文件处理 ==========
def process_uploaded_file(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, header=1)
        df["日期"] = pd.to_datetime(df["日期"])
        df["店铺名称"] = df["备注"].astype(str).str.split("_").str[-1].str.replace(r'^商店[：:]', '', regex=True).str.strip()
        df = df[df["店铺名称"].notna() & (df["店铺名称"] != "")].copy()
        df["金额/时间"] = pd.to_numeric(df["金额/时间"], errors="coerce")
        save_product_sales(df.dropna(subset=["金额/时间"]))
        rebuild_daily_data()
        return True, "处理完成"
    except Exception as e: return False, str(e)

def load_target_file(uploaded_file):
    try:
        df_target = pd.read_excel(uploaded_file, header=None)
        if "月目标" in str(df_target.iloc[0, 0]): df_target = df_target.iloc[1:]
        target_dict = {str(row[0]): float(row[1]) for _, row in df_target.iterrows() if pd.notna(row[1])}
        save_targets(target_dict)
        st.session_state.target_dict = target_dict
        return True, "成功"
    except Exception as e: return False, str(e)

# ========== 页面初始化 ==========
rebuild_daily_data()
if not st.session_state.target_dict: st.session_state.target_dict = load_targets()

# ========== 侧边栏与选项卡 ==========
with st.sidebar:
    uploaded_order = st.file_uploader("选择订单文件", type=["xlsx"])
    if uploaded_order and st.session_state.get("uploaded_order_hash") != uploaded_order.name:
        ok, msg = process_uploaded_file(uploaded_order)
        if ok: st.session_state.uploaded_order_hash = uploaded_order.name; st.rerun()
        else: st.error(msg)
    
    target_file = st.file_uploader("选择目标文件", type=["xlsx"])
    if target_file:
        ok, msg = load_target_file(target_file)
        if ok: st.success(msg)

tab1, tab2, tab3, tab4, tab5, tab6, tab_debug = st.tabs(["📅 明细", "🏪 累计", "🔍 查询", "📦 发退", "🗄️ 历史", "📊 商品", "🔧 调试"])

with tab1:
    if st.session_state.get("daily_latest") is not None:
        st.dataframe(st.session_state.daily_latest, use_container_width=True)

with tab6:
    st.subheader("📊 商品销售分析（按货号汇总）")
    prod_df = load_product_sales()
    if prod_df.empty:
        st.warning("暂无数据")
    else:
        # 修复后的逻辑：先聚合，再合并商品库信息
        grouped = prod_df.groupby("style_code").agg(
            发货金额=("ship_amount", "sum"),
            退货金额=("return_amount", "sum"),
            净销售金额=("net_amount", "sum")
        ).reset_index().rename(columns={"style_code": "货号"})
        
        master_df = load_product_master()
        if not master_df.empty and "style_code" in master_df.columns:
            attr = master_df[["style_code", "image_url", "category"]].drop_duplicates(subset="style_code")
            attr.rename(columns={"style_code": "货号", "category": "master_category"}, inplace=True)
            grouped = grouped.merge(attr, on="货号", how="left")
        
        st.dataframe(
            grouped.sort_values("净销售金额", ascending=False),
            column_config={"image_url": st.column_config.ImageColumn("图片")},
            hide_index=True, use_container_width=True
        )

with tab_debug:
    st.write("调试：检查列名")
    prod_df = load_product_sales()
    if not prod_df.empty: st.write("当前字段:", prod_df.columns.tolist())
