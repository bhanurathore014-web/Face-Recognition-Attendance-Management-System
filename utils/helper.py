"""
utils/helper.py
===============
Shared utility functions and constants used across the entire application.

Provides:
    - Color palette & font constants (design system)
    - Input validators
    - Path helpers
    - Image loading utility for Tkinter
"""

import os
import re
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from datetime import datetime

# ===========================================================================
# PROJECT PATHS
# ===========================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
TRAINED_MODEL_DIR = os.path.join(BASE_DIR, "trained_model")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
ENCODINGS_PATH = os.path.join(TRAINED_MODEL_DIR, "encodings.pkl")
LABELS_PATH = os.path.join(TRAINED_MODEL_DIR, "labels.pkl")

# Ensure directories exist at import time
for _dir in [DATASET_DIR, TRAINED_MODEL_DIR, REPORTS_DIR]:
    os.makedirs(_dir, exist_ok=True)

# ===========================================================================
# DESIGN SYSTEM — Color Palette & Fonts
# ===========================================================================
# Dark professional theme inspired by modern dashboards
COLORS = {
    # Backgrounds
    "bg_dark":       "#F0F2F5",   # Main window background (Light gray)
    "bg_card":       "#FFFFFF",   # Card / panel background (White)
    "bg_sidebar":    "#FFFFFF",   # Sidebar background (White)
    "bg_input":      "#F9FAFC",   # Input field background (Very light gray)
    "bg_hover":      "#E3F2FD",   # Hover state (Light Blue)
    "bg_table_alt":  "#FAFAFA",   # Alternating table row

    # Accents
    "accent_primary":  "#1976D2",  # Material Blue — primary actions
    "accent_secondary":"#388E3C",  # Material Green — secondary / success
    "accent_danger":   "#D32F2F",  # Red — delete / errors
    "accent_warning":  "#FBC02D",  # Yellow — warnings
    "accent_info":     "#1976D2",  # Blue — info / stats

    # Text
    "text_primary":   "#212121",  # Main text (Very dark gray)
    "text_secondary":  "#757575",  # Muted text / labels
    "text_muted":      "#BDBDBD",  # Placeholder / disabled
    "text_on_accent":  "#FFFFFF",  # Text on colored buttons

    # Borders
    "border":         "#E0E0E0",  # Subtle borders
    "border_active":  "#1976D2",  # Active/focused border
}

FONTS = {
    "heading_xl": ("Helvetica", 24, "bold"),
    "heading_lg": ("Helvetica", 18, "bold"),
    "heading_md": ("Helvetica", 14, "bold"),
    "heading_sm": ("Helvetica", 12, "bold"),
    "body":       ("Helvetica", 11),
    "body_sm":    ("Helvetica", 10),
    "mono":       ("Courier", 10),
    "caption":    ("Helvetica", 9),
}

# ===========================================================================
# INPUT VALIDATORS
# ===========================================================================

def validate_name(name: str) -> tuple[bool, str]:
    """
    Validate a person's name.
    Rules: 2-60 chars, letters and spaces only.
    Returns (is_valid, error_message).
    """
    name = name.strip()
    if len(name) < 2:
        return False, "Name must be at least 2 characters."
    if len(name) > 60:
        return False, "Name must not exceed 60 characters."
    if not re.match(r"^[A-Za-z\s\-']+$", name):
        return False, "Name can only contain letters, spaces, hyphens, and apostrophes."
    return True, ""


def validate_roll(roll: str) -> tuple[bool, str]:
    """
    Validate a roll/employee number.
    Rules: 3-20 alphanumeric chars.
    """
    roll = roll.strip()
    if len(roll) < 2:
        return False, "Roll number must be at least 2 characters."
    if len(roll) > 20:
        return False, "Roll number must not exceed 20 characters."
    if not re.match(r"^[A-Za-z0-9\-_]+$", roll):
        return False, "Roll number can only contain letters, digits, hyphens, and underscores."
    return True, ""


def validate_department(dept: str) -> tuple[bool, str]:
    """Validate department name."""
    dept = dept.strip()
    if len(dept) < 2:
        return False, "Department must be at least 2 characters."
    if len(dept) > 50:
        return False, "Department must not exceed 50 characters."
    return True, ""


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email address (optional field — empty is allowed)."""
    email = email.strip()
    if email == "":
        return True, ""  # Email is optional
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "Invalid email address format."
    return True, ""


def validate_all_student_fields(name: str, roll: str, dept: str, email: str) -> tuple[bool, str]:
    """Run all student field validators. Returns (all_valid, first_error_message)."""
    for validator, value in [
        (validate_name, name),
        (validate_roll, roll),
        (validate_department, dept),
        (validate_email, email),
    ]:
        ok, msg = validator(value)
        if not ok:
            return False, msg
    return True, ""


# ===========================================================================
# PATH HELPERS
# ===========================================================================

def get_student_dataset_path(student_id: int) -> str:
    """Return the absolute path to a student's image folder (creates it if needed)."""
    path = os.path.join(DATASET_DIR, str(student_id))
    os.makedirs(path, exist_ok=True)
    return path


def get_image_count(student_id: int) -> int:
    """Count how many face images exist for a student."""
    folder = os.path.join(DATASET_DIR, str(student_id))
    if not os.path.isdir(folder):
        return 0
    return len([f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))])


def model_is_trained() -> bool:
    """Return True if the trained model files exist."""
    return os.path.isfile(ENCODINGS_PATH) and os.path.isfile(LABELS_PATH)


# ===========================================================================
# TKINTER IMAGE LOADER
# ===========================================================================

def load_tk_image(path: str, size: tuple[int, int] | None = None) -> ImageTk.PhotoImage | None:
    """
    Load an image from `path`, optionally resize to `size=(w, h)`,
    and return a Tkinter-compatible PhotoImage.

    Returns None if the file does not exist or cannot be opened.
    """
    if not os.path.isfile(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
        if size:
            img = img.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


# ===========================================================================
# TKINTER HELPERS
# ===========================================================================

def show_error(title: str, message: str) -> None:
    """Display an error messagebox."""
    messagebox.showerror(title, message)


def show_info(title: str, message: str) -> None:
    """Display an info messagebox."""
    messagebox.showinfo(title, message)


def show_warning(title: str, message: str) -> None:
    """Display a warning messagebox."""
    messagebox.showwarning(title, message)


def ask_yes_no(title: str, message: str) -> bool:
    """Display a yes/no confirmation dialog. Returns True if user clicks Yes."""
    return messagebox.askyesno(title, message)


def center_window(window: tk.Tk | tk.Toplevel, width: int, height: int) -> None:
    """
    Center a Tk window on the screen.

    Args:
        window: The Tk or Toplevel window to center.
        width:  Desired window width in pixels.
        height: Desired window height in pixels.
    """
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


def make_rounded_button(
    parent,
    text: str,
    command,
    bg: str = None,
    fg: str = None,
    width: int = 15,
    pady: int = 8,
    font=None,
) -> tk.Button:
    """
    Create a styled flat button consistent with the design system.
    Tkinter doesn't support border-radius natively, so we simulate the premium
    feel via padx/pady, relief=FLAT, and active color changes.
    """
    bg = bg or COLORS["accent_primary"]
    fg = fg or COLORS["text_on_accent"]
    font = font or FONTS["body"]

    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        font=font,
        width=width,
        pady=pady,
        relief=tk.FLAT,
        cursor="hand2",
        activebackground=COLORS["bg_hover"],
        activeforeground=COLORS["text_primary"],
        bd=0,
    )
    return btn


def get_current_date() -> str:
    """Return today's date as YYYY-MM-DD string."""
    return datetime.now().strftime("%Y-%m-%d")


def get_current_time() -> str:
    """Return current time as HH:MM:SS string."""
    return datetime.now().strftime("%H:%M:%S")


def get_current_datetime_display() -> str:
    """Return a human-readable datetime string for display."""
    return datetime.now().strftime("%d %b %Y  %I:%M %p")
