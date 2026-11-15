"""Dataclasses métier pures définissant le contrat de données partagé."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class Book:
    """Métadonnées d'un livre."""

    id: str
    title: str
    authors: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    description: str = ""
    average_rating: float = 0.0
    thumbnail_url: str = ""
    published_date: str = ""


@dataclass
class UserProfile:
    """Profil utilisateur : genres préférés, historique, wishlist."""

    user_id: str
    preferred_genres: List[str] = field(default_factory=list)
    reading_history: Dict[str, float] = field(default_factory=dict)  # book_id -> note (0-5)
    wishlist: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Recommendation:
    """Résultat du moteur de recommandation."""

    book: Book
    score: float  # entre 0.0 et 1.0
    justification: str
    source: str  # 'genre' | 'collaborative' | 'hybrid'


@dataclass
class Feedback:
    """Like/dislike d'un utilisateur sur un livre."""

    user_id: str
    book_id: str
    liked: bool
    timestamp: datetime = field(default_factory=datetime.now)
