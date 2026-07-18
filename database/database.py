"""
database/database.py
====================
Central database management module for the Face Recognition Attendance System.

Design Patterns Used:
    - Singleton: Only one DatabaseManager instance is created per session.
    - Context Manager: `with` statement ensures connections are always closed.
    - Repository Pattern: All SQL is encapsulated here; no raw SQL elsewhere.

Tables:
    students   — stores registered student profiles
    attendance — stores per-day attendance records (FK → students.id)

Dependencies:
    - sqlite3 (Python standard library)
    - os      (Python standard library)
"""

import sqlite3
import os
import sys
import logging
from datetime import datetime
from typing import Optional

# Make sure the project root is on sys.path when running this file directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.security import hash_password

# ---------------------------------------------------------------------------
# Logging setup — writes INFO+ to console; helps debug SQL errors
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve the absolute path to the database file.
# The DB lives inside the `database/` folder alongside this file.
# Using __file__ makes the path work regardless of where the app is launched.
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "attendance.db")


# ===========================================================================
# DatabaseManager — Singleton context-manager-aware database helper
# ===========================================================================
class DatabaseManager:
    """
    Manages all interactions with the SQLite database.

    Usage (context manager — preferred):
        with DatabaseManager() as db:
            db.insert_student(...)

    Usage (manual):
        db = DatabaseManager()
        db.connect()
        db.insert_student(...)
        db.close()
    """

    _instance: Optional["DatabaseManager"] = None  # Singleton holder

    # -----------------------------------------------------------------------
    # Singleton: __new__ guarantees only one DatabaseManager exists
    # -----------------------------------------------------------------------
    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connection = None
        return cls._instance

    # -----------------------------------------------------------------------
    # Context Manager Protocol
    # -----------------------------------------------------------------------
    def __enter__(self) -> "DatabaseManager":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Always close the connection; roll back on exception."""
        if exc_type is not None:
            logger.error("DB error: %s — rolling back.", exc_val)
            if self._connection:
                self._connection.rollback()
        self.close()
        return False  # Re-raise any exception

    # -----------------------------------------------------------------------
    # Connection management
    # -----------------------------------------------------------------------
    def connect(self) -> None:
        """Open (or reuse) the SQLite connection and ensure tables exist."""
        if self._connection is None:
            try:
                self._connection = sqlite3.connect(DB_PATH)
                # Return rows as dict-like objects (access by column name)
                self._connection.row_factory = sqlite3.Row
                # Enforce foreign key constraints (disabled by default in SQLite)
                self._connection.execute("PRAGMA foreign_keys = ON;")
                self._initialize_tables()
                logger.info("Connected to database: %s", DB_PATH)
            except sqlite3.Error as e:
                logger.critical("Failed to connect to database: %s", e)
                raise

    def close(self) -> None:
        """Commit any pending changes and close the connection."""
        if self._connection:
            self._connection.commit()
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed.")

    # -----------------------------------------------------------------------
    # Schema Initialization
    # -----------------------------------------------------------------------
    def _initialize_tables(self) -> None:
        """
        Create the `students` and `attendance` tables if they do not exist.

        SQL Notes:
            INTEGER PRIMARY KEY AUTOINCREMENT — SQLite auto-generates unique IDs.
            UNIQUE(roll) — enforces no duplicate roll numbers at the DB level.
            FOREIGN KEY — links attendance.student_id → students.id;
                          ON DELETE CASCADE removes attendance when student is deleted.
            TEXT NOT NULL — enforces mandatory fields.
        """
        create_students_sql = """
        CREATE TABLE IF NOT EXISTS students (
            id            INTEGER  PRIMARY KEY AUTOINCREMENT,
            name          TEXT     NOT NULL,
            roll          TEXT     NOT NULL UNIQUE,
            department    TEXT     NOT NULL,
            email         TEXT,
            image_path    TEXT,
            encoding_path TEXT,
            created_at    TEXT     NOT NULL
        );
        """

        create_admins_sql = """
        CREATE TABLE IF NOT EXISTS admins (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            username           TEXT    NOT NULL UNIQUE,
            password_hash      TEXT    NOT NULL,
            email              TEXT,
            is_verified        INTEGER DEFAULT 0,
            reset_token        TEXT,
            reset_token_expiry TEXT,
            failed_attempts    INTEGER DEFAULT 0,
            locked_until       TEXT
        );
        """

        create_attendance_sql = """
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id     INTEGER NOT NULL,
            name           TEXT    NOT NULL,
            date           TEXT    NOT NULL,
            time           TEXT    NOT NULL,
            status         TEXT    NOT NULL DEFAULT 'Present',
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        );
        """

        # Composite unique index: one attendance record per student per day
        create_unique_idx_sql = """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique
        ON attendance (student_id, date);
        """

        try:
            cursor = self._connection.cursor()
            cursor.execute(create_students_sql)
            cursor.execute(create_attendance_sql)
            cursor.execute(create_unique_idx_sql)
            cursor.execute(create_admins_sql)
            self._connection.commit()
            
            # Seed default admin if table is empty
            cursor.execute("SELECT COUNT(*) FROM admins;")
            if cursor.fetchone()[0] == 0:
                logger.info("Seeding default admin account...")
                default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "fallback_admin_password")
                hashed_pw = hash_password(default_password)
                cursor.execute(
                    "INSERT INTO admins (username, password_hash) VALUES (?, ?);",
                    ("admin", hashed_pw)
                )
                self._connection.commit()
                
            # Add admin_id to students if it doesn't exist
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN admin_id INTEGER REFERENCES admins(id) DEFAULT 1;")
                self._connection.commit()
                logger.info("Migrated students table to include admin_id.")
            except sqlite3.OperationalError:
                # Column already exists
                pass
                
            logger.info("Database tables initialized.")
        except sqlite3.Error as e:
            logger.error("Table initialization failed: %s", e)
            raise

    # =======================================================================
    # ADMIN CRUD AND AUTH OPERATIONS
    # =======================================================================

    def get_admin_by_username(self, username: str) -> Optional[dict]:
        """Fetch an admin by username."""
        sql = "SELECT * FROM admins WHERE username = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("get_admin_by_username failed: %s", e)
            return None

    def update_admin_login_status(self, username: str, failed_attempts: int, locked_until: Optional[str] = None) -> bool:
        """Update rate-limiting fields for an admin."""
        sql = "UPDATE admins SET failed_attempts = ?, locked_until = ? WHERE username = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (failed_attempts, locked_until, username))
            self._connection.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("update_admin_login_status failed: %s", e)
            return False

    # =======================================================================
    # STUDENT CRUD OPERATIONS
    # =======================================================================

    def insert_student(
        self,
        admin_id: int,
        name: str,
        roll: str,
        department: str,
        email: str = "",
        image_path: str = "",
        encoding_path: str = "",
    ) -> int:
        """
        Insert a new student record.

        Args:
            admin_id:      FK to admins.id
            name:          Full name of the student.
            roll:          Unique roll/employee number.
            department:    Department or class name.
            email:         Optional email address.
            image_path:    Path to the student's dataset folder.
            encoding_path: Path to the student's individual encoding file (future use).

        Returns:
            The auto-generated integer ID of the new student.

        Raises:
            sqlite3.IntegrityError: If roll number already exists.
        """
        sql = """
        INSERT INTO students (admin_id, name, roll, department, email, image_path, encoding_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (admin_id, name, roll, department, email, image_path, encoding_path, created_at))
            self._connection.commit()
            student_id = cursor.lastrowid
            logger.info("Inserted student: %s (ID=%d) under admin_id=%d", name, student_id, admin_id)
            return student_id
        except sqlite3.IntegrityError as e:
            logger.warning("Duplicate roll number '%s': %s", roll, e)
            raise
        except sqlite3.Error as e:
            logger.error("insert_student failed: %s", e)
            raise

    def get_all_students(self, admin_id: int) -> list[dict]:
        """
        Retrieve all student records ordered by name.

        Returns:
            List of dicts with keys: id, admin_id, name, roll, department, email,
            image_path, encoding_path, created_at.
        """
        sql = "SELECT * FROM students WHERE admin_id = ? ORDER BY name ASC;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (admin_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_all_students failed: %s", e)
            return []

    def get_student_by_id(self, student_id: int, admin_id: int) -> Optional[dict]:
        """Fetch a single student by primary key."""
        sql = "SELECT * FROM students WHERE id = ? AND admin_id = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id, admin_id))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("get_student_by_id failed: %s", e)
            return None

    def get_student_by_roll(self, roll: str, admin_id: int) -> Optional[dict]:
        """Fetch a single student by roll number."""
        sql = "SELECT * FROM students WHERE roll = ? AND admin_id = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (roll, admin_id))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("get_student_by_roll failed: %s", e)
            return None

    def search_students(self, keyword: str, admin_id: int) -> list[dict]:
        """
        Search students by name, roll, or department.

        SQL LIKE with '%keyword%' performs a substring match.
        """
        sql = """
        SELECT * FROM students
        WHERE admin_id = ? AND (name LIKE ? OR roll LIKE ? OR department LIKE ?)
        ORDER BY name ASC;
        """
        pattern = f"%{keyword}%"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (admin_id, pattern, pattern, pattern))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("search_students failed: %s", e)
            return []

    def update_student(
        self,
        student_id: int,
        admin_id: int,
        name: str,
        roll: str,
        department: str,
        email: str,
        image_path: str = "",
        encoding_path: str = "",
    ) -> bool:
        """Update an existing student record. Returns True on success."""
        sql = """
        UPDATE students
        SET name=?, roll=?, department=?, email=?, image_path=?, encoding_path=?
        WHERE id=? AND admin_id=?;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (name, roll, department, email, image_path, encoding_path, student_id, admin_id))
            self._connection.commit()
            logger.info("Updated student ID=%d", student_id)
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("update_student failed: %s", e)
            return False

    def delete_student(self, student_id: int, admin_id: int) -> bool:
        """
        Delete a student and cascade-delete all their attendance records.
        Returns True on success.
        """
        sql = "DELETE FROM students WHERE id = ? AND admin_id = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id, admin_id))
            self._connection.commit()
            logger.info("Deleted student ID=%d", student_id)
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("delete_student failed: %s", e)
            return False

    def get_total_students(self, admin_id: int) -> int:
        """Return the total count of registered students."""
        sql = "SELECT COUNT(*) FROM students WHERE admin_id = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (admin_id,))
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error("get_total_students failed: %s", e)
            return 0

    # =======================================================================
    # ATTENDANCE CRUD OPERATIONS
    # =======================================================================

    def insert_attendance(
        self, student_id: int, admin_id: int, name: str, date: str, time: str, status: str = "Present"
    ) -> bool:
        """
        Mark attendance for a student on a given date.

        The UNIQUE INDEX on (student_id, date) means this INSERT will silently
        fail (IGNORE) if the student has already been marked today — preventing
        duplicates without raising an exception.

        Args:
            student_id: FK to students.id
            admin_id:   The admin_id of the logged in user (IDOR prevention)
            name:       Student's name (denormalized for fast report queries)
            date:       "YYYY-MM-DD" format
            time:       "HH:MM:SS" format
            status:     "Present" (extensible to "Late", "Absent")

        Returns:
            True if a new record was inserted, False if duplicate was skipped or ownership invalid.
        """
        sql = """
        INSERT OR IGNORE INTO attendance (student_id, name, date, time, status)
        SELECT ?, ?, ?, ?, ?
        WHERE EXISTS (SELECT 1 FROM students WHERE id = ? AND admin_id = ?);
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id, name, date, time, status, student_id, admin_id))
            self._connection.commit()
            inserted = cursor.rowcount > 0
            if inserted:
                logger.info("Attendance marked: %s on %s at %s", name, date, time)
            else:
                logger.debug("Duplicate attendance skipped: %s on %s", name, date)
            return inserted
        except sqlite3.Error as e:
            logger.error("insert_attendance failed: %s", e)
            return False

    def get_attendance_by_date(self, date: str, admin_id: int) -> list[dict]:
        """Fetch all attendance records for a given date (YYYY-MM-DD)."""
        sql = """
        SELECT a.*, s.roll, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ? AND s.admin_id = ?
        ORDER BY a.time ASC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (date, admin_id))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_attendance_by_date failed: %s", e)
            return []

    def get_attendance_by_student(self, student_id: int, admin_id: int) -> list[dict]:
        """Fetch all attendance records for a specific student."""
        sql = """
        SELECT a.* FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.student_id = ? AND s.admin_id = ?
        ORDER BY a.date DESC, a.time DESC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id, admin_id))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_attendance_by_student failed: %s", e)
            return []

    def get_attendance_by_month(self, year: int, month: int, admin_id: int) -> list[dict]:
        """
        Fetch all attendance for a given YYYY-MM month.

        SQL LIKE 'YYYY-MM-%' matches all days in that month.
        """
        pattern = f"{year:04d}-{month:02d}-%"
        sql = """
        SELECT a.*, s.roll, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date LIKE ? AND s.admin_id = ?
        ORDER BY a.date ASC, a.time ASC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (pattern, admin_id))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_attendance_by_month failed: %s", e)
            return []

    def get_attendance_by_department(self, department: str, admin_id: int) -> list[dict]:
        """Fetch all attendance records filtered by department."""
        sql = """
        SELECT a.*, s.roll, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE s.department = ? AND s.admin_id = ?
        ORDER BY a.date DESC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (department, admin_id))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_attendance_by_department failed: %s", e)
            return []

    def get_all_attendance(self, admin_id: int) -> list[dict]:
        """Fetch every attendance record (for full CSV export)."""
        sql = """
        SELECT a.*, s.roll, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE s.admin_id = ?
        ORDER BY a.date DESC, a.time DESC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (admin_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_all_attendance failed: %s", e)
            return []

    def is_already_marked(self, student_id: int, admin_id: int, date: str) -> bool:
        """Return True if the student already has an attendance record for date."""
        sql = """
        SELECT 1 FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.student_id=? AND s.admin_id=? AND a.date=? LIMIT 1;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id, admin_id, date))
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error("is_already_marked failed: %s", e)
            return False

    def get_today_count(self, admin_id: int) -> int:
        """Return total attendance records for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        sql = """
        SELECT COUNT(*) FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ? AND s.admin_id = ?;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (today, admin_id))
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error("get_today_count failed: %s", e)
            return 0

    def get_departments(self, admin_id: int) -> list[str]:
        """Return a sorted list of all unique department names."""
        sql = "SELECT DISTINCT department FROM students WHERE admin_id = ? ORDER BY department ASC;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (admin_id,))
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error as e:
            logger.error("get_departments failed: %s", e)
            return []

    def update_student_paths(self, student_id: int, admin_id: int, image_path: str, encoding_path: str) -> None:
        """Update image and encoding paths after dataset capture/training."""
        sql = "UPDATE students SET image_path=?, encoding_path=? WHERE id=? AND admin_id=?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (image_path, encoding_path, student_id, admin_id))
            self._connection.commit()
        except sqlite3.Error as e:
            logger.error("update_student_paths failed: %s", e)


# ===========================================================================
# Standalone test — run `python database.py` to verify
# ===========================================================================
if __name__ == "__main__":
    print("=== DatabaseManager Self-Test ===")
    with DatabaseManager() as db:
        # Insert a test student
        sid = db.insert_student(1, "Alice Smith", "CS001", "Computer Science", "alice@example.com")
        print(f"Inserted student ID: {sid}")

        # Retrieve
        student = db.get_student_by_id(sid, 1)
        print(f"Fetched: {student}")

        # Search
        results = db.search_students("alice", 1)
        print(f"Search results: {results}")

        # Mark attendance
        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")
        marked = db.insert_attendance(sid, 1, "Alice Smith", today, now_time)
        print(f"Attendance marked: {marked}")

        # Duplicate check
        duplicate = db.insert_attendance(sid, 1, "Alice Smith", today, now_time)
        print(f"Duplicate blocked: {not duplicate}")

        # Today's count
        print(f"Today's count: {db.get_today_count(1)}")

        # Cleanup test data
        db.delete_student(sid, 1)
        print("Test student deleted. All tests passed ✓")
