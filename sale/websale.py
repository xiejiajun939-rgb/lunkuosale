# ========== 商品分析 ==========
with tabs[tab_index_product]:
    # ----- 弹窗状态管理 -----
    if st.session_state.get("detail_clicked", False):
        st.session_state.detail_clicked = False
    else:
        st.session_state.show_dialog = False
        st.session_state.dialog_style_code = None
        st.session_state.cached_detail_data = None

    st.subheader("📊 商品销售分析（按货号汇总）")
    col_btn, _ = st.columns([1, 5])
    with col_btn:
        if st.button("🔄 刷新数据", key="refresh_analysis_final_v2", help="清除缓存并重新从数据库加载最新数据"):
            st.session_state.show_dialog = False
            st.session_state.dialog_style_code = None
            st.session_state.cached_detail_data = None
            st.session_state.detail_clicked = False
            st.cache_data.clear()
            st.rerun()
    
    # 弹窗控制变量
    if "dialog_style_code" not in st.session_state:
        st.session_state.dialog_style_code = None
    if "show_dialog" not in st.session_state:
        st.session_state.show_dialog = False
    if "cached_detail_data" not in st.session_state:
        st.session_state.cached_detail_data = None
    if "detail_clicked" not in st.session_state:
        st.session_state.detail_clicked = False
    
    # 分页和排序
    if "product_page_num" not in st.session_state:
        st.session_state.product_page_num = 1
    if "sort_by" not in st.session_state:
        st.session_state.sort_by = "净销售金额"
    if "sort_ascending" not in st.session_state:
        st.session_state.sort_ascending = False
    
    prod_df = load_product_sales(st.session_state.table_suffix)
    if prod_df.empty:
        st.warning("暂无商品销售数据，请先上传订单文件。")
    else:
        if "style_code" in prod_df.columns:
            prod_df["style_code"] = prod_df["style_code"].astype(str).str.strip().str.upper()
        else:
            prod_df["style_code"] = prod_df["product_code"].str[:8].str.strip().str.upper()
        
        # 提取主播（全部数据需要，直播数据也需要）
        if st.session_state.table_suffix in ["_live", "_all"]:
            def extract_anchor_local(remark):
                if not isinstance(remark, str):
                    return None
                match = re.search(r'主播[：:]([^_]+)', remark)
                if match:
                    return match.group(1).strip()
                return None
            prod_df["anchor"] = prod_df["remark"].apply(extract_anchor_local)
        
        min_date = prod_df["sale_date"].min().date()
        max_date = prod_df["sale_date"].max().date()
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date = st.date_input("开始日期", value=min_date, key="prod_start_final_v2", min_value=min_date, max_value=max_date)
        with col_date2:
            end_date = st.date_input("结束日期", value=max_date, key="prod_end_final_v2", min_value=min_date, max_value=max_date)
        
        st.subheader("🔍 筛选条件")
        col_platform, col_shop = st.columns(2)
        with col_platform:
            platform_options = ["全部", "抖音", "视频号"]
            selected_platform = st.selectbox("平台", platform_options, key="platform_filter_final_v2")
        with col_shop:
            all_shops_all = prod_df["shop_name"].unique()
            if selected_platform == "抖音":
                shop_options = [shop for shop in all_shops_all if "抖音" in shop]
            elif selected_platform == "视频号":
                shop_options = [shop for shop in all_shops_all if "视频号" in shop]
            else:
                shop_options = list(all_shops_all)
            selected_shops = st.multiselect("店铺（可多选）", options=sorted(shop_options), default=[], key="shop_filter_final_v2")
        
        col_code, col_brand = st.columns(2)
        with col_code:
            style_codes_input = st.text_input(
                "货号筛选（多个用英文逗号分隔）",
                placeholder="例如: L262Y050, G262Y030",
                key="style_code_filter_final_v2"
            )
        with col_brand:
            brands_all = ["全部"] + sorted(prod_df["brand"].dropna().unique())
            selected_brand = st.selectbox("品牌", brands_all, key="brand_filter_final_v2")
        
        selected_anchors = []
        if st.session_state.table_suffix in ["_live", "_all"] and "anchor" in prod_df.columns:
            all_anchors = prod_df["anchor"].dropna().unique()
            if len(all_anchors) > 0:
                selected_anchors = st.multiselect(
                    "主播（可多选）",
                    options=sorted(all_anchors),
                    default=[],
                    key="anchor_filter_final_v2"
                )
        
        # 应用筛选
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
        
        if filtered.empty:
            st.warning("所选条件下无销售数据")
        else:
            # 折线图
            st.subheader("📈 每日净销售走势（按货号）")
            all_style_codes = sorted(filtered["style_code"].unique())
            if all_style_codes:
                selected_styles = st.multiselect(
                    "选择要查看的货号（可多选）",
                    options=all_style_codes,
                    default=all_style_codes[:3] if len(all_style_codes) > 3 else all_style_codes,
                    key="trend_styles_v2"
                )
                if selected_styles:
                    trend_df = filtered[filtered["style_code"].isin(selected_styles)]
                    daily_trend = trend_df.groupby(["sale_date", "style_code"])["net_amount"].sum().reset_index()
                    pivot_df = daily_trend.pivot(index="sale_date", columns="style_code", values="net_amount").fillna(0)
                    if not pivot_df.empty:
                        fig_line = px.line(
                            pivot_df, 
                            x=pivot_df.index, 
                            y=pivot_df.columns,
                            title="每日净销售走势",
                            labels={"value": "净销售金额(¥)", "sale_date": "日期", "variable": "货号"},
                            markers=True
                        )
                        fig_line.update_layout(legend_title_text="货号", xaxis_title="日期", yaxis_title="净销售金额(¥)")
                        st.plotly_chart(fig_line, use_container_width=True)
                    else:
                        st.info("所选货号无足够数据绘制趋势图")
                else:
                    st.info("请至少选择一个货号查看趋势")
            else:
                st.info("当前筛选条件下无货号数据")
            st.markdown("---")
            
            # 按货号汇总
            grouped = filtered.groupby("style_code").agg(
                发货金额=("ship_amount", "sum"),
                退货金额=("return_amount", "sum"),
                净销售金额=("net_amount", "sum")
            ).reset_index()
            grouped.rename(columns={"style_code": "货号"}, inplace=True)
            master_df = load_product_master()
            if not master_df.empty and "style_code" in master_df.columns:
                master_df["style_code"] = master_df["style_code"].astype(str).str.strip().str.upper()
                master_df = master_df.drop_duplicates(subset="style_code", keep="first")
                img_map = master_df.set_index("style_code")["image_url"].to_dict()
                cat_map = master_df.set_index("style_code")["category"].to_dict()
                grouped["image_url"] = grouped["货号"].map(img_map).fillna(None)
                if "master_category" not in filtered.columns:
                    filtered["master_category"] = None
                cat_series = filtered.groupby("style_code")["master_category"].first()
                grouped["master_category"] = grouped["货号"].map(cat_series)
                for idx, row in grouped.iterrows():
                    if pd.isna(row["master_category"]) and row["货号"] in cat_map:
                        grouped.at[idx, "master_category"] = cat_map[row["货号"]]
            else:
                grouped["master_category"] = None
                grouped["image_url"] = None
            grouped["退款率"] = grouped.apply(
                lambda row: f"{(row['退货金额'] / row['发货金额'] * 100):.2f}%" 
                if row['发货金额'] != 0 else "-", axis=1
            )
            
            # 排序控件
            st.markdown("#### 货号汇总表")
            col_sort1, col_sort2, _ = st.columns([1, 1, 2])
            with col_sort1:
                sort_options = ["货号", "发货金额", "退货金额", "净销售金额", "退款率"]
                selected_sort = st.selectbox("排序字段", sort_options, index=sort_options.index(st.session_state.sort_by) if st.session_state.sort_by in sort_options else 3, key="sort_by_selector_v2")
            with col_sort2:
                sort_order = st.radio("排序顺序", ["降序", "升序"], horizontal=True, index=0 if not st.session_state.sort_ascending else 1, key="sort_order_radio_v2")
            
            if selected_sort != st.session_state.sort_by or (sort_order == "降序" and st.session_state.sort_ascending) or (sort_order == "升序" and not st.session_state.sort_ascending):
                st.session_state.show_dialog = False
                st.session_state.dialog_style_code = None
                st.session_state.cached_detail_data = None
                st.session_state.detail_clicked = False
                st.session_state.sort_by = selected_sort
                st.session_state.sort_ascending = (sort_order == "升序")
                st.session_state.product_page_num = 1
                st.rerun()
            
            # 应用排序
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
            
            # 分页
            page_size = 20
            total_rows = len(grouped)
            total_pages = (total_rows + page_size - 1) // page_size if total_rows > 0 else 1
            if st.session_state.product_page_num > total_pages:
                st.session_state.product_page_num = 1
            
            col_prev, col_page, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("◀ 上一页", key="product_prev_page_v2"):
                    st.session_state.show_dialog = False
                    st.session_state.dialog_style_code = None
                    st.session_state.cached_detail_data = None
                    st.session_state.detail_clicked = False
                    if st.session_state.product_page_num > 1:
                        st.session_state.product_page_num -= 1
                        st.rerun()
            with col_page:
                st.write(f"第 {st.session_state.product_page_num} / {total_pages} 页")
            with col_next:
                if st.button("下一页 ▶", key="product_next_page_v2"):
                    st.session_state.show_dialog = False
                    st.session_state.dialog_style_code = None
                    st.session_state.cached_detail_data = None
                    st.session_state.detail_clicked = False
                    if st.session_state.product_page_num < total_pages:
                        st.session_state.product_page_num += 1
                        st.rerun()
            
            start_idx = (st.session_state.product_page_num - 1) * page_size
            end_idx = min(start_idx + page_size, total_rows)
            page_df = grouped.iloc[start_idx:end_idx]
            
            # 渲染表格
            cols = st.columns([2, 0.5, 1.5, 1.2, 1.2, 1.2, 1, 1.2])
            headers = ["货号", "图片", "商品分类", "发货金额(¥)", "退货金额(¥)", "净销售金额(¥)", "退款率", "操作"]
            for col, header in zip(cols, headers):
                col.markdown(f"**{header}**")
            
            for idx, row in page_df.iterrows():
                col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 0.5, 1.5, 1.2, 1.2, 1.2, 1, 1.2])
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
                if col8.button("📊 查看详情", key=f"detail_btn_{row['货号']}_{idx}_v2"):
                    style_code = row["货号"]
                    detail_df = filtered[filtered["style_code"] == style_code].copy()
                    if not detail_df.empty:
                        suffix = st.session_state.table_suffix
                        def extract_anchor_fn(remark):
                            if not isinstance(remark, str):
                                return None
                            match = re.search(r'主播[：:]([^_]+)', remark)
                            if match:
                                return match.group(1).strip()
                            return None
                        if suffix in ["_live", "_all"]:
                            detail_df["anchor"] = detail_df["remark"].apply(extract_anchor_fn)
                            detail_df = detail_df[detail_df["anchor"].notna()]
                            if not detail_df.empty:
                                shop_detail = detail_df.groupby("anchor").agg(
                                    发货金额=("ship_amount", "sum"),
                                    退货金额=("return_amount", "sum"),
                                    净销售金额=("net_amount", "sum")
                                ).reset_index().rename(columns={"anchor": "主播"})
                                shop_detail = shop_detail.sort_values("净销售金额", ascending=False)
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
                            shop_detail = shop_detail.sort_values("净销售金额", ascending=False)
                            detail_type = "shop"
                        st.session_state.cached_detail_data = {
                            "style_code": style_code,
                            "shop_detail": shop_detail,
                            "type": detail_type
                        }
                    else:
                        st.session_state.cached_detail_data = None
                    st.session_state.dialog_style_code = style_code
                    st.session_state.show_dialog = True
                    st.session_state.detail_clicked = True
                    st.rerun()
            
            # 饼图和柱状图
            pie_metric = st.radio("饼图指标", ["净销售金额", "发货金额", "退货金额"], horizontal=True, key="pie_metric_final_v2")
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
            def safe_pie_chart(data, name_col, value_col, title, color_seq):
                total = data[value_col].sum()
                if total == 0:
                    st.info(f"{title}：无销售金额")
                    return
                if total < 0:
                    if pie_metric == "净销售金额":
                        st.warning(f"{title}：净销售总额为负（{total:.2f}），无法绘制饼图。请选择「发货金额」或「退货金额」查看分布。")
                    else:
                        st.info(f"{title}：总额为负，无法绘制饼图")
                    return
                chart_data = data[data[value_col] != 0].copy()
                if chart_data.empty:
                    st.info(f"{title}：无有效数据")
                    return
                fig = px.pie(chart_data, names=name_col, values=value_col,
                             title=title, hole=0.3, color_discrete_sequence=color_seq)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            with col1:
                if grouped["master_category"].isnull().all():
                    total_val = grouped[grouped_metric_col].sum()
                    if total_val > 0:
                        pie_data = pd.DataFrame({"master_category": ["未分类"], grouped_metric_col: [total_val]})
                        safe_pie_chart(pie_data, "master_category", grouped_metric_col, f"按分类 - {pie_metric}", px.colors.qualitative.Pastel)
                    elif total_val < 0 and pie_metric == "净销售金额":
                        st.warning(f"按分类 - {pie_metric}：净销售总额为负，无法绘制饼图。请切换指标。")
                    else:
                        st.info(f"按分类 - {pie_metric}：无销售金额")
                else:
                    pie_data = grouped.groupby("master_category")[grouped_metric_col].sum().reset_index()
                    pie_data = pie_data[pie_data["master_category"].notna()]
                    safe_pie_chart(pie_data, "master_category", grouped_metric_col, f"按分类 - {pie_metric}", px.colors.qualitative.Pastel)
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
            if "brand" in filtered.columns:
                st.subheader("📈 品牌销售分析")
                brand_metric = st.radio("品牌图表指标", ["净销售金额", "发货金额", "退货金额"], horizontal=True, key="brand_metric_final_v2")
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
            export_cols = ["货号", "master_category", "发货金额", "退货金额", "净销售金额", "退款率"]
            export_df = grouped[export_cols].copy()
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False)
            st.download_button("💾 导出分析结果", data=output.getvalue(), file_name="商品分析.xlsx")

    # 弹窗显示明细
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
                    st.dataframe(shop_detail, use_container_width=True, hide_index=True)
                else:
                    st.info("无有效数据")
            else:
                st.info("该货号无销售数据")
            if st.button("关闭", key="close_dialog_v2"):
                st.session_state.show_dialog = False
                st.session_state.dialog_style_code = None
                st.session_state.cached_detail_data = None
                st.session_state.detail_clicked = False
                st.rerun()
        show_style_detail()
