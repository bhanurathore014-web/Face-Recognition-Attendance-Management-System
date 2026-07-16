"""
gui/reports.py
==============
Reports and Analytics Screen.

Features:
    - View attendance records in a tabular format (Treeview).
    - Filter by Date, Department, or view all.
    - Export current view to CSV using Pandas.
    - Basic statistics display (Total Present).
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helper import COLORS, FONTS, REPORTS_DIR, show_info, show_error, get_current_date
from database.database import DatabaseManager
from utils.csv_export import export_attendance_to_csv

class ReportsFrame(tk.Frame):
    def __init__(self, parent, db: DatabaseManager, admin_id: int):
        super().__init__(parent, bg=COLORS["bg_dark"])
        self.db = db
        self.admin_id = admin_id
        
        self.current_data = []
        self.last_export_time = 0.0
        
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        # Page heading
        heading_bar = tk.Frame(self, bg=COLORS["bg_dark"])
        heading_bar.pack(fill=tk.X, padx=20, pady=(20, 10))

        tk.Label(
            heading_bar, text="Attendance Reports",
            font=FONTS["heading_lg"], bg=COLORS["bg_dark"], fg=COLORS["text_primary"]
        ).pack(side=tk.LEFT)

        # Filters Bar
        filter_bar = tk.Frame(self, bg=COLORS["bg_card"], padx=16, pady=16)
        filter_bar.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        # Date Filter
        tk.Label(
            filter_bar, text="Date (YYYY-MM-DD):",
            font=FONTS["body_sm"], bg=COLORS["bg_card"], fg=COLORS["text_secondary"]
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.date_var = tk.StringVar(value=get_current_date())
        self.date_entry = tk.Entry(
            filter_bar, textvariable=self.date_var, font=FONTS["body"],
            bg=COLORS["bg_input"], fg=COLORS["text_primary"], insertbackground=COLORS["text_primary"],
            relief=tk.FLAT, width=15
        )
        self.date_entry.pack(side=tk.LEFT, ipady=4, padx=(0, 20))
        
        # Department Filter
        tk.Label(
            filter_bar, text="Department:",
            font=FONTS["body_sm"], bg=COLORS["bg_card"], fg=COLORS["text_secondary"]
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.dept_var = tk.StringVar(value="All")
        self.dept_combo = ttk.Combobox(
            filter_bar, textvariable=self.dept_var, state="readonly",
            font=FONTS["body"], width=20
        )
        self.dept_combo.pack(side=tk.LEFT, padx=(0, 30))
        
        # Filter Button
        self.btn_filter = tk.Button(
            filter_bar, text="🔍 Apply Filter", font=FONTS["body_sm"],
            bg=COLORS["accent_primary"], fg=COLORS["text_on_accent"], relief=tk.FLAT,
            padx=15, cursor="hand2", command=self._apply_filter
        )
        self.btn_filter.pack(side=tk.LEFT)
        
        # Export Button
        self.btn_export = tk.Button(
            filter_bar, text="📥 Export CSV", font=FONTS["body_sm"],
            bg=COLORS["accent_secondary"], fg=COLORS["text_on_accent"], relief=tk.FLAT,
            padx=15, cursor="hand2", command=self._export_csv
        )
        self.btn_export.pack(side=tk.RIGHT)
        
        # Stats Bar
        self.stats_var = tk.StringVar(value="Total Records: 0")
        tk.Label(
            self, textvariable=self.stats_var,
            font=FONTS["heading_sm"], bg=COLORS["bg_dark"], fg=COLORS["accent_info"]
        ).pack(anchor="w", padx=20, pady=(0, 10))
        
        # Table (Treeview)
        table_frame = tk.Frame(self, bg=COLORS["bg_card"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Report.Treeview",
            background=COLORS["bg_card"], foreground=COLORS["text_primary"],
            fieldbackground=COLORS["bg_card"], rowheight=30, font=FONTS["body_sm"]
        )
        style.configure(
            "Report.Treeview.Heading",
            background=COLORS["bg_sidebar"], foreground=COLORS["accent_primary"],
            font=FONTS["heading_sm"], relief="flat"
        )
        style.map("Report.Treeview", background=[("selected", COLORS["accent_primary"])])

        columns = ("ID", "Name", "Roll", "Department", "Date", "Time", "Status")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            style="Report.Treeview", selectmode="none"
        )

        col_widths = {"ID": 50, "Name": 180, "Roll": 100, "Department": 150, "Date": 100, "Time": 100, "Status": 100}
        for col in columns:
            self.tree.heading(col, text=col, anchor="w")
            self.tree.column(col, width=col_widths[col], anchor="w")

        v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
    def refresh(self) -> None:
        """Called when tab is opened."""
        # Update departments dropdown
        depts = self.db.get_departments(self.admin_id)
        self.dept_combo.config(values=["All"] + depts)
        self._apply_filter()

    def _apply_filter(self) -> None:
        date_filter = self.date_var.get().strip()
        dept_filter = self.dept_var.get().strip()
        
        if date_filter and dept_filter != "All":
            # Filter by both (we have to do this in python since DB manager doesn't have a specific query)
            all_dept = self.db.get_attendance_by_department(dept_filter, self.admin_id)
            self.current_data = [d for d in all_dept if d["date"] == date_filter]
        elif date_filter:
            self.current_data = self.db.get_attendance_by_date(date_filter, self.admin_id)
        elif dept_filter != "All":
            self.current_data = self.db.get_attendance_by_department(dept_filter, self.admin_id)
        else:
            self.current_data = self.db.get_all_attendance(self.admin_id)
            
        self._populate_table()

    def _populate_table(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        for i, row in enumerate(self.current_data):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", tk.END, values=(
                row["attendance_id"], row["name"], row.get("roll", "N/A"),
                row.get("department", "N/A"), row["date"], row["time"], row["status"]
            ), tags=(tag,))
            
        self.tree.tag_configure("odd", background=COLORS["bg_table_alt"])
        self.stats_var.set(f"Total Records: {len(self.current_data)}")

    def _export_csv(self) -> None:
        current_time = time.time()
        if current_time - self.last_export_time < 5.0:
            show_error("Rate Limit", "Please wait 5 seconds between exports.")
            return

        if not self.current_data:
            show_error("Export Error", "No data to export.")
            return
            
        success, result = export_attendance_to_csv(self.current_data, REPORTS_DIR)
        if success:
            self.last_export_time = time.time()
            show_info("Export Successful", f"CSV file saved to:\n{result}")
        else:
            show_error("Export Failed", result)
