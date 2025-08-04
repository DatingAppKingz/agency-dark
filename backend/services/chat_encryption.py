"""Chat encryption service for secure messaging."""

import os
import secrets
import base64
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.encryption import encryption_service, EncryptionService
from core.redis import redis_manager
from core.logger import get_logger
from models.chat import Conversation, Message
from models.user import User
from cryptography.fernet import Fernet

logger = get_logger(__name__)


class ChatEncryptionService:
    """Service for handling encrypted chat messages."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = encryption_service
        self.key_cache_ttl = 3600  # 1 hour
    
    async def encrypt_message(
        self, 
        message: Message,
        enable_e2e: bool = False
    ) -> None:
        """Encrypt a message before saving."""
        if not message.content:
            return
        
        if enable_e2e:
            # End-to-end encryption for sensitive conversations
            key_id = await self._get_or_create_conversation_key(message.conversation_id)
            key = await self._get_encryption_key(key_id)
            
            # Encrypt content with conversation key
            fernet = Fernet(key)
            encrypted = fernet.encrypt(message.content.encode())
            
            message.encrypted_content = base64.urlsafe_b64encode(encrypted).decode()
            message.encryption_key_id = key_id
            message.content = None  # Clear plaintext
        else:
            # Standard encryption with master key
            message.encrypted_content = self.encryption.encrypt(message.content)
            message.content = None  # Clear plaintext
    
    async def decrypt_message(self, message: Message) -> str:
        """Decrypt a message content."""
        if message.content:
            # Not encrypted
            return message.content
        
        if not message.encrypted_content:
            return ""
        
        try:
            if message.encryption_key_id:
                # E2E encrypted
                key = await self._get_encryption_key(message.encryption_key_id)
                fernet = Fernet(key)
                
                decoded = base64.urlsafe_b64decode(message.encrypted_content)
                decrypted = fernet.decrypt(decoded)
                return decrypted.decode()
            else:
                # Standard encryption
                return self.encryption.decrypt(message.encrypted_content)
                
        except Exception as e:
            logger.error(f"Failed to decrypt message {message.id}: {e}")
            return "[Decryption failed]"
    
    async def encrypt_media(
        self,
        file_path: str,
        message: Message
    ) -> str:
        """Encrypt media file and return encrypted file path."""
        try:
            # Generate unique key for this media
            media_key = Fernet.generate_key()
            fernet = Fernet(media_key)
            
            # Read and encrypt file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            encrypted_data = fernet.encrypt(file_data)
            
            # Save encrypted file
            encrypted_path = f"{file_path}.enc"
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Store encrypted key
            message.media_encryption_key = self.encryption.encrypt(
                base64.urlsafe_b64encode(media_key).decode()
            )
            
            # Delete original file
            os.unlink(file_path)
            
            return encrypted_path
            
        except Exception as e:
            logger.error(f"Failed to encrypt media: {e}")
            raise
    
    async def decrypt_media(
        self,
        encrypted_path: str,
        message: Message,
        output_path: str
    ) -> None:
        """Decrypt media file."""
        if not message.media_encryption_key:
            raise ValueError("No encryption key for media")
        
        try:
            # Decrypt the media key
            key_b64 = self.encryption.decrypt(message.media_encryption_key)
            media_key = base64.urlsafe_b64decode(key_b64)
            fernet = Fernet(media_key)
            
            # Read and decrypt file
            with open(encrypted_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Save decrypted file
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)
                
        except Exception as e:
            logger.error(f"Failed to decrypt media: {e}")
            raise
    
    async def _get_or_create_conversation_key(self, conversation_id: int) -> str:
        """Get or create encryption key for a conversation."""
        key_id = f"conv_key_{conversation_id}"
        
        # Check cache
        cached_key = await redis_manager.get(f"enc_key:{key_id}")
        if cached_key:
            return key_id
        
        # Check if key exists in database
        # For this example, we'll store keys in Redis
        # In production, use a proper key management service
        
        # Generate new key
        new_key = Fernet.generate_key()
        
        # Store in Redis with expiration
        await redis_manager.set(
            f"enc_key:{key_id}",
            base64.urlsafe_b64encode(new_key).decode(),
            expire=86400 * 30  # 30 days
        )
        
        logger.info(f"Created new encryption key for conversation {conversation_id}")
        return key_id
    
    async def _get_encryption_key(self, key_id: str) -> bytes:
        """Retrieve encryption key."""
        key_b64 = await redis_manager.get(f"enc_key:{key_id}")
        if not key_b64:
            raise ValueError(f"Encryption key {key_id} not found")
        
        return base64.urlsafe_b64decode(key_b64)
    
    async def rotate_conversation_key(self, conversation_id: int) -> None:
        """Rotate encryption key for a conversation."""
        old_key_id = f"conv_key_{conversation_id}"
        new_key_id = f"conv_key_{conversation_id}_v{int(datetime.utcnow().timestamp())}"
        
        # Get old key
        old_key = await self._get_encryption_key(old_key_id)
        
        # Generate new key
        new_key = Fernet.generate_key()
        
        # Re-encrypt existing messages
        messages = await self.db.execute(
            select(Message).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.encryption_key_id == old_key_id,
                    Message.encrypted_content.isnot(None)
                )
            )
        )
        
        for message in messages.scalars():
            try:
                # Decrypt with old key
                old_fernet = Fernet(old_key)
                decoded = base64.urlsafe_b64decode(message.encrypted_content)
                decrypted = old_fernet.decrypt(decoded)
                
                # Encrypt with new key
                new_fernet = Fernet(new_key)
                encrypted = new_fernet.encrypt(decrypted)
                
                # Update message
                message.encrypted_content = base64.urlsafe_b64encode(encrypted).decode()
                message.encryption_key_id = new_key_id
                
            except Exception as e:
                logger.error(f"Failed to re-encrypt message {message.id}: {e}")
        
        # Store new key
        await redis_manager.set(
            f"enc_key:{new_key_id}",
            base64.urlsafe_b64encode(new_key).decode(),
            expire=86400 * 30  # 30 days
        )
        
        # Delete old key after a grace period
        await redis_manager.expire(f"enc_key:{old_key_id}", 3600)  # 1 hour
        
        await self.db.commit()
        logger.info(f"Rotated encryption key for conversation {conversation_id}")
    
    async def enable_e2e_encryption(self, conversation_id: int) -> None:
        """Enable end-to-end encryption for a conversation."""
        conversation = await self.db.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        
        # Create encryption key
        key_id = await self._get_or_create_conversation_key(conversation_id)
        
        # Update conversation metadata
        if not conversation.conversation_metadata:
            conversation.conversation_metadata = {}
        
        conversation.conversation_metadata["e2e_enabled"] = True
        conversation.conversation_metadata["e2e_key_id"] = key_id
        conversation.conversation_metadata["e2e_enabled_at"] = datetime.utcnow().isoformat()
        
        await self.db.commit()
        logger.info(f"Enabled E2E encryption for conversation {conversation_id}")
    
    async def is_e2e_enabled(self, conversation_id: int) -> bool:
        """Check if E2E encryption is enabled for a conversation."""
        conversation = await self.db.get(Conversation, conversation_id)
        if not conversation or not conversation.conversation_metadata:
            return False
        
        return conversation.conversation_metadata.get("e2e_enabled", False)