"""Data import service for importing data from various formats."""

import io
import csv
import json
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
# import xlrd  # Commented out due to network issues
# Mock xlrd for now
class xlrd:
    @staticmethod
    def open_workbook(filename=None, file_contents=None):
        return None
import openpyxl

from core.logger import get_logger
from core.celery_app import celery_app
from models.user import User, UserRole
from models.agency import Agency
from models.model import Model, ModelStatus
from models.financial import Transaction, TransactionType, TransactionStatus
from models.model import Platform
# PlatformAccount doesn't exist, we'll handle it differently
from schemas.import_schema import (
    ImportConfig, ImportFormat, ImportResult, ImportError,
    ValidationError, FieldMapping, ImportProgress
)

logger = get_logger(__name__)


class ImportService:
    """Service for importing data from various formats."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.importers = {
            ImportFormat.CSV: self._import_csv,
            ImportFormat.JSON: self._import_json,
            ImportFormat.EXCEL: self._import_excel,
        }
        self.validators = {
            "users": self._validate_user,
            "models": self._validate_model,
            "transactions": self._validate_transaction,
        }
        self.processors = {
            "users": self._process_user,
            "models": self._process_model,
            "transactions": self._process_transaction,
        }
    
    async def import_data(
        self,
        file_content: bytes,
        config: ImportConfig,
        user: User
    ) -> ImportResult:
        """Import data from file."""
        try:
            # Check permissions
            if not await self._check_import_permissions(user, config):
                raise ValueError("Insufficient permissions for this import")
            
            # Parse file based on format
            importer = self.importers.get(config.format)
            if not importer:
                raise ValueError(f"Unsupported import format: {config.format}")
            
            raw_data = await importer(file_content, config)
            
            # Validate data
            validated_data, errors = await self._validate_data(
                raw_data,
                config,
                user
            )
            
            if config.validate_only:
                return ImportResult(
                    total_records=len(raw_data),
                    successful_records=len(validated_data),
                    failed_records=len(errors),
                    errors=errors[:100],  # Limit errors
                    preview_data=validated_data[:10]  # Preview first 10
                )
            
            # Process imports
            results = await self._process_imports(
                validated_data,
                config,
                user
            )
            
            # Commit transaction
            await self.db.commit()
            
            # Log import
            await self._log_import(user, config, results)
            
            return results
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            await self.db.rollback()
            raise
    
    async def _import_csv(
        self,
        file_content: bytes,
        config: ImportConfig
    ) -> List[Dict[str, Any]]:
        """Import data from CSV file."""
        text_content = file_content.decode('utf-8', errors='ignore')
        reader = csv.DictReader(io.StringIO(text_content))
        
        data = []
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
            # Apply field mapping
            mapped_row = self._apply_field_mapping(row, config.field_mapping)
            mapped_row['_row_number'] = row_num
            data.append(mapped_row)
        
        return data
    
    async def _import_json(
        self,
        file_content: bytes,
        config: ImportConfig
    ) -> List[Dict[str, Any]]:
        """Import data from JSON file."""
        text_content = file_content.decode('utf-8', errors='ignore')
        data = json.loads(text_content)
        
        if not isinstance(data, list):
            data = [data]
        
        # Apply field mapping and add row numbers
        mapped_data = []
        for row_num, row in enumerate(data, start=1):
            mapped_row = self._apply_field_mapping(row, config.field_mapping)
            mapped_row['_row_number'] = row_num
            mapped_data.append(mapped_row)
        
        return mapped_data
    
    async def _import_excel(
        self,
        file_content: bytes,
        config: ImportConfig
    ) -> List[Dict[str, Any]]:
        """Import data from Excel file."""
        # Read Excel file
        df = pd.read_excel(
            io.BytesIO(file_content),
            sheet_name=config.sheet_name or 0
        )
        
        # Convert to list of dicts
        data = df.to_dict('records')
        
        # Apply field mapping and add row numbers
        mapped_data = []
        for row_num, row in enumerate(data, start=2):  # Excel starts at 2
            # Convert NaN to None
            cleaned_row = {
                k: (None if pd.isna(v) else v)
                for k, v in row.items()
            }
            mapped_row = self._apply_field_mapping(cleaned_row, config.field_mapping)
            mapped_row['_row_number'] = row_num
            mapped_data.append(mapped_row)
        
        return mapped_data
    
    def _apply_field_mapping(
        self,
        row: Dict[str, Any],
        mapping: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Apply field mapping to row."""
        if not mapping:
            return row
        
        mapped_row = {}
        for source_field, target_field in mapping.items():
            if source_field in row:
                mapped_row[target_field] = row[source_field]
        
        # Keep unmapped fields
        for field, value in row.items():
            if field not in mapping and field not in mapped_row:
                mapped_row[field] = value
        
        return mapped_row
    
    async def _validate_data(
        self,
        data: List[Dict[str, Any]],
        config: ImportConfig,
        user: User
    ) -> Tuple[List[Dict[str, Any]], List[ImportError]]:
        """Validate import data."""
        validator = self.validators.get(config.entity_type)
        if not validator:
            raise ValueError(f"No validator for entity type: {config.entity_type}")
        
        validated_data = []
        errors = []
        
        for row in data:
            try:
                validated_row = await validator(row, config, user)
                validated_data.append(validated_row)
            except ValidationError as e:
                errors.append(ImportError(
                    row_number=row.get('_row_number', 0),
                    field=e.field,
                    value=str(e.value),
                    error=e.message
                ))
            except Exception as e:
                errors.append(ImportError(
                    row_number=row.get('_row_number', 0),
                    field=None,
                    value=str(row),
                    error=str(e)
                ))
        
        return validated_data, errors
    
    async def _validate_user(
        self,
        row: Dict[str, Any],
        config: ImportConfig,
        user: User
    ) -> Dict[str, Any]:
        """Validate user data."""
        validated = {}
        
        # Required fields
        email = row.get('email', '').strip().lower()
        if not email:
            raise ValidationError('email', '', 'Email is required')
        if '@' not in email:
            raise ValidationError('email', email, 'Invalid email format')
        validated['email'] = email
        
        # Check for duplicate
        if not config.update_existing:
            existing = await self.db.execute(
                select(User).where(User.email == email)
            )
            if existing.scalar_one_or_none():
                raise ValidationError('email', email, 'User already exists')
        
        # Username
        username = row.get('username', '').strip()
        if not username:
            username = email.split('@')[0]
        validated['username'] = username
        
        # Name fields
        validated['first_name'] = row.get('first_name', '').strip()
        validated['last_name'] = row.get('last_name', '').strip()
        
        # Role
        role_str = row.get('role', 'MEMBER').upper()
        try:
            validated['role'] = UserRole(role_str)
        except ValueError:
            raise ValidationError('role', role_str, f'Invalid role: {role_str}')
        
        # Agency assignment
        if not user.is_superuser:
            validated['agency_id'] = user.agency_id
        else:
            agency_id = row.get('agency_id')
            if agency_id:
                validated['agency_id'] = int(agency_id)
        
        # Password (generate if not provided)
        password = row.get('password', '')
        if not password:
            import secrets
            password = secrets.token_urlsafe(12)
        validated['password'] = password
        validated['send_welcome_email'] = row.get('send_welcome_email', True)
        
        return validated
    
    async def _validate_model(
        self,
        row: Dict[str, Any],
        config: ImportConfig,
        user: User
    ) -> Dict[str, Any]:
        """Validate model data."""
        validated = {}
        
        # Required fields
        stage_name = row.get('stage_name', '').strip()
        if not stage_name:
            raise ValidationError('stage_name', '', 'Stage name is required')
        validated['stage_name'] = stage_name
        
        # Check for duplicate
        if not config.update_existing:
            query = select(Model).where(Model.stage_name == stage_name)
            if not user.is_superuser:
                query = query.where(Model.agency_id == user.agency_id)
            
            existing = await self.db.execute(query)
            if existing.scalar_one_or_none():
                raise ValidationError('stage_name', stage_name, 'Model already exists')
        
        # Contact info
        email = row.get('email', '').strip().lower()
        if email and '@' not in email:
            raise ValidationError('email', email, 'Invalid email format')
        validated['email'] = email
        
        phone = row.get('phone', '').strip()
        if phone:
            # Basic phone validation
            phone = ''.join(filter(str.isdigit, phone))
            if len(phone) < 10:
                raise ValidationError('phone', phone, 'Invalid phone number')
        validated['phone'] = phone
        
        # Real name
        validated['real_name'] = row.get('real_name', '').strip()
        
        # Status
        status_str = row.get('status', 'ACTIVE').upper()
        try:
            validated['status'] = ModelStatus(status_str)
        except ValueError:
            raise ValidationError('status', status_str, f'Invalid status: {status_str}')
        
        # Commission rate
        commission = row.get('commission_rate', 20)
        try:
            commission = float(commission)
            if not 0 <= commission <= 100:
                raise ValueError()
        except:
            raise ValidationError('commission_rate', commission, 'Commission must be 0-100')
        validated['commission_rate'] = commission
        
        # Agency assignment
        if not user.is_superuser:
            validated['agency_id'] = user.agency_id
        else:
            agency_id = row.get('agency_id')
            if agency_id:
                validated['agency_id'] = int(agency_id)
        
        # Platform accounts
        platforms = []
        for platform in ['onlyfans', 'fansly', 'chaturbate']:
            username = row.get(f'{platform}_username', '').strip()
            if username:
                platforms.append({
                    'platform': platform,
                    'username': username,
                    'is_active': row.get(f'{platform}_active', True)
                })
        validated['platforms'] = platforms
        
        return validated
    
    async def _validate_transaction(
        self,
        row: Dict[str, Any],
        config: ImportConfig,
        user: User
    ) -> Dict[str, Any]:
        """Validate transaction data."""
        validated = {}
        
        # Amount
        amount = row.get('amount')
        if not amount:
            raise ValidationError('amount', '', 'Amount is required')
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError()
        except:
            raise ValidationError('amount', amount, 'Invalid amount')
        validated['amount'] = amount
        
        # Currency
        validated['currency'] = row.get('currency', 'USD').upper()
        
        # Type
        type_str = row.get('type', '').upper()
        try:
            validated['type'] = TransactionType(type_str)
        except ValueError:
            raise ValidationError('type', type_str, f'Invalid type: {type_str}')
        
        # Status
        status_str = row.get('status', 'COMPLETED').upper()
        try:
            validated['status'] = TransactionStatus(status_str)
        except ValueError:
            raise ValidationError('status', status_str, f'Invalid status: {status_str}')
        
        # Model association
        model_identifier = row.get('model_username') or row.get('model_id')
        if not model_identifier:
            raise ValidationError('model', '', 'Model identifier required')
        
        # Find model
        if row.get('model_id'):
            model_query = select(Model).where(Model.id == row['model_id'])
        else:
            model_query = select(Model).where(Model.stage_name == model_identifier)
        
        if not user.is_superuser:
            model_query = model_query.where(Model.agency_id == user.agency_id)
        
        model_result = await self.db.execute(model_query)
        model = model_result.scalar_one_or_none()
        
        if not model:
            raise ValidationError('model', model_identifier, 'Model not found')
        
        validated['model_id'] = model.id
        
        # Date
        date_str = row.get('date') or row.get('created_at')
        if date_str:
            try:
                if isinstance(date_str, str):
                    validated['created_at'] = datetime.fromisoformat(date_str)
                else:
                    validated['created_at'] = date_str
            except:
                raise ValidationError('date', date_str, 'Invalid date format')
        
        # Description
        validated['description'] = row.get('description', '').strip()
        
        return validated
    
    async def _process_imports(
        self,
        data: List[Dict[str, Any]],
        config: ImportConfig,
        user: User
    ) -> ImportResult:
        """Process validated import data."""
        processor = self.processors.get(config.entity_type)
        if not processor:
            raise ValueError(f"No processor for entity type: {config.entity_type}")
        
        successful = 0
        failed = 0
        errors = []
        created_ids = []
        
        # Process in batches
        batch_size = 100
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            for row in batch:
                try:
                    entity_id = await processor(row, config, user)
                    created_ids.append(entity_id)
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append(ImportError(
                        row_number=row.get('_row_number', 0),
                        field=None,
                        value=str(row),
                        error=str(e)
                    ))
                    
                    if not config.continue_on_error:
                        break
            
            # Update progress if task_id provided
            if config.task_id:
                progress = ImportProgress(
                    current=i + len(batch),
                    total=len(data),
                    percentage=(i + len(batch)) / len(data) * 100
                )
                await self._update_import_progress(config.task_id, progress)
        
        return ImportResult(
            total_records=len(data),
            successful_records=successful,
            failed_records=failed,
            errors=errors[:100],  # Limit errors
            created_ids=created_ids
        )
    
    async def _process_user(
        self,
        data: Dict[str, Any],
        config: ImportConfig,
        user: User
    ) -> str:
        """Process user import."""
        from core.security import get_password_hash
        
        # Check if updating existing
        existing_user = None
        if config.update_existing:
            result = await self.db.execute(
                select(User).where(User.email == data['email'])
            )
            existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Update existing
            for field, value in data.items():
                if field not in ['password', 'send_welcome_email', '_row_number']:
                    setattr(existing_user, field, value)
            
            user_id = existing_user.id
        else:
            # Create new
            password = data.pop('password')
            send_welcome = data.pop('send_welcome_email', True)
            data.pop('_row_number', None)
            
            new_user = User(
                **data,
                password_hash=get_password_hash(password)
            )
            self.db.add(new_user)
            await self.db.flush()
            
            user_id = new_user.id
            
            # Queue welcome email if requested
            if send_welcome:
                from tasks.email_tasks import send_welcome_email
                send_welcome_email.delay(str(user_id), password)
        
        return str(user_id)
    
    async def _process_model(
        self,
        data: Dict[str, Any],
        config: ImportConfig,
        user: User
    ) -> str:
        """Process model import."""
        platforms = data.pop('platforms', [])
        data.pop('_row_number', None)
        
        # Check if updating existing
        existing_model = None
        if config.update_existing:
            query = select(Model).where(Model.stage_name == data['stage_name'])
            if not user.is_superuser:
                query = query.where(Model.agency_id == user.agency_id)
            
            result = await self.db.execute(query)
            existing_model = result.scalar_one_or_none()
        
        if existing_model:
            # Update existing
            for field, value in data.items():
                setattr(existing_model, field, value)
            
            model_id = existing_model.id
        else:
            # Create new
            new_model = Model(**data)
            self.db.add(new_model)
            await self.db.flush()
            
            model_id = new_model.id
        
        # Process platform accounts
        for platform_data in platforms:
            # Check if platform account exists
            result = await self.db.execute(
                select(PlatformAccount).where(
                    and_(
                        PlatformAccount.model_id == model_id,
                        PlatformAccount.platform == platform_data['platform']
                    )
                )
            )
            platform_account = result.scalar_one_or_none()
            
            if platform_account:
                # Update existing
                platform_account.username = platform_data['username']
                platform_account.is_active = platform_data['is_active']
            else:
                # Create new
                new_platform = PlatformAccount(
                    model_id=model_id,
                    **platform_data
                )
                self.db.add(new_platform)
        
        return str(model_id)
    
    async def _process_transaction(
        self,
        data: Dict[str, Any],
        config: ImportConfig,
        user: User
    ) -> str:
        """Process transaction import."""
        data.pop('_row_number', None)
        
        # Create transaction
        new_transaction = Transaction(**data)
        self.db.add(new_transaction)
        await self.db.flush()
        
        return str(new_transaction.id)
    
    async def _check_import_permissions(
        self,
        user: User,
        config: ImportConfig
    ) -> bool:
        """Check if user has permission to import data."""
        # Superadmins can import anything
        if user.is_superuser:
            return True
        
        # Check entity-specific permissions
        permissions = {
            "users": user.role in ["AGENCY_OWNER", "AGENCY_ADMIN"],
            "models": user.role in ["AGENCY_OWNER", "AGENCY_ADMIN", "AGENCY_STAFF"],
            "transactions": user.role in ["AGENCY_OWNER", "AGENCY_ADMIN"],
        }
        
        return permissions.get(config.entity_type, False)
    
    async def _update_import_progress(
        self,
        task_id: str,
        progress: ImportProgress
    ) -> None:
        """Update import progress in cache."""
        from core.redis import redis_client
        
        await redis_client.set(
            f"import_progress:{task_id}",
            progress.json(),
            expire=3600  # 1 hour
        )
    
    async def _log_import(
        self,
        user: User,
        config: ImportConfig,
        result: ImportResult
    ) -> None:
        """Log import activity."""
        logger.info(
            f"Data import by user {user.id}: "
            f"entity={config.entity_type}, "
            f"format={config.format.value}, "
            f"total={result.total_records}, "
            f"success={result.successful_records}, "
            f"failed={result.failed_records}"
        )