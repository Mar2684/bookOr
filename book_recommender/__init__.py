"""book_recommender : moteur de recommandation de livres (stdlib uniquement).

Architecture modulaire : modèles, exceptions, stockage JSON offline-first,
client API Google Books avec fallback mock, moteur hybride et service métier.
"""

from .api_client import GoogleBooksClient, MockBookRepository
from .exceptions import (
    ApiUnavailableError,
    BookNotFoundError,
    BookRecommenderError,
    StorageError,
    UserNotFoundError,
)
from .models import Book, Feedback, Recommendation, UserProfile
from .recommender import RecommendationEngine
from .service import BookService
from .storage import JsonStorage

__all__ = [
    "ApiUnavailableError",
    "Book",
    "BookNotFoundError",
    "BookRecommenderError",
    "BookService",
    "Feedback",
    "GoogleBooksClient",
    "JsonStorage",
    "MockBookRepository",
    "Recommendation",
    "RecommendationEngine",
    "StorageError",
    "UserNotFoundError",
    "UserProfile",
]

__version__ = "0.1.0"
