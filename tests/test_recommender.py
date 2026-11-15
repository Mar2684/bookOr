"""Tests unitaires du moteur de recommandation hybride."""

import unittest
from datetime import datetime

from book_recommender.models import Book, UserProfile
from book_recommender.recommender import RecommendationEngine


def _book(book_id: str, title: str, genres: list) -> Book:
    return Book(
        id=book_id,
        title=title,
        authors=["Auteur Test"],
        genres=genres,
        description="Description de test.",
        average_rating=4.0,
        thumbnail_url="",
        published_date="2020",
    )


def _user(user_id: str = "u1", genres=None, history=None) -> UserProfile:
    return UserProfile(
        user_id=user_id,
        preferred_genres=genres or [],
        reading_history=history or {},
        wishlist=[],
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )


class TestRecommendationEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RecommendationEngine()

    def test_content_based_filters_by_preferred_genres(self):
        user = _user(genres=["Science-Fiction"], history={})
        candidates = [
            _book("sf1", "Livre SF 1", ["Science-Fiction"]),
            _book("fa1", "Livre Fantasy 1", ["Fantasy"]),
            _book("sf2", "Livre SF 2", ["Science-Fiction"]),
            _book("po1", "Livre Polar 1", ["Polar"]),
        ]
        recs = self.engine.compute_recommendations(user, candidates, limit=10)
        self.assertGreater(len(recs), 0)
        for rec in recs:
            self.assertIn("Science-Fiction", rec.book.genres)
            self.assertGreater(rec.score, 0.5)
            self.assertLessEqual(rec.score, 1.0)

    def test_collaborative_score_boosts_similar_books(self):
        user = _user(genres=["Science-Fiction"], history={"dune": 5.0})
        dune = _book("dune", "Dune", ["Science-Fiction"])
        fondation = _book("fondation", "Fondation", ["Science-Fiction"])
        roman = _book("roman1", "Roman divers", ["Roman historique"])
        recs = self.engine.compute_recommendations(
            user, [dune, fondation, roman], limit=10
        )
        top3 = recs[:3]
        self.assertTrue(
            any(r.book.id == "fondation" for r in top3),
            f"'Fondation' devrait être dans le top 3: {[r.book.id for r in recs]}",
        )
        fondation_rec = next(r for r in recs if r.book.id == "fondation")
        self.assertIn("Dune", fondation_rec.justification)

    def test_justification_mentions_liked_book_and_genre(self):
        user = _user(genres=["Science-Fiction"], history={"dune": 5.0})
        target = _book("fondation", "Fondation", ["Science-Fiction"])
        catalog = {"dune": _book("dune", "Dune", ["Science-Fiction"])}
        justification = self.engine._generate_justification(
            user, target, ["dune"], catalog
        )
        self.assertIn("Dune", justification)
        self.assertIn("Science-Fiction", justification)

    def test_update_user_vector_returns_updated_copy(self):
        user = _user(genres=["Polar"], history={"b1": 3.0})
        updated = self.engine.update_user_vector(user, "b2", 4.5)
        self.assertEqual(updated.reading_history, {"b1": 3.0, "b2": 4.5})
        # le profil original n'est pas muté
        self.assertEqual(user.reading_history, {"b1": 3.0})

    def test_already_read_books_are_excluded(self):
        user = _user(genres=["Science-Fiction"], history={"sf1": 4.0})
        candidates = [
            _book("sf1", "Livre SF 1", ["Science-Fiction"]),
            _book("sf2", "Livre SF 2", ["Science-Fiction"]),
        ]
        recs = self.engine.compute_recommendations(user, candidates, limit=10)
        self.assertEqual([r.book.id for r in recs], ["sf2"])


if __name__ == "__main__":
    unittest.main()
