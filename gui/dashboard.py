"""
gui/dashboard.py
================
Main application dashboard. Provides a sidebar for navigation and a main content
area to load different frames (Register, Attendance, Reports, etc.).
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helper import COLORS, FONTS, center_window
from database.database import DatabaseManager

# Import the frames that will be loaded into the dashboard
from gui.register import RegisterFrame
from gui.dataset import DatasetFrame
from gui.attendance import AttendanceFrame
from gui.reports import ReportsFrame

class DashboardWindow:
    def __init__(self, root: tk.Tk, db: DatabaseManager, admin_id: int, on_logout_callback):
        self.root = root
        self.db = db
        self.admin_id = admin_id
        self.on_logout = on_logout_callback
        
        self.frames = {}
        self.current_frame = None
        self.nav_buttons = {}

        self._setup_window()
        self._build_ui()
        self._init_frames()

    def _setup_window(self) -> None:
        self.root.title("FaceAttend — Dashboard")
        self.root.configure(bg=COLORS["bg_dark"])
        center_window(self.root, 1200, 750)
        self.root.resizable(True, True)
        self.root.minsize(1000, 600)

    def _build_ui(self) -> None:
        # Sidebar
        self.sidebar = tk.Frame(self.root, bg=COLORS["bg_sidebar"], width=250)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Branding in sidebar
        brand_frame = tk.Frame(self.sidebar, bg=COLORS["bg_sidebar"])
        brand_frame.pack(fill=tk.X, pady=(30, 40))
        
        tk.Label(
            brand_frame, text="👁", font=("Helvetica", 32),
            bg=COLORS["bg_sidebar"], fg=COLORS["accent_primary"]
        ).pack()
        tk.Label(
            brand_frame, text="FaceAttend", font=FONTS["heading_lg"],
            bg=COLORS["bg_sidebar"], fg=COLORS["text_primary"]
        ).pack()

        # Navigation menu
        nav_items = [
            ("Register Student", "register"),
            ("Capture Dataset", "dataset"),
            ("Take Attendance", "attendance"),
            ("View Reports", "reports"),
        ]

        for text, key in nav_items:
            btn = tk.Button(
                self.sidebar, text=f"  {text}", font=FONTS["heading_sm"],
                bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"],
                anchor="w", padx=30, pady=12, bd=0, relief=tk.FLAT,
                cursor="hand2", command=lambda k=key: self.show_frame(k)
            )
            btn.pack(fill=tk.X)
            
            # Hover effects
            btn.bind("<Enter>", lambda e, b=btn: self._on_nav_hover(b, True))
            btn.bind("<Leave>", lambda e, b=btn: self._on_nav_hover(b, False))
            
            self.nav_buttons[key] = btn

        # Spacer
        tk.Frame(self.sidebar, bg=COLORS["bg_sidebar"]).pack(fill=tk.BOTH, expand=True)

        # Logout button
        logout_btn = tk.Button(
            self.sidebar, text="  Log Out", font=FONTS["heading_sm"],
            bg=COLORS["bg_sidebar"], fg=COLORS["accent_danger"],
            anchor="w", padx=30, pady=15, bd=0, relief=tk.FLAT,
            cursor="hand2", command=self.on_logout
        )
        logout_btn.pack(fill=tk.X, side=tk.BOTTOM)
        logout_btn.bind("<Enter>", lambda e: logout_btn.config(bg=COLORS["bg_hover"]))
        logout_btn.bind("<Leave>", lambda e: logout_btn.config(bg=COLORS["bg_sidebar"]))

        # Main Content Area
        self.content_area = tk.Frame(self.root, bg=COLORS["bg_dark"])
        self.content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _init_frames(self) -> None:
        """Initialize all functional frames and store them."""
        # We wrap each frame creation in a try-except to allow partial implementation
        try:
            self.frames["register"] = RegisterFrame(self.content_area, self.db, self.admin_id)
            self.frames["register"].place(x=0, y=0, relwidth=1, relheight=1)
        except Exception as e:
            print(f"Error loading RegisterFrame: {e}")
            
        try:
            self.frames["dataset"] = DatasetFrame(self.content_area, self.db, self.admin_id)
            self.frames["dataset"].place_forget()
        except Exception as e:
            print(f"Error loading DatasetFrame: {e}")
            
        try:
            self.frames["attendance"] = AttendanceFrame(self.content_area, self.db, self.admin_id)
            self.frames["attendance"].place_forget()
        except Exception as e:
            print(f"Error loading AttendanceFrame: {e}")
            
        try:
            self.frames["reports"] = ReportsFrame(self.content_area, self.db, self.admin_id)
            self.frames["reports"].place_forget()
        except Exception as e:
            print(f"Error loading ReportsFrame: {e}")
            
        # Default to register tab
        self.show_frame("register")

    def _on_nav_hover(self, btn: tk.Button, entering: bool) -> None:
        """Handle hover colors for sidebar buttons."""
        # Don't change color if it's the currently active tab
        is_active = False
        for key, nav_btn in self.nav_buttons.items():
            if nav_btn == btn and self.current_frame == key:
                is_active = True
                
        if not is_active:
            bg_color = COLORS["bg_hover"] if entering else COLORS["bg_sidebar"]
            fg_color = COLORS["text_primary"] if entering else COLORS["text_secondary"]
            btn.config(bg=bg_color, fg=fg_color)

    def show_frame(self, frame_key: str) -> None:
        """Switch the visible frame in the content area."""
        # Update button styles
        for key, btn in self.nav_buttons.items():
            if key == frame_key:
                btn.config(bg=COLORS["bg_hover"], fg=COLORS["accent_primary"])
            else:
                btn.config(bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"])

        # Hide all frames
        for f in self.frames.values():
            f.place_forget()

        # Show target frame
        if frame_key in self.frames:
            frame = self.frames[frame_key]
            frame.place(x=0, y=0, relwidth=1, relheight=1)
            self.current_frame = frame_key
            
            # Call refresh if the frame supports it
            if hasattr(frame, 'refresh'):
                frame.refresh()
        else:
            # Placeholder for unbuilt frames
            placeholder = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
            placeholder.place(x=0, y=0, relwidth=1, relheight=1)
            tk.Label(
                placeholder, text=f"{frame_key.capitalize()} Module\n(Coming soon...)",
                font=FONTS["heading_lg"], bg=COLORS["bg_dark"], fg=COLORS["text_secondary"]
            ).pack(expand=True)
            self.frames[frame_key] = placeholder
            self.current_frame = frame_key

if __name__ == "__main__":
    root = tk.Tk()
    db = DatabaseManager()
    db.connect()
    app = DashboardWindow(root, db, 1, root.destroy)
    root.mainloop()
    db.close()
