# -*- coding: utf-8 -*-
"""
订单业绩统计工具 - 完整版（管理员可切换数据源，双通道上传，含退出登录）
管理员账号：admin / 1234567890
非直播账号：XDZ01 / 94949468
直播账号：ZBZ01 / 123456
"""

import streamlit as st
import pandas as pd
from datetime import date
import io
from supabase import create_client
import plotly.express as px
import re

# ========== 页面配置 ==========
st.set_page_config(page_title="业绩统计工具", layout="wide", page_icon="📊")

# ========== 用户认证 ==========
USERS = {
    "admin": {"password": "1234567890", "role": "admin", "default_suffix": ""},
    "XDZ01": {"password": "94949468", "role": "user", "default_suffix": ""},
    "ZBZ01": {"password": "123456", "role": "user", "default_suffix": "_live"}
}

def login():
    st.title("🔐 业绩统计工具 - 登录")
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")
        if submitted:
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = USERS[username]["role"]
                st.session_state.table_suffix = USERS[username]["default_suffix"]
                st.rerun()
            else:
                st.error("用户名或密码错误")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    login()
    st.stop()

st.title("📊 店铺业绩汇总分析")
st.markdown(f"欢迎，**{st.session_state.username}** ({'管理员' if st.session_state.role == 'admin' else '成员'})")
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
if "uploaded_order_hash" not in st.session_state:
    st.session_state.uploaded_order_hash = None

# ========== 店铺业绩数据函数 ==========
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
        st.session_state.latest_date = None
        return
    df = df.rename(columns={"sale_date": "日期", "shop_name": "店铺名称", "amount": "当日金额", "cumulative_amount": "月累计金额"})
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
            return pd.DataFrame(all_data)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载商品库失败：{e}")
        return pd.DataFrame()

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
                "master_category": row.get("category", None)
            }
    records = []
    for _, row in df_orders.iterrows():
        remark = row["备注"]
        parsed = parse_product_code(remark)
        if parsed is None:
            continue
        amount = float(row["金额/时间"])
        short_code = parsed["style_code"]
        img = master_map.get(short_code, {}).get("image_url")
        cat = master_map.get(short_code, {}).get("master_category")
        records.append({
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
        })
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
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载商品销售数据失败：{e}")
        return pd.DataFrame()

# ========== 订单文件处理 ==========
def process_uploaded_file(uploaded_file, suffix):
    try:
        df = pd.read_excel(uploaded_file, header=1)
        required = ["日期", "金额/时间", "备注"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"缺少列: {col}")

        df["日期"] = pd.to_datetime(df["日期"])
        df["店铺名称"] = df["备注"].astype(str).str.split("_").str[-1]
        df["店铺名称"] = df["店铺名称"].str.replace(r'^商店[：:]', '', regex=True).str.strip()
        df = df[df["店铺名称"].notna() & (df["店铺名称"] != "")].copy()
        if df.empty:
            raise ValueError("未提取到有效的店铺名称")

        df["金额/时间"] = pd.to_numeric(df["金额/时间"], errors="coerce")
        df = df.dropna(subset=["金额/时间"])

        save_product_sales(df, suffix)

        existing = load_daily_sales(suffix)
        if existing.empty:
            existing_df = pd.DataFrame(columns=["日期", "店铺名称", "当日金额"])
        else:
            existing_df = existing[["sale_date", "shop_name", "amount"]].copy()
            existing_df.columns = ["日期", "店铺名称", "当日金额"]
        
        new_daily = df.groupby(["日期", "店铺名称"])["金额/时间"].sum().reset_index()
        new_daily.columns = ["日期", "店铺名称", "当日金额"]
        
        if not existing_df.empty:
            existing_df["日期"] = pd.to_datetime(existing_df["日期"])
        new_daily["日期"] = pd.to_datetime(new_daily["日期"])
        
        merged = pd.concat([existing_df, new_daily], ignore_index=True)
        merged = merged.groupby(["日期", "店铺名称"])["当日金额"].sum().reset_index()
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
        return True, f"处理完成！最新日期：{merged['日期'].max().strftime('%Y-%m-%d')}"
    except Exception as e:
        return False, str(e)

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

# ========== 页面初始化加载数据 ==========
rebuild_daily_data(st.session_state.table_suffix)
if st.session_state.target_dict == {}:
    st.session_state.target_dict = load_targets(st.session_state.table_suffix)

# ========== 侧边栏 ==========
with st.sidebar:
    st.header("📂 数据加载")
    
    if st.session_state.role == "admin":
        st.subheader("🔄 数据源切换")
        current_suffix = st.session_state.table_suffix
        data_source = st.radio(
            "选择要查看的数据",
            options=["非直播数据", "直播数据"],
            index=0 if current_suffix == "" else 1,
            key="data_source_switch"
        )
        new_suffix = "" if data_source == "非直播数据" else "_live"
        if new_suffix != current_suffix:
            st.session_state.table_suffix = new_suffix
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # 根据当前数据源显示对应的上传板块
        if data_source == "非直播数据":
            st.subheader("📁 非直播数据上传")
            uploaded_order = st.file_uploader("选择订单文件 (Excel)", type=["xlsx", "xls"], key="order_uploader_normal")
            if uploaded_order is not None:
                file_id = f"{uploaded_order.name}_{uploaded_order.size}"
                if st.session_state.uploaded_order_hash != file_id:
                    ok, msg = process_uploaded_file(uploaded_order, "")
                    if ok:
                        st.success(msg)
                        st.session_state.uploaded_order_hash = file_id
                        st.rerun()
                    else:
                        st.error(msg)

            target_file = st.file_uploader("选择目标文件 (Excel)", type=["xlsx", "xls"], key="target_upload_normal")
            if target_file is not None:
                ok, msg = load_target_file(target_file, "")
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        else:  # 直播数据
            st.subheader("🎥 直播数据上传")
            uploaded_order = st.file_uploader("选择订单文件 (Excel)", type=["xlsx", "xls"], key="order_uploader_live")
            if uploaded_order is not None:
                file_id = f"{uploaded_order.name}_{uploaded_order.size}"
                if st.session_state.uploaded_order_hash != file_id:
                    ok, msg = process_uploaded_file(uploaded_order, "_live")
                    if ok:
                        st.success(msg)
                        st.session_state.uploaded_order_hash = file_id
                        st.rerun()
                    else:
                        st.error(msg)

            target_file = st.file_uploader("选择目标文件 (Excel)", type=["xlsx", "xls"], key="target_upload_live")
            if target_file is not None:
                ok, msg = load_target_file(target_file, "_live")
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        
        st.markdown("---")
        st.header("⚙️ 工具")
        template_df = pd.DataFrame({"店铺名称": ["示例店铺A", "示例店铺B"], "目标金额": [100000, 200000]})
        template_bytes = io.BytesIO()
        with pd.ExcelWriter(template_bytes, engine='openpyxl') as writer:
            template_df.to_excel(writer, index=False)
        st.download_button("📄 下载目标模板", data=template_bytes.getvalue(), file_name="目标模板.xlsx")
        if st.button("🗑️ 清除当前用户的目标记忆"):
            clear_targets(st.session_state.table_suffix)
    else:
        st.info("普通用户仅可查看数据，无法上传。")
    
    st.markdown("---")
    if st.button("🚪 退出登录"):
        st.session_state.authenticated = False
        for key in ["username", "role", "table_suffix"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# ========== 创建选项卡 ==========
tab1, tab2, tab3, tab4, tab5, tab6, tab_debug, tab_export = st.tabs([
    "📅 最新日明细", "🏪 日期范围累计", "🔍 日期查询", "📦 发货退货明细", 
    "🗄️ 历史业绩", "📊 商品分析", "🔧 调试", "📚 商品库导出"
])

# ========== 最新日明细 ==========
with tab1:
    if st.session_state.get("daily_latest") is not None and not st.session_state.daily_latest.empty:
        df = st.session_state.daily_latest.copy()
        df["目标金额"] = df["店铺名称"].map(st.session_state.target_dict).fillna(0).round(2)
        def calc_rate(row):
            actual = row["月累计金额"]
            target = row["目标金额"]
            if target == 0:
                return "-"
            return f"{(actual / target) * 100:.2f}%"
        df["达成率"] = df.apply(calc_rate, axis=1)
        cols = ["日期", "店铺名称", "当日金额", "月累计金额", "目标金额", "达成率"]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
        
        df_all = st.session_state.df_all_daily
        if df_all is not None and not df_all.empty:
            latest_cum = df_all.groupby("店铺名称")["月累计金额"].last().reset_index()
            douyin_shops = latest_cum[latest_cum["店铺名称"].str.contains("抖音", case=False, na=False)]
            video_shops = latest_cum[latest_cum["店铺名称"].str.contains("视频号", case=False, na=False)]
            douyin_cum = douyin_shops["月累计金额"].sum()
            video_cum = video_shops["月累计金额"].sum()
            total_cum = latest_cum["月累计金额"].sum()
        else:
            douyin_cum = 0
            video_cum = 0
            total_cum = 0
        
        df_sales = st.session_state.daily_latest.copy()
        douyin_df = df_sales[df_sales["店铺名称"].str.contains("抖音", case=False, na=False)]
        video_df = df_sales[df_sales["店铺名称"].str.contains("视频号", case=False, na=False)]
        target_dict = st.session_state.target_dict
        
        douyin_target = sum(target_dict.get(shop, 0) for shop in douyin_df["店铺名称"])
        video_target = sum(target_dict.get(shop, 0) for shop in video_df["店铺名称"])
        total_target = sum(target_dict.values())
        
        douyin_rate = f"{(douyin_cum / douyin_target * 100):.2f}%" if douyin_target > 0 else "未设目标"
        video_rate = f"{(video_cum / video_target * 100):.2f}%" if video_target > 0 else "未设目标"
        total_rate = f"{(total_cum / total_target * 100):.2f}%" if total_target > 0 else "未设目标"
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="📱 抖音合计", value=f"当日: {douyin_df['当日金额'].sum():,.2f}", delta=f"月累: {douyin_cum:,.2f}")
            st.caption(f"📈 月完成率: {douyin_rate}")
        with col2:
            st.metric(label="📺 视频号合计", value=f"当日: {video_df['当日金额'].sum():,.2f}", delta=f"月累: {video_cum:,.2f}")
            st.caption(f"📈 月完成率: {video_rate}")
        with col3:
            st.metric(label="📊 总业绩合计", value=f"当日: {df_sales['当日金额'].sum():,.2f}", delta=f"月累: {total_cum:,.2f}")
            st.caption(f"📈 月完成率: {total_rate}")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df[cols].to_excel(writer, index=False)
        st.download_button("💾 导出 Excel", data=output.getvalue(), file_name="最新日明细.xlsx")
    else:
        st.info("暂无店铺业绩数据，请先上传订单文件")

# ========== 日期范围累计 ==========
with tab2:
    if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("开始日期", value=date.today().replace(day=1), key="range_start")
        with c2:
            end = st.date_input("结束日期", value=date.today(), key="range_end")
        if st.button("计算累计"):
            if start > end:
                st.error("开始日期不能晚于结束日期")
            else:
                mask = (st.session_state.df_all_daily["日期"] >= pd.to_datetime(start)) & (st.session_state.df_all_daily["日期"] <= pd.to_datetime(end))
                range_data = st.session_state.df_all_daily[mask].copy()
                if range_data.empty:
                    st.warning("无数据")
                else:
                    summary = range_data.groupby("店铺名称")["当日金额"].sum().reset_index()
                    summary["累计金额"] = summary["当日金额"].round(2)
                    summary = summary[["店铺名称", "累计金额"]].sort_values("店铺名称")
                    st.dataframe(summary, use_container_width=True, hide_index=True)
                    
                    douyin_df = summary[summary["店铺名称"].str.contains("抖音", case=False, na=False)]
                    video_df = summary[summary["店铺名称"].str.contains("视频号", case=False, na=False)]
                    douyin_total = douyin_df["累计金额"].sum()
                    video_total = video_df["累计金额"].sum()
                    overall_total = summary["累计金额"].sum()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📱 抖音合计", f"{douyin_total:,.2f}")
                    with col2:
                        st.metric("📺 视频号合计", f"{video_total:,.2f}")
                    with col3:
                        st.metric("📊 总业绩合计", f"{overall_total:,.2f}")
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        summary.to_excel(writer, index=False)
                    st.download_button("💾 导出", data=output.getvalue(), file_name=f"累计_{start}_{end}.xlsx")
    else:
        st.info("暂无数据")

# ========== 日期查询 ==========
with tab3:
    if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
        query_date = st.date_input("查询日期", value=date.today(), key="query_date")
        if st.button("查询"):
            res = st.session_state.df_all_daily[st.session_state.df_all_daily["日期"] == pd.to_datetime(query_date)].copy()
            if res.empty:
                st.warning("无数据")
            else:
                res = res.sort_values("店铺名称")
                res["当日金额"] = res["当日金额"].round(2)
                res["月累计金额"] = res["月累计金额"].round(2)
                cols = ["日期", "店铺名称", "当日金额", "月累计金额"]
                st.dataframe(res[cols], use_container_width=True, hide_index=True)
                
                douyin_df = res[res["店铺名称"].str.contains("抖音", case=False, na=False)]
                video_df = res[res["店铺名称"].str.contains("视频号", case=False, na=False)]
                douyin_today = douyin_df["当日金额"].sum()
                douyin_cum = douyin_df["月累计金额"].sum()
                video_today = video_df["当日金额"].sum()
                video_cum = video_df["月累计金额"].sum()
                overall_today = res["当日金额"].sum()
                overall_cum = res["月累计金额"].sum()
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📱 抖音合计", f"当日: {douyin_today:,.2f}", delta=f"月累: {douyin_cum:,.2f}")
                with col2:
                    st.metric("📺 视频号合计", f"当日: {video_today:,.2f}", delta=f"月累: {video_cum:,.2f}")
                with col3:
                    st.metric("📊 总业绩合计", f"当日: {overall_today:,.2f}", delta=f"月累: {overall_cum:,.2f}")
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    res[cols].to_excel(writer, index=False)
                st.download_button("💾 导出", data=output.getvalue(), file_name=f"查询_{query_date}.xlsx")
    else:
        st.info("暂无数据")

# ========== 发货退货明细 ==========
with tab4:
    st.subheader("📦 发货退货明细（按店铺）")
    prod_df = load_product_sales(st.session_state.table_suffix)
    if prod_df.empty:
        st.info("暂无商品数据，请先上传订单文件")
    else:
        dates = sorted(prod_df["sale_date"].unique(), reverse=True)
        if dates:
            selected_date = st.selectbox("选择日期", dates, format_func=lambda x: x.strftime("%Y-%m-%d"))
            filtered = prod_df[prod_df["sale_date"] == selected_date]
            summary = filtered.groupby("shop_name").agg(
                当日发货=("ship_amount", "sum"),
                当日退货=("return_amount", "sum")
            ).reset_index()
            st.dataframe(summary, use_container_width=True, hide_index=True)
            
            douyin_df = summary[summary["shop_name"].str.contains("抖音", case=False, na=False)]
            video_df = summary[summary["shop_name"].str.contains("视频号", case=False, na=False)]
            douyin_ship = douyin_df["当日发货"].sum()
            douyin_return = douyin_df["当日退货"].sum()
            video_ship = video_df["当日发货"].sum()
            video_return = video_df["当日退货"].sum()
            overall_ship = summary["当日发货"].sum()
            overall_return = summary["当日退货"].sum()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📱 抖音合计", f"发货: {douyin_ship:,.2f}", delta=f"退货: {douyin_return:,.2f}")
            with col2:
                st.metric("📺 视频号合计", f"发货: {video_ship:,.2f}", delta=f"退货: {video_return:,.2f}")
            with col3:
                st.metric("📊 总业绩合计", f"发货: {overall_ship:,.2f}", delta=f"退货: {overall_return:,.2f}")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                summary.to_excel(writer, index=False)
            st.download_button("💾 导出", data=output.getvalue(), file_name=f"发货退货_{selected_date.strftime('%Y%m%d')}.xlsx")
        else:
            st.info("无日期数据")

# ========== 历史业绩 ==========
with tab5:
    st.subheader("所有已保存的每日业绩")
    daily_df = load_daily_sales()
    if not daily_df.empty:
        st.dataframe(daily_df, use_container_width=True, hide_index=True)
        
        douyin_df = daily_df[daily_df["shop_name"].str.contains("抖音", case=False, na=False)]
        video_df = daily_df[daily_df["shop_name"].str.contains("视频号", case=False, na=False)]
        douyin_total = douyin_df["amount"].sum()
        video_total = video_df["amount"].sum()
        overall_total = daily_df["amount"].sum()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📱 抖音合计", f"{douyin_total:,.2f}")
        with col2:
            st.metric("📺 视频号合计", f"{video_total:,.2f}")
        with col3:
            st.metric("📊 总业绩合计", f"{overall_total:,.2f}")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            daily_df.to_excel(writer, index=False)
        st.download_button("💾 导出全部", data=output.getvalue(), file_name="历史业绩.xlsx")
    else:
        st.info("暂无历史数据")

# ========== 商品分析 ==========
with tab6:
    st.subheader("📊 商品销售分析（按货号汇总）")
    prod_df = load_product_sales(st.session_state.table_suffix)
    if prod_df.empty:
        st.warning("暂无商品销售数据，请先上传订单文件。")
    else:
        # 确保 style_code 存在
        if "style_code" in prod_df.columns:
            prod_df["style_code"] = prod_df["style_code"].astype(str).str.strip().str.upper()
        else:
            prod_df["style_code"] = prod_df["product_code"].str[:8].str.strip().str.upper()
        
        # 日期选择器
        min_date = prod_df["sale_date"].min().date()
        max_date = prod_df["sale_date"].max().date()
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date = st.date_input("开始日期", value=min_date, key="prod_start", min_value=min_date, max_value=max_date)
        with col_date2:
            end_date = st.date_input("结束日期", value=max_date, key="prod_end", min_value=min_date, max_value=max_date)
        mask = (prod_df["sale_date"] >= pd.to_datetime(start_date)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))
        filtered = prod_df[mask].copy()
        if filtered.empty:
            st.warning("所选日期范围内无销售数据")
        else:
            st.subheader("🔍 筛选条件")
            col_platform, col_shop = st.columns(2)
            with col_platform:
                platform_options = ["全部", "抖音", "视频号"]
                selected_platform = st.selectbox("平台", platform_options, key="platform_filter")
            all_shops = filtered["shop_name"].unique()
            if selected_platform == "抖音":
                shop_options = [shop for shop in all_shops if "抖音" in shop]
            elif selected_platform == "视频号":
                shop_options = [shop for shop in all_shops if "视频号" in shop]
            else:
                shop_options = list(all_shops)
            selected_shops = st.multiselect("店铺（可多选）", options=sorted(shop_options), default=[], key="shop_filter")
            
            col_code, col_brand = st.columns(2)
            with col_code:
                style_codes_input = st.text_input(
                    "货号筛选（多个用英文逗号分隔）",
                    placeholder="例如: L262Y050, G262Y030",
                    key="style_code_filter"
                )
            with col_brand:
                brands = ["全部"] + sorted(filtered["brand"].dropna().unique())
                selected_brand = st.selectbox("品牌", brands, key="brand_filter")
            
            # 应用筛选
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
            
            if filtered.empty:
                st.warning("所选条件下无销售数据")
            else:
                # 按货号汇总
                grouped = filtered.groupby("style_code").agg(
                    发货金额=("ship_amount", "sum"),
                    退货金额=("return_amount", "sum"),
                    净销售金额=("net_amount", "sum")
                ).reset_index()
                grouped = grouped.sort_values("净销售金额", ascending=False)
                grouped.rename(columns={"style_code": "货号"}, inplace=True)
                
                # 获取商品主库信息（仅用于补充图片和缺失的分类，不覆盖现有分类）
                master_df = load_product_master()
                if not master_df.empty and "style_code" in master_df.columns:
                    master_df["style_code"] = master_df["style_code"].astype(str).str.strip().str.upper()
                    master_df = master_df.drop_duplicates(subset="style_code", keep="first")
                    img_map = master_df.set_index("style_code")["image_url"].to_dict()
                    cat_map = master_df.set_index("style_code")["category"].to_dict()
                    
                    # 添加图片列
                    if "image_url" not in grouped.columns:
                        grouped["image_url"] = None
                    for idx, row in grouped.iterrows():
                        code = row["货号"]
                        if pd.isna(row["image_url"]) and code in img_map:
                            grouped.at[idx, "image_url"] = img_map[code]
                    
                    # 分类列：优先使用表中已有的 master_category，若为空则用主库的 category
                    if "master_category" not in filtered.columns:
                        filtered["master_category"] = None
                    # 汇总表里加上 master_category（取每个货号的第一个非空值）
                    cat_series = filtered.groupby("style_code")["master_category"].first()
                    grouped["master_category"] = grouped["货号"].map(cat_series)
                    # 若仍为空，尝试从主库补充
                    for idx, row in grouped.iterrows():
                        if pd.isna(row["master_category"]) and row["货号"] in cat_map:
                            grouped.at[idx, "master_category"] = cat_map[row["货号"]]
                else:
                    # 没有主库时，直接从 filtered 中取分类
                    if "master_category" in filtered.columns:
                        cat_series = filtered.groupby("style_code")["master_category"].first()
                        grouped["master_category"] = grouped["货号"].map(cat_series)
                    else:
                        grouped["master_category"] = None
                    grouped["image_url"] = None
                
                # 显示表格
                col_order = ["货号", "image_url", "master_category", "发货金额", "退货金额", "净销售金额"]
                grouped = grouped[col_order]
                st.dataframe(
                    grouped,
                    column_config={
                        "货号": st.column_config.TextColumn("货号"),
                        "image_url": st.column_config.ImageColumn("商品图片", help="点击放大"),
                        "master_category": "商品分类",
                        "发货金额": st.column_config.NumberColumn("发货金额", format="%.2f"),
                        "退货金额": st.column_config.NumberColumn("退货金额", format="%.2f"),
                        "净销售金额": st.column_config.NumberColumn("净销售金额", format="%.2f")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # 饼图指标选择
                pie_metric = st.radio("饼图指标", ["净销售金额", "发货金额", "退货金额"], horizontal=True, key="pie_metric")
                if pie_metric == "净销售金额":
                    metric_col = "net_amount"
                    grouped_metric_col = "净销售金额"
                elif pie_metric == "发货金额":
                    metric_col = "ship_amount"
                    grouped_metric_col = "发货金额"
                else:
                    metric_col = "return_amount"
                    grouped_metric_col = "退货金额"
                
                st.subheader("📊 销售分布")
                col1, col2, col3 = st.columns(3)
                
                # 辅助函数：安全绘制饼图（处理总额为负或零）
                def safe_pie_chart(data, name_col, value_col, title, color_seq):
                    total = data[value_col].sum()
                    if total == 0:
                        st.info(f"{title}：无销售金额")
                        return
                    if total < 0:
                        # 净销售额为负时的特殊提示
                        if pie_metric == "净销售金额":
                            st.warning(f"{title}：净销售总额为负（{total:.2f}），无法绘制饼图。请选择「发货金额」或「退货金额」查看分布。")
                        else:
                            st.info(f"{title}：总额为负，无法绘制饼图")
                        return
                    # 过滤掉零值行，避免无意义扇区
                    chart_data = data[data[value_col] != 0].copy()
                    if chart_data.empty:
                        st.info(f"{title}：无有效数据")
                        return
                    fig = px.pie(chart_data, names=name_col, values=value_col,
                                 title=title, hole=0.3, color_discrete_sequence=color_seq)
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)
                
                # 1. 按分类饼图
                with col1:
                    if grouped["master_category"].isnull().all():
                        # 全为空，构造一个“未分类”扇区
                        total_val = grouped[grouped_metric_col].sum()
                        if total_val > 0:
                            pie_data = pd.DataFrame({name_col: ["未分类"], value_col: [total_val]})
                            safe_pie_chart(pie_data, name_col, value_col, f"按分类 - {pie_metric}", px.colors.qualitative.Pastel)
                        elif total_val < 0 and pie_metric == "净销售金额":
                            st.warning(f"按分类 - {pie_metric}：净销售总额为负，无法绘制饼图。请切换指标。")
                        else:
                            st.info(f"按分类 - {pie_metric}：无销售金额")
                    else:
                        pie_data = grouped.groupby("master_category")[grouped_metric_col].sum().reset_index()
                        pie_data = pie_data[pie_data["master_category"].notna()]
                        safe_pie_chart(pie_data, "master_category", grouped_metric_col, f"按分类 - {pie_metric}", px.colors.qualitative.Pastel)
                
                # 2. 按年份饼图
                with col2:
                    if "year" not in filtered.columns or filtered["year"].isnull().all():
                        total_val = filtered[metric_col].sum()
                        if total_val > 0:
                            pie_data = pd.DataFrame({"year": ["无年份信息"], metric_col: [total_val]})
                            safe_pie_chart(pie_data, "year", metric_col, f"按年份 - {pie_metric}", px.colors.qualitative.Set2)
                        elif total_val < 0 and pie_metric == "净销售金额":
                            st.warning(f"按年份 - {pie_metric}：净销售总额为负，无法绘制饼图。请切换指标。")
                        else:
                            st.info(f"按年份 - {pie_metric}：无销售金额")
                    else:
                        year_data = filtered.groupby("year")[metric_col].sum().reset_index()
                        year_data = year_data[year_data["year"].notna()]
                        safe_pie_chart(year_data, "year", metric_col, f"按年份 - {pie_metric}", px.colors.qualitative.Set2)
                
                # 3. 按季节饼图
                with col3:
                    if "season" not in filtered.columns or filtered["season"].isnull().all():
                        total_val = filtered[metric_col].sum()
                        if total_val > 0:
                            pie_data = pd.DataFrame({"season": ["无季节信息"], metric_col: [total_val]})
                            safe_pie_chart(pie_data, "season", metric_col, f"按季节 - {pie_metric}", px.colors.qualitative.Set1)
                        elif total_val < 0 and pie_metric == "净销售金额":
                            st.warning(f"按季节 - {pie_metric}：净销售总额为负，无法绘制饼图。请切换指标。")
                        else:
                            st.info(f"按季节 - {pie_metric}：无销售金额")
                    else:
                        season_data = filtered.groupby("season")[metric_col].sum().reset_index()
                        season_data = season_data[season_data["season"].notna()]
                        safe_pie_chart(season_data, "season", metric_col, f"按季节 - {pie_metric}", px.colors.qualitative.Set1)
                
                # 品牌柱状图
                if "brand" in filtered.columns:
                    st.subheader("📈 品牌销售分析")
                    brand_metric = st.radio("品牌图表指标", ["净销售金额", "发货金额", "退货金额"], horizontal=True, key="brand_metric")
                    if brand_metric == "净销售金额":
                        brand_col = "net_amount"
                        brand_title = "净销售金额"
                    elif brand_metric == "发货金额":
                        brand_col = "ship_amount"
                        brand_title = "发货金额"
                    else:
                        brand_col = "return_amount"
                        brand_title = "退货金额"
                    brand_data = filtered.groupby("brand")[brand_col].sum().reset_index()
                    brand_data = brand_data.sort_values(brand_col, ascending=False)
                    if not brand_data.empty:
                        fig = px.bar(brand_data, x="brand", y=brand_col, title=f"各品牌{brand_title}", color="brand")
                        st.plotly_chart(fig, use_container_width=True)
                
                # 导出按钮
                export_cols = ["货号", "master_category", "发货金额", "退货金额", "净销售金额"]
                export_df = grouped[export_cols].copy()
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False)
                st.download_button("💾 导出分析结果", data=output.getvalue(), file_name="商品分析.xlsx")

# ========== 调试选项卡 ==========
with tab_debug:
    st.subheader("🔧 数据库调试信息")
    if supabase is None:
        st.error("Supabase 未连接")
    else:
        try:
            table_name = get_table_name("product_sales")
            st.write(f"当前使用的商品销售表: {table_name}")
            resp = supabase.table(table_name).select("*").limit(5).execute()
            st.write(f"前5条数据: {resp.data}")
        except Exception as e:
            st.error(f"查询失败: {e}")
        
        try:
            table_name = get_table_name("daily_sales")
            st.write(f"当前使用的每日业绩表: {table_name}")
            resp = supabase.table(table_name).select("*").limit(5).execute()
            st.write(f"前5条数据: {resp.data}")
        except Exception as e:
            st.error(f"查询失败: {e}")

# ========== 商品库导出选项卡 ==========
with tab_export:
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
