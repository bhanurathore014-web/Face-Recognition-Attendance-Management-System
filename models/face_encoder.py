"""
models/face_encoder.py
======================
Wraps the `face_recognition` (dlib) library to generate 128-dimensional 
face embeddings from images.

How it works:
1. `face_locations()` finds the bounding box using HOG or CNN.
2. `face_encodings()` uses a ResNet neural network to map the face 
   to a 128-d vector where distance corresponds to face similarity.
"""

import face_recognition
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class FaceEncoder:
    @staticmethod
    def get_encoding(rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract the 128-d face embedding from an RGB image array.
        
        Args:
            rgb_image: numpy array of the image in RGB format
            
        Returns:
            numpy array of shape (128,) if exactly one face is found, else None
        """
        try:
            # Detect face locations first
            # model="hog" is faster for CPU; "cnn" is more accurate but requires GPU
            locations = face_recognition.face_locations(rgb_image, model="hog")
            
            if not locations:
                return None
                
            if len(locations) > 1:
                logger.warning("Multiple faces detected in image, skipping to ensure clean dataset.")
                return None
                
            # Generate the embedding for the single face found
            encodings = face_recognition.face_encodings(rgb_image, known_face_locations=locations)
            
            if encodings:
                return encodings[0]
            return None
            
        except Exception as e:
            logger.error(f"Error encoding face: {e}")
            return None

    @staticmethod
    def compare_faces(known_encodings: list[np.ndarray], face_encoding_to_check: np.ndarray, tolerance: float = 0.55) -> list[bool]:
        """
        Compare a list of face encodings against a candidate encoding.
        
        Args:
            known_encodings: List of 128-d arrays.
            face_encoding_to_check: Single 128-d array.
            tolerance: Lower is stricter. 0.45 is recommended for strong accuracy.
            
        Returns:
            List of booleans indicating matches.
        """
        return face_recognition.compare_faces(known_encodings, face_encoding_to_check, tolerance=tolerance)

    @staticmethod
    def face_distance(known_encodings: list[np.ndarray], face_encoding_to_check: np.ndarray) -> np.ndarray:
        """
        Get the euclidean distance between known encodings and a candidate.
        
        Returns:
            Numpy array of distances (lower distance = closer match).
        """
        return face_recognition.face_distance(known_encodings, face_encoding_to_check)
