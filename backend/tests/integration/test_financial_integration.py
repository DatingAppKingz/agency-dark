"""
Integration tests for financial module including transactions, commissions, and payouts.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock

from models.financial import Transaction, Payout, TransactionStatus, PayoutStatus
from modules.financial.domain.models import Commission, PaymentGateway, CommissionTier
from modules.financial.application.transaction_service import TransactionService
from modules.financial.application.commission_service import CommissionService
from modules.financial.application.payout_service import PayoutService
from modules.models.domain.models import Model
from modules.analytics.domain.models import Fan
from modules.agencies.domain.models import Agency


class TestFinancialIntegration:
    """Test complete financial workflows."""
    
    @pytest.fixture
    async def setup_financial_data(self, test_db: AsyncSession):
        """Setup comprehensive financial test data."""
        # Create agency with commission tiers
        agency = Agency(
            id=uuid4(),
            name="Test Agency",
            subdomain="testagency",
            is_active=True
        )
        test_db.add(agency)
        
        # Create commission tiers
        tiers = [
            CommissionTier(
                id=uuid4(),
                agency_id=agency.id,
                name="Standard",
                commission_rate=Decimal("0.20"),
                min_revenue=Decimal("0"),
                max_revenue=Decimal("5000"),
                is_active=True
            ),
            CommissionTier(
                id=uuid4(),
                agency_id=agency.id,
                name="Premium",
                commission_rate=Decimal("0.15"),
                min_revenue=Decimal("5000"),
                max_revenue=Decimal("10000"),
                is_active=True
            ),
            CommissionTier(
                id=uuid4(),
                agency_id=agency.id,
                name="Elite",
                commission_rate=Decimal("0.10"),
                min_revenue=Decimal("10000"),
                max_revenue=None,
                is_active=True
            )
        ]
        for tier in tiers:
            test_db.add(tier)
        
        # Create models
        models = []
        for i in range(3):
            model = Model(
                id=uuid4(),
                agency_id=agency.id,
                username=f"model_{i}",
                display_name=f"Model {i}",
                platform="onlyfans",
                commission_tier_id=tiers[i].id if i < len(tiers) else tiers[0].id,
                is_active=True
            )
            test_db.add(model)
            models.append(model)
        
        # Create fans
        fans = []
        for model in models:
            for j in range(10):
                fan = Fan(
                    id=uuid4(),
                    model_id=model.id,
                    username=f"fan_{model.username}_{j}",
                    display_name=f"Fan {j}",
                    subscription_status="active",
                    total_spent=Decimal("0"),
                    platform_data={"onlyfans": {"user_id": f"of_{uuid4()}"}}
                )
                test_db.add(fan)
                fans.append(fan)
        
        # Create payment gateway
        gateway = PaymentGateway(
            id=uuid4(),
            name="Stripe",
            provider="stripe",
            is_active=True,
            supported_currencies=["USD", "EUR", "GBP"],
            configuration={
                "api_key": "test_api_key",
                "webhook_secret": "test_webhook_secret"
            }
        )
        test_db.add(gateway)
        
        await test_db.commit()
        
        return {
            "agency": agency,
            "models": models,
            "fans": fans,
            "tiers": tiers,
            "gateway": gateway
        }
    
    @pytest.mark.asyncio
    async def test_transaction_processing_workflow(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_financial_data
    ):
        """Test complete transaction processing workflow."""
        model = setup_financial_data["models"][0]
        fan = setup_financial_data["fans"][0]
        
        # 1. Create transaction
        response = await async_client.post(
            "/api/v1/financial/transactions",
            json={
                "model_id": str(model.id),
                "fan_id": str(fan.id),
                "amount": 100.00,
                "currency": "USD",
                "transaction_type": "tip",
                "platform": "onlyfans",
                "platform_transaction_id": "of_txn_123456",
                "description": "Thank you tip"
            }
        )
        assert response.status_code == 200
        transaction = response.json()
        transaction_id = transaction["transaction_id"]
        
        # 2. Check transaction status
        response = await async_client.get(
            f"/api/v1/financial/transactions/{transaction_id}"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        
        # 3. Process transaction (webhook simulation)
        response = await async_client.post(
            "/api/v1/payments/webhooks/stripe",
            json={
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "id": "pi_123456",
                        "amount": 10000,  # Stripe uses cents
                        "currency": "usd",
                        "metadata": {
                            "transaction_id": transaction_id
                        }
                    }
                }
            },
            headers={"Stripe-Signature": "test_signature"}
        )
        assert response.status_code == 200
        
        # 4. Verify transaction completed
        response = await async_client.get(
            f"/api/v1/financial/transactions/{transaction_id}"
        )
        assert response.status_code == 200
        completed_txn = response.json()
        assert completed_txn["status"] == "completed"
        
        # 5. Check commission was calculated
        response = await async_client.get(
            "/api/v1/financial/commissions",
            params={
                "transaction_id": transaction_id
            }
        )
        assert response.status_code == 200
        commissions = response.json()
        assert len(commissions["items"]) > 0
        assert commissions["items"][0]["commission_amount"] == 20.00  # 20% of 100
    
    @pytest.mark.asyncio
    async def test_commission_calculation_with_tiers(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_financial_data
    ):
        """Test commission calculation with different tiers."""
        models = setup_financial_data["models"]
        fans = setup_financial_data["fans"]
        
        # Create transactions for different revenue levels
        test_cases = [
            {"model": models[0], "amount": 1000, "expected_rate": 0.20},  # Standard tier
            {"model": models[1], "amount": 7000, "expected_rate": 0.15},  # Premium tier
            {"model": models[2], "amount": 15000, "expected_rate": 0.10}  # Elite tier
        ]
        
        for case in test_cases:
            # Create transaction
            transaction = Transaction(
                id=uuid4(),
                agency_id=case["model"].agency_id,
                model_id=case["model"].id,
                fan_id=fans[0].id,
                amount=Decimal(str(case["amount"])),
                currency="USD",
                transaction_type="subscription",
                status=TransactionStatus.COMPLETED,
                platform="onlyfans",
                platform_transaction_id=f"of_txn_{uuid4()}"
            )
            test_db.add(transaction)
            await test_db.commit()
            
            # Calculate commission
            response = await async_client.post(
                "/api/v1/financial/commissions/calculate",
                json={
                    "transaction_id": str(transaction.id)
                }
            )
            assert response.status_code == 200
            
            commission = response.json()
            expected_commission = case["amount"] * case["expected_rate"]
            assert commission["commission_amount"] == expected_commission
            assert commission["commission_rate"] == case["expected_rate"]
    
    @pytest.mark.asyncio
    async def test_bulk_payout_processing(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_financial_data
    ):
        """Test bulk payout processing for multiple models."""
        models = setup_financial_data["models"]
        
        # Create completed transactions for each model
        for model in models:
            for i in range(5):
                transaction = Transaction(
                    id=uuid4(),
                    agency_id=model.agency_id,
                    model_id=model.id,
                    fan_id=setup_financial_data["fans"][i].id,
                    amount=Decimal("200"),
                    currency="USD",
                    transaction_type="tip",
                    status=TransactionStatus.COMPLETED,
                    platform="onlyfans",
                    created_at=datetime.utcnow() - timedelta(days=i)
                )
                test_db.add(transaction)
                
                # Create commission
                commission = Commission(
                    id=uuid4(),
                    transaction_id=transaction.id,
                    agency_id=model.agency_id,
                    model_id=model.id,
                    gross_amount=transaction.amount,
                    commission_rate=Decimal("0.20"),
                    commission_amount=Decimal("40"),
                    net_amount=Decimal("160"),
                    status="pending"
                )
                test_db.add(commission)
        
        await test_db.commit()
        
        # 1. Generate payout batch
        response = await async_client.post(
            "/api/v1/financial/payouts/batch",
            json={
                "period": {
                    "from": (datetime.utcnow() - timedelta(days=30)).date().isoformat(),
                    "to": datetime.utcnow().date().isoformat()
                },
                "model_ids": [str(m.id) for m in models],
                "payment_method": "bank_transfer"
            }
        )
        assert response.status_code == 200
        batch = response.json()
        assert len(batch["payouts"]) == 3
        assert batch["total_amount"] == 2400.00  # 3 models * 5 transactions * 160 net
        
        # 2. Approve payouts
        for payout in batch["payouts"]:
            response = await async_client.post(
                f"/api/v1/financial/payouts/{payout['id']}/approve"
            )
            assert response.status_code == 200
        
        # 3. Process payouts
        response = await async_client.post(
            "/api/v1/financial/payouts/process",
            json={
                "payout_ids": [p["id"] for p in batch["payouts"]]
            }
        )
        assert response.status_code == 200
        
        # 4. Check payout status
        for payout in batch["payouts"]:
            response = await async_client.get(
                f"/api/v1/financial/payouts/{payout['id']}"
            )
            assert response.status_code == 200
            assert response.json()["status"] in ["processing", "completed"]
    
    @pytest.mark.asyncio
    async def test_financial_reporting(
        self,
        async_client: AsyncClient,
        setup_financial_data
    ):
        """Test financial reporting and analytics."""
        agency = setup_financial_data["agency"]
        
        # 1. Get revenue summary
        response = await async_client.get(
            "/api/v1/financial/reports/revenue",
            params={
                "agency_id": str(agency.id),
                "period": "monthly",
                "months": 3
            }
        )
        assert response.status_code == 200
        revenue_report = response.json()
        assert "monthly_data" in revenue_report
        assert "totals" in revenue_report
        
        # 2. Get commission report
        response = await async_client.get(
            "/api/v1/financial/reports/commissions",
            params={
                "agency_id": str(agency.id),
                "group_by": "model",
                "date_from": (datetime.utcnow() - timedelta(days=30)).date().isoformat()
            }
        )
        assert response.status_code == 200
        commission_report = response.json()
        assert "by_model" in commission_report
        
        # 3. Get payout history
        response = await async_client.get(
            "/api/v1/financial/reports/payouts",
            params={
                "agency_id": str(agency.id),
                "status": "completed"
            }
        )
        assert response.status_code == 200
        
        # 4. Export financial data
        response = await async_client.post(
            "/api/v1/reporting/export",
            json={
                "export_type": "financial",
                "format": "excel",
                "date_from": (datetime.utcnow() - timedelta(days=90)).date().isoformat(),
                "date_to": datetime.utcnow().date().isoformat(),
                "include_details": True
            }
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_payment_gateway_integration(
        self,
        async_client: AsyncClient,
        setup_financial_data
    ):
        """Test payment gateway integration."""
        gateway = setup_financial_data["gateway"]
        model = setup_financial_data["models"][0]
        
        # 1. Initiate payout via gateway
        with patch('stripe.Transfer.create') as mock_transfer:
            mock_transfer.return_value = MagicMock(
                id="tr_123456",
                amount=50000,  # $500.00
                currency="usd",
                status="pending"
            )
            
            response = await async_client.post(
                "/api/v1/financial/payouts",
                json={
                    "model_id": str(model.id),
                    "amount": 500.00,
                    "currency": "USD",
                    "payment_method": "stripe",
                    "payment_details": {
                        "account_id": "acct_123456"
                    }
                }
            )
            assert response.status_code == 200
            payout = response.json()
            assert payout["gateway_reference"] == "tr_123456"
        
        # 2. Handle gateway webhook
        response = await async_client.post(
            "/api/v1/payments/webhooks/stripe",
            json={
                "type": "transfer.paid",
                "data": {
                    "object": {
                        "id": "tr_123456",
                        "amount": 50000,
                        "currency": "usd",
                        "metadata": {
                            "payout_id": payout["id"]
                        }
                    }
                }
            },
            headers={"Stripe-Signature": "test_signature"}
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_financial_reconciliation(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_financial_data
    ):
        """Test financial reconciliation process."""
        model = setup_financial_data["models"][0]
        
        # Create transactions with various statuses
        transactions = []
        for i in range(10):
            status = TransactionStatus.COMPLETED if i < 7 else TransactionStatus.FAILED
            transaction = Transaction(
                id=uuid4(),
                agency_id=model.agency_id,
                model_id=model.id,
                fan_id=setup_financial_data["fans"][0].id,
                amount=Decimal("50"),
                currency="USD",
                transaction_type="tip",
                status=status,
                platform="onlyfans",
                platform_transaction_id=f"of_txn_{i}",
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            test_db.add(transaction)
            transactions.append(transaction)
        
        await test_db.commit()
        
        # 1. Run reconciliation
        response = await async_client.post(
            "/api/v1/financial/reconcile",
            json={
                "model_id": str(model.id),
                "date_from": (datetime.utcnow() - timedelta(days=30)).date().isoformat(),
                "date_to": datetime.utcnow().date().isoformat()
            }
        )
        assert response.status_code == 200
        reconciliation = response.json()
        
        assert reconciliation["total_transactions"] == 10
        assert reconciliation["completed_transactions"] == 7
        assert reconciliation["failed_transactions"] == 3
        assert reconciliation["total_revenue"] == 350.00  # 7 * 50
        
        # 2. Get discrepancies
        response = await async_client.get(
            "/api/v1/financial/discrepancies",
            params={
                "model_id": str(model.id)
            }
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_subscription_revenue_tracking(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_financial_data
    ):
        """Test subscription revenue tracking and recurring payments."""
        model = setup_financial_data["models"][0]
        fans = setup_financial_data["fans"][:5]
        
        # Create subscription transactions
        for i, fan in enumerate(fans):
            # Initial subscription
            response = await async_client.post(
                "/api/v1/financial/transactions",
                json={
                    "model_id": str(model.id),
                    "fan_id": str(fan.id),
                    "amount": 9.99,
                    "currency": "USD",
                    "transaction_type": "subscription",
                    "platform": "onlyfans",
                    "platform_transaction_id": f"of_sub_{fan.id}",
                    "metadata": {
                        "subscription_id": f"sub_{fan.id}",
                        "billing_period": "monthly",
                        "rebill_date": (datetime.utcnow() + timedelta(days=30)).isoformat()
                    }
                }
            )
            assert response.status_code == 200
        
        # Get subscription analytics
        response = await async_client.get(
            "/api/v1/financial/analytics/subscriptions",
            params={
                "model_id": str(model.id)
            }
        )
        assert response.status_code == 200
        
        sub_analytics = response.json()
        assert sub_analytics["active_subscriptions"] == 5
        assert sub_analytics["mrr"] == 49.95  # Monthly Recurring Revenue
        assert sub_analytics["arpu"] == 9.99  # Average Revenue Per User


class TestFinancialWebhooks:
    """Test financial webhook processing."""
    
    @pytest.mark.asyncio
    async def test_stripe_webhook_signature_validation(
        self,
        async_client: AsyncClient
    ):
        """Test Stripe webhook signature validation."""
        # Invalid signature
        response = await async_client.post(
            "/api/v1/payments/webhooks/stripe",
            json={"type": "payment_intent.succeeded"},
            headers={"Stripe-Signature": "invalid_signature"}
        )
        assert response.status_code == 400
        
        # Missing signature
        response = await async_client.post(
            "/api/v1/payments/webhooks/stripe",
            json={"type": "payment_intent.succeeded"}
        )
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_webhook_idempotency(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_financial_data
    ):
        """Test webhook idempotency handling."""
        model = setup_financial_data["models"][0]
        
        # Create transaction
        transaction = Transaction(
            id=uuid4(),
            agency_id=model.agency_id,
            model_id=model.id,
            fan_id=setup_financial_data["fans"][0].id,
            amount=Decimal("100"),
            currency="USD",
            transaction_type="tip",
            status=TransactionStatus.PENDING,
            platform="onlyfans",
            platform_transaction_id="of_txn_duplicate"
        )
        test_db.add(transaction)
        await test_db.commit()
        
        webhook_payload = {
            "type": "payment_intent.succeeded",
            "id": "evt_123456",  # Event ID for idempotency
            "data": {
                "object": {
                    "id": "pi_123456",
                    "amount": 10000,
                    "metadata": {
                        "transaction_id": str(transaction.id)
                    }
                }
            }
        }
        
        # First webhook call
        response = await async_client.post(
            "/api/v1/payments/webhooks/stripe",
            json=webhook_payload,
            headers={"Stripe-Signature": "test_signature"}
        )
        assert response.status_code == 200
        
        # Duplicate webhook call (should be idempotent)
        response = await async_client.post(
            "/api/v1/payments/webhooks/stripe",
            json=webhook_payload,
            headers={"Stripe-Signature": "test_signature"}
        )
        assert response.status_code == 200
        
        # Verify transaction was only processed once
        await test_db.refresh(transaction)
        assert transaction.status == TransactionStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])