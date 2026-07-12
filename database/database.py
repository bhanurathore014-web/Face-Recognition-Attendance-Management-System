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
import logging
from datetime import datetime
from typing import Optional

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
            self._connection.commit()
            logger.info("Database tables initialized.")
        except sqlite3.Error as e:
            logger.error("Table initialization failed: %s", e)
            raise

    # =======================================================================
    # STUDENT CRUD OPERATIONS
    # =======================================================================

    def insert_student(
        self,
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
        INSERT INTO students (name, roll, department, email, image_path, encoding_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (name, roll, department, email, image_path, encoding_path, created_at))
            self._connection.commit()
            student_id = cursor.lastrowid
            logger.info("Inserted student: %s (ID=%d)", name, student_id)
            return student_id
        except sqlite3.IntegrityError as e:
            logger.warning("Duplicate roll number '%s': %s", roll, e)
            raise
        except sqlite3.Error as e:
            logger.error("insert_student failed: %s", e)
            raise

    def get_all_students(self) -> list[dict]:
        """
        Retrieve all student records ordered by name.

        Returns:
            List of dicts with keys: id, name, roll, department, email,
            image_path, encoding_path, created_at.
        """
        sql = "SELECT * FROM students ORDER BY name ASC;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_all_students failed: %s", e)
            return []

    def get_student_by_id(self, student_id: int) -> Optional[dict]:
        """Fetch a single student by primary key."""
        sql = "SELECT * FROM students WHERE id = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("get_student_by_id failed: %s", e)
            return None

    def get_student_by_roll(self, roll: str) -> Optional[dict]:
        """Fetch a single student by roll number."""
        sql = "SELECT * FROM students WHERE roll = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (roll,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("get_student_by_roll failed: %s", e)
            return None

    def search_students(self, keyword: str) -> list[dict]:
        """
        Search students by name, roll, or department.

        SQL LIKE with '%keyword%' performs a substring match.
        """
        sql = """
        SELECT * FROM students
        WHERE name LIKE ? OR roll LIKE ? OR department LIKE ?
        ORDER BY name ASC;
        """
        pattern = f"%{keyword}%"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (pattern, pattern, pattern))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("search_students failed: %s", e)
            return []

    def update_student(
        self,
        student_id: int,
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
        WHERE id=?;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (name, roll, department, email, image_path, encoding_path, student_id))
            self._connection.commit()
            logger.info("Updated student ID=%d", student_id)
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("update_student failed: %s", e)
            return False

    def delete_student(self, student_id: int) -> bool:
        """
        Delete a student and cascade-delete all their attendance records.
        Returns True on success.
        """
        sql = "DELETE FROM students WHERE id = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id,))
            self._connection.commit()
            logger.info("Deleted student ID=%d", student_id)
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("delete_student failed: %s", e)
            return False

    def get_total_students(self) -> int:
        """Return the total count of registered students."""
        sql = "SELECT COUNT(*) FROM students;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql)
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error("get_total_students failed: %s", e)
            return 0

    # =======================================================================
    # ATTENDANCE CRUD OPERATIONS
    # =======================================================================

    def insert_attendance(
        self, student_id: int, name: str, date: str, time: str, status: str = "Present"
    ) -> bool:
        """
        Mark attendance for a student on a given date.

        The UNIQUE INDEX on (student_id, date) means this INSERT will silently
        fail (IGNORE) if the student has already been marked today — preventing
        duplicates without raising an exception.

        Args:
            student_id: FK to students.id
            name:       Student's name (denormalized for fast report queries)
            date:       "YYYY-MM-DD" format
            time:       "HH:MM:SS" format
            status:     "Present" (extensible to "Late", "Absent")

        Returns:
            True if a new record was inserted, False if duplicate was skipped.
        """
        sql = """
        INSERT OR IGNORE INTO attendance (student_id, name, date, time, status)
        VALUES (?, ?, ?, ?, ?);
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id, name, date, time, status))
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

    def get_attendance_by_date(self, date: str) -> list[dict]:
        """Fetch all attendance records for a given date (YYYY-MM-DD)."""
        sql = """
        SELECT a.*, s.roll, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ?
        ORDER BY a.time ASC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (date,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_attendance_by_date failed: %s", e)
            return []

    def get_attendance_by_student(self, student_id: int) -> list[dict]:
        """Fetch all attendance records for a specific student."""
        sql = """
        SELECT * FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC, time DESC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_attendance_by_student failed: %s", e)
            return []

    def get_attendance_by_month(self, year: int, month: int) -> list[dict]:
        """
        Fetch all attendance for a given YYYY-MM month.

        SQL LIKE 'YYYY-MM-%' matches all days in that month.
        """
        pattern = f"{year:04d}-{month:02d}-%"
        sql = """
        SELECT a.*, s.roll, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date LIKE ?
        ORDER BY a.date ASC, a.time ASC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (pattern,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_attendance_by_month failed: %s", e)
            return []

    def get_attendance_by_department(self, department: str) -> list[dict]:
        """Fetch all attendance records filtered by department."""
        sql = """
        SELECT a.*, s.roll, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE s.department = ?
        ORDER BY a.date DESC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (department,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_attendance_by_department failed: %s", e)
            return []

    def get_all_attendance(self) -> list[dict]:
        """Fetch every attendance record (for full CSV export)."""
        sql = """
        SELECT a.*, s.roll, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        ORDER BY a.date DESC, a.time DESC;
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("get_all_attendance failed: %s", e)
            return []

    def is_already_marked(self, student_id: int, date: str) -> bool:
        """Return True if the student already has an attendance record for date."""
        sql = "SELECT 1 FROM attendance WHERE student_id=? AND date=? LIMIT 1;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (student_id, date))
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error("is_already_marked failed: %s", e)
            return False

    def get_today_count(self) -> int:
        """Return total attendance records for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        sql = "SELECT COUNT(*) FROM attendance WHERE date = ?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (today,))
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error("get_today_count failed: %s", e)
            return 0

    def get_departments(self) -> list[str]:
        """Return a sorted list of all unique department names."""
        sql = "SELECT DISTINCT department FROM students ORDER BY department ASC;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error as e:
            logger.error("get_departments failed: %s", e)
            return []

    def update_student_paths(self, student_id: int, image_path: str, encoding_path: str) -> None:
        """Update image and encoding paths after dataset capture/training."""
        sql = "UPDATE students SET image_path=?, encoding_path=? WHERE id=?;"
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, (image_path, encoding_path, student_id))
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
        sid = db.insert_student("Alice Smith", "CS001", "Computer Science", "alice@example.com")
        print(f"Inserted student ID: {sid}")

        # Retrieve
        student = db.get_student_by_id(sid)
        print(f"Fetched: {student}")

        # Search
        results = db.search_students("alice")
        print(f"Search results: {results}")

        # Mark attendance
        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")
        marked = db.insert_attendance(sid, "Alice Smith", today, now_time)
        print(f"Attendance marked: {marked}")

        # Duplicate check
        duplicate = db.insert_attendance(sid, "Alice Smith", today, now_time)
        print(f"Duplicate blocked: {not duplicate}")

        # Today's count
        print(f"Today's count: {db.get_today_count()}")

        # Cleanup test data
        db.delete_student(sid)
        print("Test student deleted. All tests passed ✓")
