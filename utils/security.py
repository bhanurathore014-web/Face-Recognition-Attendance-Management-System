"""
utils/security.py
=================
Security utilities for password hashing and token generation.

Dependencies:
    - hashlib (built-in)
    - secrets (built-in)
"""

import hashlib
import secrets

def hash_password(password: str) -> str:
    """
    Hash a plain-text password securely using PBKDF2 HMAC with SHA-256.
    
    Args:
        password: The plain-text password.
        
    Returns:
        The hashed password as a hex string with the salt prepended.
    """
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + hashed.hex()

def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verify a plain-text password against a stored PBKDF2 HMAC hash.
    
    Args:
        plain_password: The plain-text password input by the user.
        stored_hash: The stored hash (format "salt_hex:hash_hex").
        
    Returns:
        True if the password matches, False otherwise.
    """
    try:
        salt_hex, hash_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        
        new_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, 100000)
        return secrets.compare_digest(new_hash, expected_hash)
    except Exception:
        return False

def generate_reset_token(length: int = 32) -> str:
    """
    Generate a secure, random token for password resets.
    
    Args:
        length: The length of the token (in bytes).
        
    Returns:
        A hex-encoded secure random token string.
    """
    return secrets.token_hex(length)
