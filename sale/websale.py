# -*- coding: utf-8 -*-
"""
订单业绩统计工具 - 带云端持久化存储（Supabase）
上传的每日业绩会自动保存到数据库，可永久查看历史数据
"""

import streamlit as st
import pandas as pd
from datetime import date
import io
from supabase import create_client, Client

# ========== Supabase 配置（请替换为你的实际值） ==========
SUPABASE_URL = "https://你的项目.supabase.co"   # 改成你的 URL
SUPABASE_KEY = "你的 anon public key"            # 改成你的 anon key

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

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

# ========== 数据库存取函数 ==========
def save_to_supabase(df_all):
    """将每日业绩数据保存到 Supabase（相同日期+店铺会跳过或更新）"""
    for _, row in df_all.iterrows():
        data = {
            "sale_date": row["日期"].strftime("%Y-%m-%d"),
            "shop_name": row["店铺名称"],
            "amount": float(row["当日金额"]),
            "cumulative_amount": float(row["月累计金额"])
        }
        # 检查是否已存在
        existing = supabase.table("daily_sales").select("*").eq("sale_date", data["sale_date"]).eq("shop_name", data["shop_name"]).execute()
        if not existing.data:
            supabase.table("daily_sales").insert(data).execute()
        else:
            # 已存在则更新累计金额
            supabase.table("daily_sales").update({"cumulative_amount": data["cumulative_amount"]}).eq("sale_date", data["sale_date"]).eq("shop_name", data["shop_name"]).execute()

def load_from_supabase():
    """从 Supabase 加载所有历史业绩数据"""
    response = supabase.table("daily_sales").select("*").execute()
    if response.data:
        df = pd.DataFrame(response.data)
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        df = df.rename(columns={"sale_date": "日期", "shop_name": "店铺名称", "amount": "当日金额", "cumulative_amount": "月累计金额"})
        return df
    else:
        return pd.DataFrame()

# ========== 以下是你原有的所有数据处理函数（未做修改，仅增加保存调用） ==========
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

        df_all = daily[["日期", "店铺名称", "当日金额", "月累计金额"]].copy()
        latest_date = daily["日期"].max()

        # 获取所有店铺的最新月累计
        latest_cumulative = daily.groupby("店铺名称").last().reset_index()[["店铺名称", "月累计金额"]]
        daily_latest = daily[daily["日期"] == latest_date][["日期", "店铺名称", "当日金额"]]
        daily_latest = pd.merge(latest_cumulative, daily_latest, on='店铺名称', how='left')
        daily_latest['当日金额'] = daily_latest['当日金额'].fillna(0).round(2)
        daily_latest['日期'] = daily_latest['日期'].fillna(latest_date)
        daily_latest = daily_latest[["日期", "店铺名称", "当日金额", "月累计金额"]]

        monthly_actual = df.groupby("店铺名称")["金额/时间"].sum().reset_index()
        monthly_actual["月累计金额"] = monthly_actual["金额/时间"].round(2)
        monthly_actual = monthly_actual.sort_values("店铺名称")
        monthly_actual = monthly_actual[["店铺名称", "月累计金额"]]

        # 发货退货
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

        # ========== 关键修改：保存到数据库 ==========
        save_to_supabase(df_all)

        return {
            "df_all": df_all,
            "daily_latest": daily_latest,
            "monthly_actual": monthly_actual,
            "df_ship": df_ship,
            "latest_date": latest_date,
            "success": True,
            "message": f"处理完成并已保存！最新日期：{latest_date.strftime('%Y-%m-%d')}"
        }
    except Exception as e:
        return {"success": False, "message": f"处理失败：{str(e)}"}

# 以下是目标文件、导出、界面等原有函数（保持原样，这里省略以节省篇幅，但实际运行时必须包含）
# 由于你之前已有完整代码，请将下面缺失的部分从你原有的 websale.py 中复制过来。
# 为方便，我在这里给出关键函数的骨架，你需要补全。

def load_target_file(uploaded_file):
    # 原函数内容，保持不变
    pass

def add_target_and_rate(df, target_dict):
    # 原函数内容，保持不变
    pass

def to_excel_download(df, filename="export.xlsx"):
    # 原函数内容，保持不变
    pass

def download_target_template():
    # 原函数内容，保持不变
    pass

# ========== 界面布局 ==========
with st.sidebar:
    # 原侧边栏代码（文件上传等），保持不变
    pass

# 选项卡
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 最新日明细", "🏪 日期范围累计", "🔍 日期查询", "📦 发货退货明细", "🗄️ 历史业绩"])

with tab1:
    # 原最新日明细代码
    pass

with tab2:
    # 原日期范围累计代码
    pass

with tab3:
    # 原日期查询代码
    pass

with tab4:
    # 原发货退货明细代码
    pass

with tab5:
    st.subheader("所有已保存的每日业绩")
    history_df = load_from_supabase()
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        excel_data = to_excel_download(history_df, "历史业绩.xlsx")
        st.download_button("💾 导出全部历史数据", data=excel_data, file_name="历史业绩.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("暂无历史数据，请先上传订单文件")
