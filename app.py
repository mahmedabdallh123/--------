import streamlit as st
import pandas as pd
import numpy as np

# ===============================
# GitHub RAW FILE URL
# ===============================
FILE_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/logbook-analysis/main/data/Logbook_20241225.txt"

st.set_page_config(page_title="Logbook Reliability Dashboard", layout="wide")

st.title("📘 Logbook Reliability Analysis")
st.caption("MTTR • MTBF • Event Frequency • Time Analysis")

# ===============================
# Load & Parse Logbook
# ===============================
@st.cache_data
def load_logbook(url):
    lines = pd.read_csv(url, sep="\n", header=None)[0].tolist()

    data = []
    for line in lines:
        if line.startswith("=") or line.strip() == "":
            continue

        parts = line.split("\t")
        while len(parts) < 4:
            parts.append("")

        data.append([p.strip() for p in parts])

    df = pd.DataFrame(data, columns=["Date", "Time", "Event", "Details"])

    # datetime
    df["Datetime"] = pd.to_datetime(
        df["Date"] + " " + df["Time"],
        format="%d.%m.%Y %H:%M:%S",
        errors="coerce"
    )

    df = df.dropna(subset=["Datetime"])
    df = df.sort_values("Datetime").reset_index(drop=True)

    return df


df = load_logbook(FILE_URL)

# ===============================
# Sidebar Filters
# ===============================
st.sidebar.header("🔎 Filters")

event_filter = st.sidebar.multiselect(
    "Select Events",
    options=df["Event"].unique()
)

if event_filter:
    df_filtered = df[df["Event"].isin(event_filter)]
else:
    df_filtered = df.copy()

# ===============================
# Event Frequency
# ===============================
st.subheader("📊 Event Frequency")

event_count = (
    df_filtered["Event"]
    .value_counts()
    .reset_index()
)
event_count.columns = ["Event", "Count"]

st.dataframe(event_count, use_container_width=True)

# ===============================
# Time Between Events
# ===============================
st.subheader("⏱️ Time Between Events")

df_filtered["Time_Diff_Min"] = (
    df_filtered["Datetime"]
    .diff()
    .dt.total_seconds() / 60
)

st.dataframe(
    df_filtered[["Datetime", "Event", "Time_Diff_Min"]],
    use_container_width=True
)

# ===============================
# Failure Definition
# ===============================
st.subheader("🚨 Failure-Based Metrics")

failure_keywords = ["break", "stopped", "error", "fault", "deviation"]

df["Is_Failure"] = df["Event"].str.lower().apply(
    lambda x: any(k in x for k in failure_keywords)
)

failures = df[df["Is_Failure"]].copy()

# ===============================
# MTTR Calculation
# ===============================
failures["Repair_Time_Min"] = (
    failures["Datetime"]
    .shift(-1) - failures["Datetime"]
).dt.total_seconds() / 60

MTTR = failures["Repair_Time_Min"].mean()

# ===============================
# MTBF Calculation
# ===============================
failures["Failure_Gap_Min"] = (
    failures["Datetime"]
    .diff()
    .dt.total_seconds() / 60
)

MTBF = failures["Failure_Gap_Min"].mean()

# ===============================
# KPIs
# ===============================
col1, col2, col3 = st.columns(3)

col1.metric("🔧 Total Failures", len(failures))
col2.metric("⏱️ MTTR (min)", round(MTTR, 2))
col3.metric("📈 MTBF (min)", round(MTBF, 2))

# ===============================
# Failure Details
# ===============================
st.subheader("🧾 Failure Details")
st.dataframe(
    failures[["Datetime", "Event", "Repair_Time_Min", "Failure_Gap_Min"]],
    use_container_width=True
)

# ===============================
# Download Cleaned Data
# ===============================
st.subheader("⬇️ Download Data")

excel_data = df.to_excel(index=False, engine="openpyxl")

st.download_button(
    label="Download Excel",
    data=excel_data,
    file_name="organized_logbook.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
