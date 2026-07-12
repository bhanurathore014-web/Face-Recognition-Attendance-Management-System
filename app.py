"""
app.py
======
Entry point for the Face Recognition Attendance System.

Handles the application lifecycle:
1. Initialize the SQLite database connection.
2. Launch the Login window.
3. Upon successful login, transition to the main Dashboard.
4. Close the database connection on exit.
"""

import tkinter as tk
import logging
from database.database import DatabaseManager
from gui.login import LoginWindow
from gui.dashboard import DashboardWindow

# Basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class FaceAttendApp:
    def __init__(self):
        self.root = tk.Tk()
        # Start hidden, let the screens manage visibility and centering
        self.root.withdraw()
        
        # Connect to DB
        self.db = DatabaseManager()
        self.db.connect()

        # Handle window close (X button) safely
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self):
        """Launch the application starting with the login screen."""
        self.show_login()
        self.root.mainloop()

    def show_login(self):
        """Show the login screen and wait for authentication."""
        self.root.deiconify() # Ensure root is visible
        # We clear the root in case we are logging out from dashboard
        for widget in self.root.winfo_children():
            widget.destroy()
            
        LoginWindow(self.root, on_success_callback=self.show_dashboard)

    def show_dashboard(self):
        """Transition from login to main dashboard."""
        for widget in self.root.winfo_children():
            widget.destroy()
            
        DashboardWindow(self.root, self.db, on_logout_callback=self.show_login)

    def on_close(self):
        """Gracefully shutdown the app and database."""
        logging.info("Shutting down application...")
        self.db.close()
        self.root.destroy()

if __name__ == "__main__":
    app = FaceAttendApp()
    app.start()
