"""
Feature flag system for OAuth migration.
Allows gradual rollout and emergency killswitch.
"""
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timezone
from enum import Enum
import logging
import json
from pathlib import Path
import redis.asyncio as redis

from core.config import settings

logger = logging.getLogger(__name__)


class FeatureFlag(str, Enum):
    """Available feature flags."""
    
    # OAuth features
    OAUTH_ENABLED = "oauth_enabled"
    OAUTH_AUTHORIZATION_CODE = "oauth_authorization_code"
    OAUTH_CLIENT_CREDENTIALS = "oauth_client_credentials"
    OAUTH_REFRESH_TOKEN = "oauth_refresh_token"
    OAUTH_PKCE_REQUIRED = "oauth_pkce_required"
    OAUTH_EXTERNAL_PROVIDERS = "oauth_external_providers"
    
    # JWT features (for backward compatibility)
    JWT_FALLBACK = "jwt_fallback"
    JWT_DISABLED = "jwt_disabled"
    
    # Migration features
    MIGRATION_IN_PROGRESS = "migration_in_progress"
    MIGRATION_COMPLETE = "migration_complete"
    
    # Security features
    RATE_LIMITING_ENABLED = "rate_limiting_enabled"
    CSRF_PROTECTION_ENABLED = "csrf_protection_enabled"
    GEO_BLOCKING_ENABLED = "geo_blocking_enabled"


class RolloutStrategy(str, Enum):
    """Rollout strategies for features."""
    
    ALL = "all"  # Enable for all
    NONE = "none"  # Disable for all
    PERCENTAGE = "percentage"  # Enable for X% of users/agencies
    WHITELIST = "whitelist"  # Enable for specific agencies
    BLACKLIST = "blacklist"  # Disable for specific agencies
    GRADUAL = "gradual"  # Gradual rollout over time


class FeatureFlagManager:
    """
    Manages feature flags for OAuth migration.
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        config_file: Optional[Path] = None
    ):
        """
        Initialize feature flag manager.
        
        Args:
            redis_client: Redis client for distributed flags
            config_file: Path to configuration file
        """
        self.redis_client = redis_client
        self.config_file = config_file or Path("feature_flags.json")
        
        # Default flag configurations
        self.default_flags = {
            FeatureFlag.OAUTH_ENABLED: {
                "enabled": True,
                "strategy": RolloutStrategy.PERCENTAGE,
                "percentage": 100,  # Start with 100% for new deployments
                "whitelist": [],
                "blacklist": [],
                "description": "Enable OAuth2.0 authentication"
            },
            FeatureFlag.OAUTH_AUTHORIZATION_CODE: {
                "enabled": True,
                "strategy": RolloutStrategy.ALL,
                "description": "Enable authorization code grant"
            },
            FeatureFlag.OAUTH_CLIENT_CREDENTIALS: {
                "enabled": True,
                "strategy": RolloutStrategy.ALL,
                "description": "Enable client credentials grant for M2M"
            },
            FeatureFlag.OAUTH_REFRESH_TOKEN: {
                "enabled": True,
                "strategy": RolloutStrategy.ALL,
                "description": "Enable refresh token grant"
            },
            FeatureFlag.OAUTH_PKCE_REQUIRED: {
                "enabled": True,
                "strategy": RolloutStrategy.ALL,
                "description": "Require PKCE for authorization code grant"
            },
            FeatureFlag.OAUTH_EXTERNAL_PROVIDERS: {
                "enabled": True,
                "strategy": RolloutStrategy.WHITELIST,
                "whitelist": ["google", "instagram", "microsoft"],
                "description": "Enable external OAuth providers"
            },
            FeatureFlag.JWT_FALLBACK: {
                "enabled": True,
                "strategy": RolloutStrategy.ALL,
                "description": "Allow JWT authentication as fallback"
            },
            FeatureFlag.JWT_DISABLED: {
                "enabled": False,
                "strategy": RolloutStrategy.NONE,
                "description": "Disable JWT authentication completely"
            },
            FeatureFlag.MIGRATION_IN_PROGRESS: {
                "enabled": False,
                "strategy": RolloutStrategy.ALL,
                "description": "Migration is currently in progress"
            },
            FeatureFlag.MIGRATION_COMPLETE: {
                "enabled": False,
                "strategy": RolloutStrategy.ALL,
                "description": "Migration has been completed"
            },
            FeatureFlag.RATE_LIMITING_ENABLED: {
                "enabled": True,
                "strategy": RolloutStrategy.ALL,
                "description": "Enable rate limiting"
            },
            FeatureFlag.CSRF_PROTECTION_ENABLED: {
                "enabled": True,
                "strategy": RolloutStrategy.ALL,
                "description": "Enable CSRF protection"
            },
            FeatureFlag.GEO_BLOCKING_ENABLED: {
                "enabled": True,
                "strategy": RolloutStrategy.ALL,
                "description": "Enable geo-blocking"
            }
        }
        
        # Load configuration from file if exists
        self.flags = self._load_configuration()
    
    def _load_configuration(self) -> Dict[str, Any]:
        """
        Load feature flag configuration from file.
        
        Returns:
            Configuration dictionary
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    loaded = json.load(f)
                    
                # Merge with defaults
                flags = self.default_flags.copy()
                for flag_name, config in loaded.items():
                    if flag_name in flags:
                        flags[flag_name].update(config)
                    else:
                        flags[flag_name] = config
                
                logger.info(f"Loaded feature flags from {self.config_file}")
                return flags
                
            except Exception as e:
                logger.error(f"Failed to load feature flags: {e}")
        
        return self.default_flags.copy()
    
    def save_configuration(self) -> None:
        """
        Save current configuration to file.
        """
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.flags, f, indent=2, default=str)
            
            logger.info(f"Saved feature flags to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save feature flags: {e}")
    
    async def is_enabled(
        self,
        flag: FeatureFlag,
        agency_id: Optional[str] = None,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag: Feature flag to check
            agency_id: Agency ID for agency-specific flags
            user_id: User ID for user-specific flags
            context: Additional context for evaluation
            
        Returns:
            True if feature is enabled
        """
        # Check Redis for override
        if self.redis_client:
            try:
                override = await self.redis_client.get(f"feature_flag:{flag}")
                if override is not None:
                    return override.lower() == "true"
            except Exception as e:
                logger.error(f"Failed to check Redis for flag {flag}: {e}")
        
        # Get flag configuration
        config = self.flags.get(flag, {})
        
        if not config.get("enabled", False):
            return False
        
        strategy = config.get("strategy", RolloutStrategy.ALL)
        
        # Evaluate based on strategy
        if strategy == RolloutStrategy.ALL:
            return True
        
        elif strategy == RolloutStrategy.NONE:
            return False
        
        elif strategy == RolloutStrategy.PERCENTAGE:
            percentage = config.get("percentage", 0)
            if agency_id:
                # Use consistent hashing for agency
                hash_value = hash(agency_id) % 100
                return hash_value < percentage
            return percentage >= 100
        
        elif strategy == RolloutStrategy.WHITELIST:
            whitelist = config.get("whitelist", [])
            if agency_id and agency_id in whitelist:
                return True
            if user_id and user_id in whitelist:
                return True
            # Check external providers
            if flag == FeatureFlag.OAUTH_EXTERNAL_PROVIDERS and context:
                provider = context.get("provider")
                return provider in whitelist
            return False
        
        elif strategy == RolloutStrategy.BLACKLIST:
            blacklist = config.get("blacklist", [])
            if agency_id and agency_id in blacklist:
                return False
            if user_id and user_id in blacklist:
                return False
            return True
        
        elif strategy == RolloutStrategy.GRADUAL:
            # Gradual rollout based on time
            start_date = config.get("start_date")
            end_date = config.get("end_date")
            
            if start_date and end_date:
                now = datetime.now(timezone.utc)
                start = datetime.fromisoformat(start_date)
                end = datetime.fromisoformat(end_date)
                
                if now < start:
                    return False
                elif now > end:
                    return True
                else:
                    # Calculate percentage based on time
                    total_duration = (end - start).total_seconds()
                    elapsed = (now - start).total_seconds()
                    percentage = (elapsed / total_duration) * 100
                    
                    if agency_id:
                        hash_value = hash(agency_id) % 100
                        return hash_value < percentage
            
            return True
        
        return False
    
    async def enable_flag(
        self,
        flag: FeatureFlag,
        strategy: Optional[RolloutStrategy] = None,
        **kwargs
    ) -> None:
        """
        Enable a feature flag.
        
        Args:
            flag: Feature flag to enable
            strategy: Rollout strategy
            **kwargs: Additional configuration
        """
        if flag not in self.flags:
            self.flags[flag] = {}
        
        self.flags[flag]["enabled"] = True
        
        if strategy:
            self.flags[flag]["strategy"] = strategy
        
        # Update additional configuration
        self.flags[flag].update(kwargs)
        
        # Save to Redis if available
        if self.redis_client:
            try:
                await self.redis_client.set(
                    f"feature_flag:{flag}",
                    "true",
                    ex=3600  # 1 hour cache
                )
            except Exception as e:
                logger.error(f"Failed to update Redis flag {flag}: {e}")
        
        # Save to file
        self.save_configuration()
        
        logger.info(f"Enabled feature flag: {flag}")
    
    async def disable_flag(self, flag: FeatureFlag) -> None:
        """
        Disable a feature flag (emergency killswitch).
        
        Args:
            flag: Feature flag to disable
        """
        if flag not in self.flags:
            self.flags[flag] = {}
        
        self.flags[flag]["enabled"] = False
        
        # Save to Redis if available
        if self.redis_client:
            try:
                await self.redis_client.set(
                    f"feature_flag:{flag}",
                    "false",
                    ex=3600  # 1 hour cache
                )
            except Exception as e:
                logger.error(f"Failed to update Redis flag {flag}: {e}")
        
        # Save to file
        self.save_configuration()
        
        logger.warning(f"DISABLED feature flag: {flag}")
    
    async def set_rollout_percentage(
        self,
        flag: FeatureFlag,
        percentage: int
    ) -> None:
        """
        Set rollout percentage for a flag.
        
        Args:
            flag: Feature flag
            percentage: Rollout percentage (0-100)
        """
        if flag not in self.flags:
            self.flags[flag] = {}
        
        self.flags[flag]["strategy"] = RolloutStrategy.PERCENTAGE
        self.flags[flag]["percentage"] = max(0, min(100, percentage))
        
        self.save_configuration()
        
        logger.info(f"Set {flag} rollout to {percentage}%")
    
    async def add_to_whitelist(
        self,
        flag: FeatureFlag,
        identifier: str
    ) -> None:
        """
        Add agency/user to whitelist.
        
        Args:
            flag: Feature flag
            identifier: Agency or user ID
        """
        if flag not in self.flags:
            self.flags[flag] = {}
        
        if "whitelist" not in self.flags[flag]:
            self.flags[flag]["whitelist"] = []
        
        if identifier not in self.flags[flag]["whitelist"]:
            self.flags[flag]["whitelist"].append(identifier)
            self.save_configuration()
            logger.info(f"Added {identifier} to {flag} whitelist")
    
    async def remove_from_whitelist(
        self,
        flag: FeatureFlag,
        identifier: str
    ) -> None:
        """
        Remove agency/user from whitelist.
        
        Args:
            flag: Feature flag
            identifier: Agency or user ID
        """
        if flag in self.flags and "whitelist" in self.flags[flag]:
            if identifier in self.flags[flag]["whitelist"]:
                self.flags[flag]["whitelist"].remove(identifier)
                self.save_configuration()
                logger.info(f"Removed {identifier} from {flag} whitelist")
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get current status of all feature flags.
        
        Returns:
            Status dictionary
        """
        status = {}
        
        for flag_name, config in self.flags.items():
            status[flag_name] = {
                "enabled": config.get("enabled", False),
                "strategy": config.get("strategy", RolloutStrategy.ALL),
                "description": config.get("description", ""),
            }
            
            # Add strategy-specific info
            strategy = config.get("strategy")
            if strategy == RolloutStrategy.PERCENTAGE:
                status[flag_name]["percentage"] = config.get("percentage", 0)
            elif strategy == RolloutStrategy.WHITELIST:
                status[flag_name]["whitelist_count"] = len(config.get("whitelist", []))
            elif strategy == RolloutStrategy.BLACKLIST:
                status[flag_name]["blacklist_count"] = len(config.get("blacklist", []))
        
        return status
    
    async def emergency_killswitch(self) -> None:
        """
        Emergency killswitch - disable OAuth and enable JWT fallback.
        """
        logger.critical("EMERGENCY KILLSWITCH ACTIVATED!")
        
        # Disable OAuth
        await self.disable_flag(FeatureFlag.OAUTH_ENABLED)
        await self.disable_flag(FeatureFlag.OAUTH_EXTERNAL_PROVIDERS)
        
        # Enable JWT fallback
        await self.enable_flag(FeatureFlag.JWT_FALLBACK, RolloutStrategy.ALL)
        
        # Disable JWT disabled flag
        await self.disable_flag(FeatureFlag.JWT_DISABLED)
        
        logger.critical("OAuth disabled, JWT fallback enabled")


# Global feature flag manager instance
_feature_flags: Optional[FeatureFlagManager] = None


def get_feature_flags() -> FeatureFlagManager:
    """
    Get global feature flag manager instance.
    
    Returns:
        Feature flag manager
    """
    global _feature_flags
    
    if _feature_flags is None:
        # Initialize with Redis if available
        redis_client = None
        if hasattr(settings, "REDIS_URL"):
            try:
                import asyncio
                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for feature flags: {e}")
        
        _feature_flags = FeatureFlagManager(redis_client=redis_client)
    
    return _feature_flags


async def check_feature(
    flag: FeatureFlag,
    agency_id: Optional[str] = None,
    user_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Convenience function to check if a feature is enabled.
    
    Args:
        flag: Feature flag to check
        agency_id: Agency ID
        user_id: User ID
        context: Additional context
        
    Returns:
        True if feature is enabled
    """
    manager = get_feature_flags()
    return await manager.is_enabled(flag, agency_id, user_id, context)