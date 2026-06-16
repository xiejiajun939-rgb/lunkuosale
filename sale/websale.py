# -*- coding: utf-8 -*-
"""
订单业绩统计工具 - 最终完整版
管理员账号：admin / 1234567890
子账号示例：NC01 / 123456
"""

import streamlit as st
import pandas as pd
from datetime import date
import io
import hashlib
import time
import re
import numpy as np
from supabase import create_client
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="业绩统计工具", layout="wide", page_icon="📊")

# ========== 自定义CSS - 调整标题比例和布局 ==========
st.markdown("""
<style>
    /* 主标题（原 st.title） */
    .custom-main-title {
        font-size: 28px !important;
        font-weight: 600 !important;
        margin-top: -0.5rem !important;
        margin-bottom: 0.25rem !important;
        padding-bottom: 0 !important;
    }
    /* 欢迎信息 */
    .welcome-text {
        font-size: 14px !important;
        color: #555 !important;
        margin-top: 0 !important;
        margin-bottom: 0.5rem !important;
    }
    /* 全局标题样式（覆盖 st.header, st.subheader,  markdown 标题） */
    h1 {
        font-size: 28px !important;
        margin-top: -0.5rem !important;
        margin-bottom: 0.25rem !important;
    }
    h2 {
        font-size: 24px !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.25rem !important;
        font-weight: 500 !important;
    }
    h3 {
        font-size: 20px !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.25rem !important;
        font-weight: 500 !important;
    }
    h4 {
        font-size: 18px !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.25rem !important;
        font-weight: 500 !important;
    }
    h5, h6 {
        font-size: 16px !important;
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
    }
    /* 分割线间距 */
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    /* 侧边栏标题（可选） */
    .css-1d391kg h1, .css-1d391kg h2, .css-1d391kg h3 {
        font-size: 1.2rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ========== 子账号存储 ==========
if "sub_users" not in st.session_state:
    st.session_state.sub_users = {"NC01": {"password": "123456", "role": "viewer", "default_suffix": "_all"}}

def get_all_users():
    users = {
        "admin": {"password": "1234567890", "role": "admin", "default_suffix": ""},
        "XDZ01": {"password": "94949468", "role": "user", "default_suffix": ""},
        "ZBZ01": {"password": "123456", "role": "user", "default_suffix": "_live"}
    }
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

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    login()
    st.stop()

# ========== 主页面 - 使用自定义标题替代默认的st.title ==========
st.markdown('<div class="custom-main-title">📊 商品销售分析罗盘测试页</div>', unsafe_allow_html=True)
st.markdown(f'<div class="welcome-text">欢迎，**{st.session_state.username}** ({"管理员" if st.session_state.role == "admin" else ("子账号" if st.session_state.role == "viewer" else "成员")})</div>', unsafe_allow_html=True)
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

def get_table_name(base_name, suffix=None):
    if suffix is None:
        suffix = st.session_state.get("table_suffix", "")
    return f"{base_name}{suffix}"

# ========== 初始化 session_state ==========
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

# ========== 辅助函数 ==========
def extract_anchor(remark):
    if not isinstance(remark, str):
        return None
    match = re.search(r'主播[：:]([^_]+)', remark)
    return match.group(1).strip() if match else None

def load_daily_sales(suffix=None):
    if supabase is None:
        return pd.DataFrame()
    try:
        table_name = get_table_name("daily_sales", suffix)
        resp = supabase.table(table_name).select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df["sale_date"] = pd.to_datetime(df["sale_date"])
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载店铺业绩失败：{e}")
        return pd.DataFrame()

def save_daily_sales(records, suffix=None):
    if supabase is None or not records:
        return
    table_name = get_table_name("daily_sales", suffix)
    supabase.table(table_name).upsert(records, on_conflict="sale_date,shop_name").execute()

def rebuild_daily_data(suffix=None):
    df = load_daily_sales(suffix)
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
        with st.spinner("正在重建每日业绩，请稍候..."):
            product_table = get_table_name("product_sales", suffix)
            all_data = []
            page = 0
            page_size = 1000
            while True:
                resp = supabase.table(product_table).select("sale_date, shop_name, net_amount, remark").range(page * page_size, (page + 1) * page_size - 1).execute()
                if not resp.data:
                    break
                all_data.extend(resp.data)
                if len(resp.data) < page_size:
                    break
                page += 1
            if not all_data:
                daily_table = get_table_name("daily_sales", suffix)
                supabase.table(daily_table).delete().neq("id", 0).execute()
                return True, "商品销售表无数据，已清空每日业绩表"
            df = pd.DataFrame(all_data)
            df["sale_date"] = pd.to_datetime(df["sale_date"])
            if suffix == "_all":
                df["anchor"] = df["remark"].apply(extract_anchor)
                daily_agg = df.groupby(["sale_date", "anchor"])["net_amount"].sum().reset_index()
                daily_agg.columns = ["sale_date", "店铺名称", "amount"]
            else:
                daily_agg = df.groupby(["sale_date", "shop_name"])["net_amount"].sum().reset_index()
                daily_agg.columns = ["sale_date", "店铺名称", "amount"]
            daily_agg = daily_agg.sort_values(["店铺名称", "sale_date"])
            daily_agg["cumulative_amount"] = daily_agg.groupby("店铺名称")["amount"].cumsum().round(2)
            records = []
            for _, row in daily_agg.iterrows():
                records.append({
                    "sale_date": row["sale_date"].strftime("%Y-%m-%d"),
                    "shop_name": row["店铺名称"],
                    "amount": float(row["amount"]),
                    "cumulative_amount": float(row["cumulative_amount"])
                })
            if records:
                daily_table = get_table_name("daily_sales", suffix)
                supabase.table(daily_table).delete().neq("id", 0).execute()
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

# ========== 商品相关函数 ==========
SEASON_MAP = {"1": "春", "2": "夏", "3": "秋", "4": "冬"}
SIZE_MAP = {"001": "S", "002": "M", "003": "L", "004": "XL", "008": "均码"}

def parse_product_code(remark):
    try:
        parts = remark.split('_')
        if len(parts) < 2:
            return None
        product_code = parts[1]
        if len(product_code) < 14:
            return None
        brand = product_code[0]
        year_season = product_code[1:4]
        year = year_season[:2]
        season_code = year_season[2]
        category = product_code[4]
        style = product_code[5:8]
        color_code = product_code[8:11]
        size_code = product_code[11:14]
        style_code = product_code[:8]
        return {
            "product_code": product_code,
            "style_code": style_code,
            "brand": brand,
            "year": year,
            "season": SEASON_MAP.get(season_code, season_code),
            "category": category,
            "style": style,
            "color_code": color_code,
            "size": SIZE_MAP.get(size_code, size_code)
        }
    except:
        return None

@st.cache_data(ttl=600)
def load_product_master():
    if supabase is None:
        return pd.DataFrame()
    try:
        all_data = []
        page = 0
        page_size = 1000
        while True:
            resp = supabase.table("product_master").select("*").range(page * page_size, (page + 1) * page_size - 1).execute()
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
        resp = supabase.table("product_master").update({"has_newbie_coupon": flag_value}).eq("style_code", style_code).execute()
        return True, "更新成功"
    except Exception as e:
        return False, str(e)

def save_product_sales(df_orders, suffix=None):
    if supabase is None:
        return
    master_df = load_product_master()
    master_map = {}
    if not master_df.empty:
        for _, row in master_df.iterrows():
            code = row["style_code"]
            master_map[code] = {
                "image_url": row.get("image_url", None),
                "master_category": row.get("category", None),
                "has_newbie_coupon": row.get("has_newbie_coupon", False)
            }
    temp_records = {}
    for _, row in df_orders.iterrows():
        remark = row["备注"]
        parsed = parse_product_code(remark)
        if parsed is None:
            continue
        amount = float(row["金额/时间"])
        short_code = parsed["style_code"]
        img = master_map.get(short_code, {}).get("image_url")
        cat = master_map.get(short_code, {}).get("master_category")
        if remark not in temp_records:
            temp_records[remark] = {
                "remark": remark,
                "sale_date": row["日期"].strftime("%Y-%m-%d"),
                "shop_name": row["店铺名称"],
                "product_code": parsed["product_code"],
                "style_code": short_code,
                "brand": parsed["brand"],
                "year": parsed["year"],
                "season": parsed["season"],
                "product_category": parsed["category"],
                "style": parsed["style"],
                "color_code": parsed["color_code"],
                "size_code": parsed["size"],
                "ship_amount": max(amount, 0),
                "return_amount": max(-amount, 0),
                "net_amount": amount,
                "image_url": img,
                "master_category": cat
            }
        else:
            existing = temp_records[remark]
            existing["ship_amount"] += max(amount, 0)
            existing["return_amount"] += max(-amount, 0)
            existing["net_amount"] += amount
    records = list(temp_records.values())
    if records:
        table_name = get_table_name("product_sales", suffix)
        supabase.table(table_name).upsert(records, on_conflict="remark").execute()

@st.cache_data(ttl=600)
def load_product_sales(suffix=None):
    if supabase is None:
        return pd.DataFrame()
    try:
        table_name = get_table_name("product_sales", suffix)
        all_data = []
        page = 0
        page_size = 1000
        while True:
            resp = supabase.table(table_name).select("*").range(page * page_size, (page + 1) * page_size - 1).execute()
            if not resp.data:
                break
            all_data.extend(resp.data)
            if len(resp.data) < page_size:
                break
            page += 1
        if all_data:
            df = pd.DataFrame(all_data)
            df["sale_date"] = pd.to_datetime(df["sale_date"])
            if "style_code" not in df.columns or df["style_code"].isnull().all():
                df["style_code"] = df["product_code"].str[:8]
            else:
                df["style_code"] = df["style_code"].fillna(df["product_code"].str[:8])
            for col in ["ship_amount", "return_amount", "net_amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            # 补充主播列（用于直播/全部数据）
            if suffix in ["_live", "_all"] and "anchor" not in df.columns:
                df["anchor"] = df["remark"].apply(extract_anchor)
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载商品销售数据失败：{e}")
        return pd.DataFrame()

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
        if suffix == "_all":
            df_valid["anchor"] = df_valid["备注"].apply(extract_anchor)
            new_daily = df_valid.groupby(["日期", "anchor"])["金额/时间"].sum().reset_index()
            new_daily.columns = ["日期", "店铺名称", "当日金额"]
        else:
            new_daily = df_valid.groupby(["日期", "店铺名称"])["金额/时间"].sum().reset_index()
            new_daily.columns = ["日期", "店铺名称", "当日金额"]
        new_daily["日期"] = pd.to_datetime(new_daily["日期"])
        existing = load_daily_sales(suffix)
        if not existing.empty:
            new_dates = new_daily["日期"].dt.date.unique()
            existing = existing[~existing["sale_date"].dt.date.isin(new_dates)]
            if not existing.empty:
                existing_df = existing[["sale_date", "shop_name", "amount"]].rename(
                    columns={"sale_date": "日期", "shop_name": "店铺名称", "amount": "当日金额"}
                )
                merged = pd.concat([existing_df, new_daily], ignore_index=True)
            else:
                merged = new_daily.copy()
        else:
            merged = new_daily.copy()
        merged = merged.sort_values(["店铺名称", "日期"])
        merged["当日金额"] = pd.to_numeric(merged["当日金额"], errors="coerce").fillna(0)
        merged["月累计金额"] = merged.groupby("店铺名称")["当日金额"].cumsum().round(2)
        records = []
        for _, row in merged.iterrows():
            records.append({
                "sale_date": row["日期"].strftime("%Y-%m-%d"),
                "shop_name": row["店铺名称"],
                "amount": float(row["当日金额"]),
                "cumulative_amount": float(row["月累计金额"])
            })
        save_daily_sales(records, suffix)
        if suffix == st.session_state.get("table_suffix", ""):
            rebuild_daily_data(suffix)
            st.session_state.target_dict = load_targets(suffix)
        latest_date = merged["日期"].max().strftime('%Y-%m-%d') if not merged.empty else "无数据"
        return True, f"处理完成！最新日期：{latest_date}"
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

def manage_sub_accounts():
    st.subheader("👥 子账号管理")
    with st.expander("创建新子账号"):
        new_username = st.text_input("用户名", key="new_username")
        new_password = st.text_input("密码", type="password", key="new_password")
        default_suffix = st.selectbox("默认数据源", ["非直播数据", "直播数据", "全部数据"], key="new_default_suffix")
        suffix_map = {"非直播数据": "", "直播数据": "_live", "全部数据": "_all"}
        if st.button("创建子账号"):
            if new_username and new_password:
                if new_username in st.session_state.sub_users:
                    st.error("用户名已存在")
                else:
                    st.session_state.sub_users[new_username] = {
                        "password": new_password,
                        "role": "viewer",
                        "default_suffix": suffix_map[default_suffix]
                    }
                    st.success(f"子账号 {new_username} 创建成功")
                    st.rerun()
            else:
                st.error("请填写用户名和密码")
    st.markdown("#### 已有子账号")
    if st.session_state.sub_users:
        for username, info in list(st.session_state.sub_users.items()):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            col1.write(username)
            col2.write("●" * len(info["password"]))
            suffix_display = {"": "非直播", "_live": "直播", "_all": "全部"}.get(info["default_suffix"], "未知")
            col3.write(suffix_display)
            with col4:
                if st.button("删除", key=f"del_{username}"):
                    del st.session_state.sub_users[username]
                    st.rerun()
    else:
        st.info("暂无子账号")

def manage_newbie_coupon():
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
                else:  # 整体替换
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

# ========== 侧边栏 ==========
with st.sidebar:
    st.header("📂 数据加载")
    if st.session_state.role == "admin":
        st.subheader("🔄 数据源切换")
        suffix_names = {"": "非直播数据", "_live": "直播数据", "_all": "全部数据"}
        current_source_name = suffix_names.get(st.session_state.table_suffix, "未知")
        st.info(f"📌 当前正在查看：**{current_source_name}**")
        source_options = {"非直播数据": "", "直播数据": "_live", "全部数据": "_all"}
        default_index = list(source_options.keys()).index(current_source_name) if current_source_name in source_options else 0
        selected_source = st.selectbox("选择要切换到的数据源", options=list(source_options.keys()), index=default_index, key="source_selectbox_final")
        if st.button("✅ 确认切换", key="confirm_switch_final"):
            new_suffix = source_options[selected_source]
            if new_suffix != st.session_state.table_suffix:
                st.session_state.table_suffix = new_suffix
                st.cache_data.clear()
                st.rerun()
        st.markdown("---")
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
        manage_sub_accounts()
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
base_tab_labels = [
    "📅 最新日明细", "🏪 日期范围累计", "🔍 日期查询",
    "📦 发货退货明细", "🗄️ 历史业绩", "📊 商品分析",
    "🎤 销售对比", "📈 销售分布与品牌"
]
admin_extra_tabs = []
if st.session_state.role == "admin":
    admin_extra_tabs = ["🔧 调试", "📚 商品库导出"]
    all_tab_labels = base_tab_labels + admin_extra_tabs
else:
    all_tab_labels = base_tab_labels

tabs = st.tabs(all_tab_labels)

tab_index_latest = 0
tab_index_range = 1
tab_index_query = 2
tab_index_ship_return = 3
tab_index_history = 4
tab_index_product = 5
tab_index_anchor_compare = 6
tab_index_distribution = 7
if st.session_state.role == "admin":
    tab_index_debug = 8
    tab_index_export = 9

# ========== 最新日明细 ==========
with tabs[tab_index_latest]:
    source_names = {"": "非直播数据", "_live": "直播数据", "_all": "全部数据"}
    current_source = source_names.get(st.session_state.table_suffix, "未知")
    st.info(f"📌 当前查看的数据源：**{current_source}**")
    if st.session_state.table_suffix == "_all":
        df_daily_all = st.session_state.df_all_daily
        all_entities = df_daily_all["店铺名称"].unique().tolist() if df_daily_all is not None and not df_daily_all.empty else []
        target_entities = list(st.session_state.target_dict.keys())
        all_entities = list(set(all_entities + target_entities))
        col_name = "主播名称"
    else:
        df_daily_all = st.session_state.df_all_daily
        all_entities = df_daily_all["店铺名称"].unique().tolist() if df_daily_all is not None and not df_daily_all.empty else []
        target_entities = list(st.session_state.target_dict.keys())
        all_entities = list(set(all_entities + target_entities))
        col_name = "店铺名称"
    if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
        latest_date_global = st.session_state.df_all_daily["日期"].max()
    else:
        latest_date_global = None
    if latest_date_global is not None:
        month_start = latest_date_global.replace(day=1)
        df_latest_existing = st.session_state.df_all_daily[st.session_state.df_all_daily["日期"] == latest_date_global].copy()
        df_month = st.session_state.df_all_daily[(st.session_state.df_all_daily["日期"] >= month_start) & (st.session_state.df_all_daily["日期"] <= latest_date_global)].copy()
        result_rows = []
        for entity in all_entities:
            existing_today = df_latest_existing[df_latest_existing["店铺名称"] == entity] if st.session_state.table_suffix == "_all" else df_latest_existing[df_latest_existing["店铺名称"] == entity]
            today_amount = existing_today.iloc[0]["当日金额"] if not existing_today.empty else 0.0
            entity_month_data = df_month[df_month["店铺名称"] == entity] if st.session_state.table_suffix == "_all" else df_month[df_month["店铺名称"] == entity]
            monthly_cum = entity_month_data["当日金额"].sum() if not entity_month_data.empty else 0.0
            result_rows.append({"日期": latest_date_global, "店铺名称": entity, "当日金额": today_amount, "月累计金额": monthly_cum})
        df = pd.DataFrame(result_rows).sort_values("店铺名称")
        if st.session_state.table_suffix == "_all":
            df = df.rename(columns={"店铺名称": "主播名称"})
            col_name = "主播名称"
    else:
        df = pd.DataFrame(columns=["日期", col_name, "当日金额", "月累计金额"])
    if not df.empty:
        df["目标金额"] = df[col_name].map(st.session_state.target_dict).fillna(0).round(2)
        df["达成率"] = df.apply(lambda r: f"{(r['月累计金额']/r['目标金额']*100):.2f}%" if r['目标金额']!=0 else "-", axis=1)
        cols = ["日期", col_name, "当日金额", "月累计金额", "目标金额", "达成率"]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
        if st.session_state.table_suffix == "_all":
            total_cum = df["月累计金额"].sum()
            total_target = sum(st.session_state.target_dict.values())
            total_rate = f"{(total_cum / total_target * 100):.2f}%" if total_target > 0 else "未设目标"
            st.metric("📊 总业绩合计", f"当日: {df['当日金额'].sum():,.2f}", delta=f"月累: {total_cum:,.2f}")
            st.caption(f"📈 月完成率: {total_rate}")
        else:
            douyin_entities = [e for e in all_entities if "抖音" in e]
            video_entities = [e for e in all_entities if "视频号" in e]
            douyin_cum = df[df[col_name].isin(douyin_entities)]["月累计金额"].sum()
            video_cum = df[df[col_name].isin(video_entities)]["月累计金额"].sum()
            total_cum = df["月累计金额"].sum()
            douyin_target = sum(st.session_state.target_dict.get(shop, 0) for shop in douyin_entities)
            video_target = sum(st.session_state.target_dict.get(shop, 0) for shop in video_entities)
            total_target = sum(st.session_state.target_dict.values())
            douyin_rate = f"{(douyin_cum / douyin_target * 100):.2f}%" if douyin_target > 0 else "未设目标"
            video_rate = f"{(video_cum / video_target * 100):.2f}%" if video_target > 0 else "未设目标"
            total_rate = f"{(total_cum / total_target * 100):.2f}%" if total_target > 0 else "未设目标"
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="📱 抖音合计", value=f"当日: {df[df[col_name].isin(douyin_entities)]['当日金额'].sum():,.2f}", delta=f"月累: {douyin_cum:,.2f}")
                st.caption(f"📈 月完成率: {douyin_rate}")
            with col2:
                st.metric(label="📺 视频号合计", value=f"当日: {df[df[col_name].isin(video_entities)]['当日金额'].sum():,.2f}", delta=f"月累: {video_cum:,.2f}")
                st.caption(f"📈 月完成率: {video_rate}")
            with col3:
                st.metric(label="📊 总业绩合计", value=f"当日: {df['当日金额'].sum():,.2f}", delta=f"月累: {total_cum:,.2f}")
                st.caption(f"📈 月完成率: {total_rate}")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df[cols].to_excel(writer, index=False)
        st.download_button("💾 导出 Excel", data=output.getvalue(), file_name="最新日明细.xlsx")
    else:
        st.info("暂无店铺业绩数据，请先上传订单文件")

# ========== 日期范围累计 ==========
with tabs[tab_index_range]:
    if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
        c1, c2 = st.columns(2)
        start = st.date_input("开始日期", value=date.today().replace(day=1), key="range_start_final")
        end = st.date_input("结束日期", value=date.today(), key="range_end_final")
        if st.button("计算累计", key="calc_range_final"):
            if start > end:
                st.error("开始日期不能晚于结束日期")
            else:
                mask = (st.session_state.df_all_daily["日期"] >= pd.to_datetime(start)) & (st.session_state.df_all_daily["日期"] <= pd.to_datetime(end))
                range_data = st.session_state.df_all_daily[mask].copy()
                if range_data.empty:
                    st.warning("无数据")
                else:
                    if st.session_state.table_suffix == "_all":
                        summary = range_data.groupby("店铺名称")["当日金额"].sum().reset_index().rename(columns={"店铺名称": "主播名称"})
                        summary["累计金额"] = summary["当日金额"].round(2)
                        summary = summary[["主播名称", "累计金额"]].sort_values("主播名称")
                        st.dataframe(summary, use_container_width=True, hide_index=True)
                        st.metric("📊 总业绩合计", f"{summary['累计金额'].sum():,.2f}")
                    else:
                        summary = range_data.groupby("店铺名称")["当日金额"].sum().reset_index()
                        summary["累计金额"] = summary["当日金额"].round(2)
                        summary = summary[["店铺名称", "累计金额"]].sort_values("店铺名称")
                        st.dataframe(summary, use_container_width=True, hide_index=True)
                        douyin_df = summary[summary["店铺名称"].str.contains("抖音", case=False, na=False)]
                        video_df = summary[summary["店铺名称"].str.contains("视频号", case=False, na=False)]
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("📱 抖音合计", f"{douyin_df['累计金额'].sum():,.2f}")
                        with col2:
                            st.metric("📺 视频号合计", f"{video_df['累计金额'].sum():,.2f}")
                        with col3:
                            st.metric("📊 总业绩合计", f"{summary['累计金额'].sum():,.2f}")
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        summary.to_excel(writer, index=False)
                    st.download_button("💾 导出", data=output.getvalue(), file_name=f"累计_{start}_{end}.xlsx")
    else:
        st.info("暂无数据")

# ========== 日期查询 ==========
with tabs[tab_index_query]:
    if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
        query_date = st.date_input("查询日期", value=date.today(), key="query_date_final")
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
                st.download_button("💾 导出", data=output.getvalue(), file_name=f"查询_{query_date}.xlsx")
    else:
        st.info("暂无数据")

# ========== 发货退货明细 ==========
with tabs[tab_index_ship_return]:
    with st.spinner("正在加载商品数据，请稍候..."):
        prod_df = load_product_sales(st.session_state.table_suffix)
    if prod_df.empty:
        st.info("暂无商品数据，请先上传订单文件")
    else:
        dates = sorted(prod_df["sale_date"].unique(), reverse=True)
        if dates:
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
            st.download_button("💾 导出", data=output.getvalue(), file_name=f"发货退货_{selected_date.strftime('%Y%m%d')}.xlsx")
        else:
            st.info("无日期数据")

# ========== 历史业绩 ==========
with tabs[tab_index_history]:
    with st.spinner("正在加载历史数据，请稍候..."):
        daily_df = load_daily_sales()
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
        st.download_button("💾 导出全部", data=output.getvalue(), file_name="历史业绩.xlsx")
    else:
        st.info("暂无历史数据")

# ========== 商品分析 ==========
with tabs[tab_index_product]:
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
        
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date = st.date_input("开始日期", value=min_date, key="prod_start_final", min_value=min_date, max_value=max_date)
        with col_date2:
            end_date = st.date_input("结束日期", value=max_date, key="prod_end_final", min_value=min_date, max_value=max_date)
        
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

# ========== 销售对比（主播/店铺维度） ==========
with tabs[tab_index_anchor_compare]:
    use_anchor = st.session_state.table_suffix in ["_live", "_all"]
    dimension_name = "主播" if use_anchor else "店铺"
    dimension_col = "anchor" if use_anchor else "shop_name"
    
    with st.spinner("正在加载数据..."):
        prod_df = load_product_sales(st.session_state.table_suffix)
    if prod_df.empty:
        st.info("暂无商品销售数据，请先上传订单文件。")
    else:
        if dimension_col not in prod_df.columns:
            if use_anchor:
                prod_df["anchor"] = prod_df["remark"].astype(str).apply(extract_anchor)
            else:
                if "shop_name" not in prod_df.columns:
                    st.error("数据中缺少店铺名称信息，无法进行店铺对比。")
                    st.stop()
        prod_df = prod_df[prod_df[dimension_col].notna()].copy()
        if prod_df.empty:
            st.info(f"当前数据中未识别到任何{dimension_name}信息，请检查数据。")
        else:
            all_dimensions = sorted(prod_df[dimension_col].unique())
            col_select1, col_select2, col_select3 = st.columns(3)
            with col_select1:
                selected_dimensions = st.multiselect(f"选择对比的{dimension_name}（最多3个）", options=all_dimensions, default=all_dimensions[:min(3, len(all_dimensions))])
                if len(selected_dimensions) > 3:
                    st.warning("最多只能选择3个，已自动截取前3个。")
                    selected_dimensions = selected_dimensions[:3]
                    st.rerun()
            with col_select2:
                metric_options = ["净销售金额", "发货金额", "退货金额"]
                selected_metrics = st.multiselect("选择要对比的指标", options=metric_options, default=["净销售金额"])
            with col_select3:
                chart_type = st.radio("图表类型", ["折线图", "柱状图"], horizontal=True, key="compare_chart_type")
            
            min_date = prod_df["sale_date"].min().date()
            max_date = prod_df["sale_date"].max().date()
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input("开始日期", value=min_date, key="compare_start", min_value=min_date, max_value=max_date)
            with col_date2:
                end_date = st.date_input("结束日期", value=max_date, key="compare_end", min_value=min_date, max_value=max_date)
            
            if not selected_dimensions:
                st.info(f"请至少选择一个{dimension_name}")
            else:
                mask_date = (prod_df["sale_date"] >= pd.to_datetime(start_date)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))
                filtered = prod_df[mask_date].copy()
                if filtered.empty:
                    st.warning("所选日期范围内无销售数据")
                else:
                    daily_agg = filtered.groupby(["sale_date", dimension_col]).agg(
                        净销售金额=("net_amount", "sum"),
                        发货金额=("ship_amount", "sum"),
                        退货金额=("return_amount", "sum")
                    ).reset_index()
                    daily_agg = daily_agg[daily_agg[dimension_col].isin(selected_dimensions)]
                    if daily_agg.empty:
                        st.warning(f"所选{dimension_name}在日期范围内无销售数据")
                    else:
                        for metric in selected_metrics:
                            st.markdown(f"#### {metric} 趋势对比")
                            pivot_df = daily_agg.pivot(index="sale_date", columns=dimension_col, values=metric)
                            if chart_type == "折线图":
                                fig = go.Figure()
                                for dim in pivot_df.columns:
                                    fig.add_trace(go.Scatter(
                                        x=pivot_df.index,
                                        y=pivot_df[dim],
                                        mode="lines+markers",
                                        name=dim,
                                        hovertemplate=f"{dim}<br>日期: %{{x|%Y-%m-%d}}<br>{metric}: %{{y:,.2f}}<extra></extra>"
                                    ))
                                fig.update_layout(
                                    title=f"{metric} 按日对比（折线图）",
                                    xaxis_title="日期",
                                    yaxis_title=f"{metric} (¥)",
                                    legend_title=dimension_name,
                                    hovermode="x unified"
                                )
                            else:
                                fig = go.Figure()
                                for dim in pivot_df.columns:
                                    fig.add_trace(go.Bar(
                                        x=pivot_df.index,
                                        y=pivot_df[dim],
                                        name=dim,
                                        hovertemplate=f"{dim}<br>日期: %{{x|%Y-%m-%d}}<br>{metric}: %{{y:,.2f}}<extra></extra>"
                                    ))
                                fig.update_layout(
                                    title=f"{metric} 按日对比（柱状图）",
                                    xaxis_title="日期",
                                    yaxis_title=f"{metric} (¥)",
                                    legend_title=dimension_name,
                                    barmode='group',
                                    hovermode="x unified"
                                )
                            st.plotly_chart(fig, use_container_width=True, key=f"compare_{metric}_{chart_type}")
                        
                        # 品类分析
                        st.markdown(f"#### {dimension_name}品类销售分析")
                        col_cat1, col_cat2 = st.columns([1, 2])
                        with col_cat1:
                            cat_chart_type = st.radio("品类图表类型", ["柱状图（对比品类）", "饼图（各维度品类分布）"], horizontal=False, key="cat_chart_type")
                        with col_cat2:
                            cat_metric = st.selectbox("品类金额指标", ["净销售金额", "发货金额", "退货金额"], key="cat_metric")
                        cat_metric_col = {"净销售金额": "net_amount", "发货金额": "ship_amount", "退货金额": "return_amount"}[cat_metric]
                        cat_metric_name = cat_metric
                        
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
                        
                        if cat_chart_type == "柱状图（对比品类）":
                            cat_agg = filtered.groupby([dimension_col, "master_category"])[cat_metric_col].sum().reset_index()
                            cat_agg.rename(columns={cat_metric_col: "金额"}, inplace=True)
                            top_cats_per_dim = {}
                            for dim in selected_dimensions:
                                dim_data = cat_agg[cat_agg[dimension_col] == dim].copy()
                                if not dim_data.empty:
                                    dim_data = dim_data.sort_values("金额", ascending=False)
                                    top5 = dim_data.head(5)
                                    top_cats_per_dim[dim] = top5
                            all_top_cats = set()
                            for dim, df_top in top_cats_per_dim.items():
                                all_top_cats.update(df_top["master_category"].tolist())
                            all_top_cats = sorted(list(all_top_cats))
                            if all_top_cats:
                                compare_df = pd.DataFrame(index=all_top_cats)
                                for dim in selected_dimensions:
                                    dim_sales = {}
                                    if dim in top_cats_per_dim:
                                        for _, row in top_cats_per_dim[dim].iterrows():
                                            dim_sales[row["master_category"]] = row["金额"]
                                    compare_df[dim] = [dim_sales.get(cat, 0) for cat in all_top_cats]
                                fig_cat = px.bar(
                                    compare_df,
                                    x=compare_df.index,
                                    y=selected_dimensions,
                                    barmode='group',
                                    title=f"{dimension_name}Top5品类{cat_metric_name}对比",
                                    labels={"value": f"{cat_metric_name}(¥)", "index": "商品品类"},
                                    color_discrete_sequence=px.colors.qualitative.Set2
                                )
                                fig_cat.update_layout(xaxis_title="商品品类", yaxis_title=f"{cat_metric_name}(¥)", legend_title=dimension_name)
                                st.plotly_chart(fig_cat, use_container_width=True)
                            else:
                                st.info("无法获取品类数据，无法生成对比图。")
                        else:
                            cat_agg = filtered.groupby([dimension_col, "master_category"])[cat_metric_col].sum().reset_index()
                            cat_agg.rename(columns={cat_metric_col: "金额"}, inplace=True)
                            dim_pie_data = {}
                            for dim in selected_dimensions:
                                dim_data = cat_agg[cat_agg[dimension_col] == dim].copy()
                                if dim_data.empty:
                                    continue
                                dim_data = dim_data.sort_values("金额", ascending=False)
                                top5 = dim_data.head(5)
                                other_sum = dim_data.iloc[5:]["金额"].sum() if len(dim_data) > 5 else 0
                                if other_sum > 0:
                                    other_row = pd.DataFrame({"master_category": ["其他"], "金额": [other_sum]})
                                    top5 = pd.concat([top5, other_row], ignore_index=True)
                                dim_pie_data[dim] = top5
                            if dim_pie_data:
                                cols = st.columns(len(dim_pie_data))
                                for idx, (dim, data) in enumerate(dim_pie_data.items()):
                                    with cols[idx]:
                                        fig_pie = px.pie(
                                            data,
                                            names="master_category",
                                            values="金额",
                                            title=f"{dim} - 品类分布 ({cat_metric_name})",
                                            hole=0.3,
                                            color_discrete_sequence=px.colors.qualitative.Pastel
                                        )
                                        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                                        st.plotly_chart(fig_pie, use_container_width=True)
                            else:
                                st.info("无有效数据")
                        
                        # 季节分析
                        st.markdown(f"#### {dimension_name}季节销售分析")
                        col_season1, col_season2 = st.columns([1, 2])
                        with col_season1:
                            season_chart_type = st.radio("季节图表类型", ["柱状图（对比季节）", "饼图（各维度季节分布）"], horizontal=False, key="season_chart_type")
                        with col_season2:
                            season_metric = st.selectbox("季节金额指标", ["净销售金额", "发货金额", "退货金额"], key="season_metric")
                        season_metric_col = {"净销售金额": "net_amount", "发货金额": "ship_amount", "退货金额": "return_amount"}[season_metric]
                        season_metric_name = season_metric
                        
                        if "season" not in filtered.columns:
                            st.info("数据中缺少季节信息，无法生成季节对比图。")
                        else:
                            season_data = filtered[filtered["season"].notna()].copy()
                            if season_data.empty:
                                st.info("所选范围内无季节数据")
                            else:
                                if season_chart_type == "柱状图（对比季节）":
                                    season_agg = season_data.groupby([dimension_col, "season"])[season_metric_col].sum().reset_index()
                                    season_agg.rename(columns={season_metric_col: "金额"}, inplace=True)
                                    season_agg = season_agg[season_agg[dimension_col].isin(selected_dimensions)]
                                    if not season_agg.empty:
                                        pivot_season = season_agg.pivot(index="season", columns=dimension_col, values="金额").fillna(0)
                                        season_order = ["春", "夏", "秋", "冬"]
                                        pivot_season = pivot_season.reindex([s for s in season_order if s in pivot_season.index])
                                        if not pivot_season.empty:
                                            fig_season = px.bar(
                                                pivot_season,
                                                x=pivot_season.index,
                                                y=selected_dimensions,
                                                barmode='group',
                                                title=f"{dimension_name}季节{season_metric_name}对比",
                                                labels={"value": f"{season_metric_name}(¥)", "index": "季节"},
                                                color_discrete_sequence=px.colors.qualitative.Set1
                                            )
                                            fig_season.update_layout(xaxis_title="季节", yaxis_title=f"{season_metric_name}(¥)", legend_title=dimension_name)
                                            st.plotly_chart(fig_season, use_container_width=True)
                                        else:
                                            st.info("无有效季节数据")
                                    else:
                                        st.info(f"所选{dimension_name}无季节数据")
                                else:
                                    season_agg = season_data.groupby([dimension_col, "season"])[season_metric_col].sum().reset_index()
                                    season_agg.rename(columns={season_metric_col: "金额"}, inplace=True)
                                    dim_season_data = {}
                                    for dim in selected_dimensions:
                                        dim_season = season_agg[season_agg[dimension_col] == dim].copy()
                                        if not dim_season.empty:
                                            dim_season_data[dim] = dim_season
                                    if dim_season_data:
                                        cols = st.columns(len(dim_season_data))
                                        for idx, (dim, data) in enumerate(dim_season_data.items()):
                                            with cols[idx]:
                                                fig_pie_season = px.pie(
                                                    data,
                                                    names="season",
                                                    values="金额",
                                                    title=f"{dim} - 季节分布 ({season_metric_name})",
                                                    hole=0.3,
                                                    color_discrete_sequence=px.colors.qualitative.Set2
                                                )
                                                fig_pie_season.update_traces(textposition='inside', textinfo='percent+label')
                                                st.plotly_chart(fig_pie_season, use_container_width=True)
                                    else:
                                        st.info("无有效数据")
                        
                        # 年份分析
                        st.markdown(f"#### {dimension_name}年份销售分析")
                        col_year1, col_year2 = st.columns([1, 2])
                        with col_year1:
                            year_chart_type = st.radio("年份图表类型", ["柱状图（对比年份）", "饼图（各维度年份分布）"], horizontal=False, key="year_chart_type")
                        with col_year2:
                            year_metric = st.selectbox("年份金额指标", ["净销售金额", "发货金额", "退货金额"], key="year_metric")
                        year_metric_col = {"净销售金额": "net_amount", "发货金额": "ship_amount", "退货金额": "return_amount"}[year_metric]
                        year_metric_name = year_metric
                        
                        if "year" not in filtered.columns:
                            st.info("数据中缺少年份信息，无法生成年份对比图。")
                        else:
                            year_data = filtered[filtered["year"].notna()].copy()
                            if year_data.empty:
                                st.info("所选范围内无年份数据")
                            else:
                                if year_chart_type == "柱状图（对比年份）":
                                    year_agg = year_data.groupby([dimension_col, "year"])[year_metric_col].sum().reset_index()
                                    year_agg.rename(columns={year_metric_col: "金额"}, inplace=True)
                                    year_agg = year_agg[year_agg[dimension_col].isin(selected_dimensions)]
                                    if not year_agg.empty:
                                        pivot_year = year_agg.pivot(index="year", columns=dimension_col, values="金额").fillna(0)
                                        pivot_year = pivot_year.sort_index()
                                        if not pivot_year.empty:
                                            fig_year = px.bar(
                                                pivot_year,
                                                x=pivot_year.index,
                                                y=selected_dimensions,
                                                barmode='group',
                                                title=f"{dimension_name}年份{year_metric_name}对比",
                                                labels={"value": f"{year_metric_name}(¥)", "index": "年份"},
                                                color_discrete_sequence=px.colors.qualitative.Pastel
                                            )
                                            fig_year.update_layout(xaxis_title="年份", yaxis_title=f"{year_metric_name}(¥)", legend_title=dimension_name)
                                            st.plotly_chart(fig_year, use_container_width=True)
                                        else:
                                            st.info("无有效年份数据")
                                    else:
                                        st.info(f"所选{dimension_name}无年份数据")
                                else:
                                    year_agg = year_data.groupby([dimension_col, "year"])[year_metric_col].sum().reset_index()
                                    year_agg.rename(columns={year_metric_col: "金额"}, inplace=True)
                                    dim_year_data = {}
                                    for dim in selected_dimensions:
                                        dim_year = year_agg[year_agg[dimension_col] == dim].copy()
                                        if not dim_year.empty:
                                            dim_year = dim_year.sort_values("year")
                                            dim_year_data[dim] = dim_year
                                    if dim_year_data:
                                        cols = st.columns(len(dim_year_data))
                                        for idx, (dim, data) in enumerate(dim_year_data.items()):
                                            with cols[idx]:
                                                fig_pie_year = px.pie(
                                                    data,
                                                    names="year",
                                                    values="金额",
                                                    title=f"{dim} - 年份分布 ({year_metric_name})",
                                                    hole=0.3,
                                                    color_discrete_sequence=px.colors.qualitative.Set3
                                                )
                                                fig_pie_year.update_traces(textposition='inside', textinfo='percent+label')
                                                st.plotly_chart(fig_pie_year, use_container_width=True)
                                    else:
                                        st.info("无有效数据")

# ========== 销售分布与品牌 ==========
with tabs[tab_index_distribution]:
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
        col_date1, col_date2 = st.columns(2)
        min_date = prod_df["sale_date"].min().date()
        max_date = prod_df["sale_date"].max().date()
        with col_date1:
            start_date = st.date_input("开始日期", value=min_date, key="dist_start_v2", min_value=min_date, max_value=max_date)
        with col_date2:
            end_date = st.date_input("结束日期", value=max_date, key="dist_end_v2", min_value=min_date, max_value=max_date)
        
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

# ========== 管理员专属：调试选项卡 ==========
if st.session_state.role == "admin":
    with tabs[tab_index_debug]:
        st.subheader("🔧 调试信息")
        st.json({
            "当前数据源后缀": st.session_state.table_suffix,
            "每日业绩数据行数": len(st.session_state.df_all_daily) if st.session_state.df_all_daily is not None else 0,
            "目标字典": st.session_state.target_dict,
            "子账号数": len(st.session_state.sub_users)
        })

# ========== 管理员专属：商品库导出选项卡 ==========
if st.session_state.role == "admin":
    with tabs[tab_index_export]:
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
