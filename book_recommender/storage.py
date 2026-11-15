"""Persistance locale en fichiers JSON (équivalent fonctionnel de Room).

Assure le mode offline : profils, livres et feedbacks sont stockés
localement sous forme de fichiers JSON.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .exceptions import StorageError
from .models import Book, Feedback, UserProfile


class JsonStorage:
    """Stockage JSON local organisé en sous-répertoires users/books/feedbacks."""

    def __init__(self, storage_dir: str) -> None:
        self.storage_dir = Path(storage_dir)
        try:
            (self.storage_dir / "users").mkdir(parents=True, exist_ok=True)
            (self.storage_dir / "books").mkdir(parents=True, exist_ok=True)
            (self.storage_dir / "feedbacks").mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Impossible de créer le répertoire de stockage: {exc}") from exc

    # ------------------------------------------------------------------ users
    def save_user(self, user: UserProfile) -> None:
        path = self.storage_dir / "users" / f"{user.user_id}.json"
        payload = {
            "user_id": user.user_id,
            "preferred_genres": list(user.preferred_genres),
            "reading_history": dict(user.reading_history),
            "wishlist": list(user.wishlist),
            "created_at": user.created_at.isoformat(),
        }
        self._write_json(path, payload)

    def load_user(self, user_id: str) -> Optional[UserProfile]:
        path = self.storage_dir / "users" / f"{user_id}.json"
        if not path.exists():
            return None
        payload = self._read_json(path)
        try:
            created_at = datetime.fromisoformat(payload["created_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise StorageError(f"Profil utilisateur illisible pour '{user_id}': {exc}") from exc
        return UserProfile(
            user_id=payload["user_id"],
            preferred_genres=list(payload.get("preferred_genres", [])),
            reading_history={k: float(v) for k, v in payload.get("reading_history", {}).items()},
            wishlist=list(payload.get("wishlist", [])),
            created_at=created_at,
        )

    # ------------------------------------------------------------------ books
    def save_book(self, book: Book) -> None:
        path = self.storage_dir / "books" / f"{book.id}.json"
        payload = {
            "id": book.id,
            "title": book.title,
            "authors": list(book.authors),
            "genres": list(book.genres),
            "description": book.description,
            "average_rating": book.average_rating,
            "thumbnail_url": book.thumbnail_url,
            "published_date": book.published_date,
        }
        self._write_json(path, payload)

    def load_book(self, book_id: str) -> Optional[Book]:
        path = self.storage_dir / "books" / f"{book_id}.json"
        if not path.exists():
            return None
        payload = self._read_json(path)
        return self._payload_to_book(payload)

    def load_all_books(self) -> List[Book]:
        books: List[Book] = []
        books_dir = self.storage_dir / "books"
        if not books_dir.exists():
            return books
        for path in sorted(books_dir.glob("*.json")):
            try:
                books.append(self._payload_to_book(self._read_json(path)))
            except StorageError:
                # On ignore un fichier livre corrompu isolé plutôt que tout casser.
                continue
        return books

    # -------------------------------------------------------------- feedbacks
    def save_feedback(self, feedback: Feedback) -> None:
        path = self.storage_dir / "feedbacks" / f"{feedback.user_id}.json"
        feedbacks = []
        if path.exists():
            feedbacks = self._read_json(path)
            if not isinstance(feedbacks, list):
                raise StorageError(
                    f"Fichier de feedbacks corrompu pour '{feedback.user_id}'"
                )
        feedbacks.append(
            {
                "user_id": feedback.user_id,
                "book_id": feedback.book_id,
                "liked": feedback.liked,
                "timestamp": feedback.timestamp.isoformat(),
            }
        )
        self._write_json(path, feedbacks)

    def load_feedbacks(self, user_id: str) -> List[Feedback]:
        path = self.storage_dir / "feedbacks" / f"{user_id}.json"
        if not path.exists():
            return []
        raw = self._read_json(path)
        if not isinstance(raw, list):
            raise StorageError(f"Fichier de feedbacks corrompu pour '{user_id}'")
        feedbacks: List[Feedback] = []
        for item in raw:
            feedbacks.append(
                Feedback(
                    user_id=item["user_id"],
                    book_id=item["book_id"],
                    liked=bool(item["liked"]),
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                )
            )
        return feedbacks

    def load_all_feedbacks(self) -> "dict[str, List[Feedback]]":
        """Retourne les feedbacks de tous les utilisateurs (pour le collaboratif)."""
        result: "dict[str, List[Feedback]]" = {}
        feedbacks_dir = self.storage_dir / "feedbacks"
        if not feedbacks_dir.exists():
            return result
        for path in sorted(feedbacks_dir.glob("*.json")):
            user_id = path.stem
            try:
                result[user_id] = self.load_feedbacks(user_id)
            except StorageError:
                continue
        return result

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _payload_to_book(payload: dict) -> Book:
        try:
            return Book(
                id=payload["id"],
                title=payload["title"],
                authors=list(payload.get("authors", [])),
                genres=list(payload.get("genres", [])),
                description=payload.get("description", ""),
                average_rating=float(payload.get("average_rating", 0.0)),
                thumbnail_url=payload.get("thumbnail_url", ""),
                published_date=payload.get("published_date", ""),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StorageError(f"Livre illisible: {exc}") from exc

    @staticmethod
    def _write_json(path: Path, payload) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except (OSError, TypeError, ValueError) as exc:
            raise StorageError(f"Échec d'écriture dans '{path}': {exc}") from exc

    @staticmethod
    def _read_json(path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StorageError(f"JSON corrompu dans '{path}': {exc}") from exc
        except OSError as exc:
            raise StorageError(f"Lecture impossible de '{path}': {exc}") from exc
