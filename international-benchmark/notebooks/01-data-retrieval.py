# Data retrieval
# 
# 1. **Institute output:** input a csv/excel with the institute output with a column 'doi'. From these DOIs, a csv of the outputs with OpenAlex data is created and saved in the data/interim folder.
# 2. **Institute core area:** input a number of topics to define core area. Output an overview of topics, percetange of total output, and an 'institute_core_area.csv' file in the data/processed folder.
# 3. **Global core area:** on the basis of the defined institute core area, all works in the global core area for the period defined by the earliest and latest publication in the institute core area are downloaded from OpenAlex.


import os
from dotenv import load_dotenv
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
import math
import time
import random
from typing import List, Dict, Any, Iterable
from urllib.parse import quote

# Set API key and polite pool from environment variables
load_dotenv('keys.env')
OPENALEX_API_KEY = os.getenv('OPENALEX_API_KEY')
EMAIL = os.getenv('EMAIL')



# Zorg dat deze bestaan in jouw omgeving/script:
# EMAIL = "jij@uva.nl"
# OPENALEX_API_KEY = "..."

# ## 1. Institute output


# This assumes that df contains a curated and deduplicated list of DOIs representing the totality of an institute's output for a given period.
# The following columns are needed for further analysis and reference: ['doi'], ['work_id.pure'], ['research_unit']. 
# This API query will request the following fields from OpenAlex: 

df = pd.read_csv('data/raw/input.csv')




# ---------------------- OpenAlex fetch ----------------------

def fetch_openalex_data(doi: str):
    """
    Look up a Work by DOI using the canonical form:
      https://api.openalex.org/works/https://doi.org/<doi>
    Returns a flat dict with safe fallbacks (''/0/False/NA).
    """
    if not isinstance(doi, str) or not doi.strip():
        return None

    doi = doi.strip()

    # Build the proper "external ID" path for DOIs
    # Docs: https://docs.openalex.org/api-entities/works/get-a-single-work
    if doi.lower().startswith("http"):
        doi_id = doi
    elif doi.lower().startswith("doi:"):
        doi_id = "https://doi.org/" + doi.split(":", 1)[1]
    else:
        doi_id = "https://doi.org/" + doi

    base_url = f"https://api.openalex.org/works/{quote(doi_id, safe='')}"

    # Use polite pool + (optional) premium api_key via query params
    # Docs: https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication
    params = {"mailto": EMAIL}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY

    headers = {
        "User-Agent": f"OpenAlexEnricher/1.0 (mailto:{EMAIL})"
    }

    resp = requests.get(base_url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        return None

    data = resp.json() or {}

    # Nested objects with safe defaults
    topic = data.get("primary_topic") or {}
    sdgs = data.get("sustainable_development_goals") or []
    authorships = data.get("authorships") or []
    open_access = data.get("open_access") or {}
    primary_location = data.get("primary_location") or {}
    best_oa_location = data.get("best_oa_location") or {}
    source_primary = (primary_location.get("source") or {})
    source_best = (best_oa_location.get("source") or {})

    # Helper to join list safely
    def _join_maybe_list(value, sep=";"):
        if not value:
            return ""
        if isinstance(value, list):
            return sep.join([str(x or "") for x in value if x is not None])
        return str(value)

    # Build authors & institutions strings
    author_ids = []
    author_names = []
    inst_ids_per_author = []
    inst_names_per_author = []

    for a in authorships:
        author = a.get("author") or {}
        author_ids.append(author.get("id", "") or "")
        author_names.append(author.get("display_name", "") or "")

        insts = a.get("institutions") or []
        inst_ids_per_author.append(_join_maybe_list([i.get("id", "") or "" for i in insts]))
        inst_names_per_author.append(_join_maybe_list([i.get("display_name", "") or "" for i in insts]))


    # make string SDG-score
    sdg_names = []
    sdg_scores = []
    sdg_ids = []
    for sdg in sdgs:
        sdg_names.append(sdg.get("display_name", "") or "")
        sdg_scores.append(float(sdg.get("score", 0.0) or 0.0))
        sdg_ids.append(sdg.get("id", "") or "")

    # fwci is a top-level field on Work
    fwci_value = data.get("fwci", 0.0) or 0.0

    # ---- NEW: citation_normalized_percentile (CNP) ----
    cnp = data.get("citation_normalized_percentile") or {}
    cnp_value = cnp.get("value", None)
    cnp_top_1 = cnp.get("is_in_top_1_percent", None)
    cnp_top_10 = cnp.get("is_in_top_10_percent", None)

    return {
        # Topics
        "primary_topic.topic_id.openalex": topic.get("id", "") or "",
        "primary_topic.topic_score.openalex": float(topic.get("score", 0.0) or 0.0),
        "primary_topic.topic_display_name.openalex": topic.get("display_name", "") or "",

        #SDG
        "SDG.sdg_display_name.openalex":_join_maybe_list(sdg_names),
        "SDG.sdg_score.openalex": _join_maybe_list(sdg_scores),
        "SDG.sdg_id.openalex": _join_maybe_list(sdg_ids),
        
        # Authorships
        "authorships.author.author_id.openalex": _join_maybe_list(author_ids),
        "authorships.author.author_display_names.openalex": _join_maybe_list(author_names),
        "authorships.institutions.institutions_id.openalex": _join_maybe_list(inst_ids_per_author),
        "authorships.institutions.display_name.openalex": _join_maybe_list(inst_names_per_author),

        # Core IDs
        "work_id.openalex": data.get("id", "") or "",

        # Primary location
        "primary_location.is_oa": bool(primary_location.get("is_oa", False)),
        "primary_location.landing_page_url": primary_location.get("landing_page_url", "") or "",
        "primary_location.pdf_url.openalex": primary_location.get("pdf_url", "") or "",
        "primary_location.source_id.openalex": source_primary.get("id", "") or "",
        "primary_location.source_display_name.openalex": source_primary.get("display_name", "") or "",
        "primary_location.source_issn_l.openalex": source_primary.get("issn_l", "") or "",
        "primary_location.source_issn.openalex": _join_maybe_list(source_primary.get("issn") or []),
        "primary_location.source_host_organization.openalex": source_primary.get("host_organization", "") or "",
        "primary_location.source_type.openalex": source_primary.get("type", "") or "",

        # Best OA location (often the direct OA copy)
        "best_oa_location.is_oa": bool(best_oa_location.get("is_oa", False)),
        "best_oa_location.landing_page_url": best_oa_location.get("landing_page_url", "") or "",
        "best_oa_location.pdf_url.openalex": best_oa_location.get("pdf_url", "") or "",
        "best_oa_location.source_id.openalex": source_best.get("id", "") or "",
        "best_oa_location.source_display_name.openalex": source_best.get("display_name", "") or "",

        # Publication & access
        "publication_date.openalex": data.get("publication_date", "") or "",
        "publication_year.openalex": int(data.get("publication_year", 0) or 0),
        "oa_status_open_access.openalex": open_access.get("oa_status", "") or "",
        "open_access.is_oa": bool(open_access.get("is_oa", False)),
        "open_access.oa_url": open_access.get("oa_url", "") or "",

        # Citations
        "cited_by_count.openalex": int(data.get("cited_by_count", 0) or 0),
        "cited_by_api_url.openalex": data.get("cited_by_api_url", "") or "",

        # Normalized metric
        "fwci.openalex": float(fwci_value),

        # ---- NEW OUTPUT FIELDS: citation_normalized_percentile ----
        "citation_normalized_percentile.value.openalex": (float(cnp_value) if cnp_value is not None else pd.NA),
        "citation_normalized_percentile.is_in_top_1_percent.openalex": (bool(cnp_top_1) if cnp_top_1 is not None else pd.NA),
        "citation_normalized_percentile.is_in_top_10_percent.openalex": (bool(cnp_top_10) if cnp_top_10 is not None else pd.NA),
    }


# ---------------------- DataFrame enrich ----------------------

def enrich_df_with_openalex(df: pd.DataFrame) -> pd.DataFrame:
    openalex_columns = {
        'primary_topic.topic_id.openalex': str,
        'primary_topic.topic_score.openalex': float,
        'primary_topic.topic_display_name.openalex': str,
        
        'SDG.sdg_display_name.openalex': str,
        'SDG.sdg_score.openalex': float,
        'SDG.sdg_id.openalex': str,

        'authorships.author.author_id.openalex': str,
        'authorships.author.author_display_names.openalex': str,
        'authorships.institutions.institutions_id.openalex': str,
        'authorships.institutions.display_name.openalex': str,
        'work_id.openalex': str,

        'primary_location.is_oa': bool,
        'primary_location.landing_page_url': str,
        'primary_location.pdf_url.openalex': str,
        'primary_location.source_id.openalex': str,
        'primary_location.source_display_name.openalex': str,
        'primary_location.source_issn_l.openalex': str,
        'primary_location.source_issn.openalex': str,
        'primary_location.source_host_organization.openalex': str,
        'primary_location.source_type.openalex': str,

        'best_oa_location.is_oa': bool,
        'best_oa_location.landing_page_url': str,
        'best_oa_location.pdf_url.openalex': str,
        'best_oa_location.source_id.openalex': str,
        'best_oa_location.source_display_name.openalex': str,

        'publication_date.openalex': str,
        'publication_year.openalex': int,
        'oa_status_open_access.openalex': str,
        'open_access.is_oa': bool,
        'open_access.oa_url': str,

        'cited_by_count.openalex': int,
        'cited_by_api_url.openalex': str,
        'fwci.openalex': float,

        # ---- NEW: CNP columns ----
        "citation_normalized_percentile.value.openalex": float,
        "citation_normalized_percentile.is_in_top_1_percent.openalex": bool,
        "citation_normalized_percentile.is_in_top_10_percent.openalex": bool,
    }

    # Initialize new columns (if missing) with NA of appropriate dtype
    for col in openalex_columns.keys():
        if col not in df.columns:
            df[col] = pd.NA

    # Fetch OpenAlex data for each DOI and populate the DataFrame
    for idx, doi in df['doi'].items():
        payload = fetch_openalex_data(doi)
        if payload:
            for key, value in payload.items():
                df.at[idx, key] = value

    # Best-effort dtype coercion at the end (robust)
    for col, dtype in openalex_columns.items():
        try:
            if dtype is int:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            elif dtype is float:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif dtype is bool:
                df[col] = df[col].astype("boolean")
            else:
                df[col] = df[col].astype("string")
        except Exception:
            pass

    return df



# -------------------- Usage --------------------



df = enrich_df_with_openalex(df)
outputfile = 'data/interim/openalex-total-institute-output.pickle'
df.to_pickle(outputfile)
print("[OK] Saved: " + outputfile)
