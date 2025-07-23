"""
Agency profile management service.
"""
from typing import Optional, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import re

from backend.modules.whitelabel.domain.models import AgencyProfile
from backend.modules.whitelabel.domain.schemas import (
    AgencyProfileCreate,
    AgencyProfileUpdate,
    AgencyProfileResponse
)
from backend.core.exceptions import NotFoundException, BadRequestException
from backend.modules.auth.domain.models import Agency


class AgencyProfileService:
    """Service for managing agency profiles."""
    
    async def get_agency_profile(
        self,
        agency_id: UUID,
        db: AsyncSession
    ) -> Optional[AgencyProfileResponse]:
        """Get agency profile."""
        result = await db.execute(
            select(AgencyProfile)
            .filter(AgencyProfile.agency_id == agency_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            return None
        
        return AgencyProfileResponse.from_orm(profile)
    
    async def create_agency_profile(
        self,
        agency_id: UUID,
        profile_data: AgencyProfileCreate,
        db: AsyncSession
    ) -> AgencyProfileResponse:
        """Create agency profile."""
        # Check if profile already exists
        existing = await self.get_agency_profile(agency_id, db)
        if existing:
            raise BadRequestException("Agency profile already exists")
        
        # Verify agency exists
        agency_result = await db.execute(
            select(Agency).filter(Agency.id == agency_id)
        )
        if not agency_result.scalar_one_or_none():
            raise NotFoundException("Agency not found")
        
        # Validate data
        await self._validate_profile_data(profile_data)
        
        # Create profile
        profile = AgencyProfile(
            agency_id=agency_id,
            display_name=profile_data.display_name,
            tagline=profile_data.tagline,
            description=profile_data.description,
            support_email=profile_data.support_email,
            support_phone=profile_data.support_phone,
            website_url=str(profile_data.website_url) if profile_data.website_url else None,
            social_links=profile_data.social_links.dict() if profile_data.social_links else {},
            legal_name=profile_data.legal_name,
            tax_id=profile_data.tax_id,
            address=profile_data.address.dict() if profile_data.address else None,
            from_email_name=profile_data.from_email_name,
            from_email_address=profile_data.from_email_address,
            reply_to_email=profile_data.reply_to_email
        )
        
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        
        return AgencyProfileResponse.from_orm(profile)
    
    async def update_agency_profile(
        self,
        agency_id: UUID,
        profile_update: AgencyProfileUpdate,
        db: AsyncSession
    ) -> AgencyProfileResponse:
        """Update agency profile."""
        result = await db.execute(
            select(AgencyProfile)
            .filter(AgencyProfile.agency_id == agency_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise NotFoundException("Agency profile not found")
        
        # Validate update data
        await self._validate_profile_data(profile_update, is_update=True)
        
        # Update fields
        update_data = profile_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field == "website_url" and value:
                setattr(profile, field, str(value))
            elif field == "social_links" and value:
                setattr(profile, field, value.dict())
            elif field == "address" and value:
                setattr(profile, field, value.dict())
            else:
                setattr(profile, field, value)
        
        await db.commit()
        await db.refresh(profile)
        
        return AgencyProfileResponse.from_orm(profile)
    
    async def delete_agency_profile(
        self,
        agency_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Delete agency profile."""
        result = await db.execute(
            select(AgencyProfile)
            .filter(AgencyProfile.agency_id == agency_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise NotFoundException("Agency profile not found")
        
        await db.delete(profile)
        await db.commit()
        
        return True
    
    async def verify_custom_domain(
        self,
        agency_id: UUID,
        domain: str,
        db: AsyncSession
    ) -> bool:
        """Verify custom domain ownership."""
        # Validate domain format
        domain_pattern = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        if not domain_pattern.match(domain):
            raise BadRequestException("Invalid domain format")
        
        # Get profile
        result = await db.execute(
            select(AgencyProfile)
            .filter(AgencyProfile.agency_id == agency_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise NotFoundException("Agency profile not found")
        
        # Check if domain is already in use
        existing = await db.execute(
            select(AgencyProfile)
            .filter(
                AgencyProfile.custom_domain == domain,
                AgencyProfile.agency_id != agency_id
            )
        )
        if existing.scalar_one_or_none():
            raise BadRequestException("Domain is already in use")
        
        # In production, implement actual domain verification
        # For now, just update the domain
        profile.custom_domain = domain
        profile.custom_domain_verified = False  # Would be True after verification
        
        await db.commit()
        
        return True
    
    async def _validate_profile_data(
        self,
        data: Union[AgencyProfileCreate, AgencyProfileUpdate],
        is_update: bool = False
    ):
        """Validate profile data."""
        # Validate phone number format
        if hasattr(data, 'support_phone') and data.support_phone:
            phone_pattern = re.compile(r'^\+?[1-9]\d{1,14}$')
            if not phone_pattern.match(data.support_phone):
                raise BadRequestException("Invalid phone number format")
        
        # Validate social links
        if hasattr(data, 'social_links') and data.social_links:
            allowed_platforms = {
                'twitter', 'instagram', 'tiktok', 
                'youtube', 'facebook', 'linkedin', 'website'
            }
            for platform in data.social_links.dict().keys():
                if platform not in allowed_platforms:
                    raise BadRequestException(f"Invalid social platform: {platform}")
        
        # Validate email addresses
        if hasattr(data, 'from_email_address') and data.from_email_address:
            # Email validation is handled by Pydantic EmailStr
            pass
        
        # Validate address
        if hasattr(data, 'address') and data.address:
            if not is_update or data.address:
                if not data.address.street or not data.address.city or not data.address.zip_code:
                    raise BadRequestException("Incomplete address information")