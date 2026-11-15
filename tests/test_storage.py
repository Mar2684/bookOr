"""Tests de la persistance JSON locale (offline-first)."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from book_recommender.exceptions import StorageError
from book_recommender.models import Book, Feedback, UserProfile
from book_recommender.storage import JsonStorage


class TestJsonStorage(unittest.TestCase):
    def test_user_persistence_roundtrip_preserves_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorage(tmp)
            user = UserProfile(
                user_id="u1",
                preferred_genres=["Polar", "Fantasy"],
                reading_history={"b1": 4.5, "b2": 3.0},
                wishlist=["b3"],
                created_at=datetime(2024, 5, 1, 10, 30, 0),
            )
            storage.save_user(user)
            loaded = storage.load_user("u1")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.preferred_genres, user.preferred_genres)
            self.assertEqual(loaded.reading_history, user.reading_history)
            self.assertEqual(loaded.wishlist, user.wishlist)
            self.assertEqual(loaded.user_id, user.user_id)
            self.assertEqual(loaded.created_at, user.created_at)

    def test_corrupted_json_raises_storage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorage(tmp)
            user_file = Path(tmp) / "users" / "u1.json"
            user_file.write_text("{invalid json", encoding="utf-8")
            with self.assertRaises(StorageError):
                storage.load_user("u1")

    def test_load_missing_user_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorage(tmp)
            self.assertIsNone(storage.load_user("inconnu"))

    def test_book_and_feedback_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = JsonStorage(tmp)
            book = Book(
                id="b1",
                title="Titre",
                authors=["Auteur"],
                genres=["Polar"],
                description="Desc",
                average_rating=4.2,
                thumbnail_url="http://x",
                published_date="2020",
            )
            storage.save_book(book)
            loaded = storage.load_book("b1")
            self.assertEqual(loaded, book)
            self.assertEqual(storage.load_all_books(), [book])
            self.assertIsNone(storage.load_book("absent"))

            fb = Feedback(
                user_id="u1", book_id="b1", liked=True,
                timestamp=datetime(2024, 1, 1),
            )
            storage.save_feedback(fb)
            storage.save_feedback(
                Feedback(user_id="u1", book_id="b2", liked=False,
                         timestamp=datetime(2024, 1, 2))
            )
            feedbacks = storage.load_feedbacks("u1")
            self.assertEqual(len(feedbacks), 2)
            self.assertEqual(feedbacks[0].book_id, "b1")
            self.assertTrue(feedbacks[0].liked)
            self.assertEqual(storage.load_feedbacks("personne"), [])
            all_fb = storage.load_all_feedbacks()
            self.assertIn("u1", all_fb)
            self.assertEqual(len(all_fb["u1"]), 2)


if __name__ == "__main__":
    unittest.main()
