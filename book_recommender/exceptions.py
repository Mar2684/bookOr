"""Hiérarchie d'exceptions métier pour book_recommender."""


class BookRecommenderError(Exception):
    """Exception de base pour toutes les erreurs du domaine."""

    pass


class StorageError(BookRecommenderError):
    """Erreur de persistance locale (lecture/écriture JSON)."""

    pass


class UserNotFoundError(BookRecommenderError):
    """L'utilisateur demandé est introuvable."""

    pass


class BookNotFoundError(BookRecommenderError):
    """Le livre demandé est introuvable."""

    pass


class ApiUnavailableError(BookRecommenderError):
    """L'API externe est indisponible (réseau, timeout, HTTP != 200)."""

    pass
