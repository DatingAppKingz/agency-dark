"""Search indexing tasks for Elasticsearch."""

from typing import Dict, Any, Optional
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session
import asyncio

from core.database_sync import get_db_sync
from core.elasticsearch_client import es_client
from core.logger import get_logger
from models.model import Model
from models.message import Message
from models.media import Media
from models.transaction import Transaction
from models.user import User
from services.search_service import SearchService

logger = get_logger(__name__)


@shared_task(bind=True, name='tasks.search_tasks.index_model')
def index_model(self, model_id: str):
    """Index a model in Elasticsearch."""
    try:
        with get_db_sync() as db:
            model = db.get(Model, model_id)
            if not model:
                logger.error(f"Model {model_id} not found")
                return
            
            # Create search service and index model
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_index_model_async(db, model))
            finally:
                loop.close()
            
            logger.info(f"Successfully indexed model {model_id}")
            
    except Exception as e:
        logger.error(f"Error indexing model {model_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name='tasks.search_tasks.index_message')
def index_message(self, message_id: str):
    """Index a message in Elasticsearch."""
    try:
        with get_db_sync() as db:
            message = db.get(Message, message_id)
            if not message:
                logger.error(f"Message {message_id} not found")
                return
            
            # Create search service and index message
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_index_message_async(db, message))
            finally:
                loop.close()
            
            logger.info(f"Successfully indexed message {message_id}")
            
    except Exception as e:
        logger.error(f"Error indexing message {message_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name='tasks.search_tasks.index_media')
def index_media(self, media_id: str):
    """Index media in Elasticsearch."""
    try:
        with get_db_sync() as db:
            media = db.get(Media, media_id)
            if not media:
                logger.error(f"Media {media_id} not found")
                return
            
            # Create search service and index media
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_index_media_async(db, media))
            finally:
                loop.close()
            
            logger.info(f"Successfully indexed media {media_id}")
            
    except Exception as e:
        logger.error(f"Error indexing media {media_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name='tasks.search_tasks.remove_from_index')
def remove_from_index(self, index_name: str, doc_id: str):
    """Remove a document from Elasticsearch index."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_remove_from_index_async(index_name, doc_id))
        finally:
            loop.close()
        
        logger.info(f"Successfully removed {doc_id} from {index_name}")
        
    except Exception as e:
        logger.error(f"Error removing {doc_id} from {index_name}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name='tasks.search_tasks.reindex_agency')
def reindex_agency(self, agency_id: str):
    """Reindex all data for an agency."""
    try:
        with get_db_sync() as db:
            logger.info(f"Starting reindex for agency {agency_id}")
            
            # Index all models
            models = db.execute(
                select(Model).where(Model.agency_id == agency_id)
            ).scalars().all()
            
            model_count = 0
            for model in models:
                index_model.delay(str(model.id))
                model_count += 1
            
            # Index all media
            media_items = db.execute(
                select(Media).where(Media.agency_id == agency_id)
            ).scalars().all()
            
            media_count = 0
            for media in media_items:
                index_media.delay(str(media.id))
                media_count += 1
            
            logger.info(f"Queued reindex for agency {agency_id}: {model_count} models, {media_count} media items")
            
            return {
                "agency_id": agency_id,
                "models_queued": model_count,
                "media_queued": media_count
            }
            
    except Exception as e:
        logger.error(f"Error reindexing agency {agency_id}: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, name='tasks.search_tasks.bulk_index_messages')
def bulk_index_messages(self, model_id: str, limit: int = 1000):
    """Bulk index messages for a model."""
    try:
        with get_db_sync() as db:
            messages = db.execute(
                select(Message)
                .where(Message.model_id == model_id)
                .limit(limit)
            ).scalars().all()
            
            # Prepare documents for bulk indexing
            documents = []
            for message in messages:
                doc = {
                    "id": str(message.id),
                    "model_id": str(message.model_id),
                    "fan_id": str(message.fan_id),
                    "content": message.content,
                    "platform": message.platform,
                    "is_from_fan": message.is_from_fan,
                    "has_media": message.has_media,
                    "tip_amount": float(message.tip_amount) if message.tip_amount else 0,
                    "sentiment": message.sentiment,
                    "created_at": message.created_at.isoformat()
                }
                documents.append(doc)
            
            if documents:
                # Bulk index
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_bulk_index_async('messages', documents))
                finally:
                    loop.close()
                
                logger.info(f"Successfully bulk indexed {len(documents)} messages for model {model_id}")
            
            return {"model_id": model_id, "indexed_count": len(documents)}
            
    except Exception as e:
        logger.error(f"Error bulk indexing messages for model {model_id}: {e}")
        raise self.retry(exc=e, countdown=300)


# Helper async functions
async def _index_model_async(db: Session, model: Model):
    """Async helper to index model."""
    await es_client.initialize()
    search_service = SearchService(db)
    await search_service.index_model(model)


async def _index_message_async(db: Session, message: Message):
    """Async helper to index message."""
    await es_client.initialize()
    search_service = SearchService(db)
    await search_service.index_message(message)


async def _index_media_async(db: Session, media: Media):
    """Async helper to index media."""
    await es_client.initialize()
    search_service = SearchService(db)
    await search_service.index_media(media)


async def _remove_from_index_async(index_name: str, doc_id: str):
    """Async helper to remove from index."""
    await es_client.initialize()
    await es_client.delete_document(index_name, doc_id)


async def _bulk_index_async(index_name: str, documents: list):
    """Async helper for bulk indexing."""
    await es_client.initialize()
    await es_client.bulk_index(index_name, documents)