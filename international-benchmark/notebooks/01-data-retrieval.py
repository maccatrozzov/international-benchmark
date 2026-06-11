

# # Data retrieval
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

import requests
import pandas as pd
from urllib.parse import quote


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
    for sdg in sdgs:
        sdg_names.append(sdg.get("display_name", "") or "")
        sdg_scores.append(float(sdg.get("score", 0.0) or 0.0))

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



# ## 2. Institute Core Area


# -------------------- Config --------------------
START_YEAR = 2019
END_YEAR = 2025

# Define Top-N topics (default n=5)
n = 2

def filter_top_n_topics(df, n=5):
    # Clean up topic ids (drop blanks/NA)
    topic_series = df['primary_topic.topic_id.openalex'].fillna("").astype(str)
    topic_series = topic_series[topic_series.str.len() > 0]

    # Step 1: Count occurrences of each topic_id
    topic_counts = topic_series.value_counts()

    if topic_counts.empty:
        print("No primary_topic IDs found in the dataframe.")
        return df.iloc[0:0].copy(), 0.0

    # Step 2: SELECT N TOPICS
    top_n_topics = topic_counts.head(n)

    # Step 3: Filter the dataframe to only include rows with the top N topics
    df_institute_core_area = df[df['primary_topic.topic_id.openalex'].isin(top_n_topics.index)]

    # Step 4: Calculate the percentage of rows with top N topics
    total_rows = len(df)
    top_n_rows = len(df_institute_core_area)
    percentage = (top_n_rows / total_rows) * 100 if total_rows else 0.0

    # Step 5: Print the value counts for the topic ids
    print("\nCore area topics (by topic_id):")
    print(top_n_topics)

    return df_institute_core_area, percentage

# # Apply function
# df_institute_core_area, top_n_percentage = filter_top_n_topics(df, n)
# print(f"Top {n} most recurrent topics represent {top_n_percentage:.2f}% of the total data.")
# df_institute_core_area.head()
# df_institute_core_area.to_csv('../data/processed/institute_core_area.csv', index=False)


# ---- OpenAlex counting helpers ----

def _openalex_params():
    """Standard query params for OpenAlex."""
    params = {"mailto": EMAIL}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    return params

def count_works_for_topic(topic_id: str, start_year: int, end_year: int) -> int:
    """
    Count works for a topic over a publication year range.
    Uses proper range syntax: publication_year:START-END
    """
    if not topic_id or not isinstance(topic_id, str):
        return 0
    if start_year is None or end_year is None:
        return 0
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    base_url = "https://api.openalex.org/works"

    # Build filter. topic_id can be full URL (https://openalex.org/T...) or short (T...).
    # Requests will URL-encode the filter value automatically.
    filter_value = f"primary_topic.id:{topic_id},publication_year:{start_year}-{end_year}"

    params = {
        "filter": filter_value,
        "per-page": 1,   # only need meta.count
        "page": 1,
        **_openalex_params(),
    }

    headers = {
        "User-Agent": f"OpenAlexCounter/1.0 (mailto:{EMAIL})"
    }

    try:
        resp = requests.get(base_url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            return int((resp.json() or {}).get("meta", {}).get("count", 0) or 0)
        else:
            print(f"[warn] OpenAlex response {resp.status_code} for topic {topic_id}")
            return 0
    except Exception as e:
        print(f"[error] Counting topic {topic_id} failed: {e}")
        return 0

def estimate_total_works(df_core, start_year=START_YEAR, end_year=END_YEAR):
    """
    Sum counts across unique topics present in df_core over a fixed publication-year span.
    """
    # Unique topics
    topics = (
        df_core['primary_topic.topic_id.openalex']
        .dropna()
        .astype(str)
        .str.strip()
    )
    topics = topics[topics != ""].unique()

    if topics.size == 0:
        print("No topics in the core-area dataframe.")
        return

    total_works = 0
    for t in topics:
        cnt = count_works_for_topic(t, start_year, end_year)
        print(f"Topic {t} has {cnt} works from {start_year} to {end_year}.")
        total_works += cnt

    print(f"\nTotal estimated number of works in Global Core area: {total_works}")

# # Run the estimate with the filtered dataframe
# estimate_total_works(df_institute_core_area, start_year=START_YEAR, end_year=END_YEAR)


# ## 3. Global Core Area


# ---------------------- HTTP helpers ------------------------

def _openalex_params() -> dict:
    """Standard OpenAlex query params. Use api_key + mailto as query args (no Authorization header)."""
    params = {"mailto": EMAIL}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    return params

def _user_agent(suffix="Fetcher"):
    return f"GlobalCoreArea/{suffix} (mailto:{EMAIL})"

def _retry_get(session: requests.Session, url: str, *, headers: dict, params: dict, max_retries: int = 4, base_delay: float = 0.8) -> requests.Response:
    """
    GET with bounded retries/backoff on common transient statuses.
    Obeys server Retry-After when present.
    """
    attempt = 0
    while True:
        resp = session.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code in (200, 204):
            return resp

        retryable = resp.status_code in (429, 500, 502, 503, 504)
        if not retryable or attempt >= max_retries:
            return resp

        # Honor Retry-After (seconds) if present; otherwise jittered backoff
        retry_after = 0.0
        try:
            retry_after = float(resp.headers.get("Retry-After", "0"))
        except Exception:
            retry_after = 0.0

        sleep_s = max(retry_after, base_delay * (2 ** attempt)) + random.uniform(0, 0.25)
        time.sleep(sleep_s)
        attempt += 1

# -------------------- Transformation helpers --------------------

def _flatten_work(work: dict) -> dict:
    """Flatten a Work object into the schema used in your pipeline."""
    topic = work.get("primary_topic") or {}
    sdgs = work.get("sustainable_development_goals") or {}
    authorships = work.get("authorships") or []
    open_access = work.get("open_access") or {}
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}

    # --- NEW: citation_normalized_percentile ---
    cnp = work.get("citation_normalized_percentile") or {}
    cnp_value = cnp.get("value", None)
    cnp_top_1 = cnp.get("is_in_top_1_percent", None)
    cnp_top_10 = cnp.get("is_in_top_10_percent", None)

    author_ids = []
    author_names = []
    inst_ids_per_author = []
    inst_names_per_author = []

    for a in authorships:
        a_author = a.get("author") or {}
        author_ids.append(a_author.get("id", "") or "")
        author_names.append(a_author.get("display_name", "") or "")

        insts = a.get("institutions") or []
        inst_ids_per_author.append(";".join([i.get("id", "") or "" for i in insts]))
        inst_names_per_author.append(";".join([i.get("display_name", "") or "" for i in insts]))
   
    sdg_names = []
    sdg_scores = []
    for sdg in sdgs:
        
        sdg_names.append(sdg.get("display_name", "") or "")
        sdg_scores.append(float(sdg.get("score", 0.0) or 0.0))
    return {
        "primary_topic.topic_id.openalex": topic.get("id", "") or "",
        "primary_topic.topic_score.openalex": float(topic.get("score", 0.0) or 0.0),
        "primary_topic.topic_display_name.openalex": topic.get("display_name", "") or "",

        
        "SDG.sdg_display_name.openalex": ";".join(sdg_names),
        "SDG.sdg_score.openalex": ";".join(sdg_scores),

        "authorships.author.author_id.openalex": ";".join(author_ids),
        "authorships.author.author_display_names.openalex": ";".join(author_names),
        "authorships.institutions.institutions_id.openalex": ";".join(inst_ids_per_author),
        "authorships.institutions.display_name.openalex": ";".join(inst_names_per_author),

        "work_id.openalex": work.get("id", "") or "",

        "primary_location.is_oa": bool(primary_location.get("is_oa", False)),
        "primary_location.landing_page_url": primary_location.get("landing_page_url", "") or "",
        "primary_location.pdf_url.openalex": primary_location.get("pdf_url", "") or "",
        "primary_location.source_id.openalex": source.get("id", "") or "",
        "primary_location.source_display_name.openalex": source.get("display_name", "") or "",
        "primary_location.source_issn_l.openalex": source.get("issn_l", "") or "",
        "primary_location.source_issn.openalex": ";".join(source.get("issn") or []),
        "primary_location.source_host_organization.openalex": source.get("host_organization", "") or "",
        "primary_location.source_type.openalex": source.get("type", "") or "",

        "publication_date.openalex": work.get("publication_date", "") or "",
        "publication_year.openalex": int(work.get("publication_year", 0) or 0),

        "oa_status_open_access.openalex": open_access.get("oa_status", "") or "",
        "open_access.is_oa": bool(open_access.get("is_oa", False)),
        "open_access.oa_url": open_access.get("oa_url", "") or "",

        "cited_by_count.openalex": int(work.get("cited_by_count", 0) or 0),
        "cited_by_api_url.openalex": work.get("cited_by_api_url", "") or "",

        "fwci.openalex": float(work.get("fwci", 0.0) or 0.0),

        # --- NEW OUTPUT FIELDS ---
        "citation_normalized_percentile.value.openalex": (float(cnp_value) if cnp_value is not None else None),
        "citation_normalized_percentile.is_in_top_1_percent.openalex": (bool(cnp_top_1) if cnp_top_1 is not None else None),
        "citation_normalized_percentile.is_in_top_10_percent.openalex": (bool(cnp_top_10) if cnp_top_10 is not None else None),
    }

# ----------------------- Core fetching -----------------------

def fetch_openalex_data_for_topic(topic_id: str, start_year: int, end_year: int, *, per_page: int = 200, session: requests.Session | None = None) -> List[Dict[str, Any]]:
    """
    Fetch ALL works for a given primary_topic.id within [start_year, end_year] using cursor pagination.
    Sequential within a topic (to respect cursor ordering), suitable for parallel fan-out across topics.
    """
    if not topic_id:
        return []

    if start_year and end_year and int(start_year) > int(end_year):
        start_year, end_year = end_year, start_year

    base_url = "https://api.openalex.org/works"
    headers = {"User-Agent": _user_agent("TopicWorks")}
    params = {
        "filter": f"primary_topic.id:{topic_id},publication_year:{int(start_year)}-{int(end_year)}",
        "per-page": int(per_page),
        "cursor": "*",
        **_openalex_params(),
    }

    local_session = session or requests.Session()
    out = []

    while True:
        resp = _retry_get(local_session, base_url, headers=headers, params=params)
        if not resp or not resp.ok:
            print(f"[topic {topic_id}] HTTP {getattr(resp,'status_code', 'NA')}: {getattr(resp,'text','')[:200]}")
            break

        payload = resp.json() or {}
        works = payload.get("results") or []
        out.extend(_flatten_work(w) for w in works)

        next_cursor = (payload.get("meta") or {}).get("next_cursor")
        if not next_cursor:
            break
        params["cursor"] = next_cursor

    return out

# -------------------- Parallel wrapper ---------------------

def _unique_clean_topics(df_institute_core_area: pd.DataFrame) -> List[str]:
    topics = (
        df_institute_core_area["primary_topic.topic_id.openalex"]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )
    return sorted({t for t in topics if t})

def create_global_core_area_parallel(
    df_institute_core_area: pd.DataFrame,
    *,
    start_year: int = START_YEAR,
    end_year: int = END_YEAR,
    max_workers: int = 8,
    per_page: int = 200,
) -> pd.DataFrame:
    """
    Parallelizes over topics using threads. Each topic paginates sequentially with a shared requests.Session.
    - Threads are appropriate because requests is I/O-bound.
    - Adjust max_workers conservatively to respect OpenAlex rate limits.
    """
    topics = _unique_clean_topics(df_institute_core_area)
    if not topics:
        return pd.DataFrame(columns=df_institute_core_area.columns)

    all_rows: list[dict] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": _user_agent("Pool")})

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    fetch_openalex_data_for_topic,
                    topic_id=t,
                    start_year=start_year,
                    end_year=end_year,
                    per_page=per_page,
                    session=session,
                ): t
                for t in topics
            }

            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    rows = fut.result()
                    all_rows.extend(rows)
                    print(f"[topic {t}] fetched {len(rows)} works.")
                except Exception as e:
                    print(f"[topic {t}] failed: {e}")

    df = pd.DataFrame(all_rows)

    # Deduplicate by Work ID (a work might appear under multiple top topics)
    if not df.empty and "work_id.openalex" in df.columns:
        df = df.drop_duplicates(subset=["work_id.openalex"]).reset_index(drop=True)

    return df

# -------------------- Usage --------------------



df = enrich_df_with_openalex(df)
outputfile = 'data/interim/openalex-total-institute-output.pickle'
df.to_pickle(outputfile)
print("[OK] Saved: " + outputfile)
