"""
Socket.IO namespace for financial real-time updates.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
import asyncio

from socketio import AsyncNamespace
from sqlalchemy import select, and_, func

from core.database import AsyncSessionLocal
from core.domain.models import User, UserRole, ModelProfile
from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionStatus,
    Payout,
    PayoutStatus
)

logger = logging.getLogger(__name__)


class FinancialNamespace(AsyncNamespace):
    """Socket.IO namespace for financial updates and live payment tracking."""
    
    def __init__(self, namespace=None):
        super().__init__(namespace)
        self.payment_trackers = {}  # Track active payment monitoring
        self._tracker_tasks = {}
    
    async def on_connect(self, sid: str, environ: dict):
        """Handle namespace connection."""
        session = await self.get_session(sid)
        if not session:
            return False
        
        logger.info(f"User {session['username']} connected to financial namespace")
        
        # Join financial rooms based on role
        if session['role'] == UserRole.SUPER_ADMIN:
            self.enter_room(sid, 'financial:all')
        elif session['agency_id']:
            self.enter_room(sid, f"financial:agency:{session['agency_id']}")
        
        return True
    
    async def on_disconnect(self, sid: str):
        """Handle disconnection."""
        # Cancel any active payment trackers
        if sid in self._tracker_tasks:
            for task in self._tracker_tasks[sid].values():
                task.cancel()
            del self._tracker_tasks[sid]
        
        if sid in self.payment_trackers:
            del self.payment_trackers[sid]
    
    async def on_track_payment(self, sid: str, data: Dict[str, Any]):
        """Start tracking a specific payment in real-time."""
        session = await self.get_session(sid)
        if not session:
            return
        
        transaction_id = data.get('transaction_id')
        if not transaction_id:
            await self.emit('error', {
                'message': 'Transaction ID required'
            }, room=sid)
            return
        
        # Verify access to transaction
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(FinancialTransaction).where(
                    FinancialTransaction.id == transaction_id
                )
            )
            transaction = result.scalar_one_or_none()
            
            if not transaction:
                await self.emit('error', {
                    'message': 'Transaction not found'
                }, room=sid)
                return
            
            # Check permissions
            if session['role'] != UserRole.SUPER_ADMIN:
                if str(transaction.agency_id) != session['agency_id']:
                    await self.emit('error', {
                        'message': 'Access denied'
                    }, room=sid)
                    return
        
        # Start tracking
        if sid not in self.payment_trackers:
            self.payment_trackers[sid] = set()
            self._tracker_tasks[sid] = {}
        
        self.payment_trackers[sid].add(transaction_id)
        
        # Start tracking task
        task_key = f"payment_{transaction_id}"
        if task_key in self._tracker_tasks[sid]:
            self._tracker_tasks[sid][task_key].cancel()
        
        self._tracker_tasks[sid][task_key] = asyncio.create_task(
            self._track_payment_status(sid, transaction_id)
        )
        
        await self.emit('tracking_started', {
            'transaction_id': transaction_id
        }, room=sid)
    
    async def on_stop_tracking_payment(self, sid: str, data: Dict[str, Any]):
        """Stop tracking a payment."""
        transaction_id = data.get('transaction_id')
        
        if sid in self.payment_trackers and transaction_id in self.payment_trackers[sid]:
            self.payment_trackers[sid].remove(transaction_id)
            
            # Cancel tracking task
            task_key = f"payment_{transaction_id}"
            if sid in self._tracker_tasks and task_key in self._tracker_tasks[sid]:
                self._tracker_tasks[sid][task_key].cancel()
                del self._tracker_tasks[sid][task_key]
            
            await self.emit('tracking_stopped', {
                'transaction_id': transaction_id
            }, room=sid)
    
    async def on_subscribe_payouts(self, sid: str, data: Dict[str, Any]):
        """Subscribe to payout status updates."""
        session = await self.get_session(sid)
        if not session:
            return
        
        model_id = data.get('model_id')
        
        # Join appropriate payout room
        if model_id:
            # Verify access to model
            async with AsyncSessionLocal() as db:
                model = await db.get(ModelProfile, model_id)
                if not model or (
                    session['role'] != UserRole.SUPER_ADMIN and
                    str(model.agency_id) != session['agency_id']
                ):
                    await self.emit('error', {
                        'message': 'Access denied to model'
                    }, room=sid)
                    return
            
            self.enter_room(sid, f"payouts:model:{model_id}")
        elif session['agency_id']:
            self.enter_room(sid, f"payouts:agency:{session['agency_id']}")
        
        await self.emit('subscribed_payouts', {
            'model_id': model_id
        }, room=sid)
    
    async def on_get_payment_stats(self, sid: str, data: Dict[str, Any]):
        """Get real-time payment statistics."""
        session = await self.get_session(sid)
        if not session:
            return
        
        period = data.get('period', 'today')  # today, week, month
        model_id = data.get('model_id')
        
        stats = await self._get_payment_statistics(
            session['agency_id'],
            model_id,
            period
        )
        
        await self.emit('payment_stats', stats, room=sid)
    
    async def _track_payment_status(self, sid: str, transaction_id: str):
        """Track payment status changes."""
        try:
            last_status = None
            while True:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(FinancialTransaction).where(
                            FinancialTransaction.id == transaction_id
                        )
                    )
                    transaction = result.scalar_one_or_none()
                    
                    if not transaction:
                        break
                    
                    # Check if status changed
                    if transaction.status != last_status:
                        await self.emit('payment_status_update', {
                            'transaction_id': str(transaction_id),
                            'status': transaction.status.value,
                            'amount': float(transaction.amount),
                            'currency': transaction.currency,
                            'processed_at': transaction.processed_at.isoformat() if transaction.processed_at else None,
                            'metadata': transaction.metadata
                        }, room=sid)
                        
                        last_status = transaction.status
                    
                    # Stop tracking if payment is final
                    if transaction.status in [TransactionStatus.COMPLETED, TransactionStatus.FAILED]:
                        break
                
                # Check every 5 seconds
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info(f"Payment tracking cancelled for {transaction_id}")
        except Exception as e:
            logger.error(f"Error tracking payment: {e}")
    
    async def _get_payment_statistics(
        self,
        agency_id: str,
        model_id: str = None,
        period: str = 'today'
    ) -> Dict[str, Any]:
        """Get payment statistics for a period."""
        # Calculate date range
        end_date = datetime.utcnow()
        if period == 'today':
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = end_date - timedelta(days=7)
        elif period == 'month':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=1)
        
        stats = {
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        
        async with AsyncSessionLocal() as db:
            # Base query
            query = select(
                func.count(FinancialTransaction.id).label('total_count'),
                func.sum(FinancialTransaction.amount).label('total_amount'),
                func.count(
                    FinancialTransaction.id
                ).filter(
                    FinancialTransaction.status == TransactionStatus.COMPLETED
                ).label('completed_count'),
                func.sum(
                    FinancialTransaction.amount
                ).filter(
                    FinancialTransaction.status == TransactionStatus.COMPLETED
                ).label('completed_amount')
            ).where(
                and_(
                    FinancialTransaction.transaction_date >= start_date,
                    FinancialTransaction.transaction_date <= end_date
                )
            )
            
            # Add filters
            if agency_id:
                query = query.where(FinancialTransaction.agency_id == agency_id)
            if model_id:
                query = query.where(FinancialTransaction.model_id == model_id)
            
            result = await db.execute(query)
            row = result.one()
            
            stats.update({
                'total_transactions': row.total_count or 0,
                'total_amount': float(row.total_amount or 0),
                'completed_transactions': row.completed_count or 0,
                'completed_amount': float(row.completed_amount or 0),
                'pending_transactions': (row.total_count or 0) - (row.completed_count or 0),
                'pending_amount': float((row.total_amount or 0) - (row.completed_amount or 0))
            })
            
            # Get recent payouts
            payout_query = select(
                func.count(Payout.id).label('payout_count'),
                func.sum(Payout.amount).label('payout_amount')
            ).where(
                and_(
                    Payout.created_at >= start_date,
                    Payout.created_at <= end_date,
                    Payout.status == PayoutStatus.COMPLETED
                )
            )
            
            if model_id:
                payout_query = payout_query.where(Payout.model_id == model_id)
            
            payout_result = await db.execute(payout_query)
            payout_row = payout_result.one()
            
            stats.update({
                'payouts_completed': payout_row.payout_count or 0,
                'payouts_amount': float(payout_row.payout_amount or 0)
            })
        
        return stats


# Helper functions for sending financial notifications

async def notify_payment_status(transaction: FinancialTransaction, sio_server):
    """Send payment status notification to relevant rooms."""
    notification_data = {
        'transaction_id': str(transaction.id),
        'model_id': str(transaction.model_id),
        'amount': float(transaction.amount),
        'currency': transaction.currency,
        'status': transaction.status.value,
        'type': transaction.type.value,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Notify agency room
    if transaction.agency_id:
        await sio_server.emit(
            'payment_update',
            notification_data,
            room=f"financial:agency:{transaction.agency_id}",
            namespace='/financial'
        )
    
    # Notify super admin room
    await sio_server.emit(
        'payment_update',
        notification_data,
        room='financial:all',
        namespace='/financial'
    )


async def notify_payout_status(payout: Payout, sio_server):
    """Send payout status notification."""
    notification_data = {
        'payout_id': str(payout.id),
        'model_id': str(payout.model_id),
        'amount': float(payout.amount),
        'currency': payout.currency,
        'status': payout.status.value,
        'method': payout.payout_method,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Notify model room
    await sio_server.emit(
        'payout_update',
        notification_data,
        room=f"payouts:model:{payout.model_id}",
        namespace='/financial'
    )
    
    # Notify agency room (get from model)
    async with AsyncSessionLocal() as db:
        model = await db.get(ModelProfile, payout.model_id)
        if model:
            await sio_server.emit(
                'payout_update',
                notification_data,
                room=f"payouts:agency:{model.agency_id}",
                namespace='/financial'
            )