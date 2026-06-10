with tab6:
    st.subheader("📊 商品销售分析（按货号汇总）")
    
    # 可选：临时清除缓存（调试用，部署后可删除）
    # st.cache_data.clear()
    
    prod_df = load_product_sales()
    if prod_df.empty:
        st.warning("暂无商品销售数据，请先上传订单文件。")
    else:
        # 清洗销售表中的 style_code（去除空格、转大写）
        if "style_code" in prod_df.columns:
            prod_df["style_code"] = prod_df["style_code"].astype(str).str.strip().str.upper()
        else:
            prod_df["style_code"] = prod_df["product_code"].str[:8].str.strip().str.upper()
        
        # 日期筛选
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
            # 新增：货号筛选（多个货号用英文逗号分隔）
            st.subheader("🔍 筛选条件")
            col_filters = st.columns([2, 1, 1])
            with col_filters[0]:
                style_codes_input = st.text_input(
                    "按货号筛选（多个请用英文逗号分隔）",
                    placeholder="例如: L262Y050, G262Y030",
                    key="style_code_filter"
                )
            # 品牌筛选器（移到此处，与货号筛选同行更紧凑，也可以单独一行，这里作为演示）
            brands = ["全部"] + sorted(filtered["brand"].dropna().unique())
            with col_filters[1]:
                selected_brand = st.selectbox("品牌", brands, key="brand_filter")
            with col_filters[2]:
                # 可以加一个清空按钮或占位
                st.markdown("")  # 占位保持布局
            
            # 处理货号筛选
            if style_codes_input.strip():
                # 按逗号分割，去除空格，转大写
                target_codes = [code.strip().upper() for code in style_codes_input.split(",") if code.strip()]
                if target_codes:
                    filtered = filtered[filtered["style_code"].isin(target_codes)]
            
            # 品牌筛选
            if selected_brand != "全部":
                filtered = filtered[filtered["brand"] == selected_brand]
            
            if filtered.empty:
                st.warning("所选条件下无销售数据")
            else:
                # 按货号聚合销售金额
                grouped = filtered.groupby("style_code").agg(
                    发货金额=("ship_amount", "sum"),
                    退货金额=("return_amount", "sum"),
                    净销售金额=("net_amount", "sum")
                ).reset_index()
                grouped = grouped.sort_values("净销售金额", ascending=False)
                grouped.rename(columns={"style_code": "货号"}, inplace=True)
                
                # 加载商品库并清洗 style_code
                master_df = load_product_master()
                if not master_df.empty and "style_code" in master_df.columns:
                    master_df["style_code"] = master_df["style_code"].astype(str).str.strip().str.upper()
                    master_df = master_df.drop_duplicates(subset="style_code", keep="first")
                    attr = master_df[["style_code", "image_url", "category"]].copy()
                    attr.rename(columns={"style_code": "货号", "category": "master_category"}, inplace=True)
                    grouped = grouped.merge(attr, on="货号", how="left")
                else:
                    grouped["master_category"] = None
                    grouped["image_url"] = None
                
                # 调整列顺序：货号 → 图片 → 商品分类 → 发货金额 → 退货金额 → 净销售金额
                col_order = ["货号", "image_url", "master_category", "发货金额", "退货金额", "净销售金额"]
                grouped = grouped[col_order]
                
                # 显示表格
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
                
                # 饼图指标选择器
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
                
                # 按商品分类
                with col1:
                    if not grouped["master_category"].isnull().all():
                        pie_data = grouped.groupby("master_category")[grouped_metric_col].sum().reset_index()
                        pie_data = pie_data[pie_data["master_category"].notna()]
                        if not pie_data.empty:
                            fig = px.pie(pie_data, names="master_category", values=grouped_metric_col, 
                                         title=f"按分类 - {pie_metric}", hole=0.3,
                                         color_discrete_sequence=px.colors.qualitative.Pastel)
                            fig.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("无分类数据")
                    else:
                        st.info("无分类数据")
                
                # 按年份
                with col2:
                    if "year" in filtered.columns and not filtered["year"].isnull().all():
                        year_data = filtered.groupby("year")[metric_col].sum().reset_index()
                        year_data = year_data[year_data["year"].notna()]
                        if not year_data.empty:
                            fig = px.pie(year_data, names="year", values=metric_col, 
                                         title=f"按年份 - {pie_metric}", hole=0.3,
                                         color_discrete_sequence=px.colors.qualitative.Set2)
                            fig.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("无年份数据")
                    else:
                        st.info("无年份数据")
                
                # 按季节
                with col3:
                    if "season" in filtered.columns and not filtered["season"].isnull().all():
                        season_data = filtered.groupby("season")[metric_col].sum().reset_index()
                        season_data = season_data[season_data["season"].notna()]
                        if not season_data.empty:
                            fig = px.pie(season_data, names="season", values=metric_col, 
                                         title=f"按季节 - {pie_metric}", hole=0.3,
                                         color_discrete_sequence=px.colors.qualitative.Set1)
                            fig.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("无季节数据")
                    else:
                        st.info("无季节数据")
                
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
                
                # 导出
                export_cols = ["货号", "master_category", "发货金额", "退货金额", "净销售金额"]
                export_df = grouped[export_cols].copy()
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False)
                st.download_button("💾 导出分析结果", data=output.getvalue(), file_name="商品分析.xlsx")
