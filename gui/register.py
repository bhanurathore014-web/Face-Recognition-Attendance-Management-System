"""
gui/register.py
===============
Student Registration Screen.

Features:
    - Input form: Name, Roll No., Department, Email
    - Real-time field validation with inline error messages
    - Duplicate roll number check against SQLite
    - On success: saves to DB, creates dataset folder, shows next steps
    - Integrated as a Frame so it can be embedded in the Dashboard

Tkinter Concepts Used:
    - tk.Frame        — embedded panel (no separate window)
    - tk.StringVar    — form field binding
    - ttk.Combobox    — department dropdown
    - tk.Scrollbar    — in the student list Treeview
    - ttk.Treeview    — tabular student list
    - tk.PhotoImage   — (future: student photo thumbnail)
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
import shutil
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helper import (
    COLORS, FONTS,
    validate_all_student_fields,
    get_student_dataset_path,
    show_error, show_info, ask_yes_no,
)
from database.database import DatabaseManager


# Pre-defined department list (user can type a custom value too)
DEPARTMENTS = [
    "Computer Science", "Information Technology", "Electronics",
    "Mechanical", "Civil", "Electrical", "MBA", "MCA",
    "Data Science", "Artificial Intelligence",
]


class RegisterFrame(tk.Frame):
    """
    Student registration panel.

    Embed this inside the Dashboard's content area by calling:
        frame = RegisterFrame(parent, db)
        frame.pack(fill=tk.BOTH, expand=True)
    """

    def __init__(self, parent, db: DatabaseManager, admin_id: int):
        super().__init__(parent, bg=COLORS["bg_dark"])
        self.db = db
        self.admin_id = admin_id
        self.last_register_time = 0.0
        self._build_ui()
        self._load_student_list()

    # -----------------------------------------------------------------------
    # Layout: left = form, right = student list
    # -----------------------------------------------------------------------
    def _build_ui(self) -> None:
        # Page heading
        heading_bar = tk.Frame(self, bg=COLORS["bg_dark"])
        heading_bar.pack(fill=tk.X, padx=20, pady=(20, 0))

        tk.Label(
            heading_bar, text="Student Registration",
            font=FONTS["heading_lg"],
            bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
        ).pack(side=tk.LEFT)

        # Main content split
        content = tk.Frame(self, bg=COLORS["bg_dark"])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self._build_form(content)
        self._build_student_list(content)

    # -----------------------------------------------------------------------
    # Left: Registration Form
    # -----------------------------------------------------------------------
    def _build_form(self, parent) -> None:
        """Build the registration form card."""
        form_card = tk.Frame(parent, bg=COLORS["bg_card"], padx=28, pady=28)
        form_card.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        tk.Label(
            form_card, text="Register New Student",
            font=FONTS["heading_md"],
            bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
        ).pack(anchor="w", pady=(0, 20))

        # Form fields spec: (label, variable_name, is_combobox)
        fields = [
            ("Full Name *",     "name_var",   False),
            ("Roll Number *",   "roll_var",   False),
            ("Department *",    "dept_var",   True),
            ("Email Address",   "email_var",  False),
        ]
        self.entries: dict[str, tk.Entry | ttk.Combobox] = {}

        for label_text, var_name, is_combo in fields:
            # Label
            tk.Label(
                form_card, text=label_text,
                font=FONTS["body_sm"],
                bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                anchor="w",
            ).pack(fill=tk.X, pady=(0, 4))

            # String variable
            var = tk.StringVar()
            setattr(self, var_name, var)

            if is_combo:
                widget = ttk.Combobox(
                    form_card, textvariable=var,
                    values=DEPARTMENTS,
                    font=FONTS["body"],
                    width=28,
                    state="normal",  # allow custom input
                )
                widget.set(DEPARTMENTS[0])
            else:
                widget = tk.Entry(
                    form_card,
                    textvariable=var,
                    font=FONTS["body"],
                    bg=COLORS["bg_input"],
                    fg=COLORS["text_primary"],
                    insertbackground=COLORS["text_primary"],
                    relief=tk.FLAT,
                    width=30,
                )
                self._style_entry(form_card, widget)

            widget.pack(fill=tk.X, ipady=8, pady=(0, 14))
            self.entries[var_name] = widget

        # Inline error label
        self.error_var = tk.StringVar()
        tk.Label(
            form_card,
            textvariable=self.error_var,
            font=FONTS["caption"],
            bg=COLORS["bg_card"],
            fg=COLORS["accent_danger"],
            wraplength=280,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))

        # Buttons row
        btn_row = tk.Frame(form_card, bg=COLORS["bg_card"])
        btn_row.pack(fill=tk.X, pady=(4, 0))

        self._make_btn(btn_row, "💾  Register", self._on_register,
                       COLORS["accent_primary"]).pack(side=tk.LEFT, padx=(0, 10))
        self._make_btn(btn_row, "🗑  Clear", self._clear_form,
                       COLORS["bg_input"]).pack(side=tk.LEFT)

    def _style_entry(self, parent, entry: tk.Entry) -> None:
        """Add bottom-border focus effect to a plain Entry widget."""
        sep = tk.Frame(parent, bg=COLORS["border"], height=1)
        sep.pack(fill=tk.X, pady=(0, 0))
        entry.bind("<FocusIn>",  lambda e: sep.config(bg=COLORS["accent_primary"]))
        entry.bind("<FocusOut>", lambda e: sep.config(bg=COLORS["border"]))

    def _make_btn(self, parent, text: str, cmd, bg: str) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=cmd,
            font=FONTS["body_sm"],
            bg=bg, fg=COLORS["text_primary"],
            relief=tk.FLAT, cursor="hand2",
            activebackground=COLORS["bg_hover"],
            activeforeground=COLORS["text_primary"],
            padx=14, pady=8,
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=COLORS["bg_hover"]))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    # -----------------------------------------------------------------------
    # Right: Student List (Treeview)
    # -----------------------------------------------------------------------
    def _build_student_list(self, parent) -> None:
        """Build the scrollable student table on the right side."""
        list_card = tk.Frame(parent, bg=COLORS["bg_card"])
        list_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Header bar
        header = tk.Frame(list_card, bg=COLORS["bg_card"], pady=12)
        header.pack(fill=tk.X, padx=16)

        tk.Label(
            header, text="Registered Students",
            font=FONTS["heading_md"],
            bg=COLORS["bg_card"], fg=COLORS["accent_secondary"],
        ).pack(side=tk.LEFT)

        # Search bar
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        search_entry = tk.Entry(
            header,
            textvariable=self.search_var,
            font=FONTS["body_sm"],
            bg=COLORS["bg_input"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            relief=tk.FLAT,
            width=20,
        )
        search_entry.pack(side=tk.RIGHT, ipady=6, padx=(0, 4))
        tk.Label(
            header, text="🔍",
            font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_muted"],
        ).pack(side=tk.RIGHT)

        # Treeview style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Custom.Treeview",
            background=COLORS["bg_card"],
            foreground=COLORS["text_primary"],
            fieldbackground=COLORS["bg_card"],
            rowheight=30,
            font=FONTS["body_sm"],
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=COLORS["bg_sidebar"],
            foreground=COLORS["accent_primary"],
            font=FONTS["heading_sm"],
            relief="flat",
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", COLORS["accent_primary"])],
            foreground=[("selected", COLORS["text_on_accent"])],
        )

        columns = ("ID", "Name", "Roll", "Department", "Email", "Images")
        self.tree = ttk.Treeview(
            list_card,
            columns=columns,
            show="headings",
            style="Custom.Treeview",
            selectmode="browse",
        )

        col_widths = {"ID": 40, "Name": 150, "Roll": 80,
                      "Department": 130, "Email": 160, "Images": 60}
        for col in columns:
            self.tree.heading(col, text=col, anchor="w")
            self.tree.column(col, width=col_widths[col], anchor="w")

        # Scrollbars
        v_scroll = ttk.Scrollbar(list_card, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(list_card, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0), pady=(0, 0))
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X, padx=16)

        # Right-click context menu
        self.context_menu = tk.Menu(self.tree, tearoff=0,
                                    bg=COLORS["bg_card"], fg=COLORS["text_primary"])
        self.context_menu.add_command(label="🗑  Delete Student", command=self._on_delete)
        self.tree.bind("<Button-3>", self._show_context_menu)   # right-click
        self.tree.bind("<Button-2>", self._show_context_menu)   # macOS two-finger

        # Status bar
        self.status_var = tk.StringVar(value="Loading students…")
        tk.Label(
            list_card,
            textvariable=self.status_var,
            font=FONTS["caption"],
            bg=COLORS["bg_card"],
            fg=COLORS["text_muted"],
            anchor="w",
            padx=16,
            pady=6,
        ).pack(fill=tk.X, side=tk.BOTTOM)

    # -----------------------------------------------------------------------
    # Data Operations
    # -----------------------------------------------------------------------
    def _load_student_list(self, keyword: str = "") -> None:
        """Refresh the Treeview with students from the database."""
        for row in self.tree.get_children():
            self.tree.delete(row)

        if keyword:
            students = self.db.search_students(keyword, self.admin_id)
        else:
            students = self.db.get_all_students(self.admin_id)

        for i, s in enumerate(students):
            from utils.helper import get_image_count
            img_count = get_image_count(s["id"])
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", tk.END, values=(
                s["id"], s["name"], s["roll"],
                s["department"], s["email"] or "—", img_count,
            ), tags=(tag,))

        self.tree.tag_configure("odd", background=COLORS["bg_table_alt"])
        total = self.db.get_total_students(self.admin_id)
        self.status_var.set(f"Showing {len(students)} of {total} students")

    def _on_search(self) -> None:
        self._load_student_list(self.search_var.get().strip())

    # -----------------------------------------------------------------------
    # Form Actions
    # -----------------------------------------------------------------------
    def _on_register(self) -> None:
        """Validate inputs, insert into DB, create dataset folder."""
        name  = self.name_var.get().strip()
        roll  = self.roll_var.get().strip().upper()
        dept  = self.dept_var.get().strip()
        email = self.email_var.get().strip()

        # --- Rate Limiting (Debounce) ---
        current_time = time.time()
        if current_time - self.last_register_time < 3.0:
            self.error_var.set("⚠  Please wait 3 seconds before registering again.")
            return

        # --- Validate ---
        ok, msg = validate_all_student_fields(name, roll, dept, email)
        if not ok:
            self.error_var.set(f"⚠  {msg}")
            return

        # --- Duplicate check ---
        if self.db.get_student_by_roll(roll, self.admin_id):
            self.error_var.set(f"⚠  Roll number '{roll}' is already registered.")
            return

        # --- Insert ---
        try:
            student_id = self.db.insert_student(self.admin_id, name, roll, dept, email)
        except Exception as e:
            self.error_var.set(f"⚠  Database error: {e}")
            return

        # --- Create dataset folder ---
        folder = get_student_dataset_path(student_id)
        self.db.update_student_paths(student_id, self.admin_id, folder, "")

        self.last_register_time = time.time()
        
        self.error_var.set("")
        self._clear_form()
        self._load_student_list()
        show_info(
            "Registration Successful",
            f"✅ {name} registered successfully!\n\n"
            f"Student ID : {student_id}\n"
            f"Roll No.   : {roll}\n"
            f"Department : {dept}\n\n"
            f"Next Step → Go to 'Capture Images' to collect face dataset."
        )

    def _clear_form(self) -> None:
        """Reset all form fields."""
        self.name_var.set("")
        self.roll_var.set("")
        self.dept_var.set(DEPARTMENTS[0])
        self.email_var.set("")
        self.error_var.set("")

    def _on_delete(self) -> None:
        """Delete the selected student after confirmation."""
        selected = self.tree.selection()
        if not selected:
            show_error("No Selection", "Please select a student to delete.")
            return

        values = self.tree.item(selected[0])["values"]
        student_id, name = int(values[0]), values[1]

        if not ask_yes_no(
            "Confirm Delete",
            f"Delete '{name}' (ID: {student_id})?\n\n"
            "This will permanently remove the student, their attendance records, "
            "and their face image dataset.",
        ):
            return

        # Delete dataset folder
        from utils.helper import DATASET_DIR
        folder = os.path.join(DATASET_DIR, str(student_id))
        if os.path.isdir(folder):
            shutil.rmtree(folder)

        self.db.delete_student(student_id, self.admin_id)
        self._load_student_list()
        show_info("Deleted", f"'{name}' has been removed.")

    def _show_context_menu(self, event) -> None:
        """Show right-click context menu over the Treeview."""
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.context_menu.post(event.x_root, event.y_root)

    def refresh(self) -> None:
        """Called by Dashboard when this tab becomes active."""
        self._load_student_list()


# ===========================================================================
# Standalone test
# ===========================================================================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Register Test")
    root.configure(bg=COLORS["bg_dark"])
    root.geometry("1100x700")

    db = DatabaseManager()
    db.connect()

    frame = RegisterFrame(root, db, 1)
    frame.pack(fill=tk.BOTH, expand=True)
    root.mainloop()
    db.close()
