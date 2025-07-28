"""
Content Recommendation Engine using collaborative and content-based filtering
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import scipy.sparse as sp
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

from .base import BaseMLModel


class ContentRecommendationEngine(BaseMLModel):
    """
    Hybrid recommendation system combining collaborative filtering,
    content-based filtering, and popularity-based recommendations
    """
    
    def __init__(self, version: str = "1.0.0"):
        super().__init__("content_recommendation", version)
        self.user_factors = None
        self.item_factors = None
        self.content_features = None
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.svd_model = TruncatedSVD(n_components=50, random_state=42)
        self.popularity_scores = {}
        self.user_profiles = {}
        self.content_similarity_matrix = None
        
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess interaction and content data
        
        Expected columns:
        - user_id
        - content_id
        - interaction_type (view, like, purchase, etc.)
        - timestamp
        - content_title (optional)
        - content_description (optional)
        - content_tags (optional)
        """
        df = data.copy()
        
        # Convert timestamp
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Create interaction weights
        interaction_weights = {
            'view': 1.0,
            'like': 2.0,
            'comment': 3.0,
            'share': 4.0,
            'purchase': 5.0,
            'tip': 5.0
        }
        
        df['interaction_weight'] = df['interaction_type'].map(interaction_weights).fillna(1.0)
        
        # Add time decay factor (more recent interactions are more important)
        if 'timestamp' in df.columns:
            days_ago = (datetime.now() - df['timestamp']).dt.days
            df['time_decay'] = np.exp(-days_ago / 30)  # 30-day half-life
            df['weighted_interaction'] = df['interaction_weight'] * df['time_decay']
        else:
            df['weighted_interaction'] = df['interaction_weight']
        
        return df
    
    def train(self, 
              interaction_data: pd.DataFrame,
              content_data: Optional[pd.DataFrame] = None,
              **kwargs) -> Dict[str, Any]:
        """
        Train the recommendation engine
        
        Args:
            interaction_data: User-content interaction data
            content_data: Content metadata (titles, descriptions, tags)
        """
        # Preprocess interaction data
        interactions = self.preprocess_data(interaction_data)
        
        # Create user-item matrix
        user_item_matrix = self._create_user_item_matrix(interactions)
        
        # Train collaborative filtering model
        self._train_collaborative_filtering(user_item_matrix)
        
        # Train content-based model if content data is provided
        if content_data is not None:
            self._train_content_based_filtering(content_data)
        
        # Calculate popularity scores
        self._calculate_popularity_scores(interactions)
        
        # Build user profiles
        self._build_user_profiles(interactions)
        
        # Store training metadata
        self.training_metadata = {
            'n_users': len(interactions['user_id'].unique()),
            'n_items': len(interactions['content_id'].unique()),
            'n_interactions': len(interactions),
            'training_date': datetime.now().isoformat(),
            'has_content_features': content_data is not None
        }
        
        self.is_trained = True
        return self.training_metadata
    
    def _create_user_item_matrix(self, interactions: pd.DataFrame) -> sp.csr_matrix:
        """Create sparse user-item interaction matrix"""
        # Aggregate interactions by user and content
        user_item_df = interactions.groupby(['user_id', 'content_id'])['weighted_interaction'].sum().reset_index()
        
        # Create mappings
        self.user_to_idx = {user: idx for idx, user in enumerate(user_item_df['user_id'].unique())}
        self.idx_to_user = {idx: user for user, idx in self.user_to_idx.items()}
        self.item_to_idx = {item: idx for idx, item in enumerate(user_item_df['content_id'].unique())}
        self.idx_to_item = {idx: item for item, idx in self.item_to_idx.items()}
        
        # Create sparse matrix
        row_indices = [self.user_to_idx[user] for user in user_item_df['user_id']]
        col_indices = [self.item_to_idx[item] for item in user_item_df['content_id']]
        values = user_item_df['weighted_interaction'].values
        
        user_item_matrix = sp.csr_matrix(
            (values, (row_indices, col_indices)),
            shape=(len(self.user_to_idx), len(self.item_to_idx))
        )
        
        return user_item_matrix
    
    def _train_collaborative_filtering(self, user_item_matrix: sp.csr_matrix):
        """Train SVD-based collaborative filtering model"""
        # Apply SVD
        self.user_factors = self.svd_model.fit_transform(user_item_matrix)
        self.item_factors = self.svd_model.components_.T
        
        # Normalize factors
        self.user_factors = self.user_factors / np.linalg.norm(self.user_factors, axis=1, keepdims=True)
        self.item_factors = self.item_factors / np.linalg.norm(self.item_factors, axis=1, keepdims=True)
    
    def _train_content_based_filtering(self, content_data: pd.DataFrame):
        """Train content-based filtering using content features"""
        # Combine text features
        content_data['combined_text'] = (
            content_data.get('content_title', '').fillna('') + ' ' +
            content_data.get('content_description', '').fillna('') + ' ' +
            content_data.get('content_tags', '').fillna('')
        )
        
        # Create TF-IDF features
        tfidf_features = self.tfidf_vectorizer.fit_transform(content_data['combined_text'])
        
        # Store content features
        self.content_features = pd.DataFrame(
            tfidf_features.toarray(),
            index=content_data['content_id']
        )
        
        # Calculate content similarity matrix
        self.content_similarity_matrix = cosine_similarity(tfidf_features)
    
    def _calculate_popularity_scores(self, interactions: pd.DataFrame):
        """Calculate popularity scores for content"""
        # Recent popularity (last 7 days)
        recent_date = datetime.now() - timedelta(days=7)
        recent_interactions = interactions[interactions['timestamp'] > recent_date]
        
        # Calculate scores
        popularity = interactions.groupby('content_id').agg({
            'user_id': 'nunique',  # Unique users
            'weighted_interaction': 'sum'  # Total weighted interactions
        })
        
        recent_popularity = recent_interactions.groupby('content_id').agg({
            'user_id': 'nunique',
            'weighted_interaction': 'sum'
        })
        
        # Combine scores
        for content_id in popularity.index:
            total_score = popularity.loc[content_id, 'weighted_interaction']
            recent_score = recent_popularity.get(content_id, {}).get('weighted_interaction', 0)
            unique_users = popularity.loc[content_id, 'user_id']
            
            # Weighted popularity score
            self.popularity_scores[content_id] = {
                'total_score': total_score,
                'recent_score': recent_score,
                'unique_users': unique_users,
                'combined_score': 0.3 * total_score + 0.7 * recent_score
            }
    
    def _build_user_profiles(self, interactions: pd.DataFrame):
        """Build user preference profiles"""
        user_groups = interactions.groupby('user_id')
        
        for user_id, user_data in user_groups:
            # Get user's interaction history
            content_ids = user_data['content_id'].values
            weights = user_data['weighted_interaction'].values
            
            # Calculate preferences
            self.user_profiles[user_id] = {
                'content_history': list(content_ids),
                'interaction_weights': list(weights),
                'avg_interaction_weight': np.mean(weights),
                'n_interactions': len(user_data),
                'last_interaction': user_data['timestamp'].max() if 'timestamp' in user_data else None
            }
    
    def predict(self, user_id: str, n_recommendations: int = 10) -> List[Tuple[str, float]]:
        """
        Generate recommendations for a user
        
        Returns:
            List of (content_id, score) tuples
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        recommendations = []
        
        # Get collaborative filtering recommendations
        if user_id in self.user_to_idx:
            cf_recs = self._get_collaborative_recommendations(user_id, n_recommendations * 2)
            recommendations.extend(cf_recs)
        
        # Get content-based recommendations if available
        if hasattr(self, 'content_similarity_matrix') and user_id in self.user_profiles:
            cb_recs = self._get_content_based_recommendations(user_id, n_recommendations * 2)
            recommendations.extend(cb_recs)
        
        # Add popularity-based recommendations for new users or as fallback
        pop_recs = self._get_popularity_recommendations(n_recommendations)
        recommendations.extend(pop_recs)
        
        # Combine and deduplicate recommendations
        recommendation_dict = {}
        for content_id, score in recommendations:
            if content_id not in recommendation_dict:
                recommendation_dict[content_id] = score
            else:
                # Weighted combination of scores
                recommendation_dict[content_id] = max(recommendation_dict[content_id], score)
        
        # Filter out already seen content
        if user_id in self.user_profiles:
            seen_content = set(self.user_profiles[user_id]['content_history'])
            recommendation_dict = {k: v for k, v in recommendation_dict.items() if k not in seen_content}
        
        # Sort by score and return top N
        sorted_recommendations = sorted(recommendation_dict.items(), key=lambda x: x[1], reverse=True)
        return sorted_recommendations[:n_recommendations]
    
    def _get_collaborative_recommendations(self, user_id: str, n_recommendations: int) -> List[Tuple[str, float]]:
        """Get recommendations using collaborative filtering"""
        user_idx = self.user_to_idx[user_id]
        user_vector = self.user_factors[user_idx]
        
        # Calculate scores for all items
        scores = np.dot(self.item_factors, user_vector)
        
        # Get top items
        top_indices = np.argsort(scores)[::-1][:n_recommendations]
        
        recommendations = []
        for idx in top_indices:
            content_id = self.idx_to_item[idx]
            score = scores[idx]
            recommendations.append((content_id, float(score)))
        
        return recommendations
    
    def _get_content_based_recommendations(self, user_id: str, n_recommendations: int) -> List[Tuple[str, float]]:
        """Get recommendations based on content similarity"""
        user_history = self.user_profiles[user_id]['content_history']
        weights = self.user_profiles[user_id]['interaction_weights']
        
        # Calculate weighted average of content features for user's history
        user_content_indices = []
        for content_id in user_history:
            if content_id in self.content_features.index:
                idx = self.content_features.index.get_loc(content_id)
                user_content_indices.append(idx)
        
        if not user_content_indices:
            return []
        
        # Get similar content
        similarities = self.content_similarity_matrix[user_content_indices].mean(axis=0)
        top_indices = np.argsort(similarities)[::-1][:n_recommendations]
        
        recommendations = []
        for idx in top_indices:
            content_id = self.content_features.index[idx]
            score = similarities[idx]
            recommendations.append((content_id, float(score)))
        
        return recommendations
    
    def _get_popularity_recommendations(self, n_recommendations: int) -> List[Tuple[str, float]]:
        """Get popular content recommendations"""
        sorted_content = sorted(
            self.popularity_scores.items(),
            key=lambda x: x[1]['combined_score'],
            reverse=True
        )
        
        recommendations = []
        for content_id, scores in sorted_content[:n_recommendations]:
            # Normalize score to [0, 1]
            max_score = sorted_content[0][1]['combined_score'] if sorted_content else 1
            normalized_score = scores['combined_score'] / max_score
            recommendations.append((content_id, normalized_score))
        
        return recommendations
    
    def get_similar_content(self, content_id: str, n_similar: int = 5) -> List[Tuple[str, float]]:
        """Find similar content items"""
        if not hasattr(self, 'content_similarity_matrix') or content_id not in self.content_features.index:
            return []
        
        idx = self.content_features.index.get_loc(content_id)
        similarities = self.content_similarity_matrix[idx]
        
        # Get top similar items (excluding itself)
        top_indices = np.argsort(similarities)[::-1][1:n_similar+1]
        
        similar_items = []
        for similar_idx in top_indices:
            similar_content_id = self.content_features.index[similar_idx]
            score = similarities[similar_idx]
            similar_items.append((similar_content_id, float(score)))
        
        return similar_items
    
    def explain_recommendation(self, user_id: str, content_id: str) -> Dict[str, Any]:
        """
        Explain why a particular content was recommended
        """
        explanation = {
            'content_id': content_id,
            'user_id': user_id,
            'reasons': []
        }
        
        # Check collaborative filtering score
        if user_id in self.user_to_idx and content_id in self.item_to_idx:
            user_idx = self.user_to_idx[user_id]
            item_idx = self.item_to_idx[content_id]
            cf_score = np.dot(self.user_factors[user_idx], self.item_factors[item_idx])
            explanation['collaborative_score'] = float(cf_score)
            if cf_score > 0.5:
                explanation['reasons'].append("Users with similar preferences enjoyed this content")
        
        # Check content similarity
        if hasattr(self, 'content_similarity_matrix') and user_id in self.user_profiles:
            user_history = self.user_profiles[user_id]['content_history']
            similar_content = []
            for hist_content in user_history:
                similar = self.get_similar_content(hist_content, n_similar=10)
                if content_id in [c[0] for c in similar]:
                    similar_content.append(hist_content)
            
            if similar_content:
                explanation['similar_to_history'] = similar_content
                explanation['reasons'].append(f"Similar to content you've enjoyed: {', '.join(similar_content[:3])}")
        
        # Check popularity
        if content_id in self.popularity_scores:
            pop_data = self.popularity_scores[content_id]
            explanation['popularity_data'] = pop_data
            if pop_data['recent_score'] > np.mean([p['recent_score'] for p in self.popularity_scores.values()]):
                explanation['reasons'].append("Trending content with high engagement")
        
        return explanation
    
    def evaluate(self, test_data: pd.DataFrame, y_true: Optional[np.ndarray] = None) -> Dict[str, float]:
        """Evaluate recommendation quality"""
        # This would typically use metrics like precision@k, recall@k, NDCG, etc.
        # For now, return placeholder metrics
        return {
            'coverage': len(self.item_to_idx) / len(self.popularity_scores) if self.popularity_scores else 0,
            'catalog_percentage': len(self.popularity_scores) / len(self.item_to_idx) if self.item_to_idx else 0,
            'n_users': len(self.user_to_idx) if self.user_to_idx else 0,
            'n_items': len(self.item_to_idx) if self.item_to_idx else 0
        }