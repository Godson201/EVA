import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, List
from database import db
import json
import os
import re
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "eva-development-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

security = HTTPBearer()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    """Validate email address format."""
    if not email:
        return False
    return bool(EMAIL_PATTERN.match(email.strip()))


def normalize_smtp_password(password: str) -> str:
    """Remove spaces from Gmail app passwords so SMTP login works."""
    return (password or '').replace(' ', '').strip()


def send_email(to_email: str, subject: str, body: str, reply_to: str = None) -> bool:
    """Send a plaintext email using Gmail SMTP."""
    try:
        sender_email = (os.getenv('SMTP_EMAIL') or '').strip()
        sender_password = normalize_smtp_password(os.getenv('SMTP_PASSWORD') or '')
        if not sender_email or not sender_password:
            raise RuntimeError('SMTP_EMAIL and SMTP_PASSWORD must be configured')
        smtp_host = (os.getenv('SMTP_HOST') or 'smtp.gmail.com').strip()
        smtp_port = int(os.getenv('SMTP_PORT') or '587')
        use_ssl = (os.getenv('SMTP_USE_SSL') or 'False').strip().lower() in {'1', 'true', 'yes'}

        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = sender_email
        message['To'] = to_email
        if reply_to:
            message['Reply-To'] = reply_to
        message.set_content(body)

        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
                smtp.login(sender_email, sender_password)
                smtp.sendmail(sender_email, [to_email], message.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as smtp:
                smtp.starttls()
                smtp.login(sender_email, sender_password)
                smtp.sendmail(sender_email, [to_email], message.as_string())
        return True
    except Exception as exc:
        print(f"Email send error: {exc}")
        return False


def send_registration_email(username: str, email: str, password: str) -> bool:
    """Send a registration confirmation email using Gmail SMTP."""
    body = (
        f"Hello {username},\n\n"
        "Your account registration was successful.\n\n"
        f"Username: {username}\n"
        f"Email: {email}\n"
        f"Password: {password}\n\n"
        "Please sign in and change your password after your first login for security.\n\n"
        "Regards,\nEVA"
    )
    return send_email(email, 'Registration successful - EVA', body)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    plain_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def create_access_token(data: dict) -> str:
    """Create JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[Dict]:
    """Decode JWT token"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def log_activity(user_id: int, action: str, details: str = None, ip_address: str = None):
    """Log user activity"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activity_logs (user_id, action, details, ip_address) VALUES (%s, %s, %s, %s)",
            (user_id, action, details, ip_address)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Activity log error: {e}")


def authenticate_user(username: str, password: str, ip_address: str = None) -> Optional[Dict]:
    """Authenticate user credentials using either a username or email."""
    identifier = (username or '').strip()
    if not identifier:
        return None

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE (username = %s OR email = %s) AND is_active = TRUE",
        (identifier, identifier)
    )
    user = cursor.fetchone()
    cursor.close()

    if not user:
        conn.close()
        return None

    if not verify_password(password, user['password_hash']):
        conn.close()
        return None

    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_active = NOW(), last_login = NOW() WHERE id = %s", (user['id'],))
    conn.commit()
    cursor.close()

    log_activity(user['id'], "LOGIN", "User logged in", ip_address)

    user.pop('password_hash', None)
    conn.close()
    return user


def register_user(username: str, email: str, password: str, full_name: str = None, 
                  role: str = "user", department: str = None, phone: str = None,
                  created_by: int = None, provider: str = "email") -> Dict:
    """Register a new user"""
    username = (username or '').strip()
    email = (email or '').strip()

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Valid email is required")
    
    # Only directors can create users with role 'director' or 'secretary'
    if role in ["director", "secretary"] and not created_by:
        raise HTTPException(status_code=403, detail="Only directors can create staff accounts")
    
    if role in ["director", "secretary"] and created_by:
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT role FROM users WHERE id = %s", (created_by,))
        creator = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not creator or creator['role'] != 'director':
            raise HTTPException(status_code=403, detail="Only directors can create staff accounts")
    
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("SHOW COLUMNS FROM users LIKE 'provider'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN provider VARCHAR(50) DEFAULT 'email'")
        conn.commit()
    
    # Check if user already exists
    cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Create new user
    password_hash = get_password_hash(password)
    cursor.execute(
        """INSERT INTO users (username, email, password_hash, full_name, role, department, phone, is_active, provider) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (username, email, password_hash, full_name, role, department, phone, True, (provider or 'email').strip() or 'email')
    )
    conn.commit()
    user_id = cursor.lastrowid
    cursor.close()
    conn.close()
    
    # Log activity if created_by is provided
    if created_by:
        log_activity(created_by, "CREATE_USER", f"Created user: {username} (role: {role})", None)
    
    email_sent = send_registration_email(username, email, password)

    return {
        "id": user_id,
        "username": username,
        "email": email,
        "full_name": full_name,
        "role": role,
        "department": department,
        "phone": phone,
        "provider": (provider or 'email').strip() or 'email',
        "message": f"Account created successfully for {username}. Your password is: {password}",
        "email_sent": email_sent
    }


def reset_user_password(identifier: str, new_password: str) -> Dict:
    """Reset a user password by username or email."""
    identifier = (identifier or '').strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Username or email is required")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, email FROM users WHERE username = %s OR email = %s",
        (identifier, identifier)
    )
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")

    password_hash = get_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user['id']))
    conn.commit()
    cursor.close()
    conn.close()

    username = user.get('username') or identifier
    return {
        "success": True,
        "message": f"Password updated successfully for {username}. Your new password is: {new_password}",
    }


def change_user_password(user_id: int, current_password: str, new_password: str) -> Dict:
    """Change a password for an authenticated user."""
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")

    if not verify_password(current_password, user['password_hash']):
        cursor.close()
        conn.close()
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    password_hash = get_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "success": True,
        "message": "Password changed successfully"
    }


async def get_current_user(request: Request = None) -> Dict:
    """Get current user from JWT token sent either in Authorization header or httpOnly cookie"""
    token = None
    # Check Authorization header first
    if request is not None:
        auth_header = request.headers.get('authorization') or request.headers.get('Authorization')
        if auth_header and auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()

        # Fallback to cookie named 'token'
        if not token:
            token = request.cookies.get('token')

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, email, full_name, role, department, phone, is_active FROM users WHERE id = %s",
        (user_id,)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get('is_active', True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_user_permissions(user_id: int) -> List[str]:
    """Get user permissions"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT permission FROM user_permissions WHERE user_id = %s", (user_id,))
    permissions = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return permissions


def has_permission(user: Dict, permission: str) -> bool:
    """Check if user has specific permission"""
    # Roles with full privileges
    if user['role'] in ('director', 'admin'):
        return True
    
    permissions = get_user_permissions(user['id'])
    return permission in permissions


def require_permission(permission: str):
    """Dependency for permission checking"""
    async def dependency(current_user: Dict = Depends(get_current_user)):
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Requires: {permission}"
            )
        return current_user
    return dependency
