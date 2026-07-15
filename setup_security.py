import os
import stat
import sys
import shutil

def restrict_file_permissions(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return False
        
    if os.path.islink(filepath):
        print(f"Error: {filepath} is a symbolic link. Cowardly refusing to change permissions.")
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
        
    if not restrict_file_permissions(db_path):
        print("Fatal: Failed to secure database. Aborting.")
        sys.exit(1)
    
    # 2. Check for .env file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    example_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env.example')
    
    if not os.path.exists(env_path):
        if os.path.exists(example_env):
            print(".env not found. Copying .env.example to .env...")
            shutil.copy(example_env, env_path)
        else:
            print("Warning: .env and .env.example not found.")
            sys.exit(1)
            
    if not restrict_file_permissions(env_path):
        print("Fatal: Failed to secure .env file. Aborting.")
        sys.exit(1)
        
    print("=== Initialization Complete ===")

if __name__ == "__main__":
    main()
