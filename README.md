# Face Recognition Attendance Management System

An AI-powered desktop application built in Python that automates attendance tracking using real-time facial recognition. 

Designed with a modern, glassmorphism-inspired dark UI using Tkinter, and powered by OpenCV and the `face_recognition` (dlib) library for high-accuracy face embeddings.

## Features

- **Admin Dashboard**: Clean, modern Tkinter GUI with sidebar navigation.
- **Student Registration**: Register students with deduplication checks (SQLite).
- **Dataset Collection**: Automated webcam capture of 100 face images per student.
- **AI Training**: Generates 128-dimensional face embeddings and averages them for high stability.
- **Live Attendance**: Real-time multi-face recognition (~30 FPS via downscaling).
- **Duplicate Prevention**: Prevents multiple attendance entries for the same student on the same day.
- **Reporting & Analytics**: Filter attendance logs by date and department, and export to CSV.

## Technology Stack

- **Language**: Python 3.12+
- **Computer Vision**: OpenCV (`cv2`)
- **Face Recognition**: `face_recognition` (wraps `dlib`'s ResNet model)
- **GUI**: `Tkinter` (built-in)
- **Database**: `SQLite3`
- **Data Export**: `Pandas`
- **Image Processing**: `Pillow` (PIL)

## Installation Guide

### 1. Prerequisites
You must install **CMake** before installing `dlib` and `face_recognition`.
- **macOS**: `brew install cmake`
- **Windows**: Download CMake from [cmake.org](https://cmake.org/download/) or `pip install cmake`
- **Linux**: `sudo apt install cmake`

### 2. Setup Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```

*Default Admin Credentials:*
- **Username**: `admin`
- **Password**: `admin123`

## Workflow

1. **Register**: Go to "Register Student", fill out details.
2. **Dataset**: Go to "Capture Dataset", select student, click "Start Camera" then "Start Capture".
3. **Train**: Click "Start Training" to generate embeddings.
4. **Attendance**: Go to "Take Attendance", start the session, and the system will automatically log present students.
5. **Reports**: View the logs and export as CSV.

## Project Architecture

```
FaceRecognitionAttendance/
│
├── app.py                  # Main entry point (Login -> Dashboard routing)
├── requirements.txt        # Pinned dependencies
├── README.md               # Documentation
│
├── database/               # Data Layer
│   ├── database.py         # SQLite connection manager and CRUD operations
│   └── attendance.db       # (Generated) SQLite database file
│
├── gui/                    # Presentation Layer
│   ├── login.py            # Glassmorphism login screen
│   ├── dashboard.py        # Main sidebar layout
│   ├── register.py         # Student registration form & list
│   ├── dataset.py          # Camera feed & capture controls
│   ├── attendance.py       # Live recognition & attendance logging
│   └── reports.py          # Data table and CSV export
│
├── models/                 # AI / ML Logic
│   ├── face_encoder.py     # Wrapper for 128-d face embeddings
│   ├── recognizer.py       # Live comparison logic
│   └── trainer.py          # Batch processing & averaging embeddings
│
└── utils/                  # Shared Utilities
    ├── helper.py           # Design system (Colors/Fonts), UI helpers
    ├── camera.py           # OpenCV webcam wrapper & Haar cascades
    └── csv_export.py       # Pandas CSV generator
```

## Deployment / Build (.exe / .app)

To package this application into a standalone executable:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build the app:
   ```bash
   pyinstaller --noconfirm --onedir --windowed --add-data "utils:utils" --add-data "models:models" --add-data "database:database" --add-data "gui:gui" app.py
   ```
*(Note: Because of dlib and OpenCV, the resulting binary will be large.)*
