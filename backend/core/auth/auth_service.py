"""Authentication service with database support."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import uuid

from models.user import User, Session, UserRole
from models.agency import Agency
from core.config import settings
from core.exceptions import AuthenticationError, ValidationError, NotFoundError


class AuthService:
    """Authentication service for managing user authentication and sessions."""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.algorithm = settings.JWT_ALGORITHM or "HS256"
        self.secret_key = settings.JWT_SECRET_KEY or settings.SECRET_KEY
        self.access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES or 30
        self.refresh_token_expire_days = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS or 7
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise AuthenticationError("Invalid token")
    
    async def create_user(
        self,
        db: AsyncSession,
        email: str,
        username: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: UserRole = UserRole.MEMBER,
        agency_id: Optional[int] = None
    ) -> User:
        """Create a new user."""
        # Check if user already exists
        stmt = select(User).where(
            or_(User.email == email, User.username == username)
        )
        existing_user = await db.scalar(stmt)
        if existing_user:
            if existing_user.email == email:
                raise ValidationError("Email already registered")
            else:
                raise ValidationError("Username already taken")
        
        # Create new user
        user = User(
            email=email,
            username=username,
            password_hash=self.get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            role=role,
            agency_id=agency_id,
            is_active=True,
            is_verified=False
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user
    
    async def authenticate_user(
        self,
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """Authenticate a user with email and password."""
        stmt = select(User).where(User.email == email)
        user = await db.scalar(stmt)
        
        if not user:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")
        
        # Update last login
        user.last_login_at = datetime.utcnow()
        await db.commit()
        
        return user
    
    async def get_user_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        stmt = select(User).where(User.id == user_id)
        return await db.scalar(stmt)
    
    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email."""
        stmt = select(User).where(User.email == email)
        return await db.scalar(stmt)
    
    async def create_session(
        self,
        db: AsyncSession,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, str]:
        """Create a new session for a user."""
        # Create tokens
        access_token = self.create_access_token({"sub": str(user.id)})
        refresh_token = self.create_refresh_token({"sub": str(user.id)})
        
        # Create session record
        session = Session(
            user_id=user.id,
            token=access_token,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            refresh_expires_at=datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            is_active=True
        )
        
        db.add(session)
        await db.commit()
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    async def get_current_user(
        self,
        db: AsyncSession,
        token: str
    ) -> User:
        """Get the current user from a token."""
        try:
            payload = self.decode_token(token)
            user_id = payload.get("sub")
            if user_id is None:
                raise AuthenticationError("Invalid token")
            
            # Check if session exists and is active
            stmt = select(Session).where(
                and_(
                    Session.token == token,
                    Session.is_active == True,
                    Session.expires_at > datetime.utcnow()
                )
            )
            session = await db.scalar(stmt)
            
            if not session:
                raise AuthenticationError("Session expired or invalid")
            
            # Update last activity
            session.last_activity_at = datetime.utcnow()
            await db.commit()
            
            # Get user
            user = await self.get_user_by_id(db, int(user_id))
            if not user:
                raise AuthenticationError("User not found")
            
            if not user.is_active:
                raise AuthenticationError("Account is deactivated")
            
            return user
            
        except JWTError:
            raise AuthenticationError("Invalid token")
    
    async def refresh_access_token(
        self,
        db: AsyncSession,
        refresh_token: str
    ) -> Dict[str, str]:
        """Refresh an access token using a refresh token."""
        try:
            payload = self.decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")
            
            user_id = payload.get("sub")
            if user_id is None:
                raise AuthenticationError("Invalid token")
            
            # Check if session exists
            stmt = select(Session).where(
                and_(
                    Session.refresh_token == refresh_token,
                    Session.is_active == True,
                    Session.refresh_expires_at > datetime.utcnow()
                )
            )
            session = await db.scalar(stmt)
            
            if not session:
                raise AuthenticationError("Session expired or invalid")
            
            # Get user
            user = await self.get_user_by_id(db, int(user_id))
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
            
            # Create new access token
            new_access_token = self.create_access_token({"sub": str(user.id)})
            
            # Update session
            session.token = new_access_token
            session.expires_at = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
            session.last_activity_at = datetime.utcnow()
            
            await db.commit()
            
            return {
                "access_token": new_access_token,
                "token_type": "bearer"
            }
            
        except JWTError:
            raise AuthenticationError("Invalid token")
    
    async def logout(
        self,
        db: AsyncSession,
        token: str
    ) -> bool:
        """Logout a user by invalidating their session."""
        stmt = select(Session).where(
            and_(
                Session.token == token,
                Session.is_active == True
            )
        )
        session = await db.scalar(stmt)
        
        if session:
            session.is_active = False
            await db.commit()
            return True
        
        return False
    
    async def logout_all_sessions(
        self,
        db: AsyncSession,
        user_id: int
    ) -> int:
        """Logout all sessions for a user."""
        stmt = select(Session).where(
            and_(
                Session.user_id == user_id,
                Session.is_active == True
            )
        )
        sessions = await db.scalars(stmt)
        
        count = 0
        for session in sessions:
            session.is_active = False
            count += 1
        
        await db.commit()
        return count
    
    async def change_password(
        self,
        db: AsyncSession,
        user: User,
        old_password: str,
        new_password: str
    ) -> bool:
        """Change a user's password."""
        if not self.verify_password(old_password, user.password_hash):
            raise ValidationError("Incorrect current password")
        
        user.password_hash = self.get_password_hash(new_password)
        await db.commit()
        
        # Invalidate all sessions
        await self.logout_all_sessions(db, user.id)
        
        return True
    
    async def reset_password(
        self,
        db: AsyncSession,
        user: User,
        new_password: str
    ) -> bool:
        """Reset a user's password (admin action or forgot password)."""
        user.password_hash = self.get_password_hash(new_password)
        await db.commit()
        
        # Invalidate all sessions
        await self.logout_all_sessions(db, user.id)
        
        return True


# Global auth service instance
auth_service = AuthService()