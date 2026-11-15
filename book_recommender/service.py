"""Façade métier orchestrant stockage, sources de données et moteur.

Exposé haut niveau des cas d'usage : profil, recherche, recommandations,
feedback et wishlist, avec persistance offline-first à chaque mutation.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union

from .api_client import GoogleBooksClient, MockBookRepository
from .exceptions import (
    ApiUnavailableError,
    BookNotFoundError,
    UserNotFoundError,
)
from .models import Book, Feedback, Recommendation, UserProfile
from .recommender import IMPLICIT_POSITIVE_RATING, RecommendationEngine
from .storage import JsonStorage

DEFAULT_PREFERRED_GENRES = ["Science-Fiction", "Polar", "Fantasy"]


class BookService:
    """Orchestration des cas d'usage de l'application."""

    def __init__(
        self,
        storage: JsonStorage,
        primary_source: Union[GoogleBooksClient, MockBookRepository],
        engine: RecommendationEngine,
    ) -> None:
        self.storage = storage
        self.primary_source = primary_source
        self.engine = engine
        # Source mock de secours pour le fallback offline.
        self.mock_repository = MockBookRepository()

    # ------------------------------------------------------------- profil
    def create_or_get_user(
        self, user_id: str, preferred_genres: Optional[List[str]] = None
    ) -> UserProfile:
        existing = self.storage.load_user(user_id)
        if existing is not None:
            return existing
        user = UserProfile(
            user_id=user_id,
            preferred_genres=(
                list(preferred_genres)
                if preferred_genres is not None
                else list(DEFAULT_PREFERRED_GENRES)
            ),
            reading_history={},
            wishlist=[],
            created_at=datetime.now(),
        )
        self.storage.save_user(user)
        return user

    def get_user_profile(self, user_id: str) -> UserProfile:
        user = self.storage.load_user(user_id)
        if user is None:
            raise UserNotFoundError(f"Utilisateur introuvable: '{user_id}'")
        return user

    # ---------------------------------------------------- feedback / notes
    def record_feedback(self, user_id: str, book_id: str, liked: bool) -> None:
        user = self.get_user_profile(user_id)
        feedback = Feedback(
            user_id=user_id, book_id=book_id, liked=liked, timestamp=datetime.now()
        )
        self.storage.save_feedback(feedback)
        if liked:
            # Un like vaut une note implicite positive dans l'historique.
            updated = self.engine.update_user_vector(
                user, book_id, IMPLICIT_POSITIVE_RATING
            )
            self.storage.save_user(updated)

    def add_rating(self, user_id: str, book_id: str, rating: float) -> UserProfile:
        if not 0.0 <= rating <= 5.0:
            raise ValueError(f"La note doit être entre 0.0 et 5.0 (reçu: {rating})")
        user = self.get_user_profile(user_id)
        updated = self.engine.update_user_vector(user, book_id, rating)
        self.storage.save_user(updated)
        return updated

    def add_to_wishlist(self, user_id: str, book_id: str) -> UserProfile:
        user = self.get_user_profile(user_id)
        if book_id not in user.wishlist:
            user.wishlist.append(book_id)
        self.storage.save_user(user)
        return user

    # ------------------------------------------------------------ recherche
    def search_books(self, query: str, use_online: bool = True) -> List[Book]:
        online_books: List[Book] = []
        online_failed = False
        if use_online and isinstance(self.primary_source, GoogleBooksClient):
            try:
                online_books = self.primary_source.search_books(query)
            except ApiUnavailableError:
                online_failed = True
        elif isinstance(self.primary_source, MockBookRepository):
            online_books = self.primary_source.search(query)

        mock_books = self.mock_repository.search(query)
        if online_failed and not mock_books:
            # Continuité offline : on retourne tout le catalogue mock.
            mock_books = self.mock_repository.get_all_books()

        merged: List[Book] = []
        seen = set()
        for book in online_books + mock_books:
            if book.id not in seen:
                seen.add(book.id)
                merged.append(book)
        return merged

    def get_book_details(self, book_id: str) -> Book:
        # 1) stockage local (offline-first)
        book = self.storage.load_book(book_id)
        if book is not None:
            return book
        # 2) source en ligne
        if isinstance(self.primary_source, GoogleBooksClient):
            try:
                book = self.primary_source.get_book_details(book_id)
            except BookNotFoundError:
                book = None
            except ApiUnavailableError:
                book = self.mock_repository.get_book(book_id)
            if book is not None:
                self.storage.save_book(book)  # mise en cache locale
                return book
        # 3) catalogue mock
        book = self.mock_repository.get_book(book_id)
        if book is not None:
            self.storage.save_book(book)
            return book
        raise BookNotFoundError(f"Livre introuvable: '{book_id}'")

    # ------------------------------------------------------ recommandations
    def get_recommendations(self, user_id: str, limit: int = 10) -> List[Recommendation]:
        user = self.get_user_profile(user_id)
        candidates = self._get_candidate_books(user)
        all_feedbacks: Dict[str, List[Feedback]] = self.storage.load_all_feedbacks()
        return self.engine.compute_recommendations(
            user, candidates, all_feedbacks, limit=limit
        )

    def _get_candidate_books(self, user: UserProfile) -> List[Book]:
        candidates: List[Book] = []
        seen = set()

        def _add(books: List[Book]) -> None:
            for book in books:
                if book.id not in seen:
                    seen.add(book.id)
                    candidates.append(book)

        if isinstance(self.primary_source, MockBookRepository):
            _add(self.primary_source.get_all_books())
        elif isinstance(self.primary_source, GoogleBooksClient):
            try:
                for genre in user.preferred_genres:
                    _add(self.primary_source.search_books(f"subject:{genre}", max_results=20))
                _add(self.primary_source.search_books("best sellers", max_results=20))
            except ApiUnavailableError:
                pass
        # Enrichissement / secours via le catalogue mock (genres préférés d'abord)
        _add(self.mock_repository.get_books_by_genres(user.preferred_genres, limit=40))
        _add(self.mock_repository.get_all_books())
        return candidates
