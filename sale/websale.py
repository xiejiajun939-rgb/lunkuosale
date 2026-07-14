# ========== 最新日明细 ==========
if idx_latest is not None:
    with tabs[idx_latest]:
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
            st.download_button("💾 导出 Excel", data=output.getvalue(), file_name="最新日明细.xlsx", key="export_latest_detail")
        else:
            st.info("暂无店铺业绩数据，请先上传订单文件")

# ========== 日期范围累计 ==========
if idx_range is not None:
    with tabs[idx_range]:
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

# ========== 日期查询 ==========
if idx_query is not None:
    with tabs[idx_query]:
        if st.session_state.get("df_all_daily") is not None and not st.session_state.df_all_daily.empty:
            if st.button("📅 今日", key="query_today"):
                st.session_state["query_date_final"] = date.today()
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

# ========== 发货退货明细 ==========
if idx_ship_return is not None:
    with tabs[idx_ship_return]:
        with st.spinner("正在加载商品数据，请稍候..."):
            prod_df = load_product_sales(st.session_state.table_suffix)
        if prod_df.empty:
            st.info("暂无商品数据，请先上传订单文件")
        else:
            dates = sorted(prod_df["sale_date"].unique(), reverse=True)
            if dates:
                if st.button("📅 今日", key="ship_today"):
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

# ========== 历史业绩 ==========
if idx_history is not None:
    with tabs[idx_history]:
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
            st.download_button("💾 导出全部", data=output.getvalue(), file_name="历史业绩.xlsx", key="export_history_all")
        else:
            st.info("暂无历史数据")

# ========== 商品分析（不变） ==========
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
            # 获取日期值
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

# ========== 销售对比（主播/店铺维度） ==========
if idx_anchor_compare is not None:
    with tabs[idx_anchor_compare]:
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
                    selected_dimensions = st.multiselect(
                        f"选择对比的{dimension_name}（最多3个）",
                        options=all_dimensions,
                        default=[],
                        key="dimension_multiselect"
                    )
                    if len(selected_dimensions) > 3:
                        st.warning("最多只能选择3个，请取消多余的选项。")
                        selected_dimensions = selected_dimensions[:3]
                with col_select2:
                    metric_options = ["净销售金额", "发货金额", "退货金额"]
                    selected_metrics = st.multiselect("选择要对比的指标", options=metric_options, default=["净销售金额"])
                with col_select3:
                    chart_type = st.radio("图表类型", ["折线图", "柱状图"], horizontal=True, key="compare_chart_type")
                
                min_date = prod_df["sale_date"].min().date()
                max_date = prod_df["sale_date"].max().date()
                
                date_quick_buttons("compare_start", "compare_end",
                                   default_start=min_date,
                                   default_end=max_date,
                                   min_date=min_date,
                                   max_date=max_date)
                start_date = st.session_state.get("compare_start", min_date)
                end_date = st.session_state.get("compare_end", max_date)
                
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
                            st.caption(f"当前选中的 {dimension_name}：{selected_dimensions}")
                            
                            for metric in selected_metrics:
                                st.markdown(f"#### {metric} 趋势对比")
                                pivot_df = daily_agg.pivot(index="sale_date", columns=dimension_col, values=metric)
                                pivot_df = pivot_df.reindex(columns=selected_dimensions, fill_value=0)
                                st.caption(f"补全后的列：{list(pivot_df.columns)}")
                                
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
                                    compare_df = compare_df.reindex(columns=selected_dimensions, fill_value=0)
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
                                            pivot_season = pivot_season.reindex(columns=selected_dimensions, fill_value=0)
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
                                            pivot_year = pivot_year.reindex(columns=selected_dimensions, fill_value=0)
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
                        all_options = base_tabs  # 此时 base_tabs 不包含组织Tab，但我们会在后面插入，所以权限管理暂不包含它（默认允许）
                        # 但为了统一，我们可以手动添加 '🏢 组织与部门分析' 到选项列表
                        all_options = base_tabs + (["🏢 组织与部门分析"] if st.session_state.table_suffix == "_all" else [])
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

# ========== 异常预警（仅管理员） ==========
if idx_alert is not None:
    with tabs[idx_alert]:
        st.subheader("⚠️ 异常预警监控")
        st.info("监控近7天业绩下滑明显的店铺，以及退货率激增的商品。可调整敏感度阈值。")
        
        # 加载数据（利用缓存）
        with st.spinner("加载数据..."):
            daily_df = load_daily_sales(st.session_state.table_suffix)
            prod_df = load_product_sales(st.session_state.table_suffix)
        
        if daily_df.empty or prod_df.empty:
            st.warning("数据不足，请先上传订单文件。")
        else:
            # 确保 daily_df 包含必要的列（原始列名：shop_name, amount）
            if "shop_name" not in daily_df.columns or "amount" not in daily_df.columns:
                st.error("daily_sales 表中缺少 shop_name 或 amount 列，请检查数据结构。")
                st.stop()
            
            # 获取当前日期范围
            today = date.today()
            # 近7天：过去7天（不含今天，因为今天可能不全）
            end_date = today - timedelta(days=1)
            start_date_recent = end_date - timedelta(days=6)
            # 前7天：再往前推7天
            start_date_previous = start_date_recent - timedelta(days=7)
            end_date_previous = start_date_recent - timedelta(days=1)
            
            # 确保日期在数据范围内
            min_data_date = daily_df["sale_date"].min().date()
            max_data_date = daily_df["sale_date"].max().date()
            if start_date_recent < min_data_date:
                st.warning("数据不足以覆盖近7天，请检查数据日期范围。")
                st.stop()
            
            # ------ 1. 业绩下滑店铺 ------
            st.markdown("### 📉 业绩下滑店铺（近7天 vs 前7天日均）")
            col1, col2 = st.columns([2, 1])
            with col1:
                decline_threshold = st.slider("下滑幅度阈值（%）", min_value=0, max_value=100, value=20, key="decline_threshold")
            with col2:
                min_days = st.number_input("至少需要最近7天有销售天数", min_value=1, max_value=7, value=3, key="min_days")
            
            # 筛选日期范围
            mask_recent = (daily_df["sale_date"] >= pd.to_datetime(start_date_recent)) & (daily_df["sale_date"] <= pd.to_datetime(end_date))
            mask_previous = (daily_df["sale_date"] >= pd.to_datetime(start_date_previous)) & (daily_df["sale_date"] <= pd.to_datetime(end_date_previous))
            
            recent_data = daily_df[mask_recent].copy()
            previous_data = daily_df[mask_previous].copy()
            
            # 按店铺聚合（使用原始列名 shop_name 和 amount）
            recent_agg = recent_data.groupby("shop_name").agg(
                近7天总额=("amount", "sum"),
                近7天天数=("amount", "count")
            ).reset_index()
            previous_agg = previous_data.groupby("shop_name").agg(
                前7天总额=("amount", "sum"),
                前7天天数=("amount", "count")
            ).reset_index()
            
            # 合并
            merged = pd.merge(recent_agg, previous_agg, on="shop_name", how="inner")
            # 计算日均
            merged["近7天日均"] = merged["近7天总额"] / merged["近7天天数"]
            merged["前7天日均"] = merged["前7天总额"] / merged["前7天天数"]
            # 过滤有销售的天数
            merged = merged[merged["近7天天数"] >= min_days]
            # 计算下滑幅度
            merged["下滑幅度"] = ((merged["前7天日均"] - merged["近7天日均"]) / merged["前7天日均"] * 100).round(2)
            # 筛选下滑大于阈值的
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
                # 高亮显示最严重的
                worst = decline_df.iloc[0]
                st.metric("⚠️ 下滑最严重店铺", worst["shop_name"], delta=f"{worst['下滑幅度']:.2f}%", delta_color="inverse")
            
            # ------ 2. 退货率激增商品 ------
            st.markdown("### 📈 退货率激增商品（近7天 vs 前7天退货率）")
            col3, col4 = st.columns(2)
            with col3:
                return_rate_threshold = st.slider("退货率上升阈值（百分点）", min_value=0, max_value=50, value=10, key="return_rate_threshold")
            with col4:
                min_ship_recent = st.number_input("近7天发货金额至少", min_value=0, value=1000, step=100, key="min_ship")
            
            # 从 product_sales 中按货号汇总
            # 先过滤日期
            prod_recent = prod_df[(prod_df["sale_date"] >= pd.to_datetime(start_date_recent)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))]
            prod_previous = prod_df[(prod_df["sale_date"] >= pd.to_datetime(start_date_previous)) & (prod_df["sale_date"] <= pd.to_datetime(end_date_previous))]
            
            # 按货号聚合
            def agg_ship_return(df):
                return df.groupby("style_code").agg(
                    发货金额=("ship_amount", "sum"),
                    退货金额=("return_amount", "sum")
                ).reset_index()
            
            recent_prod = agg_ship_return(prod_recent)
            previous_prod = agg_ship_return(prod_previous)
            
            # 合并
            merged_prod = pd.merge(recent_prod, previous_prod, on="style_code", suffixes=("_近7天", "_前7天"), how="inner")
            # 过滤近7天发货金额大于阈值
            merged_prod = merged_prod[merged_prod["发货金额_近7天"] >= min_ship_recent]
            # 计算退货率
            merged_prod["退货率_近7天"] = (merged_prod["退货金额_近7天"] / merged_prod["发货金额_近7天"] * 100).round(2)
            merged_prod["退货率_前7天"] = (merged_prod["退货金额_前7天"] / merged_prod["发货金额_前7天"] * 100).round(2)
            # 处理前7天发货为0的情况
            merged_prod["退货率_前7天"] = merged_prod["退货率_前7天"].fillna(0)
            # 计算退货率变化
            merged_prod["退货率变化"] = (merged_prod["退货率_近7天"] - merged_prod["退货率_前7天"]).round(2)
            # 筛选增长大于阈值
            return_spike = merged_prod[merged_prod["退货率变化"] >= return_rate_threshold].sort_values("退货率变化", ascending=False)
            
            if return_spike.empty:
                st.success("🎉 近7天没有退货率激增的商品。")
            else:
                # 合并商品名称（从 master 获取）可选
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
                # 高亮最严重的
                worst_prod = return_spike.iloc[0]
                st.metric("⚠️ 退货率激增最严重商品", worst_prod["style_code"], delta=f"{worst_prod['退货率变化']:.2f} 百分点", delta_color="inverse")

# ========== 新增：组织与部门分析 Tab（仅 _all） ==========
if idx_org is not None:
    with tabs[idx_org]:
        st.subheader("🏢 组织与部门分析")
        st.info("基于全部数据源（_all）的商品销售数据，按组织/部门维度展示业绩表现。")

        with st.spinner("加载组织/部门数据..."):
            # 加载商品销售数据（已包含 org_name, dept）
            prod_df = load_product_sales(st.session_state.table_suffix)
            if prod_df.empty:
                st.warning("暂无商品数据，请先上传订单文件。")
                st.stop()
            # 仅当 _all 时才有 org_name/dept，否则提示
            if 'org_name' not in prod_df.columns or 'dept' not in prod_df.columns:
                st.error("当前数据源缺少组织/部门信息，请确保在全部数据源下使用。")
                st.stop()

        # 日期范围筛选
        min_date = prod_df["sale_date"].min().date()
        max_date = prod_df["sale_date"].max().date()
        date_quick_buttons("org_start", "org_end",
                           default_start=min_date,
                           default_end=max_date,
                           min_date=min_date,
                           max_date=max_date)
        start_date = st.session_state.get("org_start", min_date)
        end_date = st.session_state.get("org_end", max_date)

        # 筛选数据
        mask = (prod_df["sale_date"] >= pd.to_datetime(start_date)) & (prod_df["sale_date"] <= pd.to_datetime(end_date))
        df_filtered = prod_df[mask].copy()
        if df_filtered.empty:
            st.warning("所选日期范围内无数据")
            st.stop()

        # ---------- 1. 组织业绩占比（环形图） ----------
        st.markdown("#### 各组织净销售额占比")
        org_net = df_filtered.groupby('org_name')['net_amount'].sum().reset_index()
        org_net = org_net[org_net['net_amount'] != 0]
        if not org_net.empty:
            fig_org = px.pie(org_net, names='org_name', values='net_amount',
                             title='', hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_org.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_org, use_container_width=True)
        else:
            st.info("无有效组织数据")

        # ---------- 2. 部门业绩排行（堆叠柱状图） ----------
        st.markdown("#### 各部门净销售额（按组织堆叠）")
        dept_org = df_filtered.groupby(['org_name', 'dept'])['net_amount'].sum().reset_index()
        dept_org = dept_org[dept_org['net_amount'] != 0]
        if not dept_org.empty:
            # 取 top 组织，避免图表过于拥挤
            top_orgs = dept_org.groupby('org_name')['net_amount'].sum().nlargest(10).index
            dept_org_top = dept_org[dept_org['org_name'].isin(top_orgs)]
            fig_dept = px.bar(dept_org_top, x='dept', y='net_amount', color='org_name',
                              title='', labels={'net_amount':'净销售额', 'dept':'部门'},
                              barmode='stack')
            fig_dept.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_dept, use_container_width=True)
        else:
            st.info("无部门数据")

        # ---------- 3. 维度透视表 ----------
        st.markdown("#### 组织-部门 维度透视表")
        pivot = df_filtered.pivot_table(
            index=['org_name', 'dept'],
            values=['net_amount', 'ship_amount', 'return_amount'],
            aggfunc='sum',
            fill_value=0
        ).reset_index()
        pivot['退货率'] = (pivot['return_amount'] / pivot['ship_amount'] * 100).round(2).fillna(0)
        pivot['退货率'] = pivot['退货率'].map(lambda x: f"{x:.2f}%")
        pivot.columns = ['组织', '部门', '净销售额', '发货额', '退货额', '退货率']
        pivot = pivot.sort_values(['组织', '净销售额'], ascending=[True, False])
        st.dataframe(pivot, use_container_width=True, hide_index=True)

        # 导出功能
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pivot.to_excel(writer, index=False)
        st.download_button("💾 导出组织部门透视表", data=output.getvalue(),
                           file_name=f"组织部门分析_{start_date}_{end_date}.xlsx",
                           key="export_org_dept")

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
