# -*- coding: utf-8 -*-
"""
订单业绩统计工具 - 专业版
支持拖拽/选择订单文件，自动汇总每日及累计业绩，对接目标达成率
"""

import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json

# 尝试导入拖拽支持库
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    print("提示：若要使用拖拽功能，请安装 tkinterdnd2：pip install tkinterdnd2")

CONFIG_FILE = "target_config.json"

class SalesAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("业绩统计工具 | 含目标达成")
        self.root.geometry("1150x720")
        self.root.minsize(1000, 600)

        # 设置全局样式
        self.setup_styles()

        # 数据存储
        self.df_daily_latest = None
        self.df_monthly_actual = None
        self.df_monthly_with_target = None
        self.df_ship_refund = None
        self.target_dict = {}
        self.target_file_path = None

        self.create_widgets()
        self.load_auto_target()

    def setup_styles(self):
        """配置ttk样式，打造现代界面"""
        style = ttk.Style()
        # 使用clam主题作为基础（更现代）
        style.theme_use('clam')
        
        # 主色调
        primary = "#2c7da0"
        primary_light = "#61a5c2"
        secondary = "#89c2d9"
        bg_color = "#f5f7fa"
        fg_color = "#2c3e50"
        
        # 配置根窗口背景
        self.root.configure(bg=bg_color)
        
        # 顶部框架样式
        style.configure("Top.TFrame", background=bg_color)
        style.configure("Action.TButton", font=("Segoe UI", 10), padding=(12, 4))
        style.map("Action.TButton",
                  background=[("active", primary_light), ("pressed", primary)],
                  foreground=[("active", "white"), ("pressed", "white")])
        
        # 常规按钮
        style.configure("Normal.TButton", font=("Segoe UI", 10), padding=(8, 4))
        
        # Notebook (选项卡) 样式
        style.configure("TNotebook", background=bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[12, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", primary), ("active", primary_light)],
                  foreground=[("selected", "white"), ("active", "white")])
        
        # Treeview 表格样式
        style.configure("Treeview",
                        font=("Segoe UI", 9),
                        rowheight=28,
                        background="white",
                        fieldbackground="white",
                        foreground=fg_color,
                        borderwidth=1,
                        relief="solid")
        style.map("Treeview",
                  background=[("selected", primary_light)],
                  foreground=[("selected", "white")])
        style.configure("Treeview.Heading",
                        font=("Segoe UI", 10, "bold"),
                        background=primary,
                        foreground="white",
                        relief="flat",
                        borderwidth=0)
        style.map("Treeview.Heading",
                  background=[("active", primary_light)])
        
        # 状态栏
        style.configure("Status.TLabel", font=("Segoe UI", 9), background=bg_color, foreground=fg_color)

    def create_widgets(self):
        # 主容器
        main_container = ttk.Frame(self.root, style="Top.TFrame")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 15))

        # ----- 标题栏 -----
        title_frame = ttk.Frame(main_container, style="Top.TFrame")
        title_frame.pack(fill=tk.X, pady=(0, 12))
        title_label = tk.Label(title_frame, text="📊 店铺业绩汇总分析", font=("Segoe UI", 16, "bold"),
                               fg="#2c7da0", bg="#f5f7fa")
        title_label.pack(side=tk.LEFT)
        version_label = tk.Label(title_frame, text="v2.0", font=("Segoe UI", 9), fg="#7f8c8d", bg="#f5f7fa")
        version_label.pack(side=tk.LEFT, padx=(10, 0))

        # ----- 操作栏 -----
        action_frame = ttk.Frame(main_container, style="Top.TFrame")
        action_frame.pack(fill=tk.X, pady=(0, 15))

        # 左侧按钮组
        left_btn_frame = ttk.Frame(action_frame, style="Top.TFrame")
        left_btn_frame.pack(side=tk.LEFT)

        if DND_AVAILABLE:
            self.drop_label = tk.Label(
                left_btn_frame,
                text="📂 拖拽订单文件至此区域",
                bg="#e9ecef",
                fg="#2c3e50",
                font=("Segoe UI", 10),
                width=28,
                height=2,
                relief=tk.RIDGE,
                bd=1
            )
            self.drop_label.pack(side=tk.LEFT, padx=(0, 15))
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self.on_drop)

        btn_order = ttk.Button(left_btn_frame, text="📁 选择订单文件", command=self.select_order_file,
                               style="Action.TButton")
        btn_order.pack(side=tk.LEFT, padx=5)
        
        btn_target = ttk.Button(left_btn_frame, text="🎯 加载目标文件", command=self.load_target_file,
                                style="Action.TButton")
        btn_target.pack(side=tk.LEFT, padx=5)
        
        btn_clear = ttk.Button(left_btn_frame, text="🗑️ 清除目标记忆", command=self.clear_target_memory,
                               style="Normal.TButton")
        btn_clear.pack(side=tk.LEFT, padx=5)
        
        btn_template = ttk.Button(left_btn_frame, text="📄 下载目标模板", command=self.download_target_template,
                                  style="Normal.TButton")
        btn_template.pack(side=tk.LEFT, padx=5)

        # 右侧按钮组
        right_btn_frame = ttk.Frame(action_frame, style="Top.TFrame")
        right_btn_frame.pack(side=tk.RIGHT)
        
        # 日期查询区域
        query_frame = ttk.Frame(right_btn_frame, style="Top.TFrame")
        query_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        query_label = tk.Label(query_frame, text="📅 查询日期:", font=("Segoe UI", 10),
                               fg="#2c3e50", bg="#f5f7fa")
        query_label.pack(side=tk.LEFT)
        
        # 使用DateEntry日期选择器组件
        try:
            from tkcalendar import DateEntry
            self.query_date_picker = DateEntry(query_frame, width=12, background='#2c7da0',
                                               foreground='white', borderwidth=2,
                                               date_pattern='yyyy-mm-dd',
                                               font=("Segoe UI", 10))
            self.query_date_picker.pack(side=tk.LEFT, padx=(5, 5))
            self.use_date_picker = True
        except ImportError:
            # 如果tkcalendar未安装，使用普通输入框
            self.query_date_var = tk.StringVar()
            self.query_date_entry = tk.Entry(query_frame, textvariable=self.query_date_var,
                                             font=("Segoe UI", 10), width=12)
            self.query_date_entry.pack(side=tk.LEFT, padx=(5, 5))
            self.query_date_entry.insert(0, "YYYY-MM-DD")
            self.use_date_picker = False
        
        btn_query = ttk.Button(query_frame, text="🔍 查询", command=self.query_date_performance,
                               style="Action.TButton")
        btn_query.pack(side=tk.LEFT)
        
        btn_export = ttk.Button(right_btn_frame, text="💾 导出当前表", command=self.export_current,
                                style="Action.TButton")
        btn_export.pack(side=tk.LEFT)

        # ----- 选项卡区域 -----
        notebook_frame = ttk.Frame(main_container)
        notebook_frame.pack(fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 每日明细页
        self.daily_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.daily_frame, text="📅 最新日明细")
        self.daily_tree = self.create_treeview(self.daily_frame)
        # 日期范围累计页
        self.monthly_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.monthly_frame, text="🏪 日期范围累计")
        
        # 在月累计页添加日期范围选择
        range_frame = ttk.Frame(self.monthly_frame, style="Top.TFrame")
        range_frame.pack(fill=tk.X, padx=5, pady=5)
        
        range_label = tk.Label(range_frame, text="📅 日期范围:", font=("Segoe UI", 10),
                               fg="#2c3e50", bg="#f5f7fa")
        range_label.pack(side=tk.LEFT)
        
        # 开始日期选择器
        start_label = tk.Label(range_frame, text="开始:", font=("Segoe UI", 9),
                               fg="#2c3e50", bg="#f5f7fa")
        start_label.pack(side=tk.LEFT, padx=(10, 2))
        
        if self.use_date_picker:
            self.start_date_picker = DateEntry(range_frame, width=10, background='#2c7da0',
                                               foreground='white', borderwidth=2,
                                               date_pattern='yyyy-mm-dd',
                                               font=("Segoe UI", 9))
            self.start_date_picker.pack(side=tk.LEFT, padx=(0, 10))
            
            end_label = tk.Label(range_frame, text="结束:", font=("Segoe UI", 9),
                                 fg="#2c3e50", bg="#f5f7fa")
            end_label.pack(side=tk.LEFT, padx=(5, 2))
            
            self.end_date_picker = DateEntry(range_frame, width=10, background='#2c7da0',
                                             foreground='white', borderwidth=2,
                                             date_pattern='yyyy-mm-dd',
                                             font=("Segoe UI", 9))
            self.end_date_picker.pack(side=tk.LEFT, padx=(0, 10))
        else:
            self.start_date_var = tk.StringVar()
            self.start_date_entry = tk.Entry(range_frame, textvariable=self.start_date_var,
                                             font=("Segoe UI", 9), width=10)
            self.start_date_entry.pack(side=tk.LEFT, padx=(0, 10))
            self.start_date_entry.insert(0, "开始日期")
            
            end_label = tk.Label(range_frame, text="结束:", font=("Segoe UI", 9),
                                 fg="#2c3e50", bg="#f5f7fa")
            end_label.pack(side=tk.LEFT, padx=(5, 2))
            
            self.end_date_var = tk.StringVar()
            self.end_date_entry = tk.Entry(range_frame, textvariable=self.end_date_var,
                                           font=("Segoe UI", 9), width=10)
            self.end_date_entry.pack(side=tk.LEFT, padx=(0, 10))
            self.end_date_entry.insert(0, "结束日期")
        
        # 默认当前月按钮
        btn_current_month = ttk.Button(range_frame, text="📅 默认当前月", 
                                       command=self.set_current_month_range,
                                       style="Normal.TButton")
        btn_current_month.pack(side=tk.LEFT, padx=(5, 5))
        
        # 计算累计按钮
        btn_calc_range = ttk.Button(range_frame, text="🔍 计算累计", 
                                    command=self.calculate_range_summary,
                                    style="Action.TButton")
        btn_calc_range.pack(side=tk.LEFT, padx=(5, 0))
        
        self.monthly_tree = self.create_treeview(self.monthly_frame)

        # 日期查询结果页
        self.query_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.query_frame, text="🔍 日期查询")
        self.query_tree = self.create_treeview(self.query_frame)

        # 发货退货明细页
        self.ship_refund_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ship_refund_frame, text="📦 发货退货明细")
        self.ship_refund_tree = self.create_treeview(self.ship_refund_frame)

        # ----- 状态栏 -----
        status_bar = tk.Label(self.root, text="就绪", anchor=tk.W, font=("Segoe UI", 9),
                              fg="#6c757d", bg="#e9ecef", relief=tk.FLAT, padx=8, pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar.config(textvariable=self.status_var)

    def create_treeview(self, parent):
        """创建带滚动条和斑马纹的表格"""
        frame = tk.Frame(parent, bg="#f5f7fa")
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 滚动条
        scroll_y = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
        tree = ttk.Treeview(frame,
                            yscrollcommand=scroll_y.set,
                            xscrollcommand=scroll_x.set,
                            show="headings",
                            selectmode="browse")
        scroll_y.config(command=tree.yview)
        scroll_x.config(command=tree.xview)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 斑马纹 (通过tag)
        tree.tag_configure('oddrow', background='#f8f9fa')
        tree.tag_configure('evenrow', background='white')
        
        return tree

    def refresh_treeview_with_data(self, tree, data, columns, col_widths=None):
        """通用表格刷新函数，支持斑马纹"""
        # 金额列（右对齐+千分位）
        amount_cols_set = {'当日金额', '月累计金额', '累计金额', '目标金额', '当日发货', '月累计发货', '当日退货', '月累计退货'}
        # 清空
        for row in tree.get_children():
            tree.delete(row)
        # 设置列
        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col)
            width = col_widths.get(col, 140) if col_widths else 140
            anchor = "e" if col in amount_cols_set else "center"
            tree.column(col, width=width, anchor=anchor)
        # 插入数据，交替颜色
        for idx, row in data.iterrows():
            values = []
            for col in columns:
                val = row[col]
                if col in ["日期"] and hasattr(val, "strftime"):
                    val = val.strftime("%Y-%m-%d")
                elif col in amount_cols_set and isinstance(val, (int, float)):
                    val = f"{val:,.0f}"
                elif isinstance(val, float):
                    val = f"{val:.2f}"
                values.append(val)
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            tree.insert("", tk.END, values=values, tags=(tag,))
        
        # 添加平台合计行（在所有店铺数据之后）
        if not data.empty and '店铺名称' in columns:
            # 找出所有金额列
            amount_cols = [col for col in columns if col in ('当日金额', '月累计金额', '累计金额', '当日发货', '月累计发货', '当日退货', '月累计退货')]
            
            if amount_cols:
                # 计算各平台各金额列的合计
                douyin_data = data[data['店铺名称'].str.contains('抖音', case=False)]
                video_data = data[data['店铺名称'].str.contains('视频号', case=False)]
                
                # 添加空行分隔
                tree.insert("", tk.END, values=[""] * len(columns))
                
                # 构建合计行数据
                def build_summary_row(label, subset_data):
                    row = [""] * len(columns)
                    row[columns.index('店铺名称')] = label
                    for ac in amount_cols:
                        total = subset_data[ac].sum() if not subset_data.empty else 0
                        row[columns.index(ac)] = f"{total:,.0f}"
                    # 目标金额合计（累加）
                    if '目标金额' in columns and not subset_data.empty:
                        target_total = pd.to_numeric(subset_data['目标金额'].replace('-', 0), errors='coerce').sum()
                        row[columns.index('目标金额')] = f"{target_total:,.0f}"
                    # 达成率（基于合计后的月累计金额和目标金额计算）
                    if '达成率' in columns and '月累计金额' in columns:
                        total_amount = subset_data['月累计金额'].sum() if not subset_data.empty else 0
                        total_target = pd.to_numeric(subset_data['目标金额'].replace('-', 0), errors='coerce').sum() if '目标金额' in columns and not subset_data.empty else 0
                        if total_target > 0:
                            row[columns.index('达成率')] = f"{(total_amount / total_target) * 100:.2f}%"
                        else:
                            row[columns.index('达成率')] = "-"
                    return row
                
                # 抖音合计
                tree.insert("", tk.END, values=build_summary_row("📱 抖音合计", douyin_data))
                # 视频号合计
                tree.insert("", tk.END, values=build_summary_row("📺 视频号合计", video_data))
                # 空行
                tree.insert("", tk.END, values=[""] * len(columns))
                # 总业绩合计
                tree.insert("", tk.END, values=build_summary_row("📊 总业绩合计", data))

    # ---------- 功能方法（与之前相同，仅调用新的表格刷新） ----------
    def on_drop(self, event):
        file_path = event.data.strip('{}').strip()
        if file_path and os.path.isfile(file_path):
            self.process_order_file(file_path)
        else:
            self.status_var.set("无效文件，请拖拽正确的Excel文件")

    def select_order_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if path:
            self.process_order_file(path)

    def process_order_file(self, file_path):
        try:
            self.status_var.set(f"正在读取: {os.path.basename(file_path)}...")
            self.root.update()

            df = pd.read_excel(file_path, header=1)
            required = ["日期", "金额/时间", "备注"]
            for col in required:
                if col not in df.columns:
                    raise ValueError(f"表格缺少列: {col}")

            df["日期"] = pd.to_datetime(df["日期"])
            df["店铺名称"] = df["备注"].astype(str).str.split("_").str[-1]
            # 去掉店铺名称中的"商店:"前缀（兼容全角/半角冒号）
            df["店铺名称"] = df["店铺名称"].str.replace(r'^\s*商店[：:]', '', regex=True)
            df = df[df["店铺名称"].notna() & (df["店铺名称"] != "")].copy()
            if df.empty:
                raise ValueError("未提取到有效的店铺名称")

            df["金额/时间"] = pd.to_numeric(df["金额/时间"], errors="coerce")
            df = df.dropna(subset=["金额/时间"])

            daily = df.groupby(["日期", "店铺名称"])["金额/时间"].sum().reset_index()
            daily = daily.sort_values(["店铺名称", "日期"])
            daily["月累计金额"] = daily.groupby("店铺名称")["金额/时间"].cumsum().round(2)
            daily["当日金额"] = daily["金额/时间"].round(2)

            # 保存所有日期的数据，用于查询功能
            self.df_all_daily = daily[["日期", "店铺名称", "当日金额", "月累计金额"]].copy()

            latest_date = daily["日期"].max()
            # 获取所有店铺的最新月累计（取每个店铺最后一条记录的月累计）
            latest_cumulative = daily.groupby("店铺名称").last().reset_index()[["店铺名称", "月累计金额"]]
            # 获取最新日有业绩的店铺
            daily_latest = daily[daily["日期"] == latest_date][["日期", "店铺名称", "当日金额"]]
            # 合并：所有店铺都有记录，无日业绩的显示当日金额=0
            daily_latest = pd.merge(latest_cumulative, daily_latest, on='店铺名称', how='left')
            daily_latest['当日金额'] = daily_latest['当日金额'].fillna(0).round(2)
            daily_latest['日期'] = daily_latest['日期'].fillna(latest_date)
            daily_latest = daily_latest[["日期", "店铺名称", "当日金额", "月累计金额"]]
            self.df_daily_latest = daily_latest

            monthly_actual = df.groupby("店铺名称")["金额/时间"].sum().reset_index()
            monthly_actual["月累计金额"] = monthly_actual["金额/时间"].round(2)
            monthly_actual = monthly_actual.sort_values("店铺名称")
            self.df_monthly_actual = monthly_actual[["店铺名称", "月累计金额"]]

            self.refresh_daily_view()
            self.merge_and_refresh_monthly()

            # === 处理发货退货金额 ===
            # 正数=发货，负数=退货（取绝对值）
            df['发货金额'] = df['金额/时间'].clip(lower=0)
            df['退货金额'] = df['金额/时间'].clip(upper=0).abs()

            # 按日期+店铺汇总发货和退货
            ship_refund_daily = df.groupby(["日期", "店铺名称"])[["发货金额", "退货金额"]].sum().reset_index()
            ship_refund_daily = ship_refund_daily.sort_values(["店铺名称", "日期"])
            ship_refund_daily["月累计发货"] = ship_refund_daily.groupby("店铺名称")["发货金额"].cumsum().round(2)
            ship_refund_daily["月累计退货"] = ship_refund_daily.groupby("店铺名称")["退货金额"].cumsum().round(2)
            ship_refund_daily["当日发货"] = ship_refund_daily["发货金额"].round(2)
            ship_refund_daily["当日退货"] = ship_refund_daily["退货金额"].round(2)

            # 最新日发货退货（取每个店铺最新一条记录的月累计）
            latest_ship_cum = ship_refund_daily.groupby("店铺名称").last().reset_index()[["店铺名称", "月累计发货", "月累计退货"]]
            latest_ship = ship_refund_daily[ship_refund_daily["日期"] == latest_date][["日期", "店铺名称", "当日发货", "当日退货"]]
            latest_ship_refund = pd.merge(latest_ship_cum, latest_ship, on='店铺名称', how='left')
            latest_ship_refund['当日发货'] = latest_ship_refund['当日发货'].fillna(0).round(2)
            latest_ship_refund['当日退货'] = latest_ship_refund['当日退货'].fillna(0).round(2)
            latest_ship_refund['日期'] = latest_ship_refund['日期'].fillna(latest_date)
            self.df_ship_refund = latest_ship_refund[["日期", "店铺名称", "当日发货", "月累计发货", "当日退货", "月累计退货"]]

            self.refresh_ship_refund_view()

            date_str = latest_date.strftime("%Y-%m-%d")
            self.status_var.set(f"处理完成！最新日期：{date_str}，共 {len(daily_latest)} 个店铺有当日数据")
        except Exception as e:
            messagebox.showerror("错误", f"处理订单文件失败：\n{e}")
            self.status_var.set("处理失败")

    def save_config(self, target_path):
        config = {"target_file": target_path if target_path and os.path.exists(target_path) else ""}
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except:
            pass

    def load_auto_target(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            path = config.get("target_file", "")
            if path and os.path.isfile(path):
                self.load_target_file_from_path(path, silent=True)
            else:
                if path:
                    self.save_config("")
                    self.status_var.set("上次目标文件已失效，请重新加载")
        except:
            pass

    def load_target_file(self):
        path = filedialog.askopenfilename(title="选择目标Excel", filetypes=[("Excel files", "*.xlsx *.xls")])
        if path:
            self.load_target_file_from_path(path, silent=False)

    def download_target_template(self):
        """下载目标文件模板（两列示例：店铺名称、目标金额）"""
        save_path = filedialog.asksaveasfilename(
            title="保存目标模板",
            defaultextension=".xlsx",
            initialfile="目标模板.xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not save_path:
            return
        try:
            template = pd.DataFrame({
                "店铺名称": ["示例店铺A", "示例店铺B"],
                "目标金额": [100000, 200000]
            })
            template.to_excel(save_path, index=False)
            self.status_var.set(f"模板已保存至：{save_path}")
            messagebox.showinfo("成功", f"目标模板已保存至：\n{save_path}\n\n请按示例格式填入店铺名称和月目标金额后，点击「🎯 加载目标文件」导入。")
        except Exception as e:
            messagebox.showerror("失败", f"模板保存失败：\n{e}")

    def load_target_file_from_path(self, file_path, silent=False):
        try:
            df_target = pd.read_excel(file_path, header=None)
            first_cell = str(df_target.iloc[0, 0]) if len(df_target) > 0 else ""
            if "月目标" in first_cell or "目标" in first_cell:
                df_target = df_target.iloc[1:].reset_index(drop=True)
            if df_target.shape[1] < 2:
                raise ValueError("目标文件需要两列：店铺名称、目标金额")

            shop_names = df_target.iloc[:, 0].astype(str).str.strip()
            target_vals = pd.to_numeric(df_target.iloc[:, 1], errors='coerce')
            self.target_dict = {}
            for name, val in zip(shop_names, target_vals):
                if pd.notna(val) and name not in ["", "nan", "None"]:
                    self.target_dict[name] = val

            self.target_file_path = file_path
            self.save_config(file_path)
            if not silent:
                messagebox.showinfo("成功", f"已加载 {len(self.target_dict)} 个店铺的目标数据")
            self.status_var.set(f"目标已加载：{os.path.basename(file_path)}，{len(self.target_dict)} 个店铺")
            if self.df_monthly_actual is not None:
                self.merge_and_refresh_monthly()
            if self.df_daily_latest is not None:
                self.refresh_daily_view()
        except Exception as e:
            if not silent:
                messagebox.showerror("错误", f"加载目标文件失败：\n{e}")
            self.save_config("")
            self.target_dict = {}
            self.target_file_path = None
            if self.df_monthly_actual is not None:
                self.merge_and_refresh_monthly()
            if self.df_daily_latest is not None:
                self.refresh_daily_view()

    def refresh_ship_refund_view(self):
        """刷新发货退货明细"""
        if self.df_ship_refund is None or self.df_ship_refund.empty:
            return
        cols = ["日期", "店铺名称", "当日发货", "月累计发货", "当日退货", "月累计退货"]
        col_widths = {"日期": 110, "店铺名称": 200, "当日发货": 120, "月累计发货": 120, "当日退货": 120, "月累计退货": 120}
        self.refresh_treeview_with_data(self.ship_refund_tree, self.df_ship_refund, cols, col_widths)

    def clear_target_memory(self):
        self.save_config("")
        self.target_dict = {}
        self.target_file_path = None
        self.status_var.set("已清除目标记忆")
        if self.df_monthly_actual is not None:
            self.merge_and_refresh_monthly()
        else:
            self.refresh_monthly_no_target()
        if self.df_daily_latest is not None:
            self.refresh_daily_view()

    def refresh_daily_view(self):
        if self.df_daily_latest is None or self.df_daily_latest.empty:
            return
        df = self.df_daily_latest.copy()
        # 添加月目标和达成率
        df["目标金额"] = df["店铺名称"].map(self.target_dict).fillna(0).round(2)
        def calc_rate(row):
            actual = row["月累计金额"]
            target = row["目标金额"]
            if target == 0 or pd.isna(target):
                return "-"
            return f"{(actual / target) * 100:.2f}%"
        df["达成率"] = df.apply(calc_rate, axis=1)
        
        cols = ["日期", "店铺名称", "当日金额", "月累计金额", "目标金额", "达成率"]
        col_widths = {"日期": 110, "店铺名称": 200, "当日金额": 120, "月累计金额": 120, "目标金额": 120, "达成率": 100}
        self.refresh_treeview_with_data(self.daily_tree, df, cols, col_widths)

    def merge_and_refresh_monthly(self):
        if self.df_monthly_actual is None:
            return
        merged = self.df_monthly_actual.copy()
        merged["目标金额"] = merged["店铺名称"].map(self.target_dict).fillna(0).round(2)
        def calc_rate(row):
            actual = row["月累计金额"]
            target = row["目标金额"]
            if target == 0 or pd.isna(target):
                return "-"
            return f"{(actual / target) * 100:.2f}%"
        merged["达成率"] = merged.apply(calc_rate, axis=1)
        merged = merged.sort_values("店铺名称")
        self.df_monthly_with_target = merged
        self.refresh_monthly_with_target()

    def refresh_monthly_with_target(self):
        if self.df_monthly_with_target is None or self.df_monthly_with_target.empty:
            return
        cols = ["店铺名称", "月累计金额", "目标金额", "达成率"]
        col_widths = {"店铺名称": 200, "月累计金额": 120, "目标金额": 120, "达成率": 100}
        self.refresh_treeview_with_data(self.monthly_tree, self.df_monthly_with_target, cols, col_widths)

    def refresh_monthly_no_target(self):
        if self.df_monthly_actual is None or self.df_monthly_actual.empty:
            return
        cols = ["店铺名称", "月累计金额"]
        col_widths = {"店铺名称": 250, "月累计金额": 150}
        self.refresh_treeview_with_data(self.monthly_tree, self.df_monthly_actual, cols, col_widths)

    def set_current_month_range(self):
        """设置日期范围为当前月"""
        from datetime import datetime, date
        today = date.today()
        first_day = date(today.year, today.month, 1)
        
        if self.use_date_picker:
            self.start_date_picker.set_date(first_day)
            self.end_date_picker.set_date(today)
        else:
            self.start_date_var.set(first_day.strftime("%Y-%m-%d"))
            self.end_date_var.set(today.strftime("%Y-%m-%d"))
        
        self.status_var.set(f"已设置当前月日期范围：{first_day} 至 {today}")

    def calculate_range_summary(self):
        """计算指定日期范围的累计业绩"""
        if not hasattr(self, 'df_all_daily') or self.df_all_daily is None or self.df_all_daily.empty:
            messagebox.showwarning("无数据", "请先处理订单文件")
            return
        
        # 获取日期范围
        if self.use_date_picker:
            start_date = self.start_date_picker.get_date()
            end_date = self.end_date_picker.get_date()
            start_date_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, 'strftime') else str(start_date)
            end_date_str = end_date.strftime("%Y-%m-%d") if hasattr(end_date, 'strftime') else str(end_date)
        else:
            start_date_str = self.start_date_var.get().strip()
            end_date_str = self.end_date_var.get().strip()
            if not start_date_str or start_date_str == "开始日期" or not end_date_str or end_date_str == "结束日期":
                messagebox.showwarning("输入错误", "请选择开始和结束日期")
                return
        
        try:
            start_date = pd.to_datetime(start_date_str)
            end_date = pd.to_datetime(end_date_str)
        except:
            messagebox.showwarning("输入错误", "日期格式不正确")
            return
        
        if start_date > end_date:
            messagebox.showwarning("输入错误", "开始日期不能晚于结束日期")
            return
        
        try:
            self.status_var.set(f"正在计算 {start_date_str} 至 {end_date_str} 的累计业绩...")
            self.root.update()
            
            # 筛选日期范围内的数据
            mask = (self.df_all_daily["日期"] >= start_date) & (self.df_all_daily["日期"] <= end_date)
            range_data = self.df_all_daily[mask].copy()
            
            if range_data.empty:
                messagebox.showinfo("查询结果", f"{start_date_str} 至 {end_date_str} 没有业绩数据")
                self.status_var.set(f"{start_date_str} 至 {end_date_str} 无业绩数据")
                return
            
            # 按店铺汇总
            range_summary = range_data.groupby("店铺名称")["当日金额"].sum().reset_index()
            range_summary["累计金额"] = range_summary["当日金额"].round(2)
            range_summary = range_summary.sort_values("店铺名称")
            
            # 显示结果
            cols = ["店铺名称", "累计金额"]
            col_widths = {"店铺名称": 250, "累计金额": 150}
            self.refresh_treeview_with_data(self.monthly_tree, range_summary, cols, col_widths)
            
            self.status_var.set(f"计算完成！{start_date_str} 至 {end_date_str} 共 {len(range_summary)} 个店铺")
            
        except Exception as e:
            messagebox.showerror("计算失败", f"计算日期范围累计失败：\n{e}")
            self.status_var.set("计算失败")

    def query_date_performance(self):
        """查询指定日期的业绩"""
        if self.df_daily_latest is None or self.df_daily_latest.empty:
            messagebox.showwarning("无数据", "请先处理订单文件")
            return
        
        # 获取日期
        if self.use_date_picker:
            query_date = self.query_date_picker.get_date()
            query_date_str = query_date.strftime("%Y-%m-%d") if hasattr(query_date, 'strftime') else str(query_date)
            query_date = pd.to_datetime(query_date)
        else:
            query_date_str = self.query_date_var.get().strip()
            if not query_date_str or query_date_str == "YYYY-MM-DD":
                messagebox.showwarning("输入错误", "请输入有效的日期格式（YYYY-MM-DD）")
                return
            try:
                query_date = pd.to_datetime(query_date_str)
            except:
                messagebox.showwarning("输入错误", "日期格式不正确，请使用 YYYY-MM-DD 格式")
                return
        
        try:
            self.status_var.set(f"正在查询 {query_date_str} 的业绩...")
            self.root.update()
            
            # 从原始数据中查询指定日期的业绩
            # 需要重新读取数据或从已处理的数据中筛选
            if hasattr(self, 'df_all_daily') and self.df_all_daily is not None:
                query_result = self.df_all_daily[self.df_all_daily["日期"] == query_date].copy()
            else:
                messagebox.showwarning("无数据", "无法查询历史数据，请重新处理订单文件")
                return
            
            if query_result.empty:
                messagebox.showinfo("查询结果", f"{query_date_str} 没有业绩数据")
                self.status_var.set(f"{query_date_str} 无业绩数据")
                return
            
            # 准备显示数据
            query_result = query_result.sort_values("店铺名称")
            query_result["当日金额"] = query_result["当日金额"].round(2)
            query_result["月累计金额"] = query_result["月累计金额"].round(2)
            
            # 切换到查询结果页并显示
            self.notebook.select(self.query_frame)
            cols = ["日期", "店铺名称", "当日金额", "月累计金额"]
            col_widths = {"日期": 110, "店铺名称": 200, "当日金额": 120, "月累计金额": 120}
            self.refresh_treeview_with_data(self.query_tree, query_result, cols, col_widths)
            
            self.status_var.set(f"查询完成！{query_date_str} 共 {len(query_result)} 个店铺有数据")
            
        except Exception as e:
            messagebox.showerror("查询失败", f"查询日期业绩失败：\n{e}")
            self.status_var.set("查询失败")

    def export_current(self):
        cur = self.notebook.index(self.notebook.select())
        df = None
        default_name = ""
        
        if cur == 0:
            # 最新日明细
            df = self.df_daily_latest
            default_name = "最新日明细.xlsx"
        elif cur == 1:
            # 日期范围累计
            # 获取当前显示的数据（包含合计行）
            tree = self.monthly_tree
            columns = tree["columns"]
            if columns:
                data = []
                for child in tree.get_children():
                    values = tree.item(child)["values"]
                    data.append(values)
                df = pd.DataFrame(data, columns=columns)
            default_name = "日期范围累计.xlsx"
        elif cur == 2:
            # 日期查询
            # 获取当前显示的数据（包含合计行）
            tree = self.query_tree
            columns = tree["columns"]
            if columns:
                data = []
                for child in tree.get_children():
                    values = tree.item(child)["values"]
                    data.append(values)
                df = pd.DataFrame(data, columns=columns)
            default_name = "日期查询结果.xlsx"
        
        if df is None or df.empty:
            messagebox.showwarning("无数据", "请先处理订单文件")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=default_name)
        if save_path:
            try:
                df.to_excel(save_path, index=False)
                # 自动打开文件
                os.startfile(save_path)
                messagebox.showinfo("成功", f"已保存并打开：{save_path}")
            except Exception as e:
                messagebox.showerror("导出失败", str(e))

if __name__ == "__main__":
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = SalesAnalyzer(root)
    root.mainloop()