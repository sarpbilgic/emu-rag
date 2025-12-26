from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import logging
from jose import jwt, JWTError
from passlib.context import CryptContext 
from fastapi import HTTPException

from src.core.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

ALLOWED_EMAIL_DOMAIN = "@emu.edu.tr"


class AuthService:
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_access_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None

    @staticmethod
    def extract_email_from_token(decoded_token: Dict[str, Any]) -> Optional[str]:
        return (
            decoded_token.get('email') or 
            decoded_token.get('preferred_username') or 
            decoded_token.get('upn') or 
            decoded_token.get('unique_name')
        )

    @staticmethod
    def extract_user_info_from_token(decoded_token: Dict[str, Any]) -> Dict[str, Optional[str]]:
        return {
            "user_id": decoded_token.get('oid') or decoded_token.get('sub'),
            "display_name": decoded_token.get('name'),
            "first_name": decoded_token.get('given_name'),
            "last_name": decoded_token.get('family_name'),
        }

    @staticmethod
    def extract_user_info_from_sso_user_data(user_data) -> Dict[str, Optional[str]]:
        return {
            "email": user_data.email,
            "user_id": user_data.id,
            "display_name": user_data.display_name,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
        }

    @staticmethod
    def validate_emu_email(email: str) -> None:
        if not email or not email.lower().endswith(ALLOWED_EMAIL_DOMAIN.lower()):
            logger.warning(f"Login attempt with non-EMU email: {email}")
            raise HTTPException(
                status_code=403, 
                detail="Only EMU students and staff can login"
            )
