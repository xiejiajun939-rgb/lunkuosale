# -*- coding: utf-8 -*-
"""
订单业绩统计工具 - 带 Supabase 持久化（支持历史业绩+目标金额跨设备保存）
启动时自动从数据库加载历史业绩和已存储的目标金额
"""

import streamlit as st
import pandas as pd
from datetime import date
import io
from supabase import create_client

# ========== 页面配置 ==========
st.set_page_config(page_title="业绩统计工具", layout="wide", page_icon="📊")
st.title("📊 店铺业绩汇总分析")
st.markdown("---")

# ========== 初始化 session_state ==========
if "df_all_daily" not in st.session_state:
    st.session_state.df_all_daily = None
if "df_ship_refund" not in st.session_state:
    st.session_state.df_ship_refund = None
if "target_dict" not in st.session_state:
    st.session_state.target_dict = {}
if "target_file_name" not in st.session_state:
    st.session_state.target_file_name = None
if "order_file_name" not in st.session_state:
    st.session_state.order_file_name = None
if "latest_date" not in st.session_state:
    st.session_state.latest_date = None
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False

# ========== Supabase 连接 ==========
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase 连接失败，请检查 secrets 配置：{e}")
        return None

supabase = init_supabase()

# ========== 业绩数据相关函数 ==========
def load_from_supabase():
    """从 Supabase 加载所有历史业绩数据"""
    if supabase is None:
        return pd.DataFrame()
    try:
        response = supabase.table("daily_sales").select("*").execute()
    except Exception as e:
        st.error(f"读取历史业绩失败：{e}")
        return pd.DataFrame()
    if response.data:
        df = pd.DataFrame(response.data)
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        df = df.rename(columns={"sale_date": "日期", "shop_name": "店铺名称", "amount": "当日金额", "cumulative_amount": "月累计金额"})
        return df[["日期", "店铺名称", "当日金额", "月累计金额"]]
    else:
        return pd.DataFrame()

def save_to_supabase(df_all):
    """将每日业绩保存到 Supabase（避免重复）"""
    if supabase is None:
        return
    for _, row in df_all.iterrows():
        data = {
            "sale_date": row["日期"].strftime("%Y-%m-%d"),
            "shop_name": row["店铺名称"],
            "amount": float(row["当日金额"]),
            "cumulative_amount": float(row["月累计金额"])
        }
        existing = supabase.table("daily_sales").select("*").eq("sale_date", data["sale_date"]).eq("shop_name", data["shop_name"]).execute()
        if not existing.data:
            supabase.table("daily_sales").insert(data).execute()
        else:
            supabase.table("daily_sales").update({"cumulative_amount": data["cumulative_amount"]}).eq("sale_date", data["sale_date"]).eq("shop_name", data["shop_name"]).execute()

def rebuild_from_history(history_df):
    """根据历史业绩 DataFrame 重建 df_all_daily, daily_latest, monthly_actual"""
    if history_df.empty:
        return None, None, None, None
    df_all = history_df.sort_values(["店铺名称", "日期"])
    latest_date = df_all["日期"].max()
    daily_latest = df_all.loc[df_all.groupby("店铺名称")["日期"].idxmax()].copy()
    daily_latest = daily_latest[["日期", "店铺名称", "当日金额", "月累计金额"]]
    monthly_actual = df_all.groupby("店铺名称")["当日金额"].sum().reset_index()
    monthly_actual["月累计金额"] = monthly_actual["当日金额"].round(2)
    monthly_actual = monthly_actual[["店铺名称", "月累计金额"]].sort_values("店铺名称")
    return df_all, daily_latest, monthly_actual, latest_date

# ========== 目标数据持久化函数 ==========
def load_targets_from_supabase():
    """从 Supabase 加载所有已保存的目标金额"""
    if supabase is None:
        return {}
    try:
        response = supabase.table("shop_targets").select("*").execute()
    except Exception as e:
        st.error(f"读取目标数据失败：{e}")
        return {}
    if response.data:
        return {row["shop_name"]: row["target_amount"] for row in response.data}
    else:
        return {}

def save_targets_to_supabase(target_dict):
    """将目标金额保存到 Supabase（upsert）"""
    if supabase is None:
        return
    for shop_name, amount in target_dict.items():
        supabase.table("shop_targets").upsert({
            "shop_name": shop_name,
            "target_amount": amount
        }, on_conflict="shop_name").execute()

def clear_targets_in_supabase():
    """删除所有目标金额记录"""
    if supabase is None:
        return
    supabase.table("shop_targets").delete().neq("id", 0).execute()

# ========== 订单文件处理函数（保留，并追加到数据库） ==========
def process_order_file(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, header=1)
        required = ["日期", "金额/时间", "备注"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"表格缺少列: {col}")

        df["日期"] = pd.to_datetime(df["日期"])
        df["店铺名称"] = df["备注"].astype(str).str.split("_").str[-1]
        df["店铺名称"] = df["店铺名称"].str.strip()
        df["店铺名称"] = df["店铺名称"].str.replace(r'^\s*商店[：:]', '', regex=True).str.strip()

        df = df[df["店铺名称"].notna() & (df["店铺名称"] != "")].copy()
        if df.empty:
            raise ValueError("未提取到有效的店铺名称")

        df["金额/时间"] = pd.to_numeric(df["金额/时间"], errors="coerce")
        df = df.dropna(subset=["金额/时间"])

        daily = df.groupby(["日期", "店铺名称"])["金额/时间"].sum().reset_index()
        daily = daily.sort_values(["店铺名称", "日期"])
        daily["月累计金额"] = daily.groupby("店铺名称")["金额/时间"].cumsum().round(2)
        daily["当日金额"] = daily["金额/时间"].round(2)

        df_all_new = daily[["日期", "店铺名称", "当日金额", "月累计金额"]].copy()
        latest_date = daily["日期"].max()

        # 发货退货明细（仅用于本次上传展示）
        df['发货金额'] = df['金额/时间'].clip(lower=0)
        df['退货金额'] = df['金额/时间'].clip(upper=0).abs()
        ship_refund_daily = df.groupby(["日期", "店铺名称"])[["发货金额", "退货金额"]].sum().reset_index()
        ship_refund_daily = ship_refund_daily.sort_values(["店铺名称", "日期"])
        ship_refund_daily["月累计发货"] = ship_refund_daily.groupby("店铺名称")["发货金额"].cumsum().round(2)
        ship_refund_daily["月累计退货"] = ship_refund_daily.groupby("店铺名称")["退货金额"].cumsum().round(2)
        ship_refund_daily["当日发货"] = ship_refund_daily["发货金额"].round(2)
        ship_refund_daily["当日退货"] = ship_refund_daily["退货金额"].round(2)

        latest_ship_cum = ship_refund_daily.groupby("店铺名称").last().reset_index()[["店铺名称", "月累计发货", "月累计退货"]]
        latest_ship = ship_refund_daily[ship_refund_daily["日期"] == latest_date][["日期", "店铺名称", "当日发货", "当日退货"]]
        latest_ship_refund = pd.merge(latest_ship_cum, latest_ship, on='店铺名称', how='left')
        latest_ship_refund['当日发货'] = latest_ship_refund['当日发货'].fillna(0).round(2)
        latest_ship_refund['当日退货'] = latest_ship_refund['当日退货'].fillna(0).round(2)
        latest_ship_refund['日期'] = latest_ship_refund['日期'].fillna(latest_date)
        df_ship = latest_ship_refund[["日期", "店铺名称", "当日发货", "月累计发货", "当日退货", "月累计退货"]]

        # 保存业绩到数据库
        save_to_supabase(df_all_new)

        # 重新从数据库加载所有历史数据并重建
        history_df = load_from_supabase()
        df_all, daily_latest, monthly_actual, latest_date_updated = rebuild_from_history(history_df)

        return {
            "df_all": df_all,
            "daily_latest": daily_latest,
            "monthly_actual": monthly_actual,
            "df_ship": df_ship,
            "latest_date": latest_date_updated,
            "success": True,
            "message": f"处理完成并已保存！最新日期：{latest_date_updated.strftime('%Y-%m-%d')}"
        }
    except Exception as e:
        return {"success": False, "message": f"处理失败：{str(e)}"}

# ========== 目标文件处理（带持久化） ==========
def load_target_file(uploaded_file):
    try:
        df_target = pd.read_excel(uploaded_file, header=None)
        first_cell = str(df_target.iloc[0, 0]) if len(df_target) > 0 else ""
        if "月目标" in first_cell or "目标" in first_cell:
            df_target = df_target.iloc[1:].reset_index(drop=True)
        if df_target.shape[1] < 2:
            raise ValueError("目标文件需要两列：店铺名称、目标金额")
        shop_names = df_target.iloc[:, 0].astype(str).str.strip()
        target_vals = pd.to_numeric(df_target.iloc[:, 1], errors='coerce')
        target_dict = {}
        for name, val in zip(shop_names, target_vals):
            if pd.notna(val) and name not in ["", "nan", "None"]:
                target_dict[name] = val

        # 保存目标到数据库
        save_targets_to_supabase(target_dict)

        return {"success": True, "target_dict": target_dict, "count": len(target_dict), "message": f"成功加载并保存 {len(target_dict)} 个店铺目标"}
    except Exception as e:
        return {"success": False, "message": f"加载目标文件失败：{str(e)}"}

def add_target_and_rate(df, target_dict):
    if df is None or df.empty:
        return df
    result = df.copy()
    result["目标金额"] = result["店铺名称"].map(target_dict).fillna(0).round(2)
    def calc_rate(row):
        actual = row["月累计金额"]
        target = row["目标金额"]
        if target == 0 or pd.isna(target):
            return "-"
        return f"{(actual / target) * 100:.2f}%"
    result["达成率"] = result.apply(calc_rate, axis=1)
    return result

def to_excel_download(df, filename="export.xlsx"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def download_target_template():
    template = pd.DataFrame({"店铺名称": ["示例店铺A", "示例店铺B"], "目标金额": [100000, 200000]})
    return to_excel_download(template, "目标模板.xlsx")

# ========== 页面启动时自动加载历史数据和目标数据 ==========
if not st.session_state.data_loaded:
    with st.spinner("正在加载历史业绩数据..."):
        history_df = load_from_supabase()
        if not history_df.empty:
            df_all, daily_latest, monthly_actual, latest_date = rebuild_from_history(history_df)
            st.session_state.df_all_daily = df_all
            st.session_state.daily_latest = daily_latest
            st.session_state.monthly_actual = monthly_actual
            st.session_state.latest_date = latest_date
        else:
            st.session_state.df_all_daily = None
            st.session_state.daily_latest = None
            st.session_state.monthly_actual = None
            st.session_state.latest_date = None
        # 加载目标数据
        st.session_state.target_dict = load_targets_from_supabase()
        st.session_state.data_loaded = True

# ========== 侧边栏：文件上传与工具 ==========
with st.sidebar:
    st.header("📂 数据加载")
    order_file = st.file_uploader("选择订单文件 (Excel)", type=["xlsx", "xls"], key="order_upload")
    if order_file is not None:
        if st.session_state.order_file_name != order_file.name:
            with st.spinner("正在处理订单文件..."):
                result = process_order_file(order_file)
                if result["success"]:
                    st.session_state.df_all_daily = result["df_all"]
                    st.session_state.daily_latest = result["daily_latest"]
                    st.session_state.monthly_actual = result["monthly_actual"]
                    st.session_state.df_ship_refund = result["df_ship"]
                    st.session_state.latest_date = result["latest_date"]
                    st.session_state.order_file_name = order_file.name
                    st.success(result["message"])
                else:
                    st.error(result["message"])
        else:
            st.info(f"已加载：{order_file.name}")

    target_file = st.file_uploader("选择目标文件 (Excel)", type=["xlsx", "xls"], key="target_upload")
    if target_file is not None:
        if st.session_state.target_file_name != target_file.name:
            with st.spinner("正在加载目标..."):
                result = load_target_file(target_file)
                if result["success"]:
                    st.session_state.target_dict = result["target_dict"]
                    st.session_state.target_file_name = target_file.name
                    st.success(result["message"])
                else:
                    st.error(result["message"])
        else:
            st.info(f"已加载：{target_file.name}")

    st.markdown("---")
    st.header("⚙️ 工具")
    template_data = download_target_template()
    st.download_button("📄 下载目标模板", data=template_data, file_name="目标模板.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if st.button("🗑️ 清除目标记忆"):
        # 清除数据库中的目标数据
        clear_targets_in_supabase()
        st.session_state.target_dict = {}
        st.session_state.target_file_name = None
        st.success("目标已清除（包括数据库）")
        st.rerun()

# ========== 主选项卡 ==========
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 最新日明细", "🏪 日期范围累计", "🔍 日期查询", "📦 发货退货明细", "🗄️ 历史业绩"])

with tab1:
    if st.session_state.get("daily_latest") is not None and not st.session_state.daily_latest.empty:
        df_display = add_target_and_rate(st.session_state.daily_latest, st.session_state.target_dict)
        df_display = df_display[["日期", "店铺名称", "当日金额", "月累计金额", "目标金额", "达成率"]]
        st.subheader(f"最新日：{st.session_state.latest_date.strftime('%Y-%m-%d')}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        excel_data = to_excel_download(df_display, "最新日明细.xlsx")
        st.download_button("💾 导出为 Excel", data=excel_data, file_name="最新日明细.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("暂无历史业绩数据，请先上传订单文件")

with tab2:
    if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", value=date.today().replace(day=1), key="range_start")
        with col2:
            end_date = st.date_input("结束日期", value=date.today(), key="range_end")
        if st.button("🔍 计算累计", key="calc_range"):
            if start_date > end_date:
                st.error("开始日期不能晚于结束日期")
            else:
                mask = (st.session_state.df_all_daily["日期"] >= pd.to_datetime(start_date)) & (st.session_state.df_all_daily["日期"] <= pd.to_datetime(end_date))
                range_data = st.session_state.df_all_daily[mask].copy()
                if range_data.empty:
                    st.warning(f"{start_date} 至 {end_date} 没有业绩数据")
                else:
                    range_summary = range_data.groupby("店铺名称")["当日金额"].sum().reset_index()
                    range_summary["累计金额"] = range_summary["当日金额"].round(2)
                    range_summary = range_summary.sort_values("店铺名称")[["店铺名称", "累计金额"]]
                    st.success(f"共 {len(range_summary)} 个店铺")
                    st.dataframe(range_summary, use_container_width=True, hide_index=True)
                    excel_data = to_excel_download(range_summary, f"累计_{start_date}_{end_date}.xlsx")
                    st.download_button("💾 导出此结果", data=excel_data, file_name=f"累计_{start_date}_{end_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("暂无历史业绩数据，请先上传订单文件")

with tab3:
    if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
        query_date = st.date_input("查询日期", value=date.today(), key="query_date")
        if st.button("🔍 查询", key="query_btn"):
            query_date_ts = pd.to_datetime(query_date)
            result = st.session_state.df_all_daily[st.session_state.df_all_daily["日期"] == query_date_ts].copy()
            if result.empty:
                st.warning(f"{query_date} 没有业绩数据")
            else:
                result = result.sort_values("店铺名称")
                result["当日金额"] = result["当日金额"].round(2)
                result["月累计金额"] = result["月累计金额"].round(2)
                cols = ["日期", "店铺名称", "当日金额", "月累计金额"]
                st.dataframe(result[cols], use_container_width=True, hide_index=True)
                excel_data = to_excel_download(result[cols], f"查询_{query_date}.xlsx")
                st.download_button("💾 导出查询结果", data=excel_data, file_name=f"查询_{query_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("暂无历史业绩数据，请先上传订单文件")

with tab4:
    if st.session_state.get("df_ship_refund") is not None and not st.session_state.df_ship_refund.empty:
        df_ship = st.session_state.df_ship_refund.copy()
        cols = ["日期", "店铺名称", "当日发货", "月累计发货", "当日退货", "月累计退货"]
        st.subheader(f"最新日发货退货明细 - {st.session_state.latest_date.strftime('%Y-%m-%d')}")
        st.dataframe(df_ship[cols], use_container_width=True, hide_index=True)
        excel_data = to_excel_download(df_ship[cols], "发货退货明细.xlsx")
        st.download_button("💾 导出发货退货明细", data=excel_data, file_name="发货退货明细.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("发货退货明细仅在上传订单文件后显示。历史业绩中暂未包含此项，如需查看请重新上传订单文件。")

with tab5:
    st.subheader("所有已保存的每日业绩")
    history_df = load_from_supabase()
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        excel_data = to_excel_download(history_df, "历史业绩.xlsx")
        st.download_button("💾 导出全部历史数据", data=excel_data, file_name="历史业绩.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("暂无历史数据，请先上传订单文件")
