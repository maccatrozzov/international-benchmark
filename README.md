# OpenAlex Core Area Analysis

This repository contains a three-notebook workflow for retrieving OpenAlex publication data, calculating institution-level metrics, and producing figures for a core-area analysis. This workflow was developed by Manuel Llano and Kasper Abcouwer (UvA UB) inspired by the methodology of Jules van Rooij (RUG).

The notebooks are intentionally kept separate so each stage can be run, checked, and rerun independently:

1. `01-data-retrieval.ipynb` retrieves and prepares OpenAlex data.
2. `02-metrics.ipynb` calculates metrics and creates institution-level tables.
3. `03-figures.ipynb` generates exploratory figures from the processed data.

## Directory structure

```text
.
├── notebooks/
│   ├── 01-data-retrieval.ipynb
│   ├── 02-metrics.ipynb
│   └── 03-figures.ipynb
├── data/
│   ├── raw/
│   │   └── input.csv
│   ├── interim/
│   │   └── openalex-total-institute-output.csv
│   └── processed/
│       ├── institute_core_area.csv
│       ├── global_core_area.csv
│       └── institution_table_global_<timestamp>.xlsx
├── README.md
└── requirements.txt
```

The `data/raw/` folder contains the manually prepared input data, for instance using a CRIS export. The `data/interim/` folder contains retrieved OpenAlex data before final processing. The `data/processed/` folder contains analysis-ready datasets and exported tables.

If the notebooks are stored in the repository root rather than a `notebooks/` folder, keep the same `data/` structure and adjust relative paths if needed.

## Input data

The retrieval notebook expects a curated and deduplicated CSV file at:

```text
data/raw/input.csv
```

At minimum, the input file should contain a DOI column:

```text
doi
```

The workflow also expects the following columns when available, because they are used for reference and downstream analysis:

```text
work_id.pure
research_unit
```

## OpenAlex configuration

The workflow uses the OpenAlex API. To use the polite pool and, optionally, an API key, set these environment variables before running the notebooks:

```bash
export EMAIL="your.email@example.com"
export OPENALEX_API_KEY="your_openalex_api_key"
```

## Python requirements

Install the main dependencies with:

```bash
pip install pandas requests plotly itables openpyxl
```

A minimal `requirements.txt` would be:

```text
pandas
requests
plotly
itables
openpyxl
```

## Workflow

### 1. Data retrieval

Run:

```text
01-data-retrieval.ipynb
```

This notebook starts from the curated institute output in `data/raw/pure_UU.csv`, retrieves matching OpenAlex Works by DOI, and stores the enriched institute output in:

```text
data/interim/openalex-total-institute-output.csv
```

It then identifies the institute core area based on selected topics and writes:

```text
data/processed/institute_core_area.csv
```

Finally, it retrieves the global core area from OpenAlex for the same topic set and publication period, writing:

```text
data/processed/global_core_area.csv
```

The retrieved OpenAlex fields include institution identifiers, institution display names, open-access information, FWCI, and citation-normalized percentile information.

### 2. Metrics

Run:

```text
02-metrics.ipynb
```

This notebook reads the processed institute and global core-area datasets and builds institution-level metrics tables.

Institution sorting and aggregation are based on OpenAlex institution IDs. Institution names are retained as display labels, which avoids merging or splitting institutions incorrectly when display names vary.

The institution table includes, among other metrics:

- total publication count;
- FWCI;
- citation-normalized percentile metrics;
- top 10% / top 1% citation-normalized indicators, where available;
- open-access publication percentage;
- incoming and outgoing citation ranking;
- internal collaboration metrics.

The interactive table is shown in the notebook using `itables`. An Excel export is written to:

```text
data/processed/institution_table_global_<timestamp>.xlsx
```

### 3. Figures

Run:

```text
03-figures.ipynb
```

This notebook reads:

```text
data/processed/institute_core_area.csv
data/processed/global_core_area.csv
```

It creates visualizations for topic activity and citation impact over time, comparing the institute core area with the global core area.
