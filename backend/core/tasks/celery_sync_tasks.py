"""
Data synchronization tasks for Celery
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import aiohttp
import asyncio

from celery import shared_task, group
from celery.utils.log import get_task_logger
from sqlalchemy import select, delete, and_, or_

from core.config import settings
from core.database import get_db_context
from core.models import Agency, SyncLog, Transaction
from modules.external_apis.onlyfans_client import OnlyFansClient
from modules.external_apis.inflow_client import InflowClient
from modules.external_apis.stripe_client import StripeClient

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_onlyfans_data(self, agency_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Sync OnlyFans data for agencies
    
    Args:
        agency_id: Specific agency ID or None for all agencies
    """
    try:
        results = {
            'agencies_synced': 0,
            'transactions_synced': 0,
            'errors': []
        }
        
        async def _sync():
            async with get_db_context() as db:
                # Get agencies to sync
                query = select(Agency).where(Agency.is_active == True)
                if agency_id:
                    query = query.where(Agency.id == agency_id)
                
                result = await db.execute(query)
                agencies = result.scalars().all()
                
                for agency in agencies:
                    try:
                        # Check if agency has OnlyFans credentials
                        if not agency.onlyfans_api_key:
                            continue
                        
                        # Initialize client
                        client = OnlyFansClient(
                            api_key=agency.onlyfans_api_key,
                            api_secret=agency.onlyfans_api_secret
                        )
                        
                        # Get last sync time
                        last_sync_result = await db.execute(
                            select(SyncLog).where(
                                and_(
                                    SyncLog.agency_id == agency.id,
                                    SyncLog.service == 'onlyfans',
                                    SyncLog.status == 'success'
                                )
                            ).order_by(SyncLog.created_at.desc()).limit(1)
                        )
                        last_sync = last_sync_result.scalar_one_or_none()
                        
                        since = last_sync.created_at if last_sync else datetime.utcnow() - timedelta(days=30)
                        
                        # Sync transactions
                        transactions = await client.get_transactions(since=since)
                        
                        for tx_data in transactions:
                            # Create or update transaction
                            existing_tx = await db.execute(
                                select(Transaction).where(
                                    and_(
                                        Transaction.external_id == tx_data['id'],
                                        Transaction.platform == 'onlyfans'
                                    )
                                )
                            )
                            tx = existing_tx.scalar_one_or_none()
                            
                            if not tx:
                                tx = Transaction(
                                    agency_id=agency.id,
                                    platform='onlyfans',
                                    external_id=tx_data['id'],
                                    type=tx_data['type'],
                                    amount=tx_data['amount'],
                                    currency=tx_data['currency'],
                                    user_id=tx_data.get('user_id'),
                                    metadata=tx_data,
                                    created_at=tx_data['created_at']
                                )
                                db.add(tx)
                                results['transactions_synced'] += 1
                        
                        # Log successful sync
                        sync_log = SyncLog(
                            agency_id=agency.id,
                            service='onlyfans',
                            status='success',
                            records_synced=len(transactions),
                            metadata={'task_id': self.request.id}
                        )
                        db.add(sync_log)
                        
                        results['agencies_synced'] += 1
                        
                    except Exception as exc:
                        logger.error(f"Failed to sync OnlyFans for agency {agency.id}: {exc}")
                        results['errors'].append({
                            'agency_id': str(agency.id),
                            'error': str(exc)
                        })
                        
                        # Log failed sync
                        sync_log = SyncLog(
                            agency_id=agency.id,
                            service='onlyfans',
                            status='failed',
                            error_message=str(exc),
                            metadata={'task_id': self.request.id}
                        )
                        db.add(sync_log)
                
                await db.commit()
        
        # Run async function
        asyncio.run(_sync())
        
        logger.info(f"OnlyFans sync completed: {results}")
        return results
        
    except Exception as exc:
        logger.error(f"OnlyFans sync failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_inflow_transactions(self, agency_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Sync Inflow transaction data
    """
    try:
        results = {
            'agencies_synced': 0,
            'transactions_synced': 0,
            'errors': []
        }
        
        async def _sync():
            async with get_db_context() as db:
                # Get agencies to sync
                query = select(Agency).where(Agency.is_active == True)
                if agency_id:
                    query = query.where(Agency.id == agency_id)
                
                result = await db.execute(query)
                agencies = result.scalars().all()
                
                for agency in agencies:
                    try:
                        # Check if agency has Inflow credentials
                        if not agency.inflow_access_token:
                            continue
                        
                        # Initialize client
                        client = InflowClient(
                            access_token=agency.inflow_access_token
                        )
                        
                        # Get transactions
                        transactions = await client.get_recent_transactions(limit=100)
                        
                        for tx_data in transactions:
                            # Create or update transaction
                            existing_tx = await db.execute(
                                select(Transaction).where(
                                    and_(
                                        Transaction.external_id == tx_data['id'],
                                        Transaction.platform == 'inflow'
                                    )
                                )
                            )
                            tx = existing_tx.scalar_one_or_none()
                            
                            if not tx:
                                tx = Transaction(
                                    agency_id=agency.id,
                                    platform='inflow',
                                    external_id=tx_data['id'],
                                    type='payment',
                                    amount=tx_data['amount'],
                                    currency=tx_data['currency'],
                                    metadata=tx_data,
                                    created_at=tx_data['created_at']
                                )
                                db.add(tx)
                                results['transactions_synced'] += 1
                        
                        # Log successful sync
                        sync_log = SyncLog(
                            agency_id=agency.id,
                            service='inflow',
                            status='success',
                            records_synced=len(transactions),
                            metadata={'task_id': self.request.id}
                        )
                        db.add(sync_log)
                        
                        results['agencies_synced'] += 1
                        
                    except Exception as exc:
                        logger.error(f"Failed to sync Inflow for agency {agency.id}: {exc}")
                        results['errors'].append({
                            'agency_id': str(agency.id),
                            'error': str(exc)
                        })
                        
                        # Log failed sync
                        sync_log = SyncLog(
                            agency_id=agency.id,
                            service='inflow',
                            status='failed',
                            error_message=str(exc),
                            metadata={'task_id': self.request.id}
                        )
                        db.add(sync_log)
                
                await db.commit()
        
        # Run async function
        asyncio.run(_sync())
        
        logger.info(f"Inflow sync completed: {results}")
        return results
        
    except Exception as exc:
        logger.error(f"Inflow sync failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def sync_stripe_data(self, agency_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Sync Stripe data (customers, subscriptions, payments)
    """
    try:
        results = {
            'agencies_synced': 0,
            'customers_synced': 0,
            'subscriptions_synced': 0,
            'payments_synced': 0,
            'errors': []
        }
        
        async def _sync():
            async with get_db_context() as db:
                # Get agencies to sync
                query = select(Agency).where(Agency.is_active == True)
                if agency_id:
                    query = query.where(Agency.id == agency_id)
                
                result = await db.execute(query)
                agencies = result.scalars().all()
                
                for agency in agencies:
                    try:
                        # Check if agency has Stripe credentials
                        if not agency.stripe_secret_key:
                            continue
                        
                        # Initialize client
                        client = StripeClient(
                            api_key=agency.stripe_secret_key
                        )
                        
                        # Sync customers
                        customers = await client.list_customers(limit=100)
                        results['customers_synced'] += len(customers)
                        
                        # Sync subscriptions
                        subscriptions = await client.list_subscriptions(limit=100)
                        results['subscriptions_synced'] += len(subscriptions)
                        
                        # Sync recent charges
                        charges = await client.list_charges(
                            created={'gte': int((datetime.utcnow() - timedelta(days=7)).timestamp())}
                        )
                        results['payments_synced'] += len(charges)
                        
                        # Log successful sync
                        sync_log = SyncLog(
                            agency_id=agency.id,
                            service='stripe',
                            status='success',
                            records_synced=len(customers) + len(subscriptions) + len(charges),
                            metadata={
                                'task_id': self.request.id,
                                'customers': len(customers),
                                'subscriptions': len(subscriptions),
                                'charges': len(charges)
                            }
                        )
                        db.add(sync_log)
                        
                        results['agencies_synced'] += 1
                        
                    except Exception as exc:
                        logger.error(f"Failed to sync Stripe for agency {agency.id}: {exc}")
                        results['errors'].append({
                            'agency_id': str(agency.id),
                            'error': str(exc)
                        })
                        
                        # Log failed sync
                        sync_log = SyncLog(
                            agency_id=agency.id,
                            service='stripe',
                            status='failed',
                            error_message=str(exc),
                            metadata={'task_id': self.request.id}
                        )
                        db.add(sync_log)
                
                await db.commit()
        
        # Run async function
        asyncio.run(_sync())
        
        logger.info(f"Stripe sync completed: {results}")
        return results
        
    except Exception as exc:
        logger.error(f"Stripe sync failed: {exc}")
        raise self.retry(exc=exc)


@shared_task
def sync_all_platforms() -> Dict[str, Any]:
    """
    Sync data from all platforms in parallel
    """
    # Create group of tasks
    job = group(
        sync_onlyfans_data.s(),
        sync_inflow_transactions.s(),
        sync_stripe_data.s()
    )
    
    # Execute group
    result = job.apply_async()
    
    return {
        'status': 'queued',
        'group_id': result.id,
        'tasks': [task.id for task in result.results]
    }


@shared_task
def check_sync_health() -> Dict[str, Any]:
    """
    Check health of sync operations
    """
    try:
        health = {
            'status': 'healthy',
            'services': {},
            'warnings': []
        }
        
        async def _check():
            async with get_db_context() as db:
                # Check each service
                for service in ['onlyfans', 'inflow', 'stripe']:
                    # Get recent sync logs
                    result = await db.execute(
                        select(SyncLog).where(
                            and_(
                                SyncLog.service == service,
                                SyncLog.created_at > datetime.utcnow() - timedelta(hours=1)
                            )
                        )
                    )
                    recent_syncs = result.scalars().all()
                    
                    if not recent_syncs:
                        health['warnings'].append(f"No recent syncs for {service}")
                        health['services'][service] = {'status': 'warning', 'message': 'No recent syncs'}
                        continue
                    
                    # Calculate success rate
                    successful = sum(1 for s in recent_syncs if s.status == 'success')
                    success_rate = successful / len(recent_syncs)
                    
                    if success_rate < 0.8:
                        health['warnings'].append(f"Low success rate for {service}: {success_rate:.1%}")
                        health['status'] = 'degraded'
                    
                    health['services'][service] = {
                        'status': 'healthy' if success_rate >= 0.8 else 'degraded',
                        'success_rate': success_rate,
                        'total_syncs': len(recent_syncs),
                        'successful_syncs': successful
                    }
        
        # Run async function
        asyncio.run(_check())
        
        return health
        
    except Exception as exc:
        logger.error(f"Failed to check sync health: {exc}")
        return {
            'status': 'error',
            'error': str(exc)
        }