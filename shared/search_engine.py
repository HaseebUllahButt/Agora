import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict

class VectorSearch:
    """
    A simple TF-IDF based vector search engine for the marketplace.
    Provides semantic-like matching for agent descriptions.
    """
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.providers = []
        self.tfidf_matrix = None

    def index(self, providers: List[Dict]):
        """Index provider descriptions into the vector space."""
        if not providers:
            self.providers = []
            self.tfidf_matrix = None
            return

        self.providers = providers
        # Create a corpus of Name + Description + Type
        corpus = [
            f"{p['name']} {p['description']} {p['service_type']}"
            for p in providers
        ]
        
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Perform vector search using cosine similarity."""
        if self.tfidf_matrix is None or not self.providers:
            return []

        # Vectorize the query
        query_vec = self.vectorizer.transform([query])
        
        # Calculate similarity scores
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Get top indices
        top_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in top_indices:
            # Only include results with some similarity
            if similarities[idx] > 0:
                provider = self.providers[idx].copy()
                provider["search_score"] = float(similarities[idx])
                results.append(provider)
                
            if len(results) >= limit:
                break
                
        return results

# Singleton instance
_ENGINE = VectorSearch()

def get_search_engine() -> VectorSearch:
    return _ENGINE
