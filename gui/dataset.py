"""
gui/dataset.py
==============
Dataset Collection Screen.

Features:
    - Select a registered student from a dropdown.
    - Start webcam feed within the Tkinter UI (using PIL and Canvas).
    - Detect face and draw bounding box.
    - Capture 100 images of the face.
    - Progress bar to show collection status.
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helper import COLORS, FONTS, get_student_dataset_path, get_image_count, show_error, show_info, ask_yes_no
from database.database import DatabaseManager
from utils.camera import CameraManager

# Target number of images per student
TARGET_IMAGES = 100

class DatasetFrame(tk.Frame):
    """
    Dataset collection panel.
    """
    def __init__(self, parent, db: DatabaseManager, admin_id: int):
        super().__init__(parent, bg=COLORS["bg_dark"])
        self.db = db
        self.admin_id = admin_id
        self.camera = CameraManager()
        
        # State variables
        self.is_capturing = False
        self.capture_count = 0
        self.current_student_id = None
        self.current_save_dir = None
        self.video_loop_id = None
        
        from models.trainer import ModelTrainer
        self.trainer = ModelTrainer()
        
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        # Page heading
        heading_bar = tk.Frame(self, bg=COLORS["bg_dark"])
        heading_bar.pack(fill=tk.X, padx=20, pady=(20, 10))

        tk.Label(
            heading_bar, text="Dataset Collection",
            font=FONTS["heading_lg"], bg=COLORS["bg_dark"], fg=COLORS["text_primary"]
        ).pack(side=tk.LEFT)

        # Main Layout: Left (Controls), Right (Camera Feed)
        main_content = tk.Frame(self, bg=COLORS["bg_dark"])
        main_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # ─── LEFT: CONTROLS PANEL ──────────────────────────────────────────
        controls_frame = tk.Frame(main_content, bg=COLORS["bg_card"], padx=20, pady=20)
        controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        
        tk.Label(
            controls_frame, text="1. Select Student",
            font=FONTS["heading_md"], bg=COLORS["bg_card"], fg=COLORS["accent_primary"]
        ).pack(anchor="w", pady=(0, 10))
        
        self.student_var = tk.StringVar()
        self.student_combo = ttk.Combobox(
            controls_frame, textvariable=self.student_var, state="readonly",
            font=FONTS["body"], width=30
        )
        self.student_combo.pack(fill=tk.X, pady=(0, 5))
        self.student_combo.bind("<<ComboboxSelected>>", self._on_student_selected)
        
        self.info_var = tk.StringVar(value="Select a student to see status.")
        tk.Label(
            controls_frame, textvariable=self.info_var,
            font=FONTS["body_sm"], bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            justify=tk.LEFT, anchor="w", wraplength=280
        ).pack(fill=tk.X, pady=(0, 30))
        
        tk.Label(
            controls_frame, text="2. Capture Faces",
            font=FONTS["heading_md"], bg=COLORS["bg_card"], fg=COLORS["accent_primary"]
        ).pack(anchor="w", pady=(0, 10))
        
        # Action Buttons
        self.btn_start_cam = tk.Button(
            controls_frame, text="📹 Start Camera", font=FONTS["body_sm"],
            bg=COLORS["bg_input"], fg=COLORS["text_primary"], relief=tk.FLAT,
            padx=10, pady=8, cursor="hand2", command=self._toggle_camera
        )
        self.btn_start_cam.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_capture = tk.Button(
            controls_frame, text="📸 Start Capture (0/100)", font=FONTS["heading_sm"],
            bg=COLORS["accent_primary"], fg=COLORS["text_on_accent"], relief=tk.FLAT,
            padx=10, pady=10, cursor="hand2", command=self._start_capture, state=tk.DISABLED
        )
        self.btn_capture.pack(fill=tk.X, pady=(0, 20))
        
        # Progress Bar
        tk.Label(
            controls_frame, text="Collection Progress:",
            font=FONTS["caption"], bg=COLORS["bg_card"], fg=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        self.progress = ttk.Progressbar(controls_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(5, 0))
        
        tk.Label(
            controls_frame, text="3. Train Model",
            font=FONTS["heading_md"], bg=COLORS["bg_card"], fg=COLORS["accent_primary"]
        ).pack(anchor="w", pady=(30, 10))
        
        self.btn_train = tk.Button(
            controls_frame, text="🧠 Start Training", font=FONTS["body_sm"],
            bg=COLORS["accent_secondary"], fg=COLORS["text_on_accent"], relief=tk.FLAT,
            padx=10, pady=8, cursor="hand2", command=self._start_training
        )
        self.btn_train.pack(fill=tk.X)
        
        self.train_progress = ttk.Progressbar(controls_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.train_progress.pack(fill=tk.X, pady=(5, 0))
        
        # ─── RIGHT: CAMERA FEED ────────────────────────────────────────────
        self.camera_frame = tk.Frame(main_content, bg="#000000", bd=2, relief=tk.FLAT)
        self.camera_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.camera_frame, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        
        # Placeholder text for camera
        self.placeholder_text = self.canvas.create_text(
            320, 240, text="Camera Offline\nClick 'Start Camera'",
            font=FONTS["heading_md"], fill=COLORS["text_muted"], justify=tk.CENTER
        )
        
        self.current_image = None
        self.canvas_width = 640
        self.canvas_height = 480

    # -----------------------------------------------------------------------
    # Setup and Refresh
    # -----------------------------------------------------------------------
    def refresh(self) -> None:
        """Called when switching to this tab. Reloads student list."""
        students = self.db.get_all_students(self.admin_id)
        self.student_map = {f"{s['roll']} - {s['name']}": s for s in students}
        
        values = list(self.student_map.keys())
        self.student_combo.config(values=values)
        if not values:
            self.student_combo.set("")
            self.info_var.set("No students registered yet.")
        
    def _on_student_selected(self, event=None) -> None:
        selection = self.student_var.get()
        if not selection:
            return
            
        student = self.student_map[selection]
        self.current_student_id = student["id"]
        self.current_save_dir = get_student_dataset_path(self.current_student_id)
        
        count = get_image_count(self.current_student_id)
        self.progress["value"] = (count / TARGET_IMAGES) * 100
        
        if count >= TARGET_IMAGES:
            self.info_var.set(f"Dataset complete ({count}/{TARGET_IMAGES} images).")
            self.btn_capture.config(text="Dataset Complete", state=tk.DISABLED, bg=COLORS["accent_secondary"])
        else:
            self.info_var.set(f"Needs collection ({count}/{TARGET_IMAGES} images).")
            if self.camera.cap and self.camera.cap.isOpened():
                self.btn_capture.config(state=tk.NORMAL)
            self.btn_capture.config(text=f"📸 Start Capture ({count}/{TARGET_IMAGES})", bg=COLORS["accent_primary"])

    def _on_canvas_resize(self, event):
        self.canvas_width = event.width
        self.canvas_height = event.height
        if not self.camera.cap:
            self.canvas.coords(self.placeholder_text, self.canvas_width/2, self.canvas_height/2)

    # -----------------------------------------------------------------------
    # Camera Controls
    # -----------------------------------------------------------------------
    def _toggle_camera(self) -> None:
        if self.camera.cap is None or not self.camera.cap.isOpened():
            if self.camera.start():
                self.btn_start_cam.config(text="⏹ Stop Camera", bg=COLORS["accent_danger"])
                self.canvas.itemconfig(self.placeholder_text, state="hidden")
                if self.current_student_id and get_image_count(self.current_student_id) < TARGET_IMAGES:
                    self.btn_capture.config(state=tk.NORMAL)
                self._video_loop()
            else:
                show_error("Camera Error", "Could not access the webcam.")
        else:
            self._stop_camera()

    def _stop_camera(self) -> None:
        self.is_capturing = False
        if self.video_loop_id:
            self.after_cancel(self.video_loop_id)
            self.video_loop_id = None
            
        self.camera.stop()
        self.btn_start_cam.config(text="📹 Start Camera", bg=COLORS["bg_input"])
        self.btn_capture.config(state=tk.DISABLED)
        self.canvas.delete("all")
        self.placeholder_text = self.canvas.create_text(
            self.canvas_width/2, self.canvas_height/2, 
            text="Camera Offline", font=FONTS["heading_md"], fill=COLORS["text_muted"]
        )

    def _start_capture(self) -> None:
        if not self.current_student_id:
            show_error("Error", "Please select a student first.")
            return
            
        count = get_image_count(self.current_student_id)
        if count > 0:
            if not ask_yes_no("Existing Data", f"Found {count} existing images. Overwrite/add more?"):
                return
                
        self.capture_count = count
        self.is_capturing = True
        self.btn_capture.config(state=tk.DISABLED, text="Capturing... Please wait")
        self.student_combo.config(state=tk.DISABLED)

    # -----------------------------------------------------------------------
    # Video Loop & Capture Logic
    # -----------------------------------------------------------------------
    def _video_loop(self) -> None:
        ret, frame = self.camera.get_frame()
        
        if ret and frame is not None:
            # We must detect face even if not capturing to draw the box for the user
            cropped_face, bbox = self.camera.detect_face(frame)
            
            import cv2
            # Draw bounding box if face detected
            if bbox is not None:
                x, y, w, h = bbox
                # Draw rect on frame
                color = (0, 255, 0) if self.is_capturing else (255, 255, 0)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                
                # If capturing, save the face
                if self.is_capturing and cropped_face is not None:
                    success = self.camera.save_face_image(cropped_face, self.current_save_dir, self.capture_count)
                    if success:
                        self.capture_count += 1
                        self.progress["value"] = (self.capture_count / TARGET_IMAGES) * 100
                        
                        if self.capture_count >= TARGET_IMAGES:
                            self._finish_capture()

            # Display frame
            img = Image.fromarray(frame)
            # Resize to fit canvas while maintaining aspect ratio
            img.thumbnail((self.canvas_width, self.canvas_height), Image.Resampling.LANCZOS)
            self.current_image = ImageTk.PhotoImage(image=img)
            
            self.canvas.delete("all")
            # Center the image
            x_pos = (self.canvas_width - img.width) // 2
            y_pos = (self.canvas_height - img.height) // 2
            self.canvas.create_image(x_pos, y_pos, anchor=tk.NW, image=self.current_image)
            
            # Draw capture status overlay
            if self.is_capturing:
                self.canvas.create_text(
                    20, 20, anchor=tk.NW,
                    text=f"Capturing: {self.capture_count} / {TARGET_IMAGES}",
                    font=FONTS["heading_lg"], fill="#00FF00"
                )

        # Loop at ~30 FPS (33ms)
        self.video_loop_id = self.after(33, self._video_loop)
        
    def _finish_capture(self) -> None:
        self.is_capturing = False
        self.student_combo.config(state="readonly")
        
        # Update DB encoding path to empty, since new data means we need retraining
        self.db.update_student_paths(self.current_student_id, self.admin_id, self.current_save_dir, "")
        
        show_info("Capture Complete", f"Successfully captured {TARGET_IMAGES} images!")
        self._on_student_selected() # Refresh UI state

    # -----------------------------------------------------------------------
    # Training Logic
    # -----------------------------------------------------------------------
    def _start_training(self) -> None:
        if not ask_yes_no("Start Training", "Training may take a while depending on the number of students. Continue?"):
            return
            
        self.btn_train.config(state=tk.DISABLED, text="Training in progress...")
        self.train_progress["value"] = 0
        self.root = self.winfo_toplevel()
        
        # We run this in the main thread with simple progress updates for now
        # In a very large production app, this should run in a separate thread.
        def update_progress(current, total):
            self.train_progress["value"] = (current / total) * 100
            self.root.update_idletasks()
            
        success, msg = self.trainer.train(progress_callback=update_progress)
        
        self.btn_train.config(state=tk.NORMAL, text="🧠 Start Training")
        if success:
            show_info("Training Complete", msg)
        else:
            show_error("Training Failed", msg)

    def destroy(self):
        """Cleanup when frame is destroyed."""
        self._stop_camera()
        super().destroy()

