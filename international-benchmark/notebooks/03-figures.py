
import pandas as pd
import plotly.express as px


# Load core area data from processed data folder
global_ca = pd.read_pickle('data/processed/global_core_area.pickle')
institute_ca = pd.read_pickle('data/processed/institute_core_area.pickle')


# ## Area Chart-Topics over time and FWCI


# ## Topic and Impact Analysis Overview
# 
# This section presents several visualizations to understand how research topics evolve over time, both in terms of **publication activity** and **citation impact**.  
# Data are analyzed for two contexts:
# - **Global Core Area** — based on all works in `global_ca`
# - **Institute Core Area** — based on works affiliated with the institution in `institute_ca`
# 
# ---
# 
# ### 1. Topic Share Over Time (%)
# 
# **Figures:**  
# - *Global Core Area: Topic Share Over Time (%)*  
# - *Institute Core Area: Topic Share Over Time (%)*  
# 
# These stacked area charts show the **relative share of publications** per topic each year.  
# - Each color represents a different topic.  
# - The vertical axis expresses the *percentage of total publications* in that year attributed to each topic.  
# - The total for every year sums to 100%.
# 
# **Interpretation:**  
# - Expanding colored areas indicate growing topical activity or focus.  
# - Shrinking areas indicate declining publication presence.  
# - This view emphasizes **how topic composition changes** within the total body of research over time.
# 
# ---
# 
# ### 2. Average FWCI per Topic Over Time
# 
# **Figures:**  
# - *Global Core Area: Average FWCI per Topic Over Time*  
# - *Institute Core Area: Average FWCI per Topic Over Time*  
# 
# These line charts display the **mean Field-Weighted Citation Impact (FWCI)** for each topic in each year.  
# 
# **What FWCI means:**  
# - FWCI = 1.0 → world average citation performance.  
# - FWCI > 1.0 → cited more often than the global average for similar works.  
# - FWCI < 1.0 → cited less often than average.
# 
# **Interpretation:**  
# - Each line traces how the *average citation impact* of a topic evolves over time.  
# - Rising lines indicate topics with improving relative citation impact.  
# - Falling lines may suggest decreasing relative influence or fewer highly cited works.  
# - This visualization reflects **impact quality** — how influential each topic’s works are on average.
# 
# ---
# 
# ### 3. Weighted FWCI Share Over Time (%)
# 
# **Figures:**  
# - *Global Core Area: Weighted FWCI Share Over Time (%)*  
# - *Institute Core Area: Weighted FWCI Share Over Time (%)*  
# 
# These stacked area charts show each topic’s **share of total citation influence** in a given year.  
# For each topic-year, the total FWCI impact is calculated as:
# 
# $$
# \text{Weighted FWCI} = (\text{Average FWCI}) \times (\text{Number of Publications with FWCI})
# $$
# 
# Then, each topic’s weighted FWCI is expressed as a **percentage of the total FWCI** across all topics in that year.
# 
# **Interpretation:**  
# - Topics with both high impact and high output occupy larger portions of the chart.  
# - This reveals which topics contribute most to the **overall citation performance** each year.  
# - Expanding areas indicate increasing influence in the global or institutional research portfolio.  
# - This chart integrates both **quantity (output)** and **quality (citation impact)** into one metric.
# 


import pandas as pd
import plotly.express as px

# =========================================
# 1) Topic share over time (%) — Global & Institute (as before)
# =========================================

# Aggregate topic counts by year
global_trend = (
    global_ca.groupby(
        ["publication_year.openalex", "primary_topic.topic_display_name.openalex"]
    )
    .size()
    .reset_index(name="count")
)

institute_trend = (
    institute_ca.groupby(
        ["publication_year.openalex", "primary_topic.topic_display_name.openalex"]
    )
    .size()
    .reset_index(name="count")
)

# Convert counts to percentage of total topics per year
global_trend["percentage"] = (
    global_trend.groupby("publication_year.openalex")["count"]
    .transform(lambda x: x / x.sum() * 100)
)

institute_trend["percentage"] = (
    institute_trend.groupby("publication_year.openalex")["count"]
    .transform(lambda x: x / x.sum() * 100)
)

# Plot global percentage trends
fig_global = px.area(
    global_trend,
    x="publication_year.openalex",
    y="percentage",
    color="primary_topic.topic_display_name.openalex",
    title="Global Core Area: Topic Share Over Time (%)",
    labels={
        "publication_year.openalex": "Publication Year",
        "percentage": "Share of Topics (%)",
        "primary_topic.topic_display_name.openalex": "Topic",
    },
)

# Plot institute percentage trends
fig_institute = px.area(
    institute_trend,
    x="publication_year.openalex",
    y="percentage",
    color="primary_topic.topic_display_name.openalex",
    title="Institute Core Area: Topic Share Over Time (%)",
    labels={
        "publication_year.openalex": "Publication Year",
        "percentage": "Share of Topics (%)",
        "primary_topic.topic_display_name.openalex": "Topic",
    },
)

fig_global.show()
fig_institute.show()

# =========================================
# 2) FWCI Option A — Average FWCI per topic over time (LINES)
#    (More interpretable: how topic impact changes vs. world avg = 1.0)
# =========================================

# Global: mean FWCI per topic-year (drop missing FWCI)
global_fwci_mean = (
    global_ca.dropna(subset=["fwci.openalex"])
    .groupby(["publication_year.openalex", "primary_topic.topic_display_name.openalex"])["fwci.openalex"]
    .mean()
    .reset_index(name="mean_fwci")
)

fig_fwci_mean_global = px.line(
    global_fwci_mean,
    x="publication_year.openalex",
    y="mean_fwci",
    color="primary_topic.topic_display_name.openalex",
    markers=True,
    title="Global Core Area: Average FWCI per Topic Over Time",
    labels={
        "publication_year.openalex": "Publication Year",
        "mean_fwci": "Average FWCI",
        "primary_topic.topic_display_name.openalex": "Topic",
    },
)
fig_fwci_mean_global.show()

# Institute: mean FWCI per topic-year (drop missing FWCI)
institute_fwci_mean = (
    institute_ca.dropna(subset=["fwci.openalex"])
    .groupby(["publication_year.openalex", "primary_topic.topic_display_name.openalex"])["fwci.openalex"]
    .mean()
    .reset_index(name="mean_fwci")
)

fig_fwci_mean_institute = px.line(
    institute_fwci_mean,
    x="publication_year.openalex",
    y="mean_fwci",
    color="primary_topic.topic_display_name.openalex",
    markers=True,
    title="Institute Core Area: Average FWCI per Topic Over Time",
    labels={
        "publication_year.openalex": "Publication Year",
        "mean_fwci": "Average FWCI",
        "primary_topic.topic_display_name.openalex": "Topic",
    },
)
fig_fwci_mean_institute.show()

# =========================================
# 3) FWCI Option B — Weighted FWCI share (%) per topic over time (AREAS)
#    Definition: (sum of FWCI across works in topic-year) / (sum of FWCI across all topics that year)
#    Implemented as mean(FWCI) * number of works with non-null FWCI, normalized within year.
# =========================================

# Helper to compute weighted FWCI share dataframe for any dataframe with same schema
def compute_weighted_fwci_share(df: pd.DataFrame) -> pd.DataFrame:
    # Keep only rows with FWCI
    df_fwci = df.dropna(subset=["fwci.openalex"])

    # For each (year, topic): count of FWCI-bearing works and mean FWCI
    by_topic_year = (
        df_fwci.groupby(
            ["publication_year.openalex", "primary_topic.topic_display_name.openalex"]
        )["fwci.openalex"]
        .agg(n_fwci="count", mean_fwci="mean")
        .reset_index()
    )

    # Weighted FWCI = mean * count = sum of FWCI across works in that topic-year
    by_topic_year["weighted_fwci"] = by_topic_year["mean_fwci"] * by_topic_year["n_fwci"]

    # Total FWCI per year (sum across topics)
    totals = (
        by_topic_year.groupby("publication_year.openalex")["weighted_fwci"]
        .sum()
        .rename("total_fwci_year")
        .reset_index()
    )

    # Merge and compute percentage share; drop years whose total FWCI is zero (safety)
    out = by_topic_year.merge(totals, on="publication_year.openalex", how="left")
    out = out[out["total_fwci_year"] > 0].copy()
    out["fwci_share_percent"] = out["weighted_fwci"] / out["total_fwci_year"] * 100

    return out

# Global weighted FWCI share
global_fwci_share = compute_weighted_fwci_share(global_ca)

fig_fwci_share_global = px.area(
    global_fwci_share,
    x="publication_year.openalex",
    y="fwci_share_percent",
    color="primary_topic.topic_display_name.openalex",
    title="Global Core Area: Weighted FWCI Share Over Time (%)",
    labels={
        "publication_year.openalex": "Publication Year",
        "fwci_share_percent": "Share of Total FWCI (%)",
        "primary_topic.topic_display_name.openalex": "Topic",
    },
)
fig_fwci_share_global.show()

# Institute weighted FWCI share
institute_fwci_share = compute_weighted_fwci_share(institute_ca)

fig_fwci_share_institute = px.area(
    institute_fwci_share,
    x="publication_year.openalex",
    y="fwci_share_percent",
    color="primary_topic.topic_display_name.openalex",
    title="Institute Core Area: Weighted FWCI Share Over Time (%)",
    labels={
        "publication_year.openalex": "Publication Year",
        "fwci_share_percent": "Share of Total FWCI (%)",
        "primary_topic.topic_display_name.openalex": "Topic",
    },
)
fig_fwci_share_institute.show()



