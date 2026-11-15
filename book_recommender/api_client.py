"""Sources de données livres : Google Books API (stdlib) + catalogue mock interne.

En cas d'indisponibilité réseau, le service bascule vers MockBookRepository
pour assurer la continuité offline.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Optional

from .exceptions import ApiUnavailableError, BookNotFoundError
from .models import Book

GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"


class GoogleBooksClient:
    """Client HTTP pour Google Books API basé sur urllib (stdlib)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 5,
        base_url: str = GOOGLE_BOOKS_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = base_url

    def search_books(self, query: str, max_results: int = 40) -> List[Book]:
        params = {"q": query, "maxResults": str(min(max_results, 40))}
        url = self._build_url(params)
        data = self._fetch_json(url)
        books: List[Book] = []
        for item in data.get("items", []):
            book = self._volume_to_book(item)
            if book is not None:
                books.append(book)
        return books

    def get_book_details(self, volume_id: str) -> Book:
        url = self._build_url({}, volume_id)
        try:
            data = self._fetch_json(url)
        except ApiUnavailableError as exc:
            if "404" in str(exc):
                raise BookNotFoundError(f"Volume introuvable: '{volume_id}'") from exc
            raise
        book = self._volume_to_book(data)
        if book is None:
            raise BookNotFoundError(f"Volume introuvable: '{volume_id}'")
        return book

    # -------------------------------------------------------------- helpers
    def _build_url(self, params: dict, volume_id: Optional[str] = None) -> str:
        if self.api_key:
            params = dict(params, key=self.api_key)
        if volume_id:
            return f"{self.base_url}/{urllib.parse.quote(volume_id)}?{urllib.parse.urlencode(params)}"
        return f"{self.base_url}?{urllib.parse.urlencode(params)}"

    def _fetch_json(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise ApiUnavailableError(f"HTTP {response.status} pour '{url}'")
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ApiUnavailableError(f"HTTP {exc.code} pour '{url}'") from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ApiUnavailableError(f"API indisponible pour '{url}': {exc}") from exc

    @staticmethod
    def _volume_to_book(item: dict) -> Optional[Book]:
        volume_info = item.get("volumeInfo", {})
        volume_id = item.get("id")
        if not volume_id:
            return None
        image_links = volume_info.get("imageLinks", {}) or {}
        return Book(
            id=volume_id,
            title=volume_info.get("title", "Titre inconnu"),
            authors=list(volume_info.get("authors", [])),
            genres=list(volume_info.get("categories", [])),
            description=volume_info.get("description", ""),
            average_rating=float(volume_info.get("averageRating", 0.0) or 0.0),
            thumbnail_url=image_links.get("thumbnail", ""),
            published_date=volume_info.get("publishedDate", ""),
        )


class MockBookRepository:
    """Catalogue mock interne d'environ 50 livres répartis sur plusieurs genres."""

    def __init__(self) -> None:
        self._books: List[Book] = _build_mock_catalog()

    def search(self, query: str) -> List[Book]:
        needle = query.lower()
        return [
            book
            for book in self._books
            if needle in book.title.lower()
            or any(needle in author.lower() for author in book.authors)
        ]

    def get_books_by_genres(self, genres: List[str], limit: int = 20) -> List[Book]:
        wanted = {g.lower() for g in genres}
        matches = [
            book
            for book in self._books
            if wanted & {g.lower() for g in book.genres}
        ]
        return matches[:limit]

    def get_all_books(self) -> List[Book]:
        return list(self._books)

    def get_book(self, book_id: str) -> Optional[Book]:
        for book in self._books:
            if book.id == book_id:
                return book
        return None


def _b(book_id: str, title: str, authors: List[str], genres: List[str],
       description: str, rating: float, published: str) -> Book:
    return Book(
        id=book_id,
        title=title,
        authors=authors,
        genres=genres,
        description=description,
        average_rating=rating,
        thumbnail_url=f"https://books.google.com/books/content?id={book_id}",
        published_date=published,
    )


def _build_mock_catalog() -> List[Book]:
    sf = "Science-Fiction"
    fantasy = "Fantasy"
    polar = "Polar"
    romance = "Romance"
    historique = "Roman historique"
    thriller = "Thriller"
    biographie = "Biographie"
    essais = "Essai"
    jeunesse = "Jeunesse"
    horreur = "Horreur"

    return [
        # --- Science-Fiction (8)
        _b("dune", "Dune", ["Frank Herbert"], [sf], "Épopée désertique sur la planète Arrakis et l'épice.", 4.7, "1965"),
        _b("fondation", "Fondation", ["Isaac Asimov"], [sf], "La chute de l'Empire galactique et la psychohistoire.", 4.6, "1951"),
        _b("neuromancien", "Neuromancien", ["William Gibson"], [sf, "Cyberpunk"], "Le cyberspace, les hackers et les intelligences artificielles.", 4.4, "1984"),
        _b("hypérion", "Hyperion", ["Dan Simmons"], [sf], "Pèlerinage sur une planète mystérieuse aux shrikes temporels.", 4.5, "1989"),
        _b("projet-hail-mary", "Projet Hail Mary", ["Andy Weir"], [sf], "Un homme amnésique sauve l'humanité depuis l'espace.", 4.6, "2021"),
        _b("les-robots", "Les Robots", ["Isaac Asimov"], [sf], "Les trois lois de la robotique et l'émergence des machines.", 4.5, "1950"),
        _b("1984", "1984", ["George Orwell"], [sf, "Dystopie"], "Surveillance totale sous le regard de Big Brother.", 4.6, "1949"),
        _b("le-meilleur-des-mondes", "Le Meilleur des mondes", ["Aldous Huxley"], [sf, "Dystopie"], "Société eugéniste stabilisée par le soma.", 4.4, "1932"),
        # --- Fantasy (7)
        _b("le-seigneur-des-anneaux", "Le Seigneur des Anneaux", ["J.R.R. Tolkien"], [fantasy], "La quête de l'Anneau unique en Terre du Milieu.", 4.8, "1954"),
        _b("harry-potter-1", "Harry Potter à l'école des sorciers", ["J.K. Rowling"], [fantasy, jeunesse], "Un orphelin découvre qu'il est sorcier.", 4.7, "1997"),
        _b("le-nom-du-vent", "Le Nom du vent", ["Patrick Rothfuss"], [fantasy], "Kvothe raconte sa vie et sa quête contre les Chandrians.", 4.6, "2007"),
        _b("game-of-thrones", "Game of Thrones", ["George R.R. Martin"], [fantasy], "Intrigues et dragons pour le Trône de Fer.", 4.5, "1996"),
        _b("le-hobbit", "Le Hobbit", ["J.R.R. Tolkien"], [fantasy, jeunesse], "Bilbon Sacquet embarque dans une aventure inattendue.", 4.6, "1937"),
        _b("filles-du-frost", "Les Filles du Frost", ["C. Robert"], [fantasy], "Magie hivernale et secrets de famille.", 4.0, "2018"),
        _b("elden-ring-lore", "L'univers d'Elden Ring", ["FromSoftware"], [fantasy], "Mythologie des Terres brisées et du Cercle d'Elden.", 4.5, "2022"),
        # --- Polar / Thriller (8)
        _b("le-silence-des-agneaux", "Le Silence des agneaux", ["Thomas Harris"], [polar, thriller], "Clarice Starling traque Buffalo Bill avec Hannibal Lecter.", 4.6, "1988"),
        _b("gone-girl", "Gone Girl", ["Gillian Flynn"], [polar, thriller], "La disparition d'Amy et les secrets du couple.", 4.3, "2012"),
        _b("da-vinci-code", "Da Vinci Code", ["Dan Brown"], [thriller, polar], "Robert Langdon suit une piste ésotérique à travers l'Europe.", 4.2, "2003"),
        _b("milllenium-1", "Millénium : Les Hommes qui n'aimaient pas les femmes", ["Stieg Larsson"], [polar], "Mikael Blomkvist enquête sur une disparition vieille de 40 ans.", 4.5, "2005"),
        _b("shutter-island", "Shutter Island", ["Dennis Lehane"], [thriller, polar], "Un marshal enquête dans un hôpital psychiatrique isolé.", 4.4, "2003"),
        _b("le-prestige-polar", "La Vérité sur l'affaire Harry Quebert", ["Joël Dicker"], [polar], "Un écrivain enquête sur un meurtre dans le New Hampshire.", 4.3, "2012"),
        _b("zingaro", "La Fille du train", ["Paula Hawkins"], [thriller, polar], "Une femme alcoolique croit voir un crime depuis son train.", 4.1, "2015"),
        _b("dix-petits-negres", "Dix petits nègres", ["Agatha Christie"], [polar], "Dix invités piégés sur une île, assassinés un par un.", 4.5, "1939"),
        # --- Romance (6)
        _b("orgueil-et-prejuges", "Orgueil et Préjugés", ["Jane Austen"], [romance, historique], "Elizabeth Bennet et Mr Darcy entre orgueil et amour.", 4.6, "1813"),
        _b("nos-etoiles-contraires", "Nos étoiles contraires", ["John Green"], [romance, jeunesse], "Deux adolescents malades tombent amoureux.", 4.4, "2012"),
        _b("la-faute-a-nos-etoiles-film", "Le Temps d'un été", ["Guillaume Musso"], [romance], "Un été parisien qui change deux vies.", 4.0, "2014"),
        _b("outlander", "Outlander", ["Diana Gabaldon"], [romance, historique, fantasy], "Une infirmière de 1945 projetée dans l'Écosse de 1743.", 4.5, "1991"),
        _b("twilight", "Twilight", ["Stephenie Meyer"], [romance, fantasy], "Amour dangereux entre une adolescente et un vampire.", 4.0, "2005"),
        _b("me-before-you", "Avant toi", ["Jojo Moyes"], [romance], "Une jeune femme devient l'accompagnante d'un tétraplégique.", 4.2, "2012"),
        # --- Roman historique (5)
        _b("les-piliers-de-la-terre", "Les Piliers de la Terre", ["Ken Follett"], [historique], "Construction d'une cathédrale au XIIe siècle anglais.", 4.6, "1989"),
        _b("tous-les-hommes-nes-libres", "Tous les hommes nés libres", ["Solomon Northup"], [historique, biographie], "Douze ans d'esclavage racontés par un homme libre kidnappé.", 4.6, "1853"),
        _b("the-book-thief", "La Voleuse de livres", ["Markus Zusak"], [historique, jeunesse], "La Mort raconte l'histoire de Liesel en Allemagne nazie.", 4.6, "2005"),
        _b("les-miserables", "Les Misérables", ["Victor Hugo"], [historique], "Jean Valjean, Fantine et l'insurrection de 1832.", 4.5, "1862"),
        _b("wolf-hall", "Wolf Hall", ["Hilary Mantel"], [historique], "L'ascension de Thomas Cromwell à la cour d'Henri VIII.", 4.4, "2009"),
        # --- Horreur (4)
        _b("shining", "Shining", ["Stephen King"], [horreur], "L'hôtel Overlook et la folie de Jack Torrance.", 4.5, "1977"),
        _b("ca", "Ça", ["Stephen King"], [horreur], "Les enfants du Club des ratés affrontent Pennywise.", 4.4, "1986"),
        _b("exorciste", "L'Exorciste", ["William Peter Blatty"], [horreur], "La possession de Regan et les deux prêtres.", 4.3, "1971"),
        _b("dracula", "Dracula", ["Bram Stoker"], [horreur, fantasy], "Le comte vampire et Jonathan Harker.", 4.3, "1897"),
        # --- Biographie / Essai (6)
        _b("sapiens", "Sapiens : Une brève histoire de l'humanité", ["Yuval Noah Harari"], [essais, biographie], "De la préhistoire à l'ère de l'information.", 4.5, "2011"),
        _b("steve-jobs", "Steve Jobs", ["Walter Isaacson"], [biographie], "La vie du cofondateur d'Apple par lui-même.", 4.5, "2011"),
        _b("devenir", "Devenir", ["Michelle Obama"], [biographie], "Mémoires de la première dame des États-Unis.", 4.5, "2018"),
        _b("educated", "Éduquée", ["Tara Westover"], [biographie], "Une enfance survivaliste dans l'Idaho et la découverte des études.", 4.6, "2018"),
        _b("le-quatrième-mur", "Le Quatrième Mur", ["Sorj Chalandon"], [essais], "Un metteur en scène monte Antigone à Beyrouth en pleine guerre.", 4.3, "2013"),
        _b("petit-traite-de-manipulation", "Petit traité de manipulation à l'usage des honnêtes gens", ["Robert-Vincent Joule"], [essais], "Les techniques d'influence décryptées par la psychologie sociale.", 4.2, "1987"),
        # --- Jeunesse (6)
        _b("petit-prince", "Le Petit Prince", ["Antoine de Saint-Exupéry"], [jeunesse, essais], "Un aviateur et un renard sur une planète minuscule.", 4.7, "1943"),
        _b("hunger-games", "Hunger Games", ["Suzanne Collins"], [jeunesse, sf, "Dystopie"], "Katniss dans l'arène télévisée de Panem.", 4.4, "2008"),
        _b("percy-jackson-1", "Percy Jackson : Le Voleur de foudre", ["Rick Riordan"], [jeunesse, fantasy], "Un adolescent découvre qu'il est fils de Poséidon.", 4.4, "2005"),
        _b("journal-d-un-degonfle", "Le Journal d'un dégonflé", ["Jeff Kinney"], [jeunesse], "Les mésaventures de Greg Heffley au collège.", 4.2, "2007"),
        _b("mona", "Mona et le mini-monde", ["Célia Verger"], [jeunesse], "Aventures fantastiques d'une petite fille.", 3.9, "2019"),
        _b("asterix-chez-les-bretons", "Astérix chez les Bretons", ["René Goscinny", "Albert Uderzo"], [jeunesse], "Astérix et Obélix en Bretagne.", 4.5, "1966"),
    ]
