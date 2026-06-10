# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import date
import io
from supabase import create_client
import plotly.express as px

# ========== 页面配置 ==========
st.set_page_config(page_title="业绩统计工具", layout="wide", page_icon="📊")

# ========== 密码验证 ==========
PASSWORD = st.secrets.get("PASSWORD", "94949468") # 建议在 secrets 中配置

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

# ========== 数据加载与保存辅助函数 ==========
@st.cache_data(ttl=600)
def load_product_master():
    if supabase is None: return pd.DataFrame()
    resp = supabase.table("product_master").select("*").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

@st.cache_data(ttl=600)
def load_product_sales():
    if supabase is None: return pd.DataFrame()
    resp = supabase.table("product_sales").select("*").execute()
    if not resp.data: return pd.DataFrame()
    df = pd.DataFrame(resp.data)
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df

def rebuild_daily_data():
    resp = supabase.table("daily_sales").select("*").execute()
    if not resp.data: return
    df = pd.DataFrame(resp.data)
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    st.session_state.df_all_daily = df.rename(columns={"sale_date": "日期", "shop_name": "店铺名称", "amount": "当日金额", "cumulative_amount": "月累计金额"})
    st.session_state.daily_latest = st.session_state.df_all_daily.loc[st.session_state.df_all_daily.groupby("店铺名称")["日期"].idxmax()].copy()

# ========== 核心逻辑执行 ==========
rebuild_daily_data()

# ========== 选项卡布局 ==========
tab1, tab2, tab3, tab4, tab5, tab6, tab_debug = st.tabs(["📅 最新日明细", "🏪 日期范围累计", "🔍 日期查询", "📦 发货退货明细", "🗄️ 历史业绩", "📊 商品分析", "🔧 调试"])

# [此处省略 tab1 - tab5 的代码，保留原有的稳定逻辑即可]

# ========== 修复后的 tab6 商品分析 ==========
with tab6:
    st.subheader("📊 商品销售分析（按货号汇总）")
    prod_df = load_product_sales()
    
    if prod_df.empty:
        st.warning("暂无商品销售数据。")
    else:
        # 1. 聚合销售数据
        grouped = prod_df.groupby("style_code").agg(
            发货金额=("ship_amount", "sum"),
            退货金额=("return_amount", "sum"),
            净销售金额=("net_amount", "sum")
        ).reset_index()
        grouped.rename(columns={"style_code": "货号"}, inplace=True)
        
        # 2. 关联商品库获取图片/分类
        master_df = load_product_master()
        if not master_df.empty and "style_code" in master_df.columns:
            attr = master_df[["style_code", "image_url", "category"]].drop_duplicates(subset="style_code")
            attr.rename(columns={"style_code": "货号", "category": "master_category"}, inplace=True)
            grouped = grouped.merge(attr, on="货号", how="left")
        else:
            grouped["master_category"] = "未知"
            grouped["image_url"] = None

        # 3. 显示结果
        st.dataframe(
            grouped.sort_values("净销售金额", ascending=False),
            column_config={
                "货号": st.column_config.TextColumn("货号"),
                "master_category": "商品分类",
                "净销售金额": st.column_config.NumberColumn("净销售金额", format="%.2f"),
                "image_url": st.column_config.ImageColumn("商品图片", help="点击放大")
            },
            hide_index=True, use_container_width=True
        )

        # 4. 可视化分析
        if not grouped["master_category"].isnull().all():
            pie_data = grouped.groupby("master_category")["净销售金额"].sum().reset_index()
            fig = px.pie(pie_data, names="master_category", values="净销售金额", title="各分类净销售占比")
            st.plotly_chart(fig, use_container_width=True)

# ========== 调试选项卡 ==========
with tab_debug:
    st.write("调试：检查列名")
    prod_df = load_product_sales()
    if not prod_df.empty:
        st.write("Sales columns:", prod_df.columns.tolist())
