with tab6:
    st.subheader("📊 商品销售分析（按品牌+产品）")
    prod_df = load_product_sales()
    
    # ===== 调试信息（部署后可删除）=====
    st.write(f"商品数据行数: {len(prod_df)}")
    st.write(f"列名: {list(prod_df.columns)}")
    # ================================
    
    if prod_df.empty:
        st.warning("暂无商品销售数据，请先上传订单文件。")
    else:
        # 确保 brand 列存在且非空
        if "brand" not in prod_df.columns or prod_df["brand"].isnull().all():
            prod_df["brand"] = prod_df["product_code"].str[0]
        else:
            prod_df["brand"] = prod_df["brand"].fillna(prod_df["product_code"].str[0])
        
        # 确保 style_code 列存在（货号）
        if "style_code" not in prod_df.columns:
            prod_df["style_code"] = prod_df["product_code"].str[:8]
        else:
            prod_df["style_code"] = prod_df["style_code"].fillna(prod_df["product_code"].str[:8])
        
        # 确保图片和分类列存在，若不存在则创建空列
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
        
        # 再次检查过滤后是否为空
        if filtered.empty:
            st.warning("所选条件下无销售数据")
        else:
            # 按品牌、货号、主分类、图片聚合
            grouped = filtered.groupby(["brand", "style_code", "master_category", "image_url"]).agg(
                发货金额=("ship_amount", "sum"),
                退货金额=("return_amount", "sum"),
                净销售金额=("net_amount", "sum")
            ).reset_index()
            grouped = grouped.sort_values("净销售金额", ascending=False)
            grouped.rename(columns={"style_code": "货号"}, inplace=True)
            
            # 显示表格（含图片列）
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
            # 导出（去掉图片列）
            export_df = grouped.drop(columns=["image_url"])
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False)
            st.download_button("💾 导出分析结果", data=output.getvalue(), file_name="商品分析.xlsx")
