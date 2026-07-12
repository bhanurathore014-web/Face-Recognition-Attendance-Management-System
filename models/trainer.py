"""
models/trainer.py
=================
Iterates through the dataset folders, encodes all face images, computes an 
average encoding for each student (for stability and performance), and serializes
the results using pickle.
"""

import os
import pickle
import numpy as np
from PIL import Image
import logging

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helper import DATASET_DIR, ENCODINGS_PATH, LABELS_PATH
from models.face_encoder import FaceEncoder

logger = logging.getLogger(__name__)

class ModelTrainer:
    def __init__(self):
        self.encoder = FaceEncoder()

    def train(self, progress_callback=None) -> tuple[bool, str]:
        """
        Process all images in the dataset directory.
        
        Args:
            progress_callback: Optional callable taking (current: int, total: int)
                               to update UI progress bars.
                               
        Returns:
            (success: bool, message: str)
        """
        if not os.path.exists(DATASET_DIR):
            return False, "Dataset directory does not exist."

        student_ids = [d for d in os.listdir(DATASET_DIR) 
                       if os.path.isdir(os.path.join(DATASET_DIR, d))]
        
        if not student_ids:
            return False, "No student data found."

        total_students = len(student_ids)
        
        known_encodings = []
        known_labels = []  # Stores student IDs
        
        for i, student_id in enumerate(student_ids):
            student_dir = os.path.join(DATASET_DIR, student_id)
            image_files = [f for f in os.listdir(student_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
            
            if not image_files:
                logger.warning(f"No images found for student ID {student_id}")
                continue
                
            student_encodings = []
            
            for img_file in image_files:
                img_path = os.path.join(student_dir, img_file)
                try:
                    # Load image in RGB
                    img = Image.open(img_path).convert("RGB")
                    img_array = np.array(img)
                    
                    encoding = self.encoder.get_encoding(img_array)
                    if encoding is not None:
                        student_encodings.append(encoding)
                except Exception as e:
                    logger.error(f"Error processing {img_path}: {e}")
                    
            if student_encodings:
                # Average the encodings to get a single robust prototype vector per student
                # This drastically speeds up recognition (O(N) where N=students instead of N=images)
                avg_encoding = np.mean(student_encodings, axis=0)
                known_encodings.append(avg_encoding)
                known_labels.append(int(student_id))
            
            if progress_callback:
                progress_callback(i + 1, total_students)

        if not known_encodings:
            return False, "Failed to extract valid face encodings from dataset."

        # Save to disk
        try:
            with open(ENCODINGS_PATH, 'wb') as f:
                pickle.dump(known_encodings, f)
            with open(LABELS_PATH, 'wb') as f:
                pickle.dump(known_labels, f)
            
            logger.info(f"Model trained successfully. Encoded {len(known_labels)} students.")
            return True, f"Successfully trained model for {len(known_labels)} students."
        except Exception as e:
            logger.error(f"Failed to save model files: {e}")
            return False, f"Serialization error: {e}"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    trainer = ModelTrainer()
    success, msg = trainer.train(lambda c, t: print(f"Progress: {c}/{t}"))
    print(msg)
