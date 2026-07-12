"""
utils/csv_export.py
===================
Handles exporting data from the SQLite database to CSV files using Pandas.
"""

import pandas as pd
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def export_attendance_to_csv(data: list[dict], save_dir: str) -> tuple[bool, str]:
    """
    Export attendance records to a CSV file.
    
    Args:
        data: List of dictionary records from the database.
        save_dir: Directory where the CSV should be saved.
        
    Returns:
        (success_bool, filepath_or_error_message)
    """
    if not data:
        return False, "No data available to export."
        
    try:
        # Convert to Pandas DataFrame for easy CSV export
        df = pd.DataFrame(data)
        
        # Reorder columns for a more logical CSV layout if they exist
        desired_order = ["attendance_id", "date", "time", "student_id", "name", "roll", "department", "status"]
        actual_columns = [col for col in desired_order if col in df.columns]
        # Append any remaining columns that weren't in desired_order
        for col in df.columns:
            if col not in actual_columns:
                actual_columns.append(col)
                
        df = df[actual_columns]
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Attendance_Report_{timestamp}.csv"
        filepath = os.path.join(save_dir, filename)
        
        df.to_csv(filepath, index=False)
        logger.info(f"Exported CSV to {filepath}")
        return True, filepath
        
    except Exception as e:
        logger.error(f"Failed to export CSV: {e}")
        return False, str(e)
