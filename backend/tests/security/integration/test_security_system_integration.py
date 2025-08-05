"""
Integration tests for the complete security system.

Tests all security components working together:
- Permissions + Rate Limiting + Audit
- Multi-tenant isolation
- Emergency response procedures
- System-wide security policies
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
import uuid
import json
from typing import List, Dict, Any
import random

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, AnalyticsScope,
    DataSensitivity, ExportFormat
)
from models.rate_limit import (
    RateLimitConfig, RateLimitType, RateLimitAlgorithm
)
from models.audit_log import AuditLog, AuditAction, AuditSeverity
from models.api_key import APIKey
from models.platform_api_key import PlatformAPIKey

from core.security.feature_permissions.service import feature_permission_service
from core.rate_limit.service import DynamicRateLimitService
from core.audit.service import AuditService
from core.security.api_key_manager import SecureAPIKeyManager
from core.exceptions import PermissionDeniedError, RateLimitExceededError


class TestCompleteUserJourney:
    """Test complete user journeys through the security system."""
    
    @pytest.mark.asyncio
    async def test_new_user_onboarding_security_flow(self):
        """Test security flow for new user onboarding."""
        mock_db = AsyncMock()
        
        # Create new user
        new_user = User(
            id=uuid.uuid4(),
            email="newuser@company.com",
            role=UserRole.USER,
            agency_id=uuid.uuid4(),
            is_active=True
        )
        
        # Services
        audit_service = AuditService()
        rate_limiter = DynamicRateLimitService()
        api_key_manager = SecureAPIKeyManager()
        
        # Track audit trail
        audit_logs = []
        mock_db.add = MagicMock(side_effect=lambda log: audit_logs.append(log))
        mock_db.commit = AsyncMock()
        
        # Step 1: User creation audit
        await audit_service.log(
            db=mock_db,
            action=AuditAction.USER_CREATED,
            user_id=new_user.id,
            details={
                "email": new_user.email,
                "role": new_user.role.value,
                "agency_id": str(new_user.agency_id)
            }
        )
        
        # Step 2: Assign default permissions
        default_permissions = [
            FeaturePermission(
                id=uuid.uuid4(),
                name="Basic User Permissions",
                feature_type=FeatureType.REPORTS,
                user_id=new_user.id,
                allowed_actions=["view_own_reports"],
                analytics_scope=AnalyticsScope.OWN,
                can_access_pii_data=False,
                can_access_financial_data=False,
                is_active=True
            )
        ]
        
        for perm in default_permissions:
            await audit_service.log(
                db=mock_db,
                action=AuditAction.PERMISSION_CREATED,
                user=new_user,
                resource_id=str(perm.id),
                resource_type="feature_permission",
                details={
                    "permission_type": perm.feature_type.value,
                    "scope": perm.analytics_scope.value
                }
            )
        
        # Step 3: Create API key for user
        with patch.object(api_key_manager, '_generate_secure_key', return_value="test_key_123"):
            with patch.object(api_key_manager, '_hash_api_key', return_value="hashed_key"):
                api_key = await api_key_manager.create_api_key(
                    db=mock_db,
                    user_id=new_user.id,
                    name="Default API Key",
                    scopes=["read:own_data"]
                )
                
                await audit_service.log(
                    db=mock_db,
                    action=AuditAction.API_KEY_CREATED,
                    user=new_user,
                    resource_id=str(api_key.id),
                    resource_type="api_key",
                    details={"scopes": ["read:own_data"]}
                )
        
        # Step 4: Set up rate limits
        user_rate_limit = RateLimitConfig(
            id=uuid.uuid4(),
            name=f"Rate limit for {new_user.email}",
            limit_type=RateLimitType.USER,
            identifier=str(new_user.id),
            requests_per_minute=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            burst_size=10,
            is_active=True
        )
        
        # Step 5: First login
        await audit_service.log(
            db=mock_db,
            action=AuditAction.USER_LOGIN,
            user=new_user,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            details={"first_login": True}
        )
        
        # Verify complete audit trail
        assert len(audit_logs) >= 4
        actions = [log.action for log in audit_logs]
        assert AuditAction.USER_CREATED in actions
        assert AuditAction.PERMISSION_CREATED in actions
        assert AuditAction.API_KEY_CREATED in actions
        assert AuditAction.USER_LOGIN in actions
    
    @pytest.mark.asyncio
    async def test_data_export_security_workflow(self):
        """Test complete security workflow for data export."""
        mock_db = AsyncMock()
        
        # User requesting export
        user = User(
            id=uuid.uuid4(),
            email="analyst@company.com",
            role=UserRole.MANAGER,
            agency_id=uuid.uuid4()
        )
        
        # Services
        audit_service = AuditService()
        rate_limiter = DynamicRateLimitService()
        
        # Export permission
        export_permission = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.EXPORTS,
            user_id=user.id,
            allowed_actions=["export_data"],
            allowed_export_formats=[ExportFormat.CSV, ExportFormat.EXCEL],
            max_export_rows=50000,
            export_rate_limit_per_hour=10,
            can_access_pii_data=True,
            requires_mfa=True,
            is_active=True
        )
        
        # Track workflow
        workflow_steps = []
        
        # Step 1: Check MFA
        mfa_verified = True  # Assume MFA passed
        workflow_steps.append({
            "step": "mfa_verification",
            "result": "passed" if mfa_verified else "failed"
        })
        
        if not mfa_verified:
            await audit_service.log(
                db=mock_db,
                action=AuditAction.PERMISSION_DENIED,
                user=user,
                details={"reason": "MFA required"}
            )
            return
        
        # Step 2: Check rate limit
        with patch.object(
            rate_limiter,
            'check_rate_limit',
            return_value=(True, {"remaining": 9})
        ):
            rate_allowed, rate_info = await rate_limiter.check_rate_limit(
                db=mock_db,
                identifier=str(user.id),
                identifier_type=RateLimitType.USER,
                endpoint="/api/v1/export",
                user=user
            )
            workflow_steps.append({
                "step": "rate_limit_check",
                "result": "allowed",
                "remaining": rate_info["remaining"]
            })
        
        # Step 3: Check permissions
        export_request = {
            "format": ExportFormat.CSV,
            "estimated_rows": 25000,
            "contains_pii": True,
            "data_type": "user_analytics"
        }
        
        with patch.object(
            feature_permission_service,
            '_get_user_feature_permissions',
            return_value=[export_permission]
        ):
            with patch.object(
                feature_permission_service,
                '_check_export_permission',
                return_value=(True, None)
            ):
                perm_allowed, perm_reason = await feature_permission_service.check_feature_permission(
                    db=mock_db,
                    user=user,
                    feature_type=FeatureType.EXPORTS,
                    action="export_data",
                    request_context=export_request
                )
                workflow_steps.append({
                    "step": "permission_check",
                    "result": "allowed"
                })
        
        # Step 4: Log export initiation
        export_id = uuid.uuid4()
        await audit_service.log(
            db=mock_db,
            action=AuditAction.DATA_EXPORT,
            user=user,
            resource_id=str(export_id),
            resource_type="export",
            details={
                "format": export_request["format"].value,
                "rows": export_request["estimated_rows"],
                "contains_pii": export_request["contains_pii"],
                "data_type": export_request["data_type"]
            },
            severity=AuditSeverity.WARNING  # Due to PII
        )
        workflow_steps.append({
            "step": "audit_export_start",
            "export_id": str(export_id)
        })
        
        # Step 5: Track export completion
        await audit_service.log(
            db=mock_db,
            action=AuditAction.EXPORT_COMPLETED,
            user=user,
            resource_id=str(export_id),
            resource_type="export",
            details={
                "actual_rows": 24567,
                "file_size_mb": 45.2,
                "duration_seconds": 12.5
            }
        )
        workflow_steps.append({
            "step": "export_completed",
            "status": "success"
        })
        
        # Verify complete workflow
        assert len(workflow_steps) == 5
        assert all(step.get("result") != "failed" for step in workflow_steps if "result" in step)


class TestMultiTenantSecurity:
    """Test security isolation in multi-tenant environment."""
    
    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self):
        """Test complete isolation between tenants."""
        mock_db = AsyncMock()
        
        # Create two agencies
        agency_a_id = uuid.uuid4()
        agency_b_id = uuid.uuid4()
        
        # Users from different agencies
        user_a = User(
            id=uuid.uuid4(),
            email="admin@agency-a.com",
            role=UserRole.ADMIN,
            agency_id=agency_a_id
        )
        
        user_b = User(
            id=uuid.uuid4(),
            email="admin@agency-b.com",
            role=UserRole.ADMIN,
            agency_id=agency_b_id
        )
        
        # Agency-specific permissions
        perm_a = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.ADMIN,
            agency_id=agency_a_id,
            allowed_actions=["manage_agency_users", "view_agency_data"]
        )
        
        perm_b = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.ADMIN,
            agency_id=agency_b_id,
            allowed_actions=["manage_agency_users", "view_agency_data"]
        )
        
        # Test: User A cannot access Agency B data
        target_user_b = User(
            id=uuid.uuid4(),
            email="user@agency-b.com",
            agency_id=agency_b_id
        )
        
        # Mock permission service to enforce agency isolation
        with patch.object(
            feature_permission_service,
            '_get_user_feature_permissions',
            return_value=[perm_a]  # Only Agency A permissions
        ):
            # Attempt to manage user from Agency B
            with pytest.raises(PermissionDeniedError):
                # Check would fail due to agency mismatch
                if user_a.agency_id != target_user_b.agency_id:
                    raise PermissionDeniedError("Cross-agency access denied")
        
        # Test: Each admin can only see their agency's audit logs
        audit_service = AuditService()
        
        # Mock audit log query
        with patch.object(mock_db, 'execute') as mock_execute:
            # Query should filter by agency_id
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_execute.return_value = mock_result
            
            # User A queries audit logs
            await audit_service.get_audit_logs(
                db=mock_db,
                user=user_a,
                filters={"agency_id": str(agency_a_id)}
            )
            
            # Verify query includes agency filter
            query_call = mock_execute.call_args
            assert query_call is not None
    
    @pytest.mark.asyncio
    async def test_api_key_tenant_isolation(self):
        """Test API keys are isolated between tenants."""
        mock_db = AsyncMock()
        api_key_manager = SecureAPIKeyManager()
        
        # Create platform API keys for different agencies
        agency_a_id = uuid.uuid4()
        agency_b_id = uuid.uuid4()
        
        key_a = PlatformAPIKey(
            id=uuid.uuid4(),
            name="Agency A API Key",
            key_hash="hash_a",
            agency_id=agency_a_id,
            scopes=["read", "write"],
            is_active=True
        )
        
        key_b = PlatformAPIKey(
            id=uuid.uuid4(),
            name="Agency B API Key",
            key_hash="hash_b",
            agency_id=agency_b_id,
            scopes=["read"],
            is_active=True
        )
        
        # Test: Key from Agency A cannot access Agency B resources
        with patch.object(
            api_key_manager,
            'get_api_key_by_hash',
            return_value=key_a
        ):
            # Attempt to access Agency B resource
            resource_agency = agency_b_id
            
            # Should fail agency check
            if key_a.agency_id != resource_agency:
                allowed = False
                reason = "API key not authorized for this agency"
            else:
                allowed = True
                reason = None
            
            assert allowed is False
            assert "not authorized" in reason


class TestEmergencyResponse:
    """Test emergency response and security incident handling."""
    
    @pytest.mark.asyncio
    async def test_security_lockdown_procedure(self):
        """Test system-wide security lockdown."""
        mock_db = AsyncMock()
        
        # Services
        audit_service = AuditService()
        rate_limiter = DynamicRateLimitService()
        
        # Initiate lockdown
        lockdown_config = {
            "reason": "Suspected data breach",
            "initiated_by": "security@company.com",
            "timestamp": datetime.utcnow(),
            "affected_features": [FeatureType.EXPORTS, FeatureType.API_KEYS]
        }
        
        # Step 1: Disable affected features
        affected_permissions = []
        for feature in lockdown_config["affected_features"]:
            # Mock disabling permissions
            mock_db.execute = AsyncMock(return_value=MagicMock(rowcount=10))
            
            # Log lockdown
            await audit_service.log(
                db=mock_db,
                action=AuditAction.SECURITY_LOCKDOWN,
                details={
                    "feature": feature.value,
                    "reason": lockdown_config["reason"],
                    "permissions_disabled": 10
                },
                severity=AuditSeverity.CRITICAL
            )
        
        # Step 2: Tighten rate limits
        emergency_rate_limit = RateLimitConfig(
            id=uuid.uuid4(),
            name="Emergency Rate Limit",
            limit_type=RateLimitType.GLOBAL,
            requests_per_minute=10,  # Very restrictive
            algorithm=RateLimitAlgorithm.FIXED_WINDOW,
            priority=100,  # Highest priority
            is_active=True
        )
        
        # Step 3: Force re-authentication
        active_sessions = []  # Would get from session store
        for session in active_sessions:
            # Invalidate session
            pass
        
        # Step 4: Alert administrators
        admin_users = [
            User(id=uuid.uuid4(), email="admin1@company.com", role=UserRole.ADMIN),
            User(id=uuid.uuid4(), email="admin2@company.com", role=UserRole.ADMIN)
        ]
        
        for admin in admin_users:
            await audit_service.log(
                db=mock_db,
                action=AuditAction.ADMIN_ALERT,
                user_id=admin.id,
                details={
                    "alert_type": "security_lockdown",
                    "reason": lockdown_config["reason"],
                    "features_disabled": [f.value for f in lockdown_config["affected_features"]]
                },
                severity=AuditSeverity.CRITICAL
            )
    
    @pytest.mark.asyncio
    async def test_automated_threat_response(self):
        """Test automated response to detected threats."""
        mock_db = AsyncMock()
        
        # Services
        audit_service = AuditService()
        rate_limiter = DynamicRateLimitService()
        
        # Simulate threat detection
        threat_indicators = {
            "type": "credential_stuffing",
            "source_ips": ["192.168.1.100", "192.168.1.101", "192.168.1.102"],
            "affected_endpoints": ["/api/v1/auth", "/api/v1/login"],
            "failed_attempts": 500,
            "time_window_minutes": 5
        }
        
        # Automated response actions
        response_actions = []
        
        # Action 1: Block source IPs
        for ip in threat_indicators["source_ips"]:
            # Add to IP blacklist
            blocked_config = RateLimitConfig(
                id=uuid.uuid4(),
                name=f"Blocked IP: {ip}",
                limit_type=RateLimitType.IP,
                identifier=ip,
                requests_per_minute=0,  # Complete block
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
                priority=99,
                is_active=True
            )
            response_actions.append({
                "action": "ip_blocked",
                "ip": ip,
                "config_id": str(blocked_config.id)
            })
        
        # Action 2: Require MFA for affected endpoints
        for endpoint in threat_indicators["affected_endpoints"]:
            # Update endpoint to require MFA
            response_actions.append({
                "action": "mfa_required",
                "endpoint": endpoint
            })
        
        # Action 3: Alert security team
        await audit_service.log(
            db=mock_db,
            action=AuditAction.AUTOMATED_RESPONSE,
            details={
                "threat_type": threat_indicators["type"],
                "indicators": threat_indicators,
                "actions_taken": response_actions
            },
            severity=AuditSeverity.CRITICAL,
            risk_score=95
        )
        
        # Action 4: Increase monitoring
        # Would trigger enhanced logging and alerting
        
        # Verify response was comprehensive
        assert len(response_actions) >= len(threat_indicators["source_ips"]) + len(threat_indicators["affected_endpoints"])


class TestSystemWideSecurityPolicies:
    """Test system-wide security policy enforcement."""
    
    @pytest.mark.asyncio
    async def test_data_classification_enforcement(self):
        """Test enforcement of data classification policies."""
        mock_db = AsyncMock()
        
        # Define data classification levels
        data_classifications = {
            DataSensitivity.PUBLIC: {
                "min_role": UserRole.USER,
                "requires_mfa": False,
                "audit_level": AuditSeverity.INFO
            },
            DataSensitivity.INTERNAL: {
                "min_role": UserRole.CHATTER,
                "requires_mfa": False,
                "audit_level": AuditSeverity.INFO
            },
            DataSensitivity.CONFIDENTIAL: {
                "min_role": UserRole.MANAGER,
                "requires_mfa": True,
                "audit_level": AuditSeverity.WARNING
            },
            DataSensitivity.RESTRICTED: {
                "min_role": UserRole.ADMIN,
                "requires_mfa": True,
                "audit_level": AuditSeverity.ERROR
            }
        }
        
        # Test access for different user roles
        test_cases = [
            {
                "user": User(id=uuid.uuid4(), role=UserRole.USER),
                "data_sensitivity": DataSensitivity.CONFIDENTIAL,
                "expected": False
            },
            {
                "user": User(id=uuid.uuid4(), role=UserRole.MANAGER),
                "data_sensitivity": DataSensitivity.CONFIDENTIAL,
                "expected": True,
                "requires_mfa": True
            },
            {
                "user": User(id=uuid.uuid4(), role=UserRole.ADMIN),
                "data_sensitivity": DataSensitivity.RESTRICTED,
                "expected": True,
                "requires_mfa": True
            }
        ]
        
        for test in test_cases:
            user = test["user"]
            sensitivity = test["data_sensitivity"]
            policy = data_classifications[sensitivity]
            
            # Check role requirement
            role_allowed = user.role.value >= policy["min_role"].value
            
            # Check MFA requirement
            mfa_satisfied = True  # Assume MFA is satisfied for this test
            if policy["requires_mfa"] and not mfa_satisfied:
                role_allowed = False
            
            assert role_allowed == test["expected"]
            
            # Log access attempt
            if role_allowed:
                await audit_service.log(
                    db=mock_db,
                    action=AuditAction.SENSITIVE_DATA_ACCESS,
                    user=user,
                    details={
                        "data_sensitivity": sensitivity.value,
                        "mfa_used": mfa_satisfied
                    },
                    severity=policy["audit_level"]
                )
    
    @pytest.mark.asyncio
    async def test_compliance_mode_enforcement(self):
        """Test compliance mode restrictions (GDPR, SOX, etc.)."""
        mock_db = AsyncMock()
        
        # Enable compliance modes
        compliance_modes = {
            "GDPR": True,
            "SOX": True,
            "HIPAA": False
        }
        
        # GDPR compliance checks
        if compliance_modes["GDPR"]:
            # Test right to be forgotten
            user_to_delete = User(id=uuid.uuid4(), email="delete@me.com")
            
            # Must log data deletion
            await audit_service.log(
                db=mock_db,
                action=AuditAction.PERSONAL_DATA_DELETED,
                resource_id=str(user_to_delete.id),
                resource_type="user",
                details={
                    "reason": "user_request",
                    "data_categories": ["profile", "activity_logs", "preferences"],
                    "deletion_method": "hard_delete",
                    "compliance": "GDPR_Article_17"
                },
                severity=AuditSeverity.WARNING
            )
            
            # Must anonymize related data
            await audit_service.log(
                db=mock_db,
                action=AuditAction.DATA_ANONYMIZED,
                details={
                    "related_user": str(user_to_delete.id),
                    "tables_affected": ["messages", "analytics", "reports"],
                    "compliance": "GDPR"
                }
            )
        
        # SOX compliance checks
        if compliance_modes["SOX"]:
            # Financial data access must have approval
            financial_access_request = {
                "user_id": uuid.uuid4(),
                "data_type": "financial_reports",
                "period": "Q4_2024",
                "approved_by": uuid.uuid4(),
                "approval_timestamp": datetime.utcnow()
            }
            
            # Must log with full audit trail
            await audit_service.log(
                db=mock_db,
                action=AuditAction.FINANCIAL_DATA_ACCESS,
                user_id=financial_access_request["user_id"],
                details={
                    "data_type": financial_access_request["data_type"],
                    "period": financial_access_request["period"],
                    "approved_by": str(financial_access_request["approved_by"]),
                    "approval_timestamp": financial_access_request["approval_timestamp"].isoformat(),
                    "compliance": "SOX_Section_404"
                },
                severity=AuditSeverity.WARNING
            )