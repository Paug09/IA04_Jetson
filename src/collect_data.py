"""
Fetches artwork data from the Louvre Collections API and enriches it with
Wikipedia summaries. Saves results to data/raw/artworks.json.

Run: python src/collect_data.py
"""

import json
import time
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    RAW_DATA_PATH,
    LOUVRE_BASE_URL,
    WIKIPEDIA_REST_URL,
    REQUEST_DELAY_SECONDS,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Artwork registry — ~30 famous Louvre pieces across 3 wings
# ARK IDs are permanent identifiers in the Louvre Collections system.
# search_fallback is used when the direct ARK fetch returns 404.
# ---------------------------------------------------------------------------
ARTWORKS = {
    # Denon Wing — Italian paintings
    "mona_lisa": {
        "ark": "ark:/53355/cl010062370",
        "search_fallback": "Joconde",
        "wikipedia": {"fr": "La_Joconde", "en": "Mona_Lisa"},
    },
    "wedding_at_cana": {
        "ark": "ark:/53355/cl010065586",
        "search_fallback": "Noces de Cana Véronèse",
        "wikipedia": {"fr": "Les_Noces_de_Cana", "en": "The_Wedding_at_Cana"},
    },
    "coronation_napoleon": {
        "ark": "ark:/53355/cl010064863",
        "search_fallback": "Sacre Napoléon David",
        "wikipedia": {"fr": "Le_Sacre_de_Napoléon", "en": "The_Coronation_of_Napoleon"},
    },
    "grande_odalisque": {
        "ark": "ark:/53355/cl010063018",
        "search_fallback": "Grande Odalisque Ingres",
        "wikipedia": {"fr": "La_Grande_Odalisque", "en": "Grande_Odalisque"},
    },
    "liberty_leading": {
        "ark": "ark:/53355/cl010065685",
        "search_fallback": "Liberté guidant Delacroix",
        "wikipedia": {"fr": "La_Liberté_guidant_le_peuple", "en": "Liberty_Leading_the_People"},
    },
    "raft_of_medusa": {
        "ark": "ark:/53355/cl010064857",
        "search_fallback": "Radeau de la Méduse Géricault",
        "wikipedia": {"fr": "Le_Radeau_de_la_Méduse", "en": "The_Raft_of_the_Medusa"},
    },
    "oath_horatii": {
        "ark": "ark:/53355/cl010064866",
        "search_fallback": "Serment des Horaces David",
        "wikipedia": {"fr": "Le_Serment_des_Horaces", "en": "Oath_of_the_Horatii"},
    },
    "virgin_of_the_rocks": {
        "ark": "ark:/53355/cl010062372",
        "search_fallback": "Vierge aux rochers Léonard",
        "wikipedia": {"fr": "La_Vierge_aux_rochers_(Louvre)", "en": "Virgin_of_the_Rocks"},
    },
    "saint_anne": {
        "ark": "ark:/53355/cl010062371",
        "search_fallback": "Sainte Anne Léonard",
        "wikipedia": {"fr": "La_Vierge,_l%27Enfant_Jésus_et_sainte_Anne_(Léonard_de_Vinci)", "en": "Virgin_and_Child_with_Saint_Anne_(Leonardo)"},
    },
    "bathsheba": {
        "ark": "ark:/53355/cl010065533",
        "search_fallback": "Bethsabée Rembrandt",
        "wikipedia": {"fr": "Bethsabée_au_bain_(Rembrandt)", "en": "Bathsheba_at_Her_Bath"},
    },
    "lacemaker": {
        "ark": "ark:/53355/cl010064551",
        "search_fallback": "Dentellière Vermeer",
        "wikipedia": {"fr": "La_Dentellière_(Vermeer)", "en": "The_Lacemaker_(Vermeer)"},
    },
    # Denon Wing — French paintings
    "portrait_louis_xiv": {
        "ark": "ark:/53355/cl010064924",
        "search_fallback": "Louis XIV Rigaud",
        "wikipedia": {"fr": "Louis_XIV_(Rigaud,_1701)", "en": "Louis_XIV_of_France_(Rigaud)"},
    },
    # Denon Wing — Northern European paintings
    "ship_of_fools": {
        "ark": "ark:/53355/cl010064442",
        "search_fallback": "Nef des fous Bosch",
        "wikipedia": {"fr": "La_Nef_des_fous_(Bosch)", "en": "The_Ship_of_Fools_(painting)"},
    },
    "money_changer": {
        "ark": "ark:/53355/cl010064448",
        "search_fallback": "Changeur Metsys",
        "wikipedia": {"fr": "Le_Prêteur_et_sa_femme", "en": "The_Moneylender_and_his_Wife"},
    },
    "madonna_chancellor_rolin": {
        "ark": "ark:/53355/cl010064492",
        "search_fallback": "Chancelier Rolin Van Eyck",
        "wikipedia": {"fr": "La_Vierge_du_chancelier_Rolin", "en": "Madonna_of_Chancellor_Rolin"},
    },
    # Denon Wing — Greek antiquities / sculptures
    "winged_victory": {
        "ark": "ark:/53355/cl010277689",
        "search_fallback": "Victoire de Samothrace",
        "wikipedia": {"fr": "Victoire_de_Samothrace", "en": "Winged_Victory_of_Samothrace"},
    },
    "psyche_revived": {
        "ark": "ark:/53355/cl010278127",
        "search_fallback": "Psyché Cupidon Canova",
        "wikipedia": {"fr": "Psyché_ranimée_par_le_baiser_de_l%27Amour", "en": "Psyche_Revived_by_Cupid%27s_Kiss"},
    },
    "slaves_michelangelo": {
        "ark": "ark:/53355/cl010278443",
        "search_fallback": "Esclaves Michel-Ange",
        "wikipedia": {"fr": "Esclaves_de_Michel-Ange", "en": "Rebellious_Slave"},
    },
    # Sully Wing — Greek antiquities
    "venus_de_milo": {
        "ark": "ark:/53355/cl010277671",
        "search_fallback": "Vénus de Milo",
        "wikipedia": {"fr": "Vénus_de_Milo", "en": "Venus_de_Milo"},
    },
    "borghese_gladiator": {
        "ark": "ark:/53355/cl010278074",
        "search_fallback": "Gladiateur Borghèse",
        "wikipedia": {"fr": "Gladiateur_Borghèse", "en": "Borghese_Gladiator"},
    },
    # Sully Wing — Egyptian antiquities
    "seated_scribe": {
        "ark": "ark:/53355/cl010026756",
        "search_fallback": "Scribe accroupi",
        "wikipedia": {"fr": "Le_Scribe_accroupi", "en": "Seated_Scribe"},
    },
    "great_sphinx_tanis": {
        "ark": "ark:/53355/cl010028724",
        "search_fallback": "Grand Sphinx Tanis",
        "wikipedia": {"fr": "Grand_Sphinx_de_Tanis", "en": "Great_Sphinx_of_Tanis"},
    },
    # Sully Wing — Near Eastern antiquities
    "code_hammurabi": {
        "ark": "ark:/53355/cl010174648",
        "search_fallback": "Code de Hammurabi",
        "wikipedia": {"fr": "Code_de_Hammurabi", "en": "Code_of_Hammurabi"},
    },
}


# ---------------------------------------------------------------------------
# JSON-LD helpers
# ---------------------------------------------------------------------------

def _extract_lang(field, lang: str, fallback_lang: str = None) -> str:
    """
    Extracts a string value from a JSON-LD field that may be:
    - a plain string
    - {"@value": "...", "@language": "fr"}
    - [{"@value": "...", "@language": "fr"}, ...]
    """
    if field is None:
        return ""
    if isinstance(field, str):
        return field.strip()
    if isinstance(field, dict):
        if field.get("@language") == lang or fallback_lang is None:
            return field.get("@value", "").strip()
        if field.get("@language") == fallback_lang:
            return field.get("@value", "").strip()
        return field.get("@value", "").strip()
    if isinstance(field, list):
        # Prefer target language, then fallback, then first available
        for item in field:
            if isinstance(item, dict) and item.get("@language") == lang:
                return item.get("@value", "").strip()
        if fallback_lang:
            for item in field:
                if isinstance(item, dict) and item.get("@language") == fallback_lang:
                    return item.get("@value", "").strip()
        for item in field:
            if isinstance(item, dict):
                return item.get("@value", "").strip()
            if isinstance(item, str):
                return item.strip()
    return ""


def _first_str(field) -> str:
    """Returns the first plain string from any JSON-LD field shape."""
    return _extract_lang(field, lang="fr", fallback_lang="en")


# ---------------------------------------------------------------------------
# Louvre API
# ---------------------------------------------------------------------------

def _fetch_louvre_ark(ark: str, session: requests.Session) -> dict | None:
    url = f"{LOUVRE_BASE_URL}/{ark}.json"
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
        log.warning("ARK %s returned HTTP %d", ark, r.status_code)
    except requests.RequestException as e:
        log.warning("ARK %s fetch error: %s", ark, e)
    return None


def _search_louvre(query: str, session: requests.Session) -> str | None:
    """Returns the ARK of the first search result, or None."""
    url = f"{LOUVRE_BASE_URL}/recherche"
    try:
        r = session.get(url, params={"q": query, "output": "json"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            if results:
                return results[0].get("ark")
    except requests.RequestException as e:
        log.warning("Louvre search for '%s' failed: %s", query, e)
    return None


def _parse_louvre_record(data: dict) -> dict:
    """Extracts relevant fields from a Louvre JSON-LD record."""
    record = {}

    # Title
    record["title_fr"] = _extract_lang(data.get("title"), "fr", "en")
    record["title_en"] = _extract_lang(data.get("title"), "en", "fr")

    # Artist — may be nested object or array
    creator = data.get("creator") or data.get("artist") or data.get("author")
    if isinstance(creator, list):
        names = []
        for c in creator:
            name = _first_str(c.get("name") if isinstance(c, dict) else c)
            if name:
                names.append(name)
        record["artist"] = ", ".join(names)
    elif isinstance(creator, dict):
        record["artist"] = _first_str(creator.get("name", ""))
    else:
        record["artist"] = _first_str(creator)

    record["date"] = _first_str(data.get("dateCreated") or data.get("dating") or data.get("date"))
    record["technique"] = _first_str(data.get("materialsAndTechniques") or data.get("technique"))
    record["dimensions"] = _first_str(data.get("dimension") or data.get("dimensions"))
    record["department"] = _first_str(data.get("department") or data.get("collection"))
    record["location"] = _first_str(data.get("currentLocation") or data.get("location"))
    record["school"] = _first_str(data.get("school") or data.get("artisticSchool"))
    record["period"] = _first_str(data.get("period") or data.get("historicalPeriod"))
    record["inventory_number"] = _first_str(data.get("inventoryNumber") or data.get("objectNumber"))
    record["acquisition"] = _first_str(data.get("acquisitionDetails") or data.get("acquisition"))

    # Descriptions — prefer long-form
    desc = data.get("description") or data.get("objectHistory") or data.get("comment")
    record["louvre_description_fr"] = _extract_lang(desc, "fr", "en")
    record["louvre_description_en"] = _extract_lang(desc, "en", "fr")

    return record


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------

def _fetch_wikipedia_summary(title: str, lang: str, session: requests.Session) -> str:
    if not title:
        return ""
    url = WIKIPEDIA_REST_URL.format(lang=lang, title=title)
    try:
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get("extract", "").strip()
        log.debug("Wikipedia %s/%s → HTTP %d", lang, title, r.status_code)
    except requests.RequestException as e:
        log.debug("Wikipedia %s/%s fetch error: %s", lang, title, e)
    return ""


# ---------------------------------------------------------------------------
# Main collection loop
# ---------------------------------------------------------------------------

def collect_all() -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": "IA04-Jetson-RAG/1.0 (educational project)"})

    artworks_out = []
    fallbacks_used = []

    for artwork_id, meta in ARTWORKS.items():
        log.info("Collecting: %s", artwork_id)

        # 1. Fetch Louvre record
        data = _fetch_louvre_ark(meta["ark"], session)
        time.sleep(REQUEST_DELAY_SECONDS)

        if data is None:
            log.warning("  → ARK failed, trying search fallback for '%s'", meta["search_fallback"])
            ark_found = _search_louvre(meta["search_fallback"], session)
            time.sleep(REQUEST_DELAY_SECONDS)
            if ark_found:
                log.info("  → Found via search: %s", ark_found)
                fallbacks_used.append({"id": artwork_id, "original_ark": meta["ark"], "found_ark": ark_found})
                data = _fetch_louvre_ark(ark_found, session)
                time.sleep(REQUEST_DELAY_SECONDS)
            if data is None:
                log.error("  → Could not retrieve Louvre data for %s, skipping", artwork_id)
                continue

        parsed = _parse_louvre_record(data)

        # 2. Enrich with Wikipedia
        wiki = meta.get("wikipedia", {})
        parsed["wikipedia_summary_fr"] = _fetch_wikipedia_summary(wiki.get("fr", ""), "fr", session)
        time.sleep(REQUEST_DELAY_SECONDS)
        parsed["wikipedia_summary_en"] = _fetch_wikipedia_summary(wiki.get("en", ""), "en", session)
        time.sleep(REQUEST_DELAY_SECONDS)

        # 3. Attach identifiers
        parsed["id"] = artwork_id
        parsed["ark"] = meta["ark"]
        parsed["louvre_url"] = f"{LOUVRE_BASE_URL}/{meta['ark']}"

        artworks_out.append(parsed)
        log.info("  ✓ done (%d fields populated)", sum(1 for v in parsed.values() if v))

    if fallbacks_used:
        log.warning("\nARK fallbacks used (update ARTWORKS dict with correct IDs):")
        for f in fallbacks_used:
            log.warning("  %s: %s → %s", f["id"], f["original_ark"], f["found_ark"])

    return artworks_out


def main():
    RAW_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    artworks = collect_all()

    output = {
        "metadata": {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "total_artworks": len(artworks),
            "source": "Louvre Collections API + Wikipedia REST API",
        },
        "artworks": artworks,
    }

    with open(RAW_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info("\nSaved %d artworks to %s", len(artworks), RAW_DATA_PATH)


if __name__ == "__main__":
    main()
