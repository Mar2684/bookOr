# bookOr

Moteur de recommandation de livres (Python stdlib uniquement) : profils
utilisateurs, persistance JSON offline-first, client Google Books API avec
fallback mock (~50 livres), moteur de recommandation hybride
(content-based + collaboratif item-based) et façade service.

## Structure

```
book_recommender/
  models.py        # dataclasses métier (Book, UserProfile, Recommendation, Feedback)
  exceptions.py    # hiérarchie d'exceptions métier
  storage.py       # persistance JSON locale (JsonStorage)
  api_client.py    # GoogleBooksClient (urllib) + MockBookRepository
  recommender.py   # RecommendationEngine (hybride 0.6 genre + 0.4 collaboratif)
  service.py       # BookService (façade des cas d'usage)
  cli.py           # démo en ligne de commande
tests/             # tests unitaires (unittest)
```

## Utilisation

```bash
python3 -m unittest discover -s . -p "test_*.py"   # tests
python3 -m book_recommender.cli create-user --user-id alice --genres "Science-Fiction,Polar"
python3 -m book_recommender.cli rate --user-id alice --book-id dune --rating 5.0
python3 -m book_recommender.cli recommend --user-id alice --limit 5
python3 -m book_recommender.cli search "dune" --offline
```
