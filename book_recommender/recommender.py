"""Moteur de recommandation hybride.

Combine filtrage content-based (genres préférés) et filtrage collaboratif
item-based simplifié (similarité cosinus entre vecteurs de notes).
"""

import math
from typing import Dict, List, Optional, Tuple

from .models import Book, Feedback, Recommendation, UserProfile

POSITIVE_RATING_THRESHOLD = 3.5
IMPLICIT_POSITIVE_RATING = 4.5


class RecommendationEngine:
    """Calcule des recommandations hybrides pour un profil utilisateur."""

    def __init__(self) -> None:
        # Catalogue des livres candidats, renseigné par compute_recommendations
        # et utilisé par la partie item-based du filtrage collaboratif.
        self._catalog: Dict[str, Book] = {}

    def compute_recommendations(
        self,
        user: UserProfile,
        candidate_books: List[Book],
        all_users_feedbacks: Optional[Dict[str, List[Feedback]]] = None,
        limit: int = 10,
    ) -> List[Recommendation]:
        all_users_feedbacks = all_users_feedbacks or {}
        book_catalog: Dict[str, Book] = {b.id: b for b in candidate_books}
        self._catalog = book_catalog
        liked_book_ids = [
            book_id
            for book_id, rating in user.reading_history.items()
            if rating > POSITIVE_RATING_THRESHOLD
        ]

        scored: List[Tuple[Book, float, str]] = []
        for book in candidate_books:
            if book.id in user.reading_history:
                continue  # ne pas recommander un livre déjà lu
            score_genre = self._content_based_score(user, book)
            score_collab = self._collaborative_score(user, book, all_users_feedbacks)
            hybrid = 0.6 * score_genre + 0.4 * score_collab
            score = max(0.0, min(1.0, hybrid))
            if score <= 0:
                continue
            if score_genre > 0 and score_collab > 0:
                source = "hybrid"
            elif score_collab > 0:
                source = "collaborative"
            else:
                source = "genre"
            scored.append((book, score, source))

        scored.sort(key=lambda item: item[1], reverse=True)
        recommendations: List[Recommendation] = []
        for book, score, source in scored[:limit]:
            justification = self._generate_justification(
                user, book, liked_book_ids, book_catalog
            )
            recommendations.append(
                Recommendation(
                    book=book,
                    score=round(score, 4),
                    justification=justification,
                    source=source,
                )
            )
        return recommendations

    def _content_based_score(self, user: UserProfile, book: Book) -> float:
        """1.0 si au moins un genre du livre est dans les genres préférés
        de l'utilisateur, 0.0 sinon."""
        preferred = {g.lower() for g in user.preferred_genres}
        book_genres = {g.lower() for g in book.genres}
        return 1.0 if preferred & book_genres else 0.0

    def _collaborative_score(
        self,
        user: UserProfile,
        book: Book,
        all_feedbacks: Dict[str, List[Feedback]],
    ) -> float:
        """Score collaboratif item-based simplifié.

        Deux composantes (on garde le max, borné entre 0 et 1) :
        - item-based : recouvrement de genres (indice de Jaccard) entre le
          candidat et les livres notés positivement (> 3.5) par l'utilisateur,
          pondéré par la note ;
        - user-user : similarité cosinus entre le vecteur de notes de
          l'utilisateur et le vecteur moyen des autres utilisateurs ayant aimé
          les mêmes livres, modulée par la fraction de ces utilisateurs
          similaires ayant aimé le candidat.
        Retourne 0.0 si pas de données suffisantes.
        """
        liked = {
            book_id: rating
            for book_id, rating in user.reading_history.items()
            if rating > POSITIVE_RATING_THRESHOLD
        }
        if not liked:
            return 0.0

        # --- utilisateurs similaires : autres users ayant aimé >= 1 livre aimé
        liked_ids = set(liked.keys())
        similar_users: List[set] = []
        for other_id, feedbacks in all_feedbacks.items():
            if other_id == user.user_id:
                continue
            other_liked = {f.book_id for f in feedbacks if f.liked}
            if other_liked & liked_ids:
                similar_users.append(other_liked)

        # --- composante item-based (genres communs avec les livres aimés)
        book_genres_lower = {g.lower() for g in book.genres}
        item_part = 0.0
        for liked_id, rating in liked.items():
            liked_book = self._catalog.get(liked_id)
            if liked_book is None:
                continue
            liked_genres = {g.lower() for g in liked_book.genres}
            union = liked_genres | book_genres_lower
            if not union:
                continue
            jaccard = len(liked_genres & book_genres_lower) / len(union)
            item_part = max(item_part, jaccard * (rating / 5.0))

        # --- composante user-user (cosinus sur les livres aimés communs)
        user_part = 0.0
        if similar_users:
            dims = sorted(liked_ids)
            vec_user = [liked[d] for d in dims]
            mean_vec = [
                sum(IMPLICIT_POSITIVE_RATING for s in similar_users if d in s) / len(similar_users)
                for d in dims
            ]
            confidence = self._cosine(vec_user, mean_vec)
            liker_fraction = sum(1 for s in similar_users if book.id in s) / len(similar_users)
            user_part = confidence * liker_fraction
            # si le catalogue est incomplet, retombe sur la co-occurrence pure
            if item_part == 0.0 and liker_fraction > 0.0:
                item_part = liker_fraction

        return max(0.0, min(1.0, max(item_part, user_part)))

    def _generate_justification(
        self,
        user: UserProfile,
        book: Book,
        liked_book_ids: List[str],
        book_catalog: Dict[str, Book],
    ) -> str:
        preferred_lower = {p.lower() for p in user.preferred_genres}
        common_genres = [g for g in book.genres if g.lower() in preferred_lower]
        if common_genres:
            genre = common_genres[0]
        elif book.genres:
            genre = book.genres[0]
        else:
            genre = "inconnu"

        # Livre aimé le plus proche (recouvrement de genres, puis note).
        best_liked: Optional[Book] = None
        best_rank: Tuple[int, float] = (-1, -1.0)
        book_genres_lower = {g.lower() for g in book.genres}
        for liked_id in liked_book_ids:
            liked_book = book_catalog.get(liked_id)
            if liked_book is None:
                continue
            overlap = len({g.lower() for g in liked_book.genres} & book_genres_lower)
            rank = (overlap, user.reading_history.get(liked_id, 0.0))
            if rank > best_rank:
                best_liked = liked_book
                best_rank = rank

        if best_liked is not None:
            return (
                f"Recommandé car vous avez aimé '{best_liked.title}' "
                f"dans le genre '{genre}'"
            )
        return f"Recommandé car il correspond à votre genre préféré '{genre}'"

    def update_user_vector(
        self, user: UserProfile, book_id: str, rating: float
    ) -> UserProfile:
        """Retourne une copie du profil avec la note ajoutée/mise à jour."""
        new_history = dict(user.reading_history)
        new_history[book_id] = rating
        return UserProfile(
            user_id=user.user_id,
            preferred_genres=list(user.preferred_genres),
            reading_history=new_history,
            wishlist=list(user.wishlist),
            created_at=user.created_at,
        )

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
