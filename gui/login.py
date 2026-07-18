"""
gui/login.py
============
Admin Login Screen — the entry point of the application GUI.

Design:
    Dark glassmorphism-inspired card centered on a gradient background.
    Username: "admin"   Password: check .env for DEFAULT_ADMIN_PASSWORD  (hardcoded for Phase 5,
    will be moved to hashed DB record in Phase 14).

Tkinter Concepts Used:
    - tk.Tk()          — Root window (application entry point)
    - tk.Frame         — Container widgets for layout grouping
    - tk.Label         — Text display
    - tk.Entry         — Single-line text input (show='•' for password)
    - tk.Button        — Clickable button with command callback
    - tk.StringVar     — Tkinter-aware string variable (two-way binding)
    - window.bind()    — Bind keyboard events (Enter key → login)
    - place() / pack() — Two geometry managers used deliberately:
                         `place` for precise card positioning,
                         `pack` inside the card for vertical stacking.
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
from datetime import datetime, timedelta
import logging

security_logger = logging.getLogger('security')

# Make sure the project root is on sys.path when running this file directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import DatabaseManager
from utils.security import verify_password


from utils.helper import (
    COLORS, FONTS,
    center_window, show_error,
)

# ===========================================================================
# Admin Login Screen
# ===========================================================================

class LoginWindow:
    """
    Full-screen login window.

    After successful authentication, destroys itself and calls
    `on_success_callback` so the main application can launch the Dashboard.
    """

    def __init__(self, root: tk.Tk, on_success_callback):
        """
        Args:
            root:                The root Tk window.
            on_success_callback: Zero-argument callable invoked on successful login.
        """
        self.root = root
        self.on_success = on_success_callback
        self._setup_window()
        self._build_ui()
        self._bind_events()

    # -----------------------------------------------------------------------
    # Window configuration
    # -----------------------------------------------------------------------
    def _setup_window(self) -> None:
        self.root.title("FaceAttend — Admin Login")
        self.root.configure(bg=COLORS["bg_dark"])
        center_window(self.root, 1000, 650)
        self.root.resizable(False, False)

    # -----------------------------------------------------------------------
    # UI Construction
    # -----------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build all UI components."""
        self._build_background()
        self._build_left_panel()
        self._build_right_panel()

    def _build_background(self) -> None:
        """Full-window canvas for the gradient-like split background."""
        self.canvas = tk.Canvas(
            self.root, width=1000, height=650,
            bg=COLORS["bg_dark"], highlightthickness=0
        )
        self.canvas.place(x=0, y=0)

        # Left decorative half — slightly lighter accent
        self.canvas.create_rectangle(0, 0, 480, 650, fill="#13152A", outline="")

        # Decorative circles (glassmorphism feel)
        self.canvas.create_oval(-60, -60, 220, 220,
                                fill=COLORS["accent_primary"], outline="", stipple="gray25")
        self.canvas.create_oval(300, 400, 520, 620,
                                fill=COLORS["accent_secondary"], outline="", stipple="gray25")

        # Divider line
        self.canvas.create_line(480, 40, 480, 610,
                                fill=COLORS["border"], width=1)

    def _build_left_panel(self) -> None:
        """Left branding panel — app logo and tagline."""
        # App icon placeholder (emoji used since no image asset yet)
        self.canvas.create_text(
            240, 200,
            text="👁",
            font=("Helvetica", 64),
            fill=COLORS["accent_primary"],
            anchor="center",
        )
        self.canvas.create_text(
            240, 285,
            text="FaceAttend",
            font=FONTS["heading_xl"],
            fill=COLORS["text_primary"],
            anchor="center",
        )
        self.canvas.create_text(
            240, 320,
            text="AI-Powered Attendance System",
            font=FONTS["body"],
            fill=COLORS["text_secondary"],
            anchor="center",
        )
        # Feature bullets
        features = [
            "✓  Real-time face recognition",
            "✓  Automatic attendance marking",
            "✓  Detailed analytics & reports",
        ]
        for i, feat in enumerate(features):
            self.canvas.create_text(
                240, 375 + i * 28,
                text=feat,
                font=FONTS["body_sm"],
                fill=COLORS["text_secondary"],
                anchor="center",
            )

    def _build_right_panel(self) -> None:
        """Right panel — the login form card."""
        # Card frame
        card = tk.Frame(self.root, bg=COLORS["bg_card"], bd=0)
        card.place(x=530, y=100, width=400, height=440)

        # Heading
        tk.Label(
            card, text="Welcome Back",
            font=FONTS["heading_lg"],
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
        ).pack(pady=(40, 4))

        tk.Label(
            card, text="Sign in to your admin account",
            font=FONTS["body_sm"],
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
        ).pack(pady=(0, 30))

        # ── Username field ──────────────────────────────────────────────
        self._build_input_field(card, "Username", show=None)
        self.username_var = tk.StringVar()
        self.username_entry = self._last_entry
        self.username_entry.configure(textvariable=self.username_var)

        # ── Password field ──────────────────────────────────────────────
        self._build_input_field(card, "Password", show="•")
        self.password_var = tk.StringVar()
        self.password_entry = self._last_entry
        self.password_entry.configure(textvariable=self.password_var)

        # ── Error message label (hidden by default) ─────────────────────
        self.error_var = tk.StringVar()
        self.error_label = tk.Label(
            card,
            textvariable=self.error_var,
            font=FONTS["caption"],
            bg=COLORS["bg_card"],
            fg=COLORS["accent_danger"],
        )
        self.error_label.pack(pady=(4, 0))

        # ── Login button ────────────────────────────────────────────────
        login_btn = tk.Button(
            card,
            text="  Sign In  ",
            font=FONTS["heading_sm"],
            bg=COLORS["accent_primary"],
            fg=COLORS["text_on_accent"],
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#5851DB",
            activeforeground=COLORS["text_on_accent"],
            bd=0,
            pady=10,
            command=self._attempt_login,
        )
        login_btn.pack(fill=tk.X, padx=40, pady=(16, 0))

        # Hover effects
        login_btn.bind("<Enter>", lambda e: login_btn.config(bg="#5851DB"))
        login_btn.bind("<Leave>", lambda e: login_btn.config(bg=COLORS["accent_primary"]))

        # ── Footer hint ─────────────────────────────────────────────────
        tk.Label(
            card,
            text='Default: admin / admin123',
            font=FONTS["caption"],
            bg=COLORS["bg_card"],
            fg=COLORS["text_muted"],
        ).pack(pady=(20, 0))

    def _build_input_field(self, parent, label_text: str, show=None) -> None:
        """
        Helper: build a labeled input field with custom styling.
        Stores the created Entry widget in `self._last_entry`.
        """
        tk.Label(
            parent,
            text=label_text,
            font=FONTS["body_sm"],
            bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill=tk.X, padx=40, pady=(0, 4))

        entry = tk.Entry(
            parent,
            font=FONTS["body"],
            bg=COLORS["bg_input"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],  # cursor color
            relief=tk.FLAT,
            bd=0,
            show=show,
        )
        entry.pack(fill=tk.X, padx=40, ipady=10, pady=(0, 16))

        # Bottom border line to simulate Material-style underline
        sep = tk.Frame(parent, bg=COLORS["border"], height=1)
        sep.pack(fill=tk.X, padx=40, pady=(0, 4))

        # Focus highlight: change border color on focus
        entry.bind("<FocusIn>",  lambda e, s=sep: s.config(bg=COLORS["accent_primary"]))
        entry.bind("<FocusOut>", lambda e, s=sep: s.config(bg=COLORS["border"]))

        self._last_entry = entry

    # -----------------------------------------------------------------------
    # Event Bindings
    # -----------------------------------------------------------------------
    def _bind_events(self) -> None:
        """Bind Enter key to the login action."""
        self.root.bind("<Return>", lambda e: self._attempt_login())

    # -----------------------------------------------------------------------
    # Authentication Logic
    def _attempt_login(self) -> None:
        """Validate credentials against DB and handle rate limiting."""
        username = self.username_var.get().strip()
        password = self.password_var.get()

        if not username:
            self.error_var.set("⚠  Username is required.")
            return
        if not password:
            self.error_var.set("⚠  Password is required.")
            return

        db = DatabaseManager()
        admin = db.get_admin_by_username(username)

        if not admin:
            security_logger.warning(f"Failed login attempt for unknown user: '{username}'")
            self.error_var.set("⚠  Invalid username or password.")
            self.password_entry.delete(0, tk.END)
            self.password_entry.focus_set()
            return

        # Check rate limiting
        if admin["locked_until"]:
            locked_until = datetime.fromisoformat(admin["locked_until"])
            if datetime.now() < locked_until:
                remaining = (locked_until - datetime.now()).seconds // 60
                security_logger.warning(f"Blocked login attempt for locked account: '{username}'")
                self.error_var.set(f"⚠  Account locked. Try again in {remaining + 1}m.")
                return
            else:
                # Lock expired, reset
                db.update_admin_login_status(username, 0, None)
                admin["failed_attempts"] = 0

        # Verify password
        if verify_password(password, admin["password_hash"]):
            self.error_var.set("")
            db.update_admin_login_status(username, 0, None)
            security_logger.warning(f"Successful login for user: '{username}'")
            self.on_success(admin["id"])
        else:
            attempts = admin["failed_attempts"] + 1
            if attempts >= 5:
                lock_time = datetime.now() + timedelta(minutes=15)
                db.update_admin_login_status(username, attempts, lock_time.isoformat())
                security_logger.warning(f"Account locked due to multiple failed attempts: '{username}'")
                self.error_var.set("⚠  Account locked for 15 minutes.")
            else:
                db.update_admin_login_status(username, attempts, None)
                security_logger.warning(f"Failed login attempt for user: '{username}' (Attempt {attempts}/5)")
                self.error_var.set(f"⚠  Invalid password. Attempts left: {5 - attempts}")
            
            self.password_entry.delete(0, tk.END)
            self.password_entry.focus_set()

# ===========================================================================
# Standalone test
# ===========================================================================
if __name__ == "__main__":
    def on_login():
        print("Login successful!")
        root.destroy()

    root = tk.Tk()
    app = LoginWindow(root, on_login)
    root.mainloop()
