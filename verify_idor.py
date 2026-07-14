import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database.database import DatabaseManager

def main():
    print("=== IDOR Prevention Verification ===")
    
    # Using the existing database
    db = DatabaseManager()
    db.connect()
    
    cursor = db._connection.cursor()
    
    try:
        # Create a second admin to test IDOR
        cursor.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?);", ("admin2", "hash2"))
        admin2_id = cursor.lastrowid
        db._connection.commit()
        print(f"[+] Created second admin with ID: {admin2_id}")
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM admins WHERE username = 'admin2'")
        admin2_id = cursor.fetchone()[0]
        print(f"[+] Using existing second admin with ID: {admin2_id}")

    admin1_id = 1
    
    # 1. Admin 1 inserts a student
    try:
        s1_id = db.insert_student(admin1_id, "Admin1 Student", "R1", "CS")
        print(f"[+] Admin 1 inserted student ID: {s1_id}")
    except Exception as e:
        cursor.execute("SELECT id FROM students WHERE roll='R1'")
        s1_id = cursor.fetchone()[0]
        
    # 2. Admin 2 inserts a student
    try:
        s2_id = db.insert_student(admin2_id, "Admin2 Student", "R2", "IT")
        print(f"[+] Admin 2 inserted student ID: {s2_id}")
    except Exception as e:
        cursor.execute("SELECT id FROM students WHERE roll='R2'")
        s2_id = cursor.fetchone()[0]

    # Verify IDOR on Retrieval
    print("\n--- Verifying Retrieval ---")
    
    # Admin 1 attempts to get Admin 2's student
    s2_fetched_by_a1 = db.get_student_by_id(s2_id, admin1_id)
    if s2_fetched_by_a1 is None:
        print("[PASS] Admin 1 cannot fetch Admin 2's student by ID.")
    else:
        print("[FAIL] Admin 1 fetched Admin 2's student!")
        
    # Admin 1 attempts to get all students
    a1_students = db.get_all_students(admin1_id)
    a1_student_ids = [s["id"] for s in a1_students]
    if s1_id in a1_student_ids and s2_id not in a1_student_ids:
        print("[PASS] Admin 1 get_all_students only returned their own students.")
    else:
        print(f"[FAIL] Admin 1 get_all_students returned unexpected IDs: {a1_student_ids}")
        
    # Verify IDOR on Attendance Insertion
    print("\n--- Verifying Attendance Insert ---")
    marked_s2_by_a1 = db.insert_attendance(s2_id, admin1_id, "Admin2 Student", "2024-01-01", "10:00:00")
    if marked_s2_by_a1:
        print("[FAIL] Admin 1 successfully marked attendance for Admin 2's student!")
    else:
        print("[PASS] Admin 1 cannot mark attendance for Admin 2's student.")
        
    # Cleanup test data
    db.delete_student(s1_id, admin1_id)
    db.delete_student(s2_id, admin2_id)
    print("\n[+] Cleaned up test students.")
    
    db.close()
    print("=== Verification Complete ===")

if __name__ == "__main__":
    main()
