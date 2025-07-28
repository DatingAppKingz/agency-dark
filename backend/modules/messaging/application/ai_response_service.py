"""
AI-powered automated response service.

Provides intelligent response suggestions, sentiment analysis, and auto-reply capabilities.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import asyncio
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
import openai
from textblob import TextBlob
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.config import settings
from core.redis import redis_client
from core.exceptions import BadRequestError
from modules.messaging.domain.models import CannedResponse, MessageTemplate
from modules.messaging.domain.schemas import CannedResponseResponse
from modules.analytics.domain.models import Message, Fan

logger = logging.getLogger(__name__)


class AIResponseService:
    """Service for AI-powered response suggestions and automation."""
    
    def __init__(self):
        self.cache_prefix = "ai_response:"
        self.suggestion_cache_ttl = 3600  # 1 hour
        self.min_confidence_threshold = 0.7
        
        # Initialize OpenAI client if API key is provided
        self.openai_client = None
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            self.openai_client = openai
    
    async def get_response_suggestions(
        self,
        message_content: str,
        conversation_history: List[Dict[str, Any]],
        model_id: UUID,
        fan_id: UUID,
        agency_id: UUID,
        db: AsyncSession,
        num_suggestions: int = 3
    ) -> List[Dict[str, Any]]:
        """Get AI-powered response suggestions based on message and context."""
        # Check cache first
        cache_key = f"{self.cache_prefix}suggestions:{fan_id}:{hash(message_content)}"
        cached = await redis_client.get(cache_key)
        if cached:
            return eval(cached)  # In production, use proper JSON serialization
        
        suggestions = []
        
        # 1. Analyze message sentiment and intent
        sentiment = self._analyze_sentiment(message_content)
        intent = await self._classify_intent(message_content)
        
        # 2. Get fan context
        fan_context = await self._get_fan_context(fan_id, db)
        
        # 3. Find similar past conversations
        similar_responses = await self._find_similar_responses(
            message_content, model_id, agency_id, db
        )
        
        # 4. Generate AI suggestions if available
        if self.openai_client:
            ai_suggestions = await self._generate_ai_suggestions(
                message_content,
                conversation_history,
                fan_context,
                intent,
                sentiment,
                num_suggestions
            )
            suggestions.extend(ai_suggestions)
        
        # 5. Add template-based suggestions
        template_suggestions = await self._get_template_suggestions(
            intent, sentiment, agency_id, db
        )
        suggestions.extend(template_suggestions)
        
        # 6. Add canned response suggestions
        canned_suggestions = await self._get_canned_suggestions(
            message_content, intent, agency_id, db
        )
        suggestions.extend(canned_suggestions)
        
        # 7. Rank and filter suggestions
        suggestions = self._rank_suggestions(suggestions, fan_context, sentiment)
        suggestions = suggestions[:num_suggestions]
        
        # Cache results
        await redis_client.setex(
            cache_key,
            self.suggestion_cache_ttl,
            str(suggestions)
        )
        
        return suggestions
    
    async def analyze_conversation(
        self,
        model_id: UUID,
        fan_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze conversation patterns and provide insights."""
        # Get conversation history
        messages = await self._get_conversation_history(model_id, fan_id, db, limit=50)
        
        if not messages:
            return {
                "sentiment_trend": "neutral",
                "engagement_level": "low",
                "response_time_avg": 0,
                "topics": [],
                "recommendations": []
            }
        
        # Analyze sentiment trend
        sentiments = [self._analyze_sentiment(msg['content']) for msg in messages]
        sentiment_trend = self._calculate_sentiment_trend(sentiments)
        
        # Calculate engagement metrics
        engagement_level = self._calculate_engagement_level(messages)
        avg_response_time = self._calculate_avg_response_time(messages)
        
        # Extract topics
        topics = await self._extract_topics(messages)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            sentiment_trend,
            engagement_level,
            avg_response_time,
            topics
        )
        
        return {
            "sentiment_trend": sentiment_trend,
            "engagement_level": engagement_level,
            "response_time_avg": avg_response_time,
            "topics": topics,
            "recommendations": recommendations
        }
    
    async def auto_respond(
        self,
        message_content: str,
        model_id: UUID,
        fan_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> Optional[str]:
        """Generate automatic response if confidence is high enough."""
        # Check if auto-response is enabled for this model
        if not await self._is_auto_response_enabled(model_id, db):
            return None
        
        # Classify intent
        intent = await self._classify_intent(message_content)
        
        # Only auto-respond to certain intents
        auto_respond_intents = [
            "greeting", "thanks", "compliment", "faq",
            "subscription_question", "content_inquiry"
        ]
        
        if intent not in auto_respond_intents:
            return None
        
        # Get response suggestions
        suggestions = await self.get_response_suggestions(
            message_content, [], model_id, fan_id, agency_id, db, num_suggestions=1
        )
        
        if suggestions and suggestions[0]['confidence'] >= self.min_confidence_threshold:
            # Log auto-response
            await self._log_auto_response(model_id, fan_id, message_content, suggestions[0])
            return suggestions[0]['content']
        
        return None
    
    def _analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text."""
        blob = TextBlob(text)
        
        return {
            "polarity": blob.sentiment.polarity,  # -1 to 1
            "subjectivity": blob.sentiment.subjectivity,  # 0 to 1
            "label": self._get_sentiment_label(blob.sentiment.polarity)
        }
    
    def _get_sentiment_label(self, polarity: float) -> str:
        """Convert polarity score to label."""
        if polarity > 0.5:
            return "very_positive"
        elif polarity > 0.1:
            return "positive"
        elif polarity < -0.5:
            return "very_negative"
        elif polarity < -0.1:
            return "negative"
        else:
            return "neutral"
    
    async def _classify_intent(self, text: str) -> str:
        """Classify the intent of a message."""
        text_lower = text.lower()
        
        # Simple rule-based classification
        intent_patterns = {
            "greeting": [r"\bhey\b", r"\bhi\b", r"\bhello\b", r"\bgood morning\b", r"\bgood evening\b"],
            "thanks": [r"\bthank", r"\bthanks\b", r"\bappreciate\b", r"\bgrateful\b"],
            "compliment": [r"\bbeautiful\b", r"\bgorgeous\b", r"\bamazing\b", r"\blovely\b", r"\bhot\b"],
            "question": [r"\?", r"\bhow\b", r"\bwhat\b", r"\bwhen\b", r"\bwhere\b", r"\bwhy\b"],
            "subscription_question": [r"\bsubscribe", r"\bprice\b", r"\bcost\b", r"\bdiscount\b"],
            "content_inquiry": [r"\bcontent\b", r"\bvideo\b", r"\bphoto\b", r"\bcustom\b", r"\brequest\b"],
            "complaint": [r"\bissue\b", r"\bproblem\b", r"\bnot working\b", r"\bbroken\b", r"\bbug\b"],
            "sexual": [r"\bsex", r"\bnude", r"\bnaked", r"\bfuck", r"\bdick", r"\bpussy"],
            "faq": [r"\bhow does", r"\bcan i\b", r"\bdo you\b", r"\bis it possible\b"]
        }
        
        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        
        return "general"
    
    async def _get_fan_context(self, fan_id: UUID, db: AsyncSession) -> Dict[str, Any]:
        """Get contextual information about the fan."""
        result = await db.execute(
            select(Fan).where(Fan.id == fan_id)
        )
        fan = result.scalar_one_or_none()
        
        if not fan:
            return {}
        
        return {
            "name": fan.display_name or fan.username,
            "subscription_status": fan.subscription_status,
            "total_spent": float(fan.total_spent or 0),
            "subscription_duration": (datetime.utcnow() - fan.subscribed_at).days if fan.subscribed_at else 0,
            "last_activity": fan.last_activity,
            "preferences": fan.preferences or {},
            "tags": fan.tags or []
        }
    
    async def _find_similar_responses(
        self,
        message: str,
        model_id: UUID,
        agency_id: UUID,
        db: AsyncSession,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar past conversations and their responses."""
        # Get recent successful conversations
        result = await db.execute(
            select(Message).where(
                Message.model_id == model_id,
                Message.direction == "received",
                Message.created_at > datetime.utcnow() - timedelta(days=30)
            ).limit(100)
        )
        past_messages = result.scalars().all()
        
        if not past_messages:
            return []
        
        # Vectorize messages
        vectorizer = TfidfVectorizer(max_features=100)
        message_texts = [msg.content for msg in past_messages]
        message_texts.append(message)
        
        tfidf_matrix = vectorizer.fit_transform(message_texts)
        
        # Calculate similarity
        similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
        
        # Get top similar messages
        top_indices = np.argsort(similarities)[-limit:][::-1]
        
        similar_responses = []
        for idx in top_indices:
            if similarities[idx] > 0.5:  # Similarity threshold
                # Get the response to this message
                response = await self._get_response_to_message(past_messages[idx].id, db)
                if response:
                    similar_responses.append({
                        "original_message": past_messages[idx].content,
                        "response": response.content,
                        "similarity": float(similarities[idx]),
                        "success_metrics": await self._get_response_success_metrics(response.id, db)
                    })
        
        return similar_responses
    
    async def _generate_ai_suggestions(
        self,
        message: str,
        conversation_history: List[Dict[str, Any]],
        fan_context: Dict[str, Any],
        intent: str,
        sentiment: Dict[str, float],
        num_suggestions: int
    ) -> List[Dict[str, Any]]:
        """Generate AI-powered response suggestions using OpenAI."""
        if not self.openai_client:
            return []
        
        try:
            # Build context for AI
            context = f"""
            You are helping a content creator respond to a fan message.
            
            Fan Context:
            - Name: {fan_context.get('name', 'Unknown')}
            - Subscription Status: {fan_context.get('subscription_status', 'Unknown')}
            - Total Spent: ${fan_context.get('total_spent', 0):.2f}
            - Member for: {fan_context.get('subscription_duration', 0)} days
            
            Message Intent: {intent}
            Message Sentiment: {sentiment['label']}
            
            Fan Message: {message}
            
            Generate {num_suggestions} different response options that are:
            1. Personalized and engaging
            2. Appropriate for the platform
            3. Encouraging continued interaction
            4. Matching the sentiment appropriately
            """
            
            # Add conversation history if available
            if conversation_history:
                context += "\n\nRecent conversation:\n"
                for msg in conversation_history[-5:]:
                    context += f"{msg['sender']}: {msg['content']}\n"
            
            response = await self.openai_client.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for content creators."},
                    {"role": "user", "content": context}
                ],
                temperature=0.8,
                max_tokens=500,
                n=num_suggestions
            )
            
            suggestions = []
            for i, choice in enumerate(response.choices):
                suggestions.append({
                    "content": choice.message.content.strip(),
                    "type": "ai_generated",
                    "confidence": 0.8 - (i * 0.1),  # Decrease confidence for alternatives
                    "intent_match": intent,
                    "sentiment_match": sentiment['label']
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating AI suggestions: {e}")
            return []
    
    async def _get_template_suggestions(
        self,
        intent: str,
        sentiment: Dict[str, float],
        agency_id: UUID,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get template-based suggestions matching intent and sentiment."""
        # Map intents to template categories
        intent_category_map = {
            "greeting": "greeting",
            "thanks": "engagement",
            "compliment": "engagement",
            "subscription_question": "promotional",
            "content_inquiry": "promotional",
            "faq": "engagement"
        }
        
        category = intent_category_map.get(intent, "custom")
        
        # Get relevant templates
        result = await db.execute(
            select(MessageTemplate).where(
                MessageTemplate.agency_id == agency_id,
                MessageTemplate.category == category,
                MessageTemplate.is_active == True
            ).order_by(MessageTemplate.usage_count.desc()).limit(3)
        )
        templates = result.scalars().all()
        
        suggestions = []
        for template in templates:
            suggestions.append({
                "content": template.content,
                "type": "template",
                "template_id": str(template.id),
                "confidence": 0.7,
                "intent_match": intent,
                "variables": template.variables
            })
        
        return suggestions
    
    async def _get_canned_suggestions(
        self,
        message: str,
        intent: str,
        agency_id: UUID,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get canned response suggestions."""
        # Search for relevant canned responses
        search_terms = message.lower().split()[:5]  # First 5 words
        
        query = select(CannedResponse).where(
            CannedResponse.agency_id == agency_id,
            CannedResponse.is_active == True
        )
        
        # Add search conditions
        for term in search_terms:
            query = query.where(
                CannedResponse.content.ilike(f"%{term}%")
            )
        
        query = query.limit(3)
        
        result = await db.execute(query)
        canned_responses = result.scalars().all()
        
        suggestions = []
        for response in canned_responses:
            suggestions.append({
                "content": response.content,
                "type": "canned",
                "canned_id": str(response.id),
                "confidence": 0.6,
                "shortcut": response.shortcut
            })
        
        return suggestions
    
    def _rank_suggestions(
        self,
        suggestions: List[Dict[str, Any]],
        fan_context: Dict[str, Any],
        sentiment: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Rank suggestions based on relevance and context."""
        for suggestion in suggestions:
            # Adjust confidence based on various factors
            
            # Boost AI-generated suggestions
            if suggestion['type'] == 'ai_generated':
                suggestion['confidence'] *= 1.1
            
            # Boost if sentiment matches
            if suggestion.get('sentiment_match') == sentiment['label']:
                suggestion['confidence'] *= 1.05
            
            # Boost for high-value fans
            if fan_context.get('total_spent', 0) > 100:
                suggestion['confidence'] *= 1.05
            
            # Cap confidence at 1.0
            suggestion['confidence'] = min(suggestion['confidence'], 1.0)
        
        # Sort by confidence
        return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)
    
    async def _get_conversation_history(
        self,
        model_id: UUID,
        fan_id: UUID,
        db: AsyncSession,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history."""
        result = await db.execute(
            select(Message).where(
                Message.model_id == model_id,
                Message.fan_id == fan_id
            ).order_by(Message.created_at.desc()).limit(limit)
        )
        messages = result.scalars().all()
        
        return [
            {
                "content": msg.content,
                "sender": "fan" if msg.direction == "received" else "model",
                "timestamp": msg.created_at,
                "sentiment": self._analyze_sentiment(msg.content)
            }
            for msg in reversed(messages)
        ]
    
    def _calculate_sentiment_trend(self, sentiments: List[Dict[str, float]]) -> str:
        """Calculate overall sentiment trend."""
        if not sentiments:
            return "neutral"
        
        recent_sentiments = sentiments[-10:]  # Last 10 messages
        avg_polarity = np.mean([s['polarity'] for s in recent_sentiments])
        
        # Check trend
        if len(sentiments) > 5:
            first_half = sentiments[:len(sentiments)//2]
            second_half = sentiments[len(sentiments)//2:]
            
            first_avg = np.mean([s['polarity'] for s in first_half])
            second_avg = np.mean([s['polarity'] for s in second_half])
            
            if second_avg > first_avg + 0.2:
                return "improving"
            elif second_avg < first_avg - 0.2:
                return "declining"
        
        return self._get_sentiment_label(avg_polarity)
    
    def _calculate_engagement_level(self, messages: List[Dict[str, Any]]) -> str:
        """Calculate engagement level based on message frequency and length."""
        if not messages:
            return "low"
        
        # Calculate message frequency
        time_span = (messages[-1]['timestamp'] - messages[0]['timestamp']).days or 1
        msg_per_day = len(messages) / time_span
        
        # Calculate average message length
        avg_length = np.mean([len(msg['content']) for msg in messages])
        
        if msg_per_day > 5 and avg_length > 50:
            return "high"
        elif msg_per_day > 2 or avg_length > 30:
            return "medium"
        else:
            return "low"
    
    def _calculate_avg_response_time(self, messages: List[Dict[str, Any]]) -> float:
        """Calculate average response time in minutes."""
        response_times = []
        
        for i in range(1, len(messages)):
            if messages[i]['sender'] != messages[i-1]['sender']:
                time_diff = (messages[i]['timestamp'] - messages[i-1]['timestamp']).total_seconds() / 60
                if time_diff < 1440:  # Less than 24 hours
                    response_times.append(time_diff)
        
        return np.mean(response_times) if response_times else 0
    
    async def _extract_topics(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract main topics from conversation."""
        # Simple keyword extraction
        all_text = " ".join([msg['content'] for msg in messages])
        
        # Common topics in this context
        topic_keywords = {
            "content": ["video", "photo", "content", "post", "update"],
            "personal": ["life", "day", "feel", "mood", "personal"],
            "sexual": ["sexy", "hot", "naughty", "private", "custom"],
            "subscription": ["subscribe", "price", "discount", "offer", "deal"],
            "compliments": ["beautiful", "gorgeous", "amazing", "love", "perfect"],
            "technical": ["issue", "problem", "help", "work", "access"]
        }
        
        found_topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in all_text.lower() for keyword in keywords):
                found_topics.append(topic)
        
        return found_topics
    
    def _generate_recommendations(
        self,
        sentiment_trend: str,
        engagement_level: str,
        avg_response_time: float,
        topics: List[str]
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        if sentiment_trend == "declining":
            recommendations.append("Fan sentiment is declining. Consider more personalized responses.")
        
        if engagement_level == "low":
            recommendations.append("Low engagement. Try asking open-ended questions.")
        
        if avg_response_time > 60:
            recommendations.append("Response time is high. Consider using auto-responses for common questions.")
        
        if "technical" in topics:
            recommendations.append("Technical issues discussed. Ensure problems are resolved.")
        
        if "subscription" in topics and engagement_level == "high":
            recommendations.append("High engagement with subscription interest. Good opportunity for upsell.")
        
        return recommendations
    
    async def _get_response_to_message(self, message_id: UUID, db: AsyncSession) -> Optional[Message]:
        """Get the response to a specific message."""
        # This is simplified - in reality you'd need proper conversation threading
        result = await db.execute(
            select(Message).where(
                Message.reply_to_id == message_id,
                Message.direction == "sent"
            ).order_by(Message.created_at).limit(1)
        )
        return result.scalar_one_or_none()
    
    async def _get_response_success_metrics(self, response_id: UUID, db: AsyncSession) -> Dict[str, Any]:
        """Get success metrics for a response."""
        # This would analyze subsequent fan behavior
        return {
            "led_to_purchase": False,  # Placeholder
            "continued_conversation": True,
            "sentiment_improvement": 0.1
        }
    
    async def _is_auto_response_enabled(self, model_id: UUID, db: AsyncSession) -> bool:
        """Check if auto-response is enabled for the model."""
        # This would check model settings
        return False  # Default to disabled for safety
    
    async def _log_auto_response(
        self,
        model_id: UUID,
        fan_id: UUID,
        original_message: str,
        response: Dict[str, Any]
    ):
        """Log auto-response for monitoring and improvement."""
        log_data = {
            "model_id": str(model_id),
            "fan_id": str(fan_id),
            "original_message": original_message,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in Redis for analysis
        key = f"{self.cache_prefix}auto_log:{datetime.utcnow().date()}"
        await redis_client.lpush(key, str(log_data))
        await redis_client.expire(key, 86400 * 30)  # Keep for 30 days