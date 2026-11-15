"""Tests d'intégration de la façade BookService (workflow offline-first)."""

import tempfile
import unittest

from book_recommender.api_client import GoogleBooksClient, MockBookRepository
from book_recommender.exceptions import UserNotFoundError
from book_recommender.models import Book
from book_recommender.recommender import RecommendationEngine
from book_recommender.service import BookService
from book_recommender.storage import JsonStorage


def _make_service(tmp: str, primary=None):
    storage = JsonStorage(tmp)
    primary = primary if primary is not None else MockBookRepository()
    service = BookService(storage, primary, RecommendationEngine())
    return service, storage


class TestServiceIntegration(unittest.TestCase):
    def test_offline_workflow_returns_relevant_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = _make_service(tmp)  # source mock = pas d'accès réseau
            service.create_or_get_user("u1", preferred_genres=["Polar"])
            service.add_rating("u1", "milllenium-1", 5.0)
            recs = service.get_recommendations("u1")
            self.assertGreater(len(recs), 0)
            pref_or_history_genres = {"polar"}
            for rec in recs:
                book_genres = {g.lower() for g in rec.book.genres}
                self.assertTrue(
                    book_genres & pref_or_history_genres,
                    f"'{rec.book.title}' ne partage aucun genre avec les préférences/historique",
                )

    def test_feedback_positive_influences_future_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, storage = _make_service(tmp)
            service.create_or_get_user("u1", preferred_genres=["Science-Fiction"])
            engine = RecommendationEngine()
            candidates = MockBookRepository().get_all_books()

            user_before = service.get_user_profile("u1")
            recs_before = engine.compute_recommendations(
                user_before, candidates, storage.load_all_feedbacks(), limit=50
            )
            score_before = next(
                (r.score for r in recs_before if r.book.id == "fondation"), 0.0
            )

            service.record_feedback("u1", "dune", liked=True)

            user_after = service.get_user_profile("u1")
            self.assertEqual(user_after.reading_history.get("dune"), 4.5)
            recs_after = engine.compute_recommendations(
                user_after, candidates, storage.load_all_feedbacks(), limit=50
            )
            score_after = next(
                (r.score for r in recs_after if r.book.id == "fondation"), 0.0
            )
            self.assertGreater(
                score_after, score_before,
                f"Le score de 'Fondation' aurait dû augmenter ({score_before} -> {score_after})",
            )

    def test_api_fallback_to_mock_on_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            # URL de base invalide pour forcer ApiUnavailableError
            client = GoogleBooksClient(base_url="https://hote-invalide-inexistant.invalid")
            service, _ = _make_service(tmp, primary=client)
            results = service.search_books("test")  # ne doit pas lever d'exception
            self.assertGreater(len(results), 0)
            self.assertTrue(all(isinstance(b, Book) for b in results))
            mock_ids = {b.id for b in MockBookRepository().get_all_books()}
            self.assertTrue(all(b.id in mock_ids for b in results))

    def test_wishlist_and_unknown_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = _make_service(tmp)
            service.create_or_get_user("u1", preferred_genres=["Polar"])
            user = service.add_to_wishlist("u1", "dune")
            self.assertIn("dune", user.wishlist)
            # idempotent
            user = service.add_to_wishlist("u1", "dune")
            self.assertEqual(user.wishlist.count("dune"), 1)
            with self.assertRaises(UserNotFoundError):
                service.add_to_wishlist("inconnu", "dune")
            with self.assertRaises(UserNotFoundError):
                service.get_user_profile("inconnu")


if __name__ == "__main__":
    unittest.main()
