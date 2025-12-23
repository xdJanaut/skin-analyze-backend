from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Header
from typing import Optional
import jwt
from jwt.exceptions import InvalidTokenError as JWTError

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# JWT settings
SECRET_KEY = "12345678"  # Change this to something more secure in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def hash_password(password: str) -> str:
    if len(password.encode('utf-8')) > 72:
        raise ValueError("Password is too long. Please use a shorter password.")
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Get the current logged-in user from the JWT token.
    Raises 401 if token is invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not authorization:
        raise credentials_exception
    
    try:
        # Authorization header format: "Bearer <token>"
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except (JWTError, IndexError):
        raise credentials_exception

def get_current_user_optional(authorization: Optional[str] = Header(None)):
    """
    Returns username if valid token is provided, None otherwise.
    Allows endpoints to work for both logged-in and anonymous users.
    """
    if not authorization:
        return None
    
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        return username
    except (JWTError, IndexError):
        return None