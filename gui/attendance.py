"""
gui/attendance.py
=================
Real-Time Attendance Screen.

Features:
    - Live webcam feed with bounding boxes drawn over detected faces.
    - Green box + Name for recognized students.
    - Red box + "Unknown" for unrecognized faces.
    - Automatically logs attendance into the database (with duplicate prevention).
    - Sidebar list showing today's attendance logs in real time.
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helper import COLORS, FONTS, show_error, get_current_date, get_current_time
from database.database import DatabaseManager
from utils.camera import CameraManager
from models.recognizer import FaceRecognizer

class AttendanceFrame(tk.Frame):
    def __init__(self, parent, db: DatabaseManager, admin_id: int):
        super().__init__(parent, bg=COLORS["bg_dark"])
        self.db = db
        self.admin_id = admin_id
        self.camera = CameraManager()
        self.recognizer = FaceRecognizer()
        
        self.is_running = False
        self.video_loop_id = None
        self.today_date = get_current_date()
        
        # We cache student details to avoid hitting the DB every frame
        # Dict: student_id -> {"name": str, "roll": str}
        self.student_cache = {}
        
        # We also cache who we've marked today in memory so we don't spam the DB
        # Set of student_ids marked today
        self.marked_today = set()
        
        self._build_ui()

    def _build_ui(self) -> None:
        heading_bar = tk.Frame(self, bg=COLORS["bg_dark"])
        heading_bar.pack(fill=tk.X, padx=20, pady=(20, 10))

        tk.Label(
            heading_bar, text="Live Attendance",
            font=FONTS["heading_lg"], bg=COLORS["bg_dark"], fg=COLORS["text_primary"]
        ).pack(side=tk.LEFT)
        
        # Status Label (top right)
        self.status_var = tk.StringVar(value="Camera Offline")
        self.status_label = tk.Label(
            heading_bar, textvariable=self.status_var,
            font=FONTS["heading_sm"], bg=COLORS["bg_dark"], fg=COLORS["text_secondary"]
        )
        self.status_label.pack(side=tk.RIGHT)

        # Main Layout: Left (Camera), Right (Log)
        main_content = tk.Frame(self, bg=COLORS["bg_dark"])
        main_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # ─── LEFT: CAMERA FEED ────────────────────────────────────────────
        left_panel = tk.Frame(main_content, bg=COLORS["bg_dark"])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))
        
        # Control Buttons
        btn_bar = tk.Frame(left_panel, bg=COLORS["bg_dark"])
        btn_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_start = tk.Button(
            btn_bar, text="▶ Start Session", font=FONTS["heading_sm"],
            bg=COLORS["accent_primary"], fg=COLORS["text_on_accent"], relief=tk.FLAT,
            padx=20, pady=10, cursor="hand2", command=self._toggle_session
        )
        self.btn_start.pack(side=tk.LEFT)
        
        # Camera Canvas
        self.camera_frame = tk.Frame(left_panel, bg="#000000", bd=2, relief=tk.FLAT)
        self.camera_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.camera_frame, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        
        self.placeholder_text = self.canvas.create_text(
            320, 240, text="Click 'Start Session'\nto begin attendance",
            font=FONTS["heading_md"], fill=COLORS["text_muted"], justify=tk.CENTER
        )
        
        self.canvas_width = 640
        self.canvas_height = 480
        
        # ─── RIGHT: ATTENDANCE LOG ────────────────────────────────────────
        right_panel = tk.Frame(main_content, bg=COLORS["bg_card"], width=350)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False) # Keep width fixed
        
        log_header = tk.Frame(right_panel, bg=COLORS["bg_card"])
        log_header.pack(fill=tk.X, padx=16, pady=16)
        
        tk.Label(
            log_header, text="Today's Log",
            font=FONTS["heading_md"], bg=COLORS["bg_card"], fg=COLORS["accent_secondary"]
        ).pack(side=tk.LEFT)
        
        self.count_var = tk.StringVar(value="0 Present")
        tk.Label(
            log_header, textvariable=self.count_var,
            font=FONTS["body_sm"], bg=COLORS["bg_card"], fg=COLORS["text_secondary"]
        ).pack(side=tk.RIGHT)
        
        # Log Listbox
        self.log_list = tk.Listbox(
            right_panel, bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=FONTS["body"], bd=0, highlightthickness=0, selectbackground=COLORS["bg_hover"]
        )
        self.log_list.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        
        scrollbar = ttk.Scrollbar(self.log_list, orient="vertical", command=self.log_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_list.config(yscrollcommand=scrollbar.set)

    # -----------------------------------------------------------------------
    # Setup and State
    # -----------------------------------------------------------------------
    def refresh(self) -> None:
        """Called when switching to this tab."""
        self._load_cache()
        self._load_todays_log()
        # Ensure recognizer is loaded (in case we just trained it in Dataset tab)
        if not self.recognizer.is_loaded:
            self.recognizer.load_models()
            
    def _load_cache(self) -> None:
        """Pre-load student details and today's marked list to RAM."""
        students = self.db.get_all_students(self.admin_id)
        self.student_cache = {s["id"]: {"name": s["name"], "roll": s["roll"]} for s in students}
        
        self.today_date = get_current_date()
        attendance = self.db.get_attendance_by_date(self.today_date, self.admin_id)
        self.marked_today = {a["student_id"] for a in attendance}

    def _load_todays_log(self) -> None:
        """Update the right-side listbox."""
        self.log_list.delete(0, tk.END)
        attendance = self.db.get_attendance_by_date(self.today_date, self.admin_id)
        
        for record in attendance:
            # e.g., "09:30 AM - Alice Smith (CS001)"
            display_str = f"[{record['time']}] {record['name']} ({record['roll']})"
            self.log_list.insert(tk.END, display_str)
            
        # Scroll to bottom
        self.log_list.yview(tk.END)
        self.count_var.set(f"{len(attendance)} Present")

    def _on_canvas_resize(self, event):
        self.canvas_width = event.width
        self.canvas_height = event.height
        if not self.is_running:
            self.canvas.coords(self.placeholder_text, self.canvas_width/2, self.canvas_height/2)

    # -----------------------------------------------------------------------
    # Camera & Session Controls
    # -----------------------------------------------------------------------
    def _toggle_session(self) -> None:
        if not self.is_running:
            if not self.recognizer.is_loaded:
                show_error("Model Error", "No trained model found. Please train the model first.")
                return
                
            if self.camera.start():
                self.is_running = True
                self.btn_start.config(text="⏹ Stop Session", bg=COLORS["accent_danger"])
                self.status_var.set("● LIVE RUNNING")
                self.status_label.config(fg="#00FF00")
                self.canvas.itemconfig(self.placeholder_text, state="hidden")
                self._video_loop()
            else:
                show_error("Camera Error", "Could not access the webcam.")
        else:
            self._stop_session()

    def _stop_session(self) -> None:
        self.is_running = False
        if self.video_loop_id:
            self.after_cancel(self.video_loop_id)
            self.video_loop_id = None
            
        self.camera.stop()
        self.btn_start.config(text="▶ Start Session", bg=COLORS["accent_primary"])
        self.status_var.set("Camera Offline")
        self.status_label.config(fg=COLORS["text_secondary"])
        self.canvas.delete("all")
        self.placeholder_text = self.canvas.create_text(
            self.canvas_width/2, self.canvas_height/2, 
            text="Session Stopped", font=FONTS["heading_md"], fill=COLORS["text_muted"]
        )

    # -----------------------------------------------------------------------
    # Core Loop: Frame capture -> Recognize -> Draw -> Log
    # -----------------------------------------------------------------------
    def _video_loop(self) -> None:
        ret, frame = self.camera.get_frame()
        
        if ret and frame is not None:
            import cv2
            
            # 1. Recognize faces
            # downscale_factor=0.25 speeds up face_recognition significantly
            results = self.recognizer.recognize(frame, downscale_factor=0.25)
            
            # 2. Draw results and handle attendance
            for student_id, (top, right, bottom, left) in results:
                
                if student_id is not None and student_id in self.student_cache:
                    # Known Person
                    student = self.student_cache[student_id]
                    name = student["name"]
                    color = (0, 255, 0) # Green
                    label_text = f"{name} ({student['roll']})"
                    
                    # Mark attendance if not already marked today
                    if student_id not in self.marked_today:
                        self._mark_attendance(student_id, name)
                else:
                    # Unknown Person
                    color = (255, 0, 0) # Red (OpenCV is BGR natively but we are operating on RGB arrays here, so R=255)
                    label_text = "Unknown"

                # Draw bounding box (we are operating on RGB frame)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                # Draw label background
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                
                # Draw text
                # White text on the filled rectangle
                cv2.putText(frame, label_text, (left + 6, bottom - 6), font, 0.6, (255, 255, 255), 1)

            # 3. Display frame in Tkinter
            img = Image.fromarray(frame)
            img.thumbnail((self.canvas_width, self.canvas_height), Image.Resampling.LANCZOS)
            self.current_image = ImageTk.PhotoImage(image=img)
            
            self.canvas.delete("all")
            x_pos = (self.canvas_width - img.width) // 2
            y_pos = (self.canvas_height - img.height) // 2
            self.canvas.create_image(x_pos, y_pos, anchor=tk.NW, image=self.current_image)

        # Run loop (approx 30 FPS)
        if self.is_running:
            self.video_loop_id = self.after(33, self._video_loop)
            
    def _mark_attendance(self, student_id: int, name: str) -> None:
        """Handle database insertion and UI updates for a new attendance record."""
        current_time = get_current_time()
        
        # Insert into DB (database layer handles duplicate IGNORING inherently, 
        # but our memory cache prevents spamming DB)
        success = self.db.insert_attendance(student_id, self.admin_id, name, self.today_date, current_time)
        
        if success:
            self.marked_today.add(student_id)
            self._load_todays_log() # Refresh the log list
            
            # Visual feedback on canvas
            self.canvas.create_text(
                self.canvas_width/2, 30, 
                text=f"Marked: {name}", font=FONTS["heading_lg"], fill="#00FF00"
            )

    def destroy(self):
        self._stop_session()
        super().destroy()
