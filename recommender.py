# recommender.py
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel, cosine_similarity

class ContentRecommender:
    def __init__(self, places_data):
        """
        places_data: List of dicts containing 'id', 'name', 'tags', 'description', 'type'
        """
        self.df = pd.DataFrame(places_data)
        if not self.df.empty:
            self._prepare_vectors()

    def _prepare_vectors(self):
        # Create a "soup" of metadata
        # Fill NaN with empty strings to avoid errors
        self.df['description'] = self.df['description'].fillna('')
        self.df['tags'] = self.df['tags'].fillna('')
        self.df['type'] = self.df['type'].fillna('')
        
        self.df['soup'] = (
            self.df['name'] + " " + 
            self.df['type'] + " " + 
            self.df['tags'] + " " + 
            self.df['description']
        )
        
        tfidf = TfidfVectorizer(stop_words='english')
        self.tfidf_matrix = tfidf.fit_transform(self.df['soup'])
        self.cosine_sim = linear_kernel(self.tfidf_matrix, self.tfidf_matrix)
        
        # Mapping from Place ID to Matrix Index
        self.id_to_idx = pd.Series(self.df.index, index=self.df['id'])

    def recommend(self, place_id, limit=3):
        if self.df.empty or place_id not in self.id_to_idx:
            return []

        idx = self.id_to_idx[place_id]
        sim_scores = list(enumerate(self.cosine_sim[idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        
        # Skip index 0 (self)
        sim_scores = sim_scores[1:limit+1]
        
        place_indices = [i[0] for i in sim_scores]
        return self.df.iloc[place_indices]['id'].tolist()

class CollaborativeRecommender:
    def __init__(self, reviews_data):
        """
        reviews_data: List of dicts containing 'user_id', 'place_id', 'rating'
        """
        self.df = pd.DataFrame(reviews_data)
        self.user_item_matrix = None
        self.item_similarity_df = None
        
        if not self.df.empty:
            self._prepare_matrix()

    def _prepare_matrix(self):
        # Create User-Item Matrix
        self.user_item_matrix = self.df.pivot_table(index='user_id', columns='place_id', values='rating')
        
        # Fill NaN with 0 for calculation
        matrix_filled = self.user_item_matrix.fillna(0)
        
        # Calculate Item-Item Similarity (Cosine)
        # Transpose because we want similarity between columns (items)
        item_similarity = cosine_similarity(matrix_filled.T)
        self.item_similarity_df = pd.DataFrame(item_similarity, index=self.user_item_matrix.columns, columns=self.user_item_matrix.columns)

    def recommend_for_user(self, user_id, limit=3):
        """
        Recommend items for a user based on their previous ratings and item similarities.
        """
        if self.df.empty or self.user_item_matrix is None or user_id not in self.user_item_matrix.index:
            return []

        # Get user's ratings
        user_ratings = self.user_item_matrix.loc[user_id]
        user_ratings = user_ratings[user_ratings > 0] # Only rated items
        
        if user_ratings.empty:
            return []

        similar_scores = pd.Series(dtype=float)

        for place_id, rating in user_ratings.items():
            if place_id in self.item_similarity_df.index:
                # Get similar items to the one the user rated
                # Weight by the user's rating (so highly rated items have more influence)
                sims = self.item_similarity_df[place_id] * (rating / 5.0)
                similar_scores = similar_scores.add(sims, fill_value=0)
        
        # Remove items the user has already rated
        similar_scores = similar_scores.drop(user_ratings.index, errors='ignore')
        
        # Sort and return top N
        recommendations = similar_scores.sort_values(ascending=False).head(limit)
        return recommendations.index.tolist()

    def get_similar_items(self, place_id, limit=3):
        """
        "Students who liked X also liked Y"
        """
        if self.item_similarity_df is None or place_id not in self.item_similarity_df.index:
            return []
            
        sims = self.item_similarity_df[place_id].sort_values(ascending=False)
        # Skip self
        return sims.iloc[1:limit+1].index.tolist()

class HybridRecommender:
    def __init__(self, places_data, reviews_data):
        self.content_engine = ContentRecommender(places_data)
        self.collab_engine = CollaborativeRecommender(reviews_data)
        self.places_df = pd.DataFrame(places_data)
        self.reviews_df = pd.DataFrame(reviews_data)
        
        # Calculate popularity (Trending)
        self.popular_items = []
        if not self.reviews_df.empty:
            # Sort by number of ratings
            pop = self.reviews_df.groupby('place_id').size().sort_values(ascending=False)
            self.popular_items = pop.index.tolist()

    def recommend(self, user_id, user_preferences=None, limit=5):
        """
        Hybrid Recommendation:
        1. If User has history -> Collaborative Filtering
        2. If User has no history but has preferences -> Cold Start (Content Filtering)
        3. Fallback -> Popular / Random
        """
        recs = []
        
        # 1. Try Collaborative
        collab_recs = self.collab_engine.recommend_for_user(user_id, limit=limit)
        if collab_recs:
            recs.extend(collab_recs)
        
        # 2. If not enough recs, try Cold Start / Content Based on Preferences
        if len(recs) < limit and user_preferences:
            # user_preferences: list of strings (e.g. ['Italian', 'Cafe'])
            # Filter places that match preferences
            if not self.places_df.empty:
                # Simple keyword matching in 'soup' or 'type'/'tags'
                mask = self.places_df.apply(lambda x: any(p.lower() in str(x['type']).lower() or p.lower() in str(x['tags']).lower() for p in user_preferences), axis=1)
                content_recs = self.places_df[mask]['id'].tolist()
                
                # Avoid duplicates
                content_recs = [r for r in content_recs if r not in recs]
                recs.extend(content_recs)

        # 3. Fallback to Popular items
        if len(recs) < limit:
            for p in self.popular_items:
                if p not in recs:
                    recs.append(p)
                    if len(recs) >= limit:
                        break
        
        return recs[:limit]