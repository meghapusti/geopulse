"""
Named entity extractor.
Uses spaCy en_core_web_sm (small, CPU-friendly, ~12MB) to extract:
  - Countries and geopolitical entities → ISO-3166 alpha-3 codes
  - Key actors (organisations, people)
  - Location coordinates (centroid lookup)

For production accuracy upgrade to en_core_web_trf (transformer-based).
Install: python -m spacy download en_core_web_sm
"""
from typing import Optional

import structlog

from app.utils.geo import COUNTRY_NAME_TO_ISO3, COUNTRY_CENTROIDS

log = structlog.get_logger()


class EntityExtractor:
    def __init__(self):
        self._nlp = None

    def _load(self):
        if self._nlp is None:
            import spacy
            try:
                self._nlp = spacy.load("en_core_web_sm")
                log.info("spaCy model loaded", model="en_core_web_sm")
            except OSError:
                log.warning("spaCy model not found, running: python -m spacy download en_core_web_sm")
                raise
        return self._nlp

    def _resolve_country(self, entity_text: str) -> Optional[str]:
        """Map a GPE entity to ISO-3 code. Case-insensitive fuzzy lookup."""
        cleaned = entity_text.strip().title()
        return COUNTRY_NAME_TO_ISO3.get(cleaned)

    def extract_single(self, text: str) -> dict:
        nlp = self._load()
        doc = nlp(text[:10000])  # spaCy has token limits

        countries: list[str] = []
        actors: list[str] = []
        locations: dict[str, list[float]] = {}

        seen_countries: set[str] = set()
        seen_actors: set[str] = set()

        for ent in doc.ents:
            if ent.label_ in ("GPE", "LOC"):
                iso3 = self._resolve_country(ent.text)
                if iso3 and iso3 not in seen_countries:
                    countries.append(iso3)
                    seen_countries.add(iso3)
                    centroid = COUNTRY_CENTROIDS.get(iso3)
                    if centroid:
                        locations[iso3] = centroid

            elif ent.label_ in ("ORG", "PERSON"):
                name = ent.text.strip()
                if name not in seen_actors and len(name) > 2:
                    actors.append(name)
                    seen_actors.add(name)

        return {
            "countries": countries[:20],   # cap to avoid noise
            "actors": actors[:20],
            "locations": locations,
        }

    def extract_batch(self, texts: list[str]) -> list[dict]:
        nlp = self._load()
        results = []
        # spaCy pipe is faster than calling nlp() in a loop
        for doc in nlp.pipe(texts, batch_size=32):
            countries, actors, locations = [], [], {}
            seen_c: set[str] = set()
            seen_a: set[str] = set()

            for ent in doc.ents:
                if ent.label_ in ("GPE", "LOC"):
                    iso3 = self._resolve_country(ent.text)
                    if iso3 and iso3 not in seen_c:
                        countries.append(iso3)
                        seen_c.add(iso3)
                        centroid = COUNTRY_CENTROIDS.get(iso3)
                        if centroid:
                            locations[iso3] = centroid
                elif ent.label_ in ("ORG", "PERSON"):
                    name = ent.text.strip()
                    if name not in seen_a and len(name) > 2:
                        actors.append(name)
                        seen_a.add(name)

            results.append({
                "countries": countries[:20],
                "actors": actors[:20],
                "locations": locations,
            })
        return results
