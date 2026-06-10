with tab6:
    st.subheader("📊 商品销售分析（按货号汇总）")
    
    prod_df = load_product_sales()
    if prod_df.empty:
        st.warning("暂无商品销售数据，请先上传订单文件。")
    else:
        # 1. 按货号聚合销售金额
        grouped = prod_df.groupby("style_code").agg(
            发货金额=("ship_amount", "sum"),
            退货金额=("return_amount", "sum"),
            净销售金额=("net_amount", "sum")
        ).reset_index()
        grouped = grouped.sort_values("净销售金额", ascending=False)
        grouped.rename(columns={"style_code": "货号"}, inplace=True)
        
        # 2. 关联商品库获取图片和分类
        master_df = load_product_master()
        if not master_df.empty and "style_code" in master_df.columns:
            attr = master_df[["style_code", "image_url", "category"]].drop_duplicates(subset="style_code")
            attr.rename(columns={"style_code": "货号", "category": "master_category"}, inplace=True)
            grouped = grouped.merge(attr, on="货号", how="left")
        else:
            grouped["master_category"] = None
            grouped["image_url"] = None
        
        # 显示表格
        st.dataframe(
            grouped,
            column_config={
                "货号": st.column_config.TextColumn("货号"),
                "master_category": "商品分类",
                "发货金额": st.column_config.NumberColumn("发货金额", format="%.2f"),
                "退货金额": st.column_config.NumberColumn("退货金额", format="%.2f"),
                "净销售金额": st.column_config.NumberColumn("净销售金额", format="%.2f"),
                "image_url": st.column_config.ImageColumn("商品图片", help="点击放大")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # 指标选择器（用于所有饼图）
        pie_metric = st.radio("饼图指标", ["净销售金额", "发货金额", "退货金额"], horizontal=True)
        # 映射到实际列名
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
        
        # 1. 按商品分类（使用 grouped 中的列）
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
        
        # 2. 按年份（使用 prod_df 中的原始列）
        with col2:
            if "year" in prod_df.columns and not prod_df["year"].isnull().all():
                year_data = prod_df.groupby("year")[metric_col].sum().reset_index()
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
        
        # 3. 按季节（使用 prod_df 中的原始列）
        with col3:
            if "season" in prod_df.columns and not prod_df["season"].isnull().all():
                season_data = prod_df.groupby("season")[metric_col].sum().reset_index()
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
        
        # 柱状图（按品牌）
        if "brand" in prod_df.columns:
            brand_data = prod_df.groupby("brand")["net_amount"].sum().reset_index()
            brand_data = brand_data.sort_values("net_amount", ascending=False)
            if not brand_data.empty:
                st.subheader("📈 各品牌净销售金额")
                fig = px.bar(brand_data, x="brand", y="net_amount", title="各品牌净销售金额", color="brand")
                st.plotly_chart(fig, use_container_width=True)
        
        # 导出
        export_df = grouped.drop(columns=["image_url"])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False)
        st.download_button("💾 导出分析结果", data=output.getvalue(), file_name="商品分析.xlsx")
