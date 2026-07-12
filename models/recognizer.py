"""
models/recognizer.py
====================
Handles real-time face recognition. Loads the serialized encodings from disk
and compares live frames against them to identify students.
"""

import os
import pickle
import numpy as np
import face_recognition
import logging
from typing import Tuple, List, Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helper import ENCODINGS_PATH, LABELS_PATH

logger = logging.getLogger(__name__)

class FaceRecognizer:
    def __init__(self, tolerance: float = 0.55):
        """
        Args:
            tolerance: The strictness of the face matching. 
                       Lower is stricter. 0.45 is a good balance for false positives.
        """
        self.tolerance = tolerance
        self.known_encodings: List[np.ndarray] = []
        self.known_labels: List[int] = []
        self.is_loaded = False
        
        self.load_models()

    def load_models(self) -> bool:
        """Load the pickled face encodings and labels from disk."""
        if not os.path.exists(ENCODINGS_PATH) or not os.path.exists(LABELS_PATH):
            logger.warning("Model files not found. Please train the model first.")
            self.is_loaded = False
            return False
            
        try:
            with open(ENCODINGS_PATH, 'rb') as f:
                self.known_encodings = pickle.load(f)
            with open(LABELS_PATH, 'rb') as f:
                self.known_labels = pickle.load(f)
                
            self.is_loaded = True
            logger.info(f"Loaded {len(self.known_labels)} known face encodings.")
            return True
        except Exception as e:
            logger.error(f"Error loading model files: {e}")
            self.is_loaded = False
            return False

    def recognize(self, rgb_frame: np.ndarray, downscale_factor: float = 0.25) -> List[Tuple[Optional[int], Tuple[int, int, int, int]]]:
        """
        Detects and recognizes faces in an RGB frame.
        
        Optimization:
            The frame is scaled down (e.g. to 1/4 size) before detection to vastly 
            improve FPS. Bounding boxes are then scaled back up.
            
        Args:
            rgb_frame: The image frame from the webcam (RGB format).
            downscale_factor: How much to shrink the image for processing.
            
        Returns:
            A list of tuples: (student_id, bounding_box(top, right, bottom, left))
            If a face is not recognized, student_id will be None.
        """
        if not self.is_loaded or not self.known_encodings:
            # If no model, we can't recognize anyone
            return []
            
        import cv2
        # Resize frame for faster processing
        small_frame = cv2.resize(rgb_frame, (0, 0), fx=downscale_factor, fy=downscale_factor)
        
        # Detect face locations
        # "hog" model is much faster on CPU than "cnn"
        face_locations = face_recognition.face_locations(small_frame, model="hog")
        
        if not face_locations:
            return []
            
        # Get embeddings for detected faces
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)
        
        results = []
        inv_scale = 1.0 / downscale_factor
        
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            # Scale coordinates back to original size
            top = int(top * inv_scale)
            right = int(right * inv_scale)
            bottom = int(bottom * inv_scale)
            left = int(left * inv_scale)
            bbox = (top, right, bottom, left)
            
            # Compare with known encodings
            matches = face_recognition.compare_faces(self.known_encodings, face_encoding, tolerance=self.tolerance)
            
            student_id = None
            
            # Find the best match
            if True in matches:
                face_distances = face_recognition.face_distance(self.known_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)
                
                if matches[best_match_index]:
                    student_id = self.known_labels[best_match_index]
                    
            results.append((student_id, bbox))
            
        return results
