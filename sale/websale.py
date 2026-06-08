# -*- coding: utf-8 -*-
"""
订单业绩统计工具 - 完整版（商品分析饼图，直接插入无冲突）
访问密码：94949468
"""

import streamlit as st
import pandas as pd
from datetime import date
import io
from supabase import create_client
import matplotlib.pyplot as plt
import plotly.express as px   # 添加这行
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
if "df_all_daily" not in st.session_state:
    st.session_state.df_all_daily = None
if "target_dict" not in st.session_state:
    st.session_state.target_dict = {}
if "latest_date" not in st.session_state:
    st.session_state.latest_date = None
if "order_upload_key" not in st.session_state:
    st.session_state.order_upload_key = 0

# ========== 店铺业绩数据函数 ==========
def load_daily_sales():
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

def save_daily_sales(records):
    if supabase is None or not records:
        return
    supabase.table("daily_sales").upsert(records, on_conflict="sale_date,shop_name").execute()

def rebuild_daily_data():
    df = load_daily_sales()
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

def save_targets(target_dict):
    if supabase is None:
        return
    records = [{"shop_name": k, "target_amount": v} for k, v in target_dict.items()]
    if records:
        supabase.table("shop_targets").upsert(records, on_conflict="shop_name").execute()

def clear_targets():
    if supabase:
        supabase.table("shop_targets").delete().neq("id", 0).execute()
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

@st.cache_data(ttl=3600)
def load_product_master():
    if supabase is None:
        return pd.DataFrame()
    try:
        resp = supabase.table("product_master").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            if "product_code" in df.columns:
                df = df.rename(columns={"product_code": "master_code"})
            return df
        else:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def save_product_sales(df_orders):
    """直接插入订单明细，不处理冲突（假设每条记录唯一）"""
    if supabase is None:
        return
    master_df = load_product_master()
    master_map = {}
    if not master_df.empty:
        for _, row in master_df.iterrows():
            code = row["master_code"]
            master_map[code] = {
                "image_url": row.get("image_url", None),
                "master_category": row.get("category", None)
            }
    records = []
    for _, row in df_orders.iterrows():
        parsed = parse_product_code(row["备注"])
        if parsed is None:
            continue
        amount = float(row["金额/时间"])
        short_code = parsed["style_code"]
        img = master_map.get(short_code, {}).get("image_url")
        cat = master_map.get(short_code, {}).get("master_category")
        records.append({
            "sale_date": row["日期"].strftime("%Y-%m-%d"),
            "shop_name": row["店铺名称"],
            "product_code": parsed["product_code"],
            "style_code": short_code,
            "brand": parsed["brand"],
            "year": parsed["year"],
            "season": parsed["season"],
            "category": parsed["category"],
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
        # 直接插入，假设无重复
        supabase.table("product_sales").insert(records).execute()

@st.cache_data(ttl=600)
def load_product_sales():
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
        st.error(f"加载商品销售数据失败：{e}")
        return pd.DataFrame()

# ========== 订单文件处理 ==========
def process_uploaded_file(uploaded_file):
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

        # 保存商品明细（直接插入）
        save_product_sales(df)

        # 店铺业绩汇总
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
        save_targets(target_dict)
        st.session_state.target_dict = target_dict
        return True, f"成功加载 {len(target_dict)} 个店铺目标"
    except Exception as e:
        return False, str(e)

# ========== 页面初始化加载数据 ==========
rebuild_daily_data()
if st.session_state.target_dict == {}:
    st.session_state.target_dict = load_targets()

# ========== 侧边栏 ==========
with st.sidebar:
    st.header("📂 数据加载")
    order_key = f"order_upload_{st.session_state.order_upload_key}"
    uploaded_order = st.file_uploader("选择订单文件 (Excel)", type=["xlsx", "xls"], key=order_key)
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
    template_df = pd.DataFrame({"店铺名称": ["示例店铺A", "示例店铺B"], "目标金额": [100000, 200000]})
    template_bytes = io.BytesIO()
    with pd.ExcelWriter(template_bytes, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False)
    st.download_button("📄 下载目标模板", data=template_bytes.getvalue(), file_name="目标模板.xlsx")
    if st.button("🗑️ 清除目标记忆"):
        clear_targets()

# ========== 创建选项卡 ==========
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📅 最新日明细", "🏪 日期范围累计", "🔍 日期查询", "📦 发货退货明细", "🗄️ 历史业绩", "📊 商品分析"])

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
        
        # 合计卡片
        df_sales = st.session_state.daily_latest.copy()
        douyin_df = df_sales[df_sales["店铺名称"].str.contains("抖音", case=False, na=False)]
        video_df = df_sales[df_sales["店铺名称"].str.contains("视频号", case=False, na=False)]
        target_dict = st.session_state.target_dict
        
        douyin_target = sum(target_dict.get(shop, 0) for shop in douyin_df["店铺名称"])
        douyin_cum = douyin_df["月累计金额"].sum()
        douyin_rate = f"{(douyin_cum / douyin_target * 100):.2f}%" if douyin_target > 0 else "未设目标"
        
        video_target = sum(target_dict.get(shop, 0) for shop in video_df["店铺名称"])
        video_cum = video_df["月累计金额"].sum()
        video_rate = f"{(video_cum / video_target * 100):.2f}%" if video_target > 0 else "未设目标"
        
        total_target = sum(target_dict.values())
        total_cum = df_sales["月累计金额"].sum()
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
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    res[cols].to_excel(writer, index=False)
                st.download_button("💾 导出", data=output.getvalue(), file_name=f"查询_{query_date}.xlsx")
    else:
        st.info("暂无数据")

# ========== 发货退货明细 ==========
with tab4:
    st.subheader("📦 发货退货明细（按店铺）")
    prod_df = load_product_sales()
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
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            daily_df.to_excel(writer, index=False)
        st.download_button("💾 导出全部", data=output.getvalue(), file_name="历史业绩.xlsx")
    else:
        st.info("暂无历史数据")

# ========== 商品分析（含饼图） ==========
with tab6:
    st.subheader("📊 商品销售分析（按品牌+产品）")
    prod_df = load_product_sales()
    
    if prod_df.empty:
        st.warning("暂无商品销售数据，请先上传订单文件。")
    else:
        # 确保必要列
        if "brand" not in prod_df.columns or prod_df["brand"].isnull().all():
            prod_df["brand"] = prod_df["product_code"].str[0]
        else:
            prod_df["brand"] = prod_df["brand"].fillna(prod_df["product_code"].str[0])
        
        if "style_code" not in prod_df.columns:
            prod_df["style_code"] = prod_df["product_code"].str[:8]
        else:
            prod_df["style_code"] = prod_df["style_code"].fillna(prod_df["product_code"].str[:8])
        
        if "image_url" not in prod_df.columns:
            prod_df["image_url"] = None
        if "master_category" not in prod_df.columns:
            prod_df["master_category"] = None
        
        # 日期筛选
        min_date = prod_df["sale_date"].min().date()
        max_date = prod_df["sale_date"].max().date()
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", min_date, key="prod_start", min_value=min_date, max_value=max_date)
        with col2:
            end_date = st.date_input("结束日期", max_date, key="prod_end", min_value=min_date, max_value=max_date)
        
        mask = (prod_df["sale_date"] >= pd.to_datetime(start_date)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))
        filtered = prod_df[mask].copy()
        
        # 品牌筛选
        brands = ["全部"] + sorted(filtered["brand"].dropna().unique())
        selected_brand = st.selectbox("选择品牌", brands)
        if selected_brand != "全部":
            filtered = filtered[filtered["brand"] == selected_brand]
        
        if filtered.empty:
            st.warning("所选条件下无销售数据")
        else:
            # ---- 按商品分类汇总 ----
            cat_summary = filtered.groupby("master_category").agg(
                发货金额=("ship_amount", "sum"),
                退货金额=("return_amount", "sum"),
                净销售金额=("net_amount", "sum")
            ).reset_index()
            cat_summary = cat_summary[cat_summary["master_category"].notna()]  # 过滤空分类
            
            if not cat_summary.empty:
                st.subheader("📊 按商品分类统计")
                # 三列饼图
                col_pie1, col_pie2, col_pie3 = st.columns(3)
                with col_pie1:
                    fig_ship = px.pie(cat_summary, names="master_category", values="发货金额", 
                                      title="发货金额分布", hole=0.3,
                                      color_discrete_sequence=px.colors.qualitative.Set3)
                    fig_ship.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_ship, use_container_width=True)
                with col_pie2:
                    fig_return = px.pie(cat_summary, names="master_category", values="退货金额", 
                                        title="退货金额分布", hole=0.3,
                                        color_discrete_sequence=px.colors.qualitative.Set2)
                    fig_return.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_return, use_container_width=True)
                with col_pie3:
                    fig_net = px.pie(cat_summary, names="master_category", values="净销售金额", 
                                     title="净销售金额分布", hole=0.3,
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_net.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_net, use_container_width=True)
            else:
                st.info("当前筛选条件下无有效商品分类数据")
            
            # ---- 原有表格（品牌+货号） ----
            st.subheader("📋 商品销售明细（按品牌+货号）")
            grouped = filtered.groupby(["brand", "style_code", "master_category", "image_url"]).agg(
                发货金额=("ship_amount", "sum"),
                退货金额=("return_amount", "sum"),
                净销售金额=("net_amount", "sum")
            ).reset_index()
            grouped = grouped.sort_values("净销售金额", ascending=False)
            grouped.rename(columns={"style_code": "货号"}, inplace=True)
            
            st.dataframe(
                grouped,
                column_config={
                    "brand": "品牌",
                    "货号": "货号",
                    "master_category": "商品分类",
                    "发货金额": st.column_config.NumberColumn("发货金额", format="%.2f"),
                    "退货金额": st.column_config.NumberColumn("退货金额", format="%.2f"),
                    "净销售金额": st.column_config.NumberColumn("净销售金额", format="%.2f"),
                    "image_url": st.column_config.ImageColumn("商品图片", help="点击放大")
                },
                hide_index=True,
                use_container_width=True
            )
            # 导出
            export_df = grouped.drop(columns=["image_url"])
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False)
            st.download_button("💾 导出分析结果", data=output.getvalue(), file_name="商品分析.xlsx")
