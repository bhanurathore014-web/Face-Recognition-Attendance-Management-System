import os
import stat
import sys

def restrict_file_permissions(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return False
        
    try:
        # Set file permissions to 600 (read/write for owner only)
        # stat.S_IRUSR | stat.S_IWUSR corresponds to 0o600
        os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)
        print(f"Successfully restricted permissions (600) for {filepath}")
        return True
    except Exception as e:
        print(f"Failed to set permissions on {filepath}: {e}")
        return False

def main():
    print("=== FaceAttend Security Initialization ===")
    
    # 1. Restrict database permissions
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'attendance.db')
    
    # Ensure database directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Create an empty file if it doesn't exist so we can chmod it
    if not os.path.exists(db_path):
        print("Database not found, creating an empty file to secure it.")
        open(db_path, 'a').close()
        
    restrict_file_permissions(db_path)
    
    # 2. Check for .env file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        print("Warning: .env file not found. Please copy .env.example to .env to securely configure the application.")
    else:
        restrict_file_permissions(env_path)
        
    print("=== Initialization Complete ===")

if __name__ == "__main__":
    main()
