"""
Simple authentication module for plain text password comparison
"""

def verify_password(plain_password: str, stored_password: str) -> bool:
    """
    Simple plain text password comparison
    
    Args:
        plain_password: The password provided by the user
        stored_password: The password stored in the database
        
    Returns:
        bool: True if passwords match, False otherwise
    """
    # Direct string comparison - no hashing
    return plain_password == stored_password


def get_password_hash(password: str) -> str:
    """
    Return password as-is (no hashing)
    
    Args:
        password: The plain text password
        
    Returns:
        str: The same password (no transformation)
    """
    # Return password unchanged - no hashing
    return password