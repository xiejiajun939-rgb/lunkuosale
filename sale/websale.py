# -*- coding: utf-8 -*-
"""
订单业绩统计工具 - 最终稳定版（商品分析+发货退货明细持久化）
访问密码：94949468
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io
from supabase import create_client

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
if "df_all_daily" not in st.session_state:
    st.session_state.df_all_daily = None
if "target_dict" not in st.session_state:
    st.session_state.target_dict = {}
if "latest_date" not in st.session_state:
    st.session_state.latest_date = None
if "order_upload_key" not in st.session_state:
    st.session_state.order_upload_key = 0

# ========== 数据加载函数 ==========
def load_daily_sales():
    """从 daily_sales 表加载店铺业绩数据，返回 DataFrame"""
    if supabase is None:
        return pd.DataFrame()
    try:
        resp = supabase.table("daily_sales").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df["sale_date"] = pd.to_datetime(df["sale_date"])
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载店铺业绩失败：{e}")
        return pd.DataFrame()

def load_targets():
    if supabase is None:
        return {}
    try:
        resp = supabase.table("shop_targets").select("*").execute()
        if resp.data:
            return {row["shop_name"]: row["target_amount"] for row in resp.data}
        else:
            return {}
    except:
        return {}

def rebuild_daily_data():
    """根据 daily_sales 表重建店铺业绩视图"""
    df = load_daily_sales()
    if df.empty:
        st.session_state.df_all_daily = None
        st.session_state.latest_date = None
        return
    # 重命名列
    df = df.rename(columns={"sale_date": "日期", "shop_name": "店铺名称", "amount": "当日金额", "cumulative_amount": "月累计金额"})
    # 所有日期明细
    df_all = df.sort_values(["店铺名称", "日期"])
    latest_date = df_all["日期"].max()
    # 最新日明细（每个店铺最后一条记录）
    daily_latest = df_all.loc[df_all.groupby("店铺名称")["日期"].idxmax()].copy()
    # 月度累计（按店铺汇总当日金额）
    monthly_actual = df_all.groupby("店铺名称")["当日金额"].sum().reset_index()
    monthly_actual["月累计金额"] = monthly_actual["当日金额"].round(2)
    monthly_actual = monthly_actual[["店铺名称", "月累计金额"]].sort_values("店铺名称")
    st.session_state.df_all_daily = df_all
    st.session_state.daily_latest = daily_latest
    st.session_state.monthly_actual = monthly_actual
    st.session_state.latest_date = latest_date

def save_daily_sales(records):
    """批量 upsert 店铺业绩"""
    if supabase is None or not records:
        return
    supabase.table("daily_sales").upsert(records, on_conflict="sale_date,shop_name").execute()

# ========== 商品分析相关 ==========
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
        return {
            "product_code": product_code,
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

def save_product_sales(df_orders):
    """批量 upsert 商品销售明细"""
    if supabase is None:
        return
    records = []
    for _, row in df_orders.iterrows():
        parsed = parse_product_code(row["备注"])
        if parsed is None:
            continue
        amount = float(row["金额/时间"])
        records.append({
            "sale_date": row["日期"].strftime("%Y-%m-%d"),
            "shop_name": row["店铺名称"],
            "product_code": parsed["product_code"],
            "brand": parsed["brand"],
            "year": parsed["year"],
            "season": parsed["season"],
            "category": parsed["category"],
            "style": parsed["style"],
            "color_code": parsed["color_code"],
            "size_code": parsed["size"],
            "ship_amount": max(amount, 0),
            "return_amount": max(-amount, 0),
            "net_amount": amount
        })
    if records:
        supabase.table("product_sales").upsert(records, on_conflict="sale_date,product_code,shop_name").execute()

@st.cache_data(ttl=600)
def load_product_data():
    if supabase is None:
        return pd.DataFrame()
    try:
        resp = supabase.table("product_sales").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df["sale_date"] = pd.to_datetime(df["sale_date"])
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载商品数据失败：{e}")
        return pd.DataFrame()

# ========== 上传处理 ==========
def process_uploaded_file(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, header=1)
        required = ["日期", "金额/时间", "备注"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"缺少列: {col}")

        df["日期"] = pd.to_datetime(df["日期"])
        # 店铺名称提取
        df["店铺名称"] = df["备注"].astype(str).str.split("_").str[-1]
        df["店铺名称"] = df["店铺名称"].str.replace(r'^商店[：:]', '', regex=True).str.strip()
        df = df[df["店铺名称"].notna() & (df["店铺名称"] != "")].copy()
        if df.empty:
            raise ValueError("无有效店铺名称")

        df["金额/时间"] = pd.to_numeric(df["金额/时间"], errors="coerce")
        df = df.dropna(subset=["金额/时间"])

        # 存储商品明细
        save_product_sales(df)

        # 计算店铺业绩汇总（按日期+店铺）
        daily = df.groupby(["日期", "店铺名称"])["金额/时间"].sum().reset_index()
        daily = daily.sort_values(["店铺名称", "日期"])
        daily["月累计金额"] = daily.groupby("店铺名称")["金额/时间"].cumsum().round(2)
        daily["当日金额"] = daily["金额/时间"].round(2)
        records = []
        for _, row in daily.iterrows():
            records.append({
                "sale_date": row["日期"].strftime("%Y-%m-%d"),
                "shop_name": row["店铺名称"],
                "amount": float(row["当日金额"]),
                "cumulative_amount": float(row["月累计金额"])
            })
        save_daily_sales(records)

        # 刷新全局数据
        rebuild_daily_data()
        st.session_state.target_dict = load_targets()
        return True, f"处理完成！最新日期：{daily['日期'].max().strftime('%Y-%m-%d')}"
    except Exception as e:
        return False, str(e)

def load_target_file(uploaded_file):
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
        if supabase:
            records = [{"shop_name": k, "target_amount": v} for k, v in target_dict.items()]
            supabase.table("shop_targets").upsert(records, on_conflict="shop_name").execute()
        st.session_state.target_dict = target_dict
        return True, f"加载 {len(target_dict)} 个店铺目标"
    except Exception as e:
        return False, str(e)

def clear_targets():
    if supabase:
        supabase.table("shop_targets").delete().neq("id", 0).execute()
    st.session_state.target_dict = {}
    st.rerun()

# ========== 页面初始化加载数据 ==========
if "daily_latest" not in st.session_state:
    rebuild_daily_data()
if st.session_state.target_dict == {}:
    st.session_state.target_dict = load_targets()

# ========== 侧边栏 ==========
with st.sidebar:
    st.header("📂 数据加载")
    # 用 key 强制刷新文件上传组件
    uploaded_order = st.file_uploader("选择订单文件 (Excel)", type=["xlsx", "xls"], key=f"order_{st.session_state.order_upload_key}")
    if uploaded_order is not None:
        ok, msg = process_uploaded_file(uploaded_order)
        if ok:
            st.success(msg)
            st.session_state.order_upload_key += 1
            st.rerun()
        else:
            st.error(msg)

    target_file = st.file_uploader("选择目标文件 (Excel)", type=["xlsx", "xls"], key="target_upload")
    if target_file is not None:
        ok, msg = load_target_file(target_file)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    st.markdown("---")
    st.header("⚙️ 工具")
    # 下载目标模板
    template_df = pd.DataFrame({"店铺名称": ["示例店铺A", "示例店铺B"], "目标金额": [100000, 200000]})
    template_bytes = io.BytesIO()
    with pd.ExcelWriter(template_bytes, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False)
    st.download_button("📄 下载目标模板", data=template_bytes.getvalue(), file_name="目标模板.xlsx")
    if st.button("🗑️ 清除目标记忆"):
        clear_targets()

# ========== 主选项卡 ==========
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📅 最新日明细", "🏪 日期范围累计", "🔍 日期查询", "📦 发货退货明细", "🗄️ 历史业绩", "📊 商品分析"])

# ---------- 最新日明细 ----------
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
        # 导出
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df[cols].to_excel(writer, index=False)
        st.download_button("💾 导出 Excel", data=output.getvalue(), file_name="最新日明细.xlsx")
    else:
        st.info("暂无店铺业绩数据，请先上传订单文件")

# ---------- 日期范围累计 ----------
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
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        summary.to_excel(writer, index=False)
                    st.download_button("💾 导出", data=output.getvalue(), file_name=f"累计_{start}_{end}.xlsx")
    else:
        st.info("暂无数据")

# ---------- 日期查询 ----------
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
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    res[cols].to_excel(writer, index=False)
                st.download_button("💾 导出", data=output.getvalue(), file_name=f"查询_{query_date}.xlsx")
    else:
        st.info("暂无数据")

# ---------- 发货退货明细（从 product_sales 实时聚合） ----------
with tab4:
    st.subheader("📦 发货退货明细（按店铺）")
    prod_df = load_product_data()
    if prod_df.empty:
        st.info("暂无商品数据，请先上传订单文件")
    else:
        # 选择日期或默认最新日期
        dates = sorted(prod_df["sale_date"].unique(), reverse=True)
        if dates:
            selected_date = st.selectbox("选择日期", dates, format_func=lambda x: x.strftime("%Y-%m-%d"))
            filtered = prod_df[prod_df["sale_date"] == selected_date]
            # 按店铺汇总发货和退货
            summary = filtered.groupby("shop_name").agg(
                当日发货=("ship_amount", "sum"),
                当日退货=("return_amount", "sum")
            ).reset_index()
            # 计算累计（当月至今累计，可选）
            # 简单起见只显示当日
            st.dataframe(summary, use_container_width=True, hide_index=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                summary.to_excel(writer, index=False)
            st.download_button("💾 导出", data=output.getvalue(), file_name=f"发货退货_{selected_date.strftime('%Y%m%d')}.xlsx")
        else:
            st.info("无日期数据")

# ---------- 历史业绩 ----------
with tab5:
    st.subheader("所有已保存的每日业绩")
    daily_df = load_daily_sales()
    if not daily_df.empty:
        st.dataframe(daily_df, use_container_width=True, hide_index=True)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            daily_df.to_excel(writer, index=False)
        st.download_button("💾 导出全部", data=output.getvalue(), file_name="历史业绩.xlsx")
    else:
        st.info("暂无历史数据")

# ---------- 商品分析 ----------
with tab6:
    st.subheader("📊 商品销售分析（按品牌+产品）")
    prod_df = load_product_data()
    if prod_df.empty:
        st.warning("暂无商品数据，请先上传订单文件")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", value=prod_df["sale_date"].min().date() if not prod_df.empty else date.today().replace(day=1), key="prod_start")
        with col2:
            end_date = st.date_input("结束日期", value=date.today(), key="prod_end")
        mask = (prod_df["sale_date"] >= pd.to_datetime(start_date)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))
        filtered = prod_df[mask].copy()
        # 品牌筛选
        all_brands = ["全部"] + sorted(filtered["brand"].dropna().unique())
        selected_brands = st.multiselect("选择品牌（可多选）", all_brands, default="全部")
        if "全部" not in selected_brands:
            filtered = filtered[filtered["brand"].isin(selected_brands)]
        if filtered.empty:
            st.warning("无数据")
        else:
            grouped = filtered.groupby(["brand", "product_code"]).agg(
                发货金额=("ship_amount", "sum"),
                退货金额=("return_amount", "sum"),
                净销售金额=("net_amount", "sum")
            ).reset_index().sort_values("净销售金额", ascending=False)
            st.dataframe(grouped, use_container_width=True, hide_index=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                grouped.to_excel(writer, index=False)
            st.download_button("💾 导出分析结果", data=output.getvalue(), file_name="商品分析.xlsx")
