## Interactive Global Core Area Metrics Table

 
from pathlib import Path
from datetime import datetime
from itertools import zip_longest
import pandas as pd
from itables import show, init_notebook_mode

DATASET = "global"
INSTITUTE_LABEL = "INSTITUTE CORE AREA"


def find_processed_csv(filename: str) -> Path:
    base = Path.cwd().resolve()
    candidates = [
        (base / "../data/processed" / filename).resolve(),
        (base / "data/processed" / filename).resolve(),
    ]
    candidates.extend((p / "data" / "processed" / filename).resolve() for p in [base, *base.parents])

    for path in candidates:
        if path.exists():
            print(f"[OK] Found {filename} at: {path}")
            return path

    for parent in [base, *base.parents[:6]]:
        hits = list(parent.rglob(filename))
        if hits:
            path = hits[0].resolve()
            print(f"[OK] Found {filename} via rglob at: {path}")
            return path

    raise FileNotFoundError(f"Could not find '{filename}' from CWD={base}")


GLOBAL_CORE_FILE = find_processed_csv("global_core_area.pickle")
INSTITUTE_CORE_FILE = find_processed_csv("institute_core_area.pickle")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.replace("\ufeff", "", regex=False).str.strip()
    return df


def _series_or_na(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col] if col in df.columns else pd.Series([pd.NA] * len(df), index=df.index)


def _parse_numeric_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip().mask(lambda x: x.eq("") | x.eq("nan"), pd.NA)
    return pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")


def _parse_bool_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip().str.lower().replace({"1.0": "1", "0.0": "0"})
    mapped = s.map({
        "true": True, "false": False,
        "1": True, "0": False,
        "yes": True, "no": False,
        "y": True, "n": False,
        "t": True, "f": False,
    })
    return mapped.mask(s.eq("") | s.eq("nan"), pd.NA).astype("boolean")


def load_core_df(file_path: Path) -> pd.DataFrame:
    df = _clean_columns(pd.read_pickle(file_path))

    df["publication_year.openalex"] = _parse_numeric_series(_series_or_na(df, "publication_year.openalex"))
    df["cited_by_count.openalex"] = _parse_numeric_series(
        _series_or_na(df, "cited_by_count.openalex")
    ).fillna(0).astype(int)
    df["fwci.openalex"] = _parse_numeric_series(_series_or_na(df, "fwci.openalex")).fillna(0.0)

    df["citation_normalized_percentile.value.openalex"] = _parse_numeric_series(
        _series_or_na(df, "citation_normalized_percentile.value.openalex")
    )
    df["citation_normalized_percentile.is_in_top_1_percent.openalex"] = _parse_bool_series(
        _series_or_na(df, "citation_normalized_percentile.is_in_top_1_percent.openalex")
    )
    df["citation_normalized_percentile.is_in_top_10_percent.openalex"] = _parse_bool_series(
        _series_or_na(df, "citation_normalized_percentile.is_in_top_10_percent.openalex")
    )
    df["open_access.is_oa"] = _parse_bool_series(_series_or_na(df, "open_access.is_oa"))

    required = [
        "authorships.author.author_id.openalex",
        "authorships.institutions.institutions_id.openalex",
        "authorships.institutions.display_name.openalex",
        "work_id.openalex",
        "open_access.is_oa",
    ]
    for col in required:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def load_global_and_institute() -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_core_df(GLOBAL_CORE_FILE), load_core_df(INSTITUTE_CORE_FILE)


def _split_semi(value) -> list[str]:
    if not isinstance(value, str) or not value.strip() or value == "nan":
        return []
    return [x.strip() for x in value.split(";") if x.strip()]


def _institution_pairs(row: pd.Series) -> list[tuple[str, str]]:
    ids = _split_semi(row.get("authorships.institutions.institutions_id.openalex", ""))
    names = _split_semi(row.get("authorships.institutions.display_name.openalex", ""))
    pairs = {}
    for inst_id, name in zip_longest(ids, names, fillvalue=""):
        key = inst_id or (f"name:{name}" if name else "")
        if key and key not in pairs:
            pairs[key] = name or inst_id
    return sorted(pairs.items(), key=lambda item: item[0])


def enrich_work_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["n_authors"] = df["authorships.author.author_id.openalex"].fillna("").map(lambda x: len(_split_semi(x)))
    df["institution_pairs"] = df.apply(_institution_pairs, axis=1)
    df["n_institutions"] = df["institution_pairs"].map(len)
    return df


def explode_by_institution(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols = [
        "work_id.openalex",
        "fwci.openalex",
        "cited_by_count.openalex",
        "citation_normalized_percentile.value.openalex",
        "citation_normalized_percentile.is_in_top_1_percent.openalex",
        "citation_normalized_percentile.is_in_top_10_percent.openalex",
        "open_access.is_oa",
        "n_authors",
        "n_institutions",
        "institution_pairs",
    ]
    for col in cols:
        if col not in df.columns:
            df[col] = pd.NA

    out = df[cols].explode("institution_pairs", ignore_index=True)
    out = out[out["institution_pairs"].notna()].copy()
    out[["institution_id", "institution_label"]] = pd.DataFrame(
        out["institution_pairs"].tolist(), index=out.index
    )
    out = out.drop(columns="institution_pairs")
    out = out[out["institution_id"].fillna("") != ""].copy()

    out["fwci_per_author"] = out.apply(
        lambda r: r["fwci.openalex"] / r["n_authors"] if pd.notna(r["n_authors"]) and r["n_authors"] > 0 else pd.NA,
        axis=1,
    )
    out["fwci_per_inst"] = out.apply(
        lambda r: r["fwci.openalex"] / r["n_institutions"] if pd.notna(r["n_institutions"]) and r["n_institutions"] > 0 else pd.NA,
        axis=1,
    )
    return out


def compute_institution_table(exploded: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    dedup = exploded.drop_duplicates(subset=["institution_id", "work_id.openalex"]).copy()

    total_works = dedup["work_id.openalex"].nunique()
    total_citations = int(dedup.drop_duplicates("work_id.openalex")["cited_by_count.openalex"].sum())

    grp = dedup.groupby("institution_id", as_index=False).agg(
        UNIVERSITY=("institution_label", "first"),
        P=("work_id.openalex", "nunique"),
        C=("cited_by_count.openalex", "sum"),
        FWCI=("fwci.openalex", "mean"),
        SD_FWCI=("fwci.openalex", "std"),
        AUTHORS=("n_authors", "mean"),
        FWCI_per_AUTH=("fwci_per_author", "mean"),
        INSTS=("n_institutions", "mean"),
        FWCI_per_INST=("fwci_per_inst", "mean"),
        CNP=("citation_normalized_percentile.value.openalex", "mean"),
        Top1P=("citation_normalized_percentile.is_in_top_1_percent.openalex", "mean"),
        Top10P=("citation_normalized_percentile.is_in_top_10_percent.openalex", "mean"),
        OA=("open_access.is_oa", "mean"),
    )

    grp["PctP"] = (grp["P"] / total_works * 100.0) if total_works else 0.0
    grp["PctC"] = (grp["C"] / total_citations * 100.0) if total_citations else 0.0
    grp = grp.sort_values(["P", "C"], ascending=[False, False]).reset_index(drop=True)

    grp = grp.rename(columns={
        "P": "#P",
        "PctP": "%P",
        "C": "#C",
        "PctC": "%C",
        "SD_FWCI": "SD FWCI",
        "AUTHORS": "#AUTH",
        "FWCI_per_AUTH": "FWCI/ AUTH",
        "INSTS": "#INST",
        "FWCI_per_INST": "FWCI/ INST",
        "CNP": "CNP (mean)",
        "Top1P": "Top 1% (%)",
        "Top10P": "Top 10% (%)",
        "OA": "% OpenAccess",
    })

    grp["SD FWCI"] = grp["SD FWCI"].fillna(0.0)
    grp["Top 1% (%)"] = pd.to_numeric(grp["Top 1% (%)"], errors="coerce") * 100.0
    grp["Top 10% (%)"] = pd.to_numeric(grp["Top 10% (%)"], errors="coerce") * 100.0
    grp["% OpenAccess"] = pd.to_numeric(grp["% OpenAccess"], errors="coerce") * 100.0
    return grp, total_works, total_citations


def compute_institute_overall_row(institute_df: pd.DataFrame, global_denominators: tuple[int, int]) -> dict:
    inst_df = enrich_work_data(institute_df)
    inst_exploded = explode_by_institution(inst_df)
    inst_dedup = inst_exploded.drop_duplicates(subset=["work_id.openalex"]).copy()
    inst_total_works = inst_dedup["work_id.openalex"].nunique()
    inst_total_citations = int(inst_dedup["cited_by_count.openalex"].sum())

    per_work = inst_df[[
        "work_id.openalex",
        "fwci.openalex",
        "n_authors",
        "n_institutions",
        "citation_normalized_percentile.value.openalex",
        "citation_normalized_percentile.is_in_top_1_percent.openalex",
        "citation_normalized_percentile.is_in_top_10_percent.openalex",
        "open_access.is_oa",
    ]].drop_duplicates("work_id.openalex").copy()

    per_work["fwci_per_author"] = per_work.apply(
        lambda r: r["fwci.openalex"] / r["n_authors"] if pd.notna(r["n_authors"]) and r["n_authors"] > 0 else pd.NA,
        axis=1,
    )
    per_work["fwci_per_inst"] = per_work.apply(
        lambda r: r["fwci.openalex"] / r["n_institutions"] if pd.notna(r["n_institutions"]) and r["n_institutions"] > 0 else pd.NA,
        axis=1,
    )

    top1_share = per_work["citation_normalized_percentile.is_in_top_1_percent.openalex"].mean(skipna=True)
    top10_share = per_work["citation_normalized_percentile.is_in_top_10_percent.openalex"].mean(skipna=True)
    oa_share = per_work["open_access.is_oa"].mean(skipna=True)

    global_total_works, global_total_citations = global_denominators
    return {
        "institution_id": "INSTITUTE_CORE_AREA",
        "UNIVERSITY": INSTITUTE_LABEL,
        "#P": inst_total_works,
        "%P": (inst_total_works / global_total_works * 100.0) if global_total_works else 0.0,
        "#C": inst_total_citations,
        "%C": (inst_total_citations / global_total_citations * 100.0) if global_total_citations else 0.0,
        "% OpenAccess": float((oa_share * 100.0) if pd.notna(oa_share) else 0.0),
        "FWCI": float(per_work["fwci.openalex"].mean(skipna=True) or 0.0),
        "SD FWCI": float(per_work["fwci.openalex"].std(skipna=True) or 0.0),
        "#AUTH": float(per_work["n_authors"].mean(skipna=True) or 0.0),
        "FWCI/ AUTH": float(per_work["fwci_per_author"].mean(skipna=True) or 0.0),
        "#INST": float(per_work["n_institutions"].mean(skipna=True) or 0.0),
        "FWCI/ INST": float(per_work["fwci_per_inst"].mean(skipna=True) or 0.0),
        "CNP (mean)": float(per_work["citation_normalized_percentile.value.openalex"].mean(skipna=True) or 0.0),
        "Top 1% (%)": float((top1_share * 100.0) if pd.notna(top1_share) else 0.0),
        "Top 10% (%)": float((top10_share * 100.0) if pd.notna(top10_share) else 0.0),
    }


def build_institution_metrics_dataframe(dataset: str = DATASET) -> pd.DataFrame:
    global_df, institute_df = load_global_and_institute()
    base_df = enrich_work_data(global_df if dataset == "global" else institute_df)
    summary, global_total_works, global_total_citations = compute_institution_table(explode_by_institution(base_df))

    if dataset == "global":
        global_denoms = (global_total_works, global_total_citations)
    else:
        _, g_total_works, g_total_citations = compute_institution_table(explode_by_institution(enrich_work_data(global_df)))
        global_denoms = (g_total_works, g_total_citations)

    final_df = pd.concat(
        [summary, pd.DataFrame([compute_institute_overall_row(institute_df, global_denoms)])],
        ignore_index=True,
    )

    final_df["__sort_core_last"] = (final_df["UNIVERSITY"] == INSTITUTE_LABEL).astype(int)
    final_df = final_df.sort_values(["__sort_core_last", "#P", "#C"], ascending=[True, False, False]).reset_index(drop=True)

    for col in ["%P", "%C", "% OpenAccess", "Top 1% (%)", "Top 10% (%)"]:
        final_df[col] = pd.to_numeric(final_df[col], errors="coerce").round(1)
    for col in ["FWCI", "SD FWCI", "#AUTH", "FWCI/ AUTH", "#INST", "FWCI/ INST"]:
        final_df[col] = pd.to_numeric(final_df[col], errors="coerce").round(2)
    final_df["CNP (mean)"] = pd.to_numeric(final_df["CNP (mean)"], errors="coerce").round(3)
    final_df["#P"] = pd.to_numeric(final_df["#P"], errors="coerce").astype("Int64")
    final_df["#C"] = pd.to_numeric(final_df["#C"], errors="coerce").astype("Int64")
    return final_df


def show_institution_table_itables(dataset: str = DATASET):
    init_notebook_mode(all_interactive=True)
    df = build_institution_metrics_dataframe(dataset=dataset)

    sort_col_idx = df.columns.get_loc("__sort_core_last")
    id_col_idx = df.columns.get_loc("institution_id")
    column_defs = [
        {"targets": [sort_col_idx, id_col_idx], "visible": False, "searchable": False},
    ]

    numeric_cols = [
        "#P", "%P", "#C", "%C", "% OpenAccess",
        "FWCI", "SD FWCI", "#AUTH", "FWCI/ AUTH", "#INST", "FWCI/ INST",
        "CNP (mean)", "Top 1% (%)", "Top 10% (%)",
    ]
    numeric_idxs = [df.columns.get_loc(c) for c in numeric_cols if c in df.columns]
    if numeric_idxs:
        column_defs.append({"targets": numeric_idxs, "type": "num"})

    return show(
        df,
        classes="display compact stripe nowrap",
        paging=True,
        ordering=True,
        order=[[sort_col_idx, "asc"], [df.columns.get_loc("#P"), "desc"], [df.columns.get_loc("#C"), "desc"]],
        columnDefs=column_defs,
        lengthMenu=[[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
        pageLength=10,
        scrollX=True,
    )


def export_institution_table_to_excel(dataset: str = DATASET, output_dir: Path | None = None) -> Path:
    df = build_institution_metrics_dataframe(dataset=dataset).copy()
    df = df.drop(columns=["__sort_core_last"], errors="ignore")
    output_dir = output_dir or GLOBAL_CORE_FILE.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"institution_table_{dataset}_{timestamp()}.xlsx"
    df.to_excel(output_path, index=False)
    print(f"[OK] Excel exported: {output_path}")
    return output_path


table = show_institution_table_itables(dataset="global")
export_path = export_institution_table_to_excel(dataset="global")
print("Export written to:", export_path)



