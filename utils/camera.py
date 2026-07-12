"""
utils/camera.py
===============
Handles webcam access, face detection, and image processing for dataset capture.

OpenCV (cv2) is used for:
- VideoCapture: Reading frames from the webcam.
- CascadeClassifier: Detecting face bounding boxes quickly.
- cvtColor: Converting BGR (OpenCV default) to RGB (Tkinter/Pillow format).

Images are cropped to the face bounding box, resized to 200x200, and saved.
"""

import cv2
import os
import logging
from typing import Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

class CameraManager:
    """
    Manages the webcam lifecycle and provides methods for reading frames
    and capturing face datasets.
    """
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        
        # Load the Haar Cascade for fast, lightweight face detection during capture
        # (We use dlib/face_recognition later for the actual deep-learning embedding, 
        # but Haar Cascade is very fast for just cropping dataset images).
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
    def start(self) -> bool:
        """Open the webcam. Returns True if successful."""
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index)
            # Standardize resolution for consistent processing
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return self.cap.isOpened()
        
    def stop(self) -> None:
        """Release the webcam resources."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
            
    def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a frame from the webcam.
        Returns:
            (success_boolean, frame_in_RGB_format)
        """
        if not self.cap or not self.cap.isOpened():
            return False, None
            
        ret, frame = self.cap.read()
        if not ret:
            return False, None
            
        # OpenCV captures in BGR, we need RGB for Tkinter display and face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return True, rgb_frame

    def detect_face(self, rgb_frame: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
        """
        Detect a face in the RGB frame using Haar Cascade.
        
        Returns:
            (cropped_face_rgb, bounding_box_tuple(x, y, w, h))
            If no face or multiple faces are found, returns (None, None)
        """
        # Convert to grayscale for Haar Cascade
        gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
        
        # scaleFactor=1.1, minNeighbors=5, minSize=(100, 100) avoids false positives
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
        )
        
        # We enforce exactly ONE face for dataset capture to avoid ambiguity
        if len(faces) != 1:
            return None, None
            
        x, y, w, h = faces[0]
        
        # Add a margin (padding) around the face
        margin = int(0.2 * w)
        img_h, img_w = rgb_frame.shape[:2]
        
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(img_w, x + w + margin)
        y2 = min(img_h, y + h + margin)
        
        cropped = rgb_frame[y1:y2, x1:x2]
        
        return cropped, (x1, y1, x2-x1, y2-y1)

    def save_face_image(self, cropped_face_rgb: np.ndarray, save_dir: str, image_index: int) -> bool:
        """
        Resize the cropped face to 200x200 and save it as a JPEG.
        """
        try:
            # Resize to standard size for consistent encodings later
            resized = cv2.resize(cropped_face_rgb, (200, 200))
            
            # Convert back to BGR for OpenCV imwrite
            bgr_face = cv2.cvtColor(resized, cv2.COLOR_RGB2BGR)
            
            filename = f"img_{image_index:03d}.jpg"
            filepath = os.path.join(save_dir, filename)
            
            cv2.imwrite(filepath, bgr_face)
            return True
        except Exception as e:
            logger.error(f"Failed to save image {image_index}: {e}")
            return False
