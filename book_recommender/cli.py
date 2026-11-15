"""Point d'entrée CLI de démonstration (simulation de l'interface utilisateur).

Exemples :
    python -m book_recommender.cli create-user --user-id alice --genres "Polar,Fantasy"
    python -m book_recommender.cli search "dune"
    python -m book_recommender.cli rate --user-id alice --book-id dune --rating 5.0
    python -m book_recommender.cli recommend --user-id alice --limit 5
"""

import argparse
import sys
from typing import List, Optional

from .api_client import GoogleBooksClient
from .models import Book
from .recommender import RecommendationEngine
from .service import BookService
from .storage import JsonStorage

DEFAULT_STORAGE_DIR = ".book_recommender_data"


def _build_service(storage_dir: str) -> BookService:
    storage = JsonStorage(storage_dir)
    return BookService(storage, GoogleBooksClient(), RecommendationEngine())


def _print_book(book: Book) -> None:
    authors = ", ".join(book.authors) or "Auteur inconnu"
    genres = ", ".join(book.genres) or "Genre inconnu"
    print(f"  - [{book.id}] {book.title} — {authors} ({genres}) note {book.average_rating}")


def cmd_create_user(service: BookService, args: argparse.Namespace) -> None:
    genres: Optional[List[str]] = (
        [g.strip() for g in args.genres.split(",") if g.strip()] if args.genres else None
    )
    user = service.create_or_get_user(args.user_id, genres)
    print(f"Profil prêt pour '{user.user_id}' — genres: {', '.join(user.preferred_genres)}")


def cmd_search(service: BookService, args: argparse.Namespace) -> None:
    results = service.search_books(args.query, use_online=not args.offline)
    print(f"{len(results)} résultat(s) pour '{args.query}':")
    for book in results[: args.limit]:
        _print_book(book)


def cmd_recommend(service: BookService, args: argparse.Namespace) -> None:
    recs = service.get_recommendations(args.user_id, limit=args.limit)
    if not recs:
        print("Aucune recommandation pour le moment. Notez des livres d'abord !")
        return
    print(f"Top {len(recs)} recommandations pour '{args.user_id}':")
    for i, rec in enumerate(recs, 1):
        print(f"{i}. [{rec.score:.2f}] ({rec.source})")
        _print_book(rec.book)
        print(f"   -> {rec.justification}")


def cmd_rate(service: BookService, args: argparse.Namespace) -> None:
    user = service.add_rating(args.user_id, args.book_id, args.rating)
    print(f"Note {args.rating} enregistrée pour '{args.book_id}'. Historique: {user.reading_history}")


def cmd_feedback(service: BookService, args: argparse.Namespace) -> None:
    service.record_feedback(args.user_id, args.book_id, liked=not args.dislike)
    print(f"Feedback {'👍' if not args.dislike else '👎'} enregistré pour '{args.book_id}'.")


def cmd_wishlist(service: BookService, args: argparse.Namespace) -> None:
    user = service.add_to_wishlist(args.user_id, args.book_id)
    print(f"Wishlist de '{user.user_id}': {user.wishlist}")


def cmd_profile(service: BookService, args: argparse.Namespace) -> None:
    user = service.get_user_profile(args.user_id)
    print(f"Profil '{user.user_id}' (créé le {user.created_at:%Y-%m-%d %H:%M})")
    print(f"  Genres préférés : {user.preferred_genres}")
    print(f"  Historique      : {user.reading_history}")
    print(f"  À lire          : {user.wishlist}")


def cmd_details(service: BookService, args: argparse.Namespace) -> None:
    book = service.get_book_details(args.book_id)
    _print_book(book)
    if book.description:
        print(f"  {book.description}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="book_recommender",
        description="Moteur de recommandation de livres (démo CLI).",
    )
    parser.add_argument(
        "--storage-dir",
        default=DEFAULT_STORAGE_DIR,
        help=f"Répertoire de stockage local (défaut: {DEFAULT_STORAGE_DIR}).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-user", help="Créer (ou récupérer) un profil utilisateur.")
    p.add_argument("--user-id", required=True)
    p.add_argument("--genres", default=None, help="Genres préférés séparés par des virgules.")
    p.set_defaults(func=cmd_create_user)

    p = sub.add_parser("search", help="Rechercher des livres (online puis fallback mock).")
    p.add_argument("query")
    p.add_argument("--offline", action="store_true", help="Force la recherche offline.")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("recommend", help="Obtenir des recommandations personnalisées.")
    p.add_argument("--user-id", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_recommend)

    p = sub.add_parser("rate", help="Noter un livre (0.0 - 5.0).")
    p.add_argument("--user-id", required=True)
    p.add_argument("--book-id", required=True)
    p.add_argument("--rating", type=float, required=True)
    p.set_defaults(func=cmd_rate)

    p = sub.add_parser("feedback", help="Liker / disliker un livre.")
    p.add_argument("--user-id", required=True)
    p.add_argument("--book-id", required=True)
    p.add_argument("--dislike", action="store_true")
    p.set_defaults(func=cmd_feedback)

    p = sub.add_parser("wishlist", help="Ajouter un livre à la liste 'à lire'.")
    p.add_argument("--user-id", required=True)
    p.add_argument("--book-id", required=True)
    p.set_defaults(func=cmd_wishlist)

    p = sub.add_parser("profile", help="Afficher le profil utilisateur.")
    p.add_argument("--user-id", required=True)
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("details", help="Afficher la fiche détaillée d'un livre.")
    p.add_argument("--book-id", required=True)
    p.set_defaults(func=cmd_details)

    args = parser.parse_args(argv)
    service = _build_service(args.storage_dir)
    args.func(service, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
