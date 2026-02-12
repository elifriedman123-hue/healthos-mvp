import streamlit as st
import pandas as pd
import altair as alt
import re
from difflib import SequenceMatcher

# ---------------------------
# 1) CONFIG
# ---------------------------
st.set_page_config(
    page_title="HealthOS Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------
# 2) SESSION STATE (CLEAN + SINGLE SOURCE OF TRUTH)
# ---------------------------
if "data" not in st.session_state:
    st.session_state["data"] = pd.DataFrame(columns=["Date", "Marker", "Value", "Unit"])
if "events" not in st.session_state:
    st.session_state["events"] = pd.DataFrame(columns=["Date", "Event", "Type", "Notes"])
if "patient" not in st.session_state:
    st.session_state["patient"] = {
        "name": "Patient Demo",
        "sex": "M",
        "age": 47,
        "mrn": "",
        "height_cm": "",
        "weight_kg": "",
        "notes": ""
    }

# ---------------------------
# 3) APPLE-LIKE LIGHT CLINICAL THEME (CSS)
# ---------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root{
  --bg: #F7F9FB;
  --card: #FFFFFF;
  --text: #0F172A;
  --muted: #64748B;
  --border: rgba(15,23,42,0.10);
  --shadow: 0 8px 30px rgba(15,23,42,0.06);
  --primary: #2563EB;

  --ok: #16A34A;
  --optimal: #2563EB;
  --warn: #F59E0B;
  --bad: #DC2626;

  --chip-bg: rgba(15,23,42,0.04);
  --sidebar-bg: #FFFFFF;
  --sidebar-item: rgba(37,99,235,0.06);
  --sidebar-active: rgba(37,99,235,0.12);
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
[data-testid="stAppViewContainer"] { background: var(--bg); }
[data-testid="stHeader"] { display:none; }
#MainMenu, footer { visibility: hidden; }

.block-container {
    padding-top: 0.65rem;
    padding-bottom: 1.25rem;
    max-width: 100%;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* Cards / Sections */
.card{
  background: var(--card); border: 1px solid var(--border);
  border-radius: 16px; box-shadow: var(--shadow);
  padding: 14px;
}

.section-title{
  margin: 8px 0 8px 0; font-size: 13px; font-weight: 800;
  color: var(--text); letter-spacing: -0.01em;
}

.small-muted{ font-size: 11px; color: var(--muted); }

/* Top bar */
.hos-topbar{
  display:flex; align-items:center; justify-content:space-between;
  padding: 12px 14px; background: rgba(255,255,255,0.92);
  border: 1px solid var(--border); border-radius: 16px;
  box-shadow: var(--shadow); backdrop-filter: blur(10px);
  margin-bottom: 14px;
}
.brand{ display:flex; flex-direction:column; gap:2px; }
.brand h1{ margin:0; font-size: 20px; letter-spacing:-0.02em; color: var(--text); font-weight: 800; }
.brand .sub{ margin:0; font-size: 12px; color: var(--muted); }
.meta{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
.pill{
  display:inline-flex; align-items:center; gap:8px;
  padding: 8px 10px; border-radius: 999px;
  border: 1px solid var(--border); background: #FFFFFF;
  color: var(--text); font-size: 12px;
}
.pill strong{ font-weight: 800; }
.pill .dot{ width:8px; height:8px; border-radius:999px; background: var(--ok); }

/* KPI */
.kpi-grid{
  display:grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin: 10px 0 14px 0;
}
@media (max-width: 1100px){
  .kpi-grid{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.kpi{
  background: var(--card); border: 1px solid var(--border);
  border-radius: 16px; padding: 14px; box-shadow: var(--shadow);
}
.kpi .label{ font-size: 12px; color: var(--muted); margin-bottom: 6px; font-weight: 700; }
.kpi .val{ font-size: 28px; color: var(--text); font-weight: 900; letter-spacing: -0.03em; }
.kpi .hint{ font-size: 11px; color: var(--muted); margin-top: 2px; }

/* Rows */
.row{
  display:flex; justify-content:space-between; align-items:center;
  padding: 12px 12px; border-radius: 14px;
  border: 1px solid var(--border);
  background: #FFFFFF;
}
.row + .row{ margin-top: 8px; }
.row-left{ display:flex; flex-direction:column; gap:4px; }
.row-title{ font-size: 13px; font-weight: 800; color: var(--text); }
.row-sub{ font-size: 11px; color: var(--muted); display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.row-right{ text-align:right; display:flex; flex-direction:column; gap:4px; }
.row-val{ font-size: 14px; font-weight: 900; color: var(--text); }
.row-delta{ font-size: 11px; color: var(--muted); }

/* Chips */
.chip{
  display:inline-flex; align-items:center; padding: 4px 8px;
  border-radius: 999px; border: 1px solid var(--border);
  background: var(--chip-bg); font-size: 11px; font-weight: 800;
}
.chip.optimal{ color: var(--optimal); }
.chip.ok{ color: var(--ok); }
.chip.warn{ color: var(--warn); }
.chip.bad{ color: var(--bad); }

/* Buttons */
div.stButton > button{
  border-radius: 12px !important;
  border: 1px solid var(--border) !important;
  background: #FFFFFF !important;
  color: var(--text) !important;
  font-weight: 800 !important;
  padding: 0.6rem 0.9rem !important;
}
div.stButton > button:hover{
  border-color: rgba(37,99,235,0.35) !important;
  color: var(--primary) !important;
}

/* --- Inputs: force light theme (fix dark fields) --- */
input, textarea {
  background: #FFFFFF !important;
  color: #0F172A !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 14px !important;
}
[data-baseweb="select"] > div {
  background: #FFFFFF !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 14px !important;
  box-shadow: 0 8px 30px rgba(15,23,42,0.04) !important;
}
[data-baseweb="select"] * { color: #0F172A !important; font-weight: 700; }
[data-baseweb="select"] svg { color: #64748B !important; }
[data-baseweb="tag"]{
  background: rgba(37,99,235,0.10) !important;
  border: 1px solid rgba(37,99,235,0.16) !important;
  border-radius: 999px !important;
}
[data-baseweb="tag"] span{ color: #1D4ED8 !important; font-weight: 800 !important; }
ul[role="listbox"]{
  background: #FFFFFF !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 14px !important;
  box-shadow: 0 18px 60px rgba(15,23,42,0.12) !important;
}
ul[role="listbox"] li{ color: #0F172A !important; }
ul[role="listbox"] li:hover{ background: rgba(37,99,235,0.06) !important; }

/* Reduce vertical whitespace */
[data-testid="stVerticalBlock"] { gap: 0.55rem; }
h3 { margin-top: 0.55rem !important; margin-bottom: 0.35rem !important; }

/* --- Premium Sidebar --- */
[data-testid="stSidebar"] {
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  width: 255px !important;
}
[data-testid="stSidebar"] > div:first-child { width: 255px !important; }
[data-testid="stSidebar"] .block-container { padding-top: 0.9rem; }

.sidebar-brand{
  display:flex; flex-direction:column; gap:6px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow);
  background: rgba(255,255,255,0.92);
  margin-bottom: 12px;
}
.sidebar-brand .logo-line{
  display:flex; align-items:center; justify-content:space-between;
}
.sidebar-brand .logo{
  font-weight: 900; letter-spacing:-0.02em;
  color: var(--text); font-size: 16px;
}
.sidebar-brand .tag{
  font-size: 11px; font-weight: 800;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(15,23,42,0.03);
  color: var(--muted);
}
.sidebar-brand .mini{
  font-size: 11px; color: var(--muted);
  line-height: 1.2;
}

/* Sidebar radio -> iOS list */
[data-testid="stSidebar"] .stRadio div[role="radiogroup"]{
  gap: 6px;
}
[data-testid="stSidebar"] .stRadio label{
  padding: 10px 12px;
  border-radius: 14px;
  margin: 0;
  border: 1px solid transparent;
  background: transparent;
}
[data-testid="stSidebar"] .stRadio label:hover{
  background: var(--sidebar-item);
  border-color: rgba(37,99,235,0.10);
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label[data-checked="true"]{
  background: var(--sidebar-active);
  border-color: rgba(37,99,235,0.18);
}
[data-testid="stSidebar"] .stRadio p{
  color: #0F172A !important;
  font-weight: 900 !important;
  font-size: 13px !important;
}

.sidebar-section{
  font-size: 11px;
  font-weight: 900;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 10px 0 6px 6px;
}

/* Make sidebar toggles small + clean */
[data-testid="stSidebar"] [data-testid="stToggleSwitch"]{
  transform: scale(0.92);
  transform-origin: left center;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------
# 4) DATA LOGIC
# ---------------------------
def clean_numeric_value(val):
    if pd.isna(val) or str(val).strip() == "":
        return None
    s = str(val).strip().replace(",", "").replace(" ", "")
    s = s.replace("µ", "u").replace("ug/L", "").replace("ng/mL", "").replace("mg/dL", "")
    s = s.replace("<", "").replace(">", "")
    match = re.search(r"[-+]?\d*\.\d+|\d+", s)
    if match:
        try:
            return float(match.group())
        except:
            return None
    return None

def clean_marker_name(val):
    if pd.isna(val):
        return ""
    return re.sub(r"^[SPBU]-\s*", "", str(val).upper().strip())

def parse_flexible_date(date_str):
    if pd.isna(date_str) or str(date_str).strip() == "":
        return pd.NaT
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y.%m.%d"]
    for fmt in formats:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except:
            continue
    return pd.to_datetime(date_str, errors="coerce")

def get_data():
    results = st.session_state["data"].copy()
    events = st.session_state["events"].copy()

    if not results.empty:
        results["Date"] = results["Date"].apply(parse_flexible_date)
        results["CleanMarker"] = results["Marker"].apply(clean_marker_name)
        results["NumericValue"] = results["Value"].apply(clean_numeric_value)
        results["Fingerprint"] = (
            results["Date"].astype(str)
            + "_"
            + results["CleanMarker"]
            + "_"
            + results["NumericValue"].astype(str)
        )
        results = results.drop_duplicates(subset=["Fingerprint"], keep="last")

    if not events.empty:
        events["Date"] = events["Date"].apply(parse_flexible_date)

    return results, events

def process_upload(uploaded_file, show_debug=False):
    try:
        try:
            df_new = pd.read_csv(uploaded_file, sep=None, engine="python")
        except:
            uploaded_file.seek(0)
            df_new = pd.read_csv(uploaded_file, encoding="ISO-8859-1")

        if show_debug:
            with st.expander("Debug: raw upload preview", expanded=False):
                st.dataframe(df_new.head())

        df_new.columns = df_new.columns.str.strip().str.lower()
        rename_dict = {}
        for c in df_new.columns:
            if any(x in c for x in ["marker", "biomarker", "test", "name", "analyte"]):
                rename_dict[c] = "Marker"
            elif any(x in c for x in ["result", "reading", "value", "concentration"]):
                rename_dict[c] = "Value"
            elif any(x in c for x in ["time", "collected", "date"]):
                rename_dict[c] = "Date"
            elif "unit" in c:
                rename_dict[c] = "Unit"

        df_new = df_new.rename(columns=rename_dict)
        needed = ["Date", "Marker", "Value"]
        missing = [x for x in needed if x not in df_new.columns]
        if missing:
            return f"Missing columns: {missing}. Found: {df_new.columns.tolist()}", 0

        if "Unit" not in df_new.columns:
            df_new["Unit"] = ""

        df_new = df_new[needed + ["Unit"]]
        st.session_state["data"] = pd.concat([st.session_state["data"], df_new], ignore_index=True)
        return "Success", len(df_new)

    except Exception as e:
        return f"Error: {str(e)}", 0

def add_clinical_event(date, name, type, note):
    new_event = pd.DataFrame([{"Date": str(date), "Event": name, "Type": type, "Notes": note}])
    st.session_state["events"] = pd.concat([st.session_state["events"], new_event], ignore_index=True)

def delete_event(index):
    st.session_state["events"] = st.session_state["events"].drop(index).reset_index(drop=True)

def wipe_db():
    st.session_state["data"] = pd.DataFrame(columns=["Date", "Marker", "Value", "Unit"])
    st.session_state["events"] = pd.DataFrame(columns=["Date", "Event", "Type", "Notes"])

# ---------------------------
# 5) MASTER RANGES (DEMO)
# ---------------------------
def get_master_data():
    data = [
        ["Biomarker", "Standard Range", "Optimal Min", "Optimal Max", "Unit", "Fuzzy Match Keywords"],
        ["Total Testosterone", "264-916", "600", "1000", "ng/dL", "TOTAL TESTOSTERONE, TOTAL T, TESTOSTERONE"],
        ["Free Testosterone", "8.7-25.1", "15", "25", "pg/mL", "FREE TESTOSTERONE, FREE T, F-TESTO"],
        ["Haematocrit", "38.3-48.6", "40", "50", "%", "HCT, HEMATOCRIT, PCV"],
        ["Oestradiol", "7.6-42.6", "20", "35", "pg/mL", "E2, ESTRADIOL, 17-BETA"],
        ["PSA", "0-4.0", "0", "2.5", "ng/mL", "PROSTATE SPECIFIC ANTIGEN"],
        ["LDL Cholesterol", "0-100", "0", "90", "mg/dL", "LDL, BAD CHOLESTEROL"],
        ["Ferritin", "30-400", "50", "150", "ug/L", "FERRITIN"],
    ]
    return pd.DataFrame(data[1:], columns=data[0])

# ---------------------------
# 6) UTILS
# ---------------------------
def fuzzy_match(marker, master):
    lab_clean = clean_marker_name(marker)

    for _, row in master.iterrows():
        keywords = [clean_marker_name(k) for k in str(row["Fuzzy Match Keywords"]).split(",")]
        if lab_clean in keywords:
            return row

    best_score = 0
    best_row = None
    for _, row in master.iterrows():
        keywords = [clean_marker_name(k) for k in str(row["Fuzzy Match Keywords"]).split(",")]
        for key in keywords:
            score = SequenceMatcher(None, lab_clean, key).ratio()
            if score > best_score:
                best_score = score
                best_row = row

    return best_row if best_score > 0.85 else None

def parse_range(range_str):
    if pd.isna(range_str):
        return 0, 0
    clean = str(range_str).replace("–", "-").replace(",", ".")
    parts = re.findall(r"[-+]?\d*\.\d+|\d+", clean)
    if len(parts) >= 2:
        return float(parts[0]), float(parts[1])
    return 0, 0

def get_status(val, master_row):
    try:
        s_min, s_max = parse_range(master_row["Standard Range"])
        try:
            o_min = float(master_row.get("Optimal Min", 0) or 0)
            o_max = float(master_row.get("Optimal Max", 0) or 0)
        except:
            o_min, o_max = 0, 0

        if "PSA" in str(master_row["Biomarker"]).upper() and val > 4:
            return "OUT OF RANGE", "bad", 1

        if s_min > 0 and (val < s_min or val > s_max):
            return "OUT OF RANGE", "bad", 1

        if (o_min > 0 and val < o_min) or (o_max > 0 and val > o_max):
            return "BORDERLINE", "warn", 2

        if (o_min > 0 or o_max > 0):
            return "OPTIMAL", "optimal", 3

        return "IN RANGE", "ok", 4

    except:
        return "ERROR", "warn", 5

def status_chip(status_key: str, label: str) -> str:
    return f'<span class="chip {status_key}">{label}</span>'

def last_lab_date(results_df):
    if results_df.empty or results_df["Date"].dropna().empty:
        return None
    return results_df["Date"].dropna().max()

def calc_delta(marker_clean, results, current_date):
    df = results[(results["CleanMarker"] == marker_clean) & results["Date"].notna()].copy()
    df = df.sort_values("Date")

    cur = df[df["Date"] == current_date]
    if cur.empty:
        return None

    prev_df = df[df["Date"] < current_date]
    if prev_df.empty:
        return None

    prev_val = prev_df.iloc[-1]["NumericValue"]
    cur_val = cur.iloc[-1]["NumericValue"]

    if pd.isna(prev_val) or pd.isna(cur_val):
        return None
    return cur_val - prev_val

# ---------------------------
# 7) CHART ENGINE
# ---------------------------
def calculate_stagger(events_df, days_threshold=20):
    if events_df.empty:
        return events_df
    events_df = events_df.sort_values("Date").copy()
    events_df["lane"] = 0
    lane_end_dates = {}
    safe_min = pd.Timestamp("1900-01-01")
    for idx, row in events_df.iterrows():
        current_date = row["Date"]
        assigned = False
        lane = 0
        while not assigned:
            last_date = lane_end_dates.get(lane, safe_min)
            if (current_date - last_date).days > days_threshold:
                events_df.at[idx, "lane"] = lane
                lane_end_dates[lane] = current_date
                assigned = True
            else:
                lane += 1
    return events_df

def plot_chart(marker, results, events, master):
    df = results[results["CleanMarker"] == clean_marker_name(marker)].copy()
    df = df.dropna(subset=["NumericValue", "Date"]).sort_values("Date")
    if df.empty:
        return None

    m_row = fuzzy_match(marker, master)
    unit_label = "Value"
    s_min = s_max = o_min = o_max = 0

    if m_row is not None:
        s_min, s_max = parse_range(m_row["Standard Range"])
        unit_label = m_row["Unit"] if pd.notna(m_row["Unit"]) else "Value"
        try:
            o_min = float(m_row.get("Optimal Min", 0) or 0)
            o_max = float(m_row.get("Optimal Max", 0) or 0)
        except:
            o_min, o_max = 0, 0

    d_max = df["NumericValue"].max()
    d_min = df["NumericValue"].min()
    y_top = max(d_max, s_max, o_max) * 1.20 if max(d_max, s_max, o_max) > 0 else 1
    y_bottom = min(0, d_min * 0.9)

    def status_for_value(v):
        if m_row is None:
            return ("IN RANGE", "ok")
        status_label, status_key, _ = get_status(v, m_row)
        return (status_label, status_key)

    df[["StatusLabel", "StatusKey"]] = df["NumericValue"].apply(lambda v: pd.Series(status_for_value(v)))

    base = alt.Chart(df).encode(
        x=alt.X(
            "Date:T",
            title=None,
            axis=alt.Axis(format="%d %b %y", labelColor="#64748B", tickColor="rgba(15,23,42,0.15)", grid=False),
        ),
        y=alt.Y(
            "NumericValue:Q",
            title=unit_label,
            scale=alt.Scale(domain=[y_bottom, y_top]),
            axis=alt.Axis(labelColor="#64748B", tickColor="rgba(15,23,42,0.15)", gridColor="rgba(15,23,42,0.08)"),
        ),
    )

    ref_band = None
    if s_max > 0:
        ref_band = alt.Chart(pd.DataFrame({"y": [s_min], "y2": [s_max]})).mark_rect(
            color="#16A34A", opacity=0.06
        ).encode(y="y", y2="y2")

    opt_band = None
    if o_max > 0:
        opt_band = alt.Chart(pd.DataFrame({"y": [o_min], "y2": [o_max]})).mark_rect(
            color="#2563EB", opacity=0.06
        ).encode(y="y", y2="y2")

    line = base.mark_line(color="#2563EB", strokeWidth=3, interpolate="monotone")

    color_scale = alt.Scale(
        domain=["bad", "warn", "optimal", "ok"],
        range=["#DC2626", "#F59E0B", "#2563EB", "#16A34A"],
    )

    points = base.mark_circle(size=80, fill="#FFFFFF", strokeWidth=2).encode(
        color=alt.Color("StatusKey:N", scale=color_scale, legend=None),
        stroke=alt.Color("StatusKey:N", scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip("Date:T", format="%d %b %Y"),
            alt.Tooltip("NumericValue:Q", title=marker),
            alt.Tooltip("StatusLabel:N", title="Status"),
        ],
    )

    layers = []
    if ref_band:
        layers.append(ref_band)
    if opt_band:
        layers.append(opt_band)
    layers.extend([line, points])

    if not events.empty:
        ev = events.dropna(subset=["Date"]).copy()
        if not ev.empty:
            min_date, max_date = df["Date"].min(), df["Date"].max()
            date_span = max((max_date - min_date).days, 30)
            staggered = calculate_stagger(ev, days_threshold=int(date_span * 0.12))

            lane_height = (y_top - y_bottom) * 0.08
            staggered["y_text"] = y_top - (staggered["lane"] * lane_height) - ((y_top - y_bottom) * 0.06)

            s = staggered["Event"].astype(str)
            staggered["EventShort"] = s.str.slice(0, 34) + s.apply(lambda x: "…" if len(x) > 34 else "")

            ev_rule = alt.Chart(staggered).mark_rule(
                color="rgba(15,23,42,0.22)", strokeWidth=1
            ).encode(
                x="Date:T",
                tooltip=[
                    alt.Tooltip("Date:T", format="%d %b %Y"),
                    alt.Tooltip("Event:N"),
                    alt.Tooltip("Type:N"),
                ],
            )

            ev_txt = alt.Chart(staggered).mark_text(
                align="left",
                baseline="middle",
                dx=6,
                fontSize=11,
                fontWeight=600,
                color="#0F172A",
            ).encode(
                x="Date:T",
                y="y_text:Q",
                text="EventShort:N",
            )

            layers.extend([ev_rule, ev_txt])

    return alt.layer(*layers).properties(height=480, background="#FFFFFF").configure_view(strokeWidth=0)

# ---------------------------
# 8) UI SHELL (SINGLE TOP BAR)
# ---------------------------
master = get_master_data()
results, events = get_data()
patient = st.session_state["patient"]

last_date = last_lab_date(results)
last_date_str = last_date.strftime("%d %b %Y") if last_date is not None else "—"

st.markdown(
    f"""
<div class="hos-topbar">
  <div class="brand">
    <h1>HealthOS <span style="color: var(--muted); font-weight:800;">PRO</span></h1>
    <div class="sub">Clinical Intelligence Platform</div>
  </div>
  <div class="meta">
    <span class="pill"><span class="dot"></span><strong>{patient.get('name','Patient')}</strong> • {patient.get('sex','')}, {patient.get('age','')}</span>
    <span class="pill">Last Lab: <strong>{last_date_str}</strong></span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------
# 9) PREMIUM SIDEBAR
# ---------------------------
with st.sidebar:
    st.markdown(
        """
<div class="sidebar-brand">
  <div class="logo-line">
    <div class="logo">HealthOS</div>
    <div class="tag">PRO</div>
  </div>
  <div class="mini">Doctor demo build • clean clinical UI</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-section">Workspace</div>', unsafe_allow_html=True)
    nav = st.radio(
        "NAV",
        ["👤 Patient", "📊 Dashboard", "📈 Trends", "💊 Interventions", "⬆️ Import"],
        label_visibility="collapsed",
    )

    st.markdown('<div class="sidebar-section">Demo</div>', unsafe_allow_html=True)
    show_debug = st.toggle("Show debug tools", value=False)
    st.markdown('<div class="small-muted">Tip: keep debug off during doctor demos.</div>', unsafe_allow_html=True)

# ---------------------------
# 10) PAGES
# ---------------------------
if nav == "👤 Patient":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Patient intake (doctor demo)")
    st.markdown('<div class="small-muted">Enter patient details, then upload labs. This becomes the “live patient test” flow.</div>', unsafe_allow_html=True)

    with st.form("patient_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([2.2, 1.0, 0.9, 1.3], gap="large")
        with c1:
            name = st.text_input("Patient name", value=patient.get("name", ""))
        with c2:
            sex = st.selectbox("Sex", ["M", "F"], index=0 if patient.get("sex", "M") == "M" else 1)
        with c3:
            age = st.number_input("Age", min_value=0, max_value=120, value=int(patient.get("age", 0) or 0), step=1)
        with c4:
            mrn = st.text_input("MRN (optional)", value=patient.get("mrn", ""))

        c5, c6 = st.columns(2, gap="large")
        with c5:
            height_cm = st.text_input("Height (cm)", value=str(patient.get("height_cm", "")))
        with c6:
            weight_kg = st.text_input("Weight (kg)", value=str(patient.get("weight_kg", "")))

        notes = st.text_area("Optional clinical notes for context…", value=patient.get("notes", ""), height=110)

        save = st.form_submit_button("Save patient")
        if save:
            st.session_state["patient"] = {
                "name": name,
                "sex": sex,
                "age": int(age),
                "mrn": mrn,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "notes": notes,
            }
            st.success("Saved.")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Upload labs (the demo)")
    st.markdown('<div class="small-muted">For now: CSV upload. Later: PDF/image upload + AI extraction.</div>', unsafe_allow_html=True)

    up = st.file_uploader("Upload CSV", type=["csv"], key="patient_csv")
    if up and st.button("Process upload"):
        msg, count = process_upload(up, show_debug=show_debug)
        if msg == "Success":
            st.success(f"Imported {count} rows.")
            st.rerun()
        else:
            st.error(msg)

    if show_debug:
        st.markdown("---")
        if st.button("Wipe session (demo reset)"):
            wipe_db()
            st.warning("Wiped.")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

elif nav == "📊 Dashboard":
    if results.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### Upload your first lab to begin")
        st.markdown("This dashboard normalizes results across labs and highlights what needs attention.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    dates = sorted(results["Date"].dropna().unique(), reverse=True)
    sel_date = st.selectbox("Report date", dates, format_func=lambda d: d.strftime("%d %b %Y"))
    subset = results[results["Date"] == sel_date].copy()

    rows = []
    counts = {"bad": 0, "warn": 0, "optimal": 0, "ok": 0}

    for _, r in subset.iterrows():
        m_row = fuzzy_match(r["Marker"], master)
        if m_row is None or pd.isna(r["NumericValue"]):
            continue

        status_label, status_key, prio = get_status(r["NumericValue"], m_row)
        counts[status_key] = counts.get(status_key, 0) + 1

        s_min, s_max = parse_range(m_row["Standard Range"])
        unit = m_row["Unit"] if pd.notna(m_row["Unit"]) else (r.get("Unit", "") or "")
        delta = calc_delta(r["CleanMarker"], results, sel_date)

        rows.append(
            {
                "Marker": m_row["Biomarker"],
                "MarkerClean": r["CleanMarker"],
                "Value": r["NumericValue"],
                "Unit": unit,
                "StatusLabel": status_label,
                "StatusKey": status_key,
                "Prio": prio,
                "Ref": f"{s_min:g}–{s_max:g} {unit}".strip(),
                "Delta": delta,
            }
        )

    st.markdown(
        f"""
<div class="kpi-grid">
  <div class="kpi"><div class="label">Total tested</div><div class="val">{len(rows)}</div><div class="hint">Biomarkers detected</div></div>
  <div class="kpi"><div class="label">Optimal</div><div class="val" style="color:var(--optimal)">{counts.get("optimal",0)}</div><div class="hint">Within optimal band</div></div>
  <div class="kpi"><div class="label">In range</div><div class="val" style="color:var(--ok)">{counts.get("ok",0)}</div><div class="hint">Within reference</div></div>
  <div class="kpi"><div class="label">Borderline</div><div class="val" style="color:var(--warn)">{counts.get("warn",0)}</div><div class="hint">Watch & adjust</div></div>
  <div class="kpi"><div class="label">Needs attention</div><div class="val" style="color:var(--bad)">{counts.get("bad",0)}</div><div class="hint">Out of range</div></div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2, gap="large")

    def render_rows(title, filter_fn):
        st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)

        shown = 0
        for r in sorted(rows, key=lambda x: x["Prio"]):
            if not filter_fn(r):
                continue
            shown += 1

            delta_txt = ""
            if r["Delta"] is not None:
                arrow = "↑" if r["Delta"] > 0 else "↓"
                delta_txt = f"{arrow} {abs(r['Delta']):g} vs previous"

            st.markdown(
                f"""
<div class="row">
  <div class="row-left">
    <div class="row-title">{r['Marker']}</div>
    <div class="row-sub">
      {status_chip(r['StatusKey'], r['StatusLabel'])}
      <span>Ref: {r['Ref']}</span>
    </div>
  </div>
  <div class="row-right">
    <div class="row-val">{r['Value']:g} {r['Unit']}</div>
    <div class="row-delta">{delta_txt}</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

        if shown == 0:
            st.markdown('<div class="small-muted">Nothing in this section for this report date.</div>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with c1:
        render_rows("Attention required", lambda r: r["StatusKey"] in ["bad", "warn"])
    with c2:
        render_rows("Stable / optimized", lambda r: r["StatusKey"] in ["optimal", "ok"])

elif nav == "📈 Trends":
    if results.empty:
        st.warning("No data loaded yet. Upload a CSV in Patient (or Import).")
        st.stop()

    markers = sorted(results["CleanMarker"].unique())
    defaults = [m for m in ["TOTAL TESTOSTERONE", "FREE TESTOSTERONE", "OESTRADIOL", "HAEMATOCRIT", "PSA", "FERRITIN", "LDL CHOLESTEROL"] if m in markers]

    topA, topB, topC = st.columns([2.2, 1.2, 1.6], gap="large")
    with topA:
        sel = st.multiselect("Select biomarkers", markers, default=defaults)
    with topB:
        layout = st.segmented_control("Layout", options=["Stacked", "2-column"], default="2-column")
    with topC:
        compare_mode = st.toggle("Compare pair", value=True)

    if not sel:
        st.info("Select at least one biomarker.")
        st.stop()

    pair = []
    if compare_mode:
        c1, c2 = st.columns(2, gap="large")
        with c1:
            p1 = st.selectbox("Compare: left", sel, index=0 if sel else 0)
        with c2:
            p2 = st.selectbox("Compare: right", sel, index=1 if len(sel) > 1 else 0)
        if p1 and p2 and p1 != p2:
            pair = [p1, p2]

    def render_chart(marker_clean: str):
        st.markdown(f"### {marker_clean}")
        ch = plot_chart(marker_clean, results, events, master)
        if ch:
            st.altair_chart(ch, use_container_width=True)
        else:
            st.info(f"No numeric data for {marker_clean}")

    if layout == "Stacked":
        already = set()
        if pair:
            for m in pair:
                render_chart(m)
                already.add(m)
        for m in sel:
            if m not in already:
                render_chart(m)
    else:
        used = set()
        if pair:
            colL, colR = st.columns(2, gap="large")
            with colL:
                render_chart(pair[0])
            with colR:
                render_chart(pair[1])
            used.update(pair)

        remaining = [m for m in sel if m not in used]
        for i in range(0, len(remaining), 2):
            col1, col2 = st.columns(2, gap="large")
            with col1:
                render_chart(remaining[i])
            with col2:
                if i + 1 < len(remaining):
                    render_chart(remaining[i + 1])

elif nav == "💊 Interventions":
    st.markdown("### Interventions timeline")
    st.markdown('<div class="small-muted">Medication / lifestyle / procedure events appear as markers on trend charts.</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    with st.form("add_event"):
        c1, c2, c3 = st.columns([1, 2, 1], gap="large")
        with c1:
            d = st.date_input("Date")
        with c2:
            n = st.text_input("Event name", placeholder="e.g., Start TRT 200mg/wk")
        with c3:
            t = st.selectbox("Type", ["Medication", "Lifestyle", "Procedure"])
        if st.form_submit_button("Add event"):
            add_clinical_event(d, n, t, "")
            st.success("Added")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    if events.empty:
        st.markdown('<div class="card"><div class="small-muted">No interventions yet.</div></div>', unsafe_allow_html=True)
    else:
        ev = events.dropna(subset=["Date"]).sort_values("Date")
        st.markdown('<div class="card">', unsafe_allow_html=True)

        for i, row in ev.iterrows():
            st.markdown(
                f"""
<div class="row">
  <div class="row-left">
    <div class="row-title">{row['Event']}</div>
    <div class="row-sub">
      <span class="chip ok">{row['Type']}</span>
      <span>{row['Date'].strftime('%d %b %Y')}</span>
    </div>
  </div>
  <div class="row-right">
    <div class="row-delta"></div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
            colA, colB = st.columns([8, 1])
            with colB:
                if st.button("Delete", key=f"del_{i}"):
                    delete_event(i)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

elif nav == "⬆️ Import":
    st.markdown("### Import (utility)")
    st.markdown('<div class="small-muted">Raw CSV uploader. For doctor demos, use the Patient tab.</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    up = st.file_uploader("Upload CSV", type=["csv"], key="import_csv")

    if up and st.button("Process upload", key="import_btn"):
        msg, count = process_upload(up, show_debug=show_debug)
        if msg == "Success":
            st.success(f"Imported {count} rows.")
            st.rerun()
        else:
            st.error(msg)

    if show_debug:
        st.markdown("---")
        if st.button("Wipe session (debug)"):
            wipe_db()
            st.warning("Wiped.")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
