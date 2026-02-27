import streamlit as st
import pandas as pd
import altair as alt
import re
import uuid
from difflib import SequenceMatcher

# =========================================================
# 1) CONFIG
# =========================================================
st.set_page_config(
    page_title="HealthOS Pro",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# 2) SESSION STATE
# =========================================================
if "patients" not in st.session_state:
    demo_id = "demo_001"
    st.session_state["patients"] = {
        demo_id: {
            "id": demo_id,
            "name": "Patient Demo",
            "sex": "M",
            "age": 47,
            "mrn": "",
            "height_cm": "",
            "weight_kg": "",
            "notes": "",
        }
    }
    st.session_state["active_patient"] = demo_id

if "active_patient" not in st.session_state:
    st.session_state["active_patient"] = list(st.session_state["patients"].keys())[0]

if "data" not in st.session_state:
    st.session_state["data"] = pd.DataFrame(columns=["PatientID", "Date", "Marker", "Value", "Unit"])

if "events" not in st.session_state:
    st.session_state["events"] = pd.DataFrame(columns=["PatientID", "Date", "Event", "Type", "Notes"])

if "ui" not in st.session_state:
    st.session_state["ui"] = {
        "nav": "Consult",
        "show_debug": False,
        "open_upload": False,
        "open_event": False,
        "open_patient": False,
        "open_add_patient": False,
    }

# =========================================================
# 3) PATIENT HELPERS
# =========================================================
def get_active_patient():
    pid = st.session_state["active_patient"]
    return st.session_state["patients"].get(pid, None)

def set_active_patient(pid: str):
    st.session_state["active_patient"] = pid

def add_patient(name, sex="M", age=0, mrn="", height_cm="", weight_kg="", notes=""):
    pid = f"pt_{uuid.uuid4().hex[:8]}"
    st.session_state["patients"][pid] = {
        "id": pid,
        "name": name,
        "sex": sex,
        "age": int(age),
        "mrn": mrn,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "notes": notes,
    }
    return pid

def update_patient(pid, **kwargs):
    if pid in st.session_state["patients"]:
        st.session_state["patients"][pid].update(kwargs)

def delete_patient(pid):
    if pid in st.session_state["patients"]:
        del st.session_state["patients"][pid]
        st.session_state["data"] = st.session_state["data"][
            st.session_state["data"]["PatientID"] != pid
        ].reset_index(drop=True)
        st.session_state["events"] = st.session_state["events"][
            st.session_state["events"]["PatientID"] != pid
        ].reset_index(drop=True)
        if st.session_state["patients"]:
            st.session_state["active_patient"] = list(st.session_state["patients"].keys())[0]

def get_patient_list():
    items = []
    for pid, p in st.session_state["patients"].items():
        label = p.get("name", "Unnamed")
        if p.get("age"):
            label += f" · {p.get('sex','')}, {p.get('age','')}"
        if p.get("mrn"):
            label += f" · MRN: {p.get('mrn','')}"
        items.append((pid, label))
    return sorted(items, key=lambda x: x[1])

def patient_summary_counts(patient_id):
    all_data = st.session_state["data"]
    all_events = st.session_state["events"]
    lab_count = len(all_data[all_data["PatientID"] == patient_id]) if not all_data.empty else 0
    event_count = len(all_events[all_events["PatientID"] == patient_id]) if not all_events.empty else 0
    return lab_count, event_count

# =========================================================
# 4) THEME (CLEAN + MICRO-POLISH FIXES)
# =========================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root{
  --bg: #F7F9FB;
  --card: #FFFFFF;
  --text: #0F172A;
  --muted: #64748B;
  --border: rgba(15,23,42,0.10);
  --shadow: 0 6px 24px rgba(15,23,42,0.06);
  --primary: #2563EB;

  --ok: #16A34A;
  --optimal: #2563EB;
  --warn: #F59E0B;
  --bad: #DC2626;

  --sidebar-bg: #FAFBFC;
  --sidebar-border: rgba(15,23,42,0.08);
  --sidebar-hover: rgba(37,99,235,0.05);
  --sidebar-active: rgba(37,99,235,0.10);
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

/* Cards */
.card{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
  padding: 14px;
  margin-bottom: 10px;
}
.section-title{
  margin: 8px 0 6px 0;
  font-size: 11px;
  font-weight: 800;
  color: var(--muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.small-muted{ font-size: 11px; color: var(--muted); }

/* Top bar */
.hos-topbar{
  display:flex; align-items:center; justify-content:space-between;
  padding: 10px 14px;
  background: rgba(255,255,255,0.96);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
  margin-bottom: 12px;
}
.brand{ display:flex; flex-direction:column; gap:2px; }
.brand h1{ margin:0; font-size: 18px; letter-spacing:-0.02em; color: var(--text); font-weight: 900; }
.brand .sub{ margin:0; font-size: 11px; color: var(--muted); }
.meta{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
.pill{
  display:inline-flex; align-items:center; gap:6px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: #FFFFFF;
  color: var(--text);
  font-size: 11px;
  font-weight: 700;
}
.pill strong{ font-weight: 900; }
.pill .dot{ width:7px; height:7px; border-radius:999px; background: var(--ok); }

/* KPI */
.kpi-grid{
  display:grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin: 8px 0 12px 0;
}
@media (max-width: 1100px){
  .kpi-grid{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.kpi{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: var(--shadow);
}
.kpi .label{
  font-size: 10px;
  color: var(--muted);
  margin-bottom: 4px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.kpi .val{ font-size: 26px; color: var(--text); font-weight: 950; letter-spacing: -0.03em; }
.kpi .hint{ font-size: 10px; color: var(--muted); margin-top: 2px; }

/* Rows */
.row{
  display:flex; justify-content:space-between; align-items:center;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: #FFFFFF;
}
.row + .row{ margin-top: 8px; }
.row-left{ display:flex; flex-direction:column; gap:3px; min-width: 0; }
.row-title{ font-size: 13px; font-weight: 900; color: var(--text); }
.row-sub{ font-size: 11px; color: var(--muted); display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.row-right{ text-align:right; display:flex; flex-direction:column; gap:3px; }
.row-val{ font-size: 14px; font-weight: 950; color: var(--text); }
.row-delta{ font-size: 11px; color: var(--muted); }

/* Chips */
.chip{
  display:inline-flex; align-items:center;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.chip.optimal{ color: var(--optimal); background: rgba(37,99,235,0.10); }
.chip.ok{ color: var(--ok); background: rgba(22,163,74,0.10); }
.chip.warn{ color: var(--warn); background: rgba(245,158,11,0.10); }
.chip.bad{ color: var(--bad); background: rgba(220,38,38,0.10); }

/* Buttons */
div.stButton > button{
  border-radius: 10px !important;
  border: 1px solid var(--border) !important;
  background: #FFFFFF !important;
  color: var(--text) !important;
  font-weight: 900 !important;
  font-size: 12px !important;
  padding: 0.45rem 0.75rem !important;
  line-height: 1.05 !important;
}
div.stButton > button:hover{
  border-color: rgba(37,99,235,0.30) !important;
  color: var(--primary) !important;
  background: rgba(37,99,235,0.03) !important;
}
button[kind="primary"]{
  background: var(--primary) !important;
  color: #FFFFFF !important;
  border: 1px solid rgba(37,99,235,0.30) !important;
}
button[kind="primary"]:hover{ filter: brightness(0.97); }

/* Inputs */
input, textarea {
  background: #FFFFFF !important;
  color: #0F172A !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 10px !important;
}

/* BaseWeb selects */
[data-baseweb="select"] > div {
  background: #FFFFFF !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 10px !important;
  box-shadow: 0 4px 16px rgba(15,23,42,0.04) !important;
  min-height: 40px !important;
  padding-top: 2px !important;
  padding-bottom: 2px !important;
}
[data-baseweb="select"] input { line-height: 1.2 !important; }
[data-baseweb="select"] * { color: #0F172A !important; font-weight: 800; }
[data-baseweb="select"] svg { color: #64748B !important; }

ul[role="listbox"]{
  background: #FFFFFF !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 10px !important;
  box-shadow: 0 12px 40px rgba(15,23,42,0.10) !important;
}
ul[role="listbox"] li{ color: #0F172A !important; padding-top: 8px !important; padding-bottom: 8px !important; }
ul[role="listbox"] li:hover{ background: rgba(37,99,235,0.05) !important; }

/* Multiselect chips (prevents puffy / overlap look) */
[data-baseweb="tag"]{
  border-radius: 8px !important;
  padding: 2px 6px !important;
  font-weight: 800 !important;
}
[data-baseweb="tag"] span { font-size: 11px !important; }
[data-baseweb="tag"] svg { width: 12px !important; height: 12px !important; }

/* Spacing normalization */
div[data-testid="stWidget"] { margin-bottom: 0.15rem !important; }
div[data-testid="stWidget"] > div { padding-bottom: 0 !important; }
[data-testid="stVerticalBlock"] { gap: 0.55rem; }
h1, h2, h3, h4 { margin-top: 0.35rem !important; margin-bottom: 0.35rem !important; }
hr { margin: 0.6rem 0 !important; }

/* Forms spacing */
div[data-testid="stForm"] { border: 0 !important; padding: 0 !important; }
div[data-testid="stForm"] > div { gap: 0.55rem !important; }

/* ===== SIDEBAR ===== */
[data-testid="stSidebar"] {
  background: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  width: 230px !important;
}
[data-testid="stSidebar"] > div:first-child { width: 230px !important; }
[data-testid="stSidebar"] .block-container { padding-top: 0.6rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.35rem; }

.sb-brand{
  padding: 10px 12px 8px 12px;
  border-bottom: 1px solid var(--sidebar-border);
  margin: -0.6rem -1rem 8px -1rem;
  padding-left: 1rem;
}
.sb-brand-name{ font-size: 14px; font-weight: 950; color: var(--text); letter-spacing: -0.02em; }
.sb-brand-tag{
  display:inline-block; font-size: 8px; font-weight: 950;
  padding: 2px 6px; border-radius: 4px;
  background: rgba(37,99,235,0.10); color: var(--primary);
  margin-left: 6px; vertical-align: middle;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.sb-brand-sub{ font-size: 10px; color: var(--muted); margin-top: 1px; }

.sb-section{
  font-size: 9px; font-weight: 900; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.08em;
  margin: 10px 0 4px 2px;
}

/* Sidebar nav radio */
[data-testid="stSidebar"] .stRadio div[role="radiogroup"]{ gap: 2px; }
[data-testid="stSidebar"] .stRadio label{
  padding: 7px 10px;
  border-radius: 8px;
  margin: 0;
  border: 1px solid transparent;
  background: transparent;
}
[data-testid="stSidebar"] .stRadio label:hover{ background: var(--sidebar-hover); }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label[data-checked="true"]{
  background: var(--sidebar-active);
  border-color: rgba(37,99,235,0.12);
}
[data-testid="stSidebar"] .stRadio p{
  color: #0F172A !important;
  font-weight: 900 !important;
  font-size: 12px !important;
}

/* Sidebar selectbox height match */
[data-testid="stSidebar"] [data-baseweb="select"] > div { min-height: 36px !important; }

/* File uploader */
[data-testid="stFileUploaderDropzone"]{
  background: #FFFFFF !important;
  border: 1px dashed rgba(15,23,42,0.18) !important;
  border-radius: 10px !important;
  padding: 12px !important;
  box-shadow: none !important;
}
[data-testid="stFileUploaderDropzone"] *{ color: #0F172A !important; }

/* Vega container cleanup */
.vega-embed{ padding: 0 !important; margin: 0 !important; border-radius: 10px !important; overflow: visible !important; }
.vega-embed details, .vega-embed summary { display: none !important; }
.vega-embed .vega-actions { display: none !important; }
[data-testid="stVegaLiteChart"] { padding: 0 !important; }

/* Patient roster item */
.patient-item{
  display:flex; justify-content:space-between; align-items:center;
  padding: 10px 12px; border-radius: 12px;
  border: 1px solid var(--border); background: #FFFFFF;
}
.patient-item.active{
  border-color: rgba(37,99,235,0.28);
  background: rgba(37,99,235,0.04);
}
.patient-name{ font-size: 13px; font-weight: 950; color: var(--text); }
.patient-meta{ font-size: 11px; color: var(--muted); }
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# 5) DATA LOGIC
# =========================================================
def clean_numeric_value(val):
    if pd.isna(val) or str(val).strip() == "":
        return None
    s = str(val).strip().replace(",", "").replace(" ", "")
    # strip common unit text
    s = s.replace("µ", "u")
    s = s.replace("ug/L", "").replace("ug/dL", "").replace("ng/mL", "").replace("mg/dL", "")
    s = s.replace("mIU/L", "").replace("uIU/mL", "").replace("nmol/L", "").replace("%", "")
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

def get_patient_data(patient_id):
    all_results = st.session_state["data"].copy()
    all_events = st.session_state["events"].copy()

    results = all_results[all_results["PatientID"] == patient_id].copy() if not all_results.empty else all_results
    events = all_events[all_events["PatientID"] == patient_id].copy() if not all_events.empty else all_events

    if not results.empty:
        results["Date"] = results["Date"].apply(parse_flexible_date)
        results["CleanMarker"] = results["Marker"].apply(clean_marker_name)
        results["NumericValue"] = results["Value"].apply(clean_numeric_value)
        results["Fingerprint"] = (
            results["Date"].astype(str) + "_" + results["CleanMarker"] + "_" + results["NumericValue"].astype(str)
        )
        results = results.drop_duplicates(subset=["Fingerprint"], keep="last")

    if not events.empty:
        events["Date"] = events["Date"].apply(parse_flexible_date)

    return results, events

def process_upload(uploaded_file, patient_id, show_debug=False):
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
        df_new["PatientID"] = patient_id
        st.session_state["data"] = pd.concat([st.session_state["data"], df_new], ignore_index=True)
        return "Success", len(df_new)

    except Exception as e:
        return f"Error: {str(e)}", 0

def add_clinical_event(patient_id, date, name, etype, note):
    new_event = pd.DataFrame([{
        "PatientID": patient_id,
        "Date": str(date),
        "Event": name,
        "Type": etype,
        "Notes": note,
    }])
    st.session_state["events"] = pd.concat([st.session_state["events"], new_event], ignore_index=True)

def delete_event(index):
    st.session_state["events"] = st.session_state["events"].drop(index).reset_index(drop=True)

def wipe_patient_data(patient_id):
    st.session_state["data"] = st.session_state["data"][
        st.session_state["data"]["PatientID"] != patient_id
    ].reset_index(drop=True)
    st.session_state["events"] = st.session_state["events"][
        st.session_state["events"]["PatientID"] != patient_id
    ].reset_index(drop=True)

# =========================================================
# 6) MASTER RANGES
# =========================================================
def get_master_data():
    data = [
        ["Biomarker", "Standard Range", "Optimal Min", "Optimal Max", "Unit", "Fuzzy Match Keywords"],
        # Hormones - Male
        ["Total Testosterone", "264-916", "600", "1000", "ng/dL", "TOTAL TESTOSTERONE, TOTAL T, TESTOSTERONE"],
        ["Free Testosterone", "8.7-25.1", "15", "25", "pg/mL", "FREE TESTOSTERONE, FREE T, F-TESTO"],
        ["SHBG", "10-57", "20", "45", "nmol/L", "SHBG, SEX HORMONE BINDING GLOBULIN"],
        ["Oestradiol", "7.6-42.6", "20", "35", "pg/mL", "E2, ESTRADIOL, 17-BETA, OESTRADIOL"],
        ["DHT", "30-85", "40", "70", "ng/dL", "DHT, DIHYDROTESTOSTERONE"],
        ["DHEA-S", "80-560", "200", "450", "ug/dL", "DHEA-S, DHEA SULFATE, DEHYDROEPIANDROSTERONE"],
        ["Prolactin", "4-15.2", "4", "12", "ng/mL", "PROLACTIN, PRL"],
        ["Progesterone (Male)", "0.2-1.4", "0.3", "1.0", "ng/mL", "PROGESTERONE"],
        ["LH", "1.7-8.6", "3", "7", "mIU/mL", "LH, LUTEINIZING HORMONE"],
        ["FSH", "1.5-12.4", "2", "8", "mIU/mL", "FSH, FOLLICLE STIMULATING HORMONE"],
        # Thyroid
        ["TSH", "0.4-4.0", "1.0", "2.5", "mIU/L", "TSH, THYROID STIMULATING HORMONE"],
        ["Free T4", "0.8-1.8", "1.0", "1.5", "ng/dL", "FT4, FREE T4, FREE THYROXINE, THYROXINE FREE"],
        ["Free T3", "2.3-4.2", "3.0", "4.0", "pg/mL", "FT3, FREE T3, FREE TRIIODOTHYRONINE"],
        ["Reverse T3", "9.2-24.1", "9.2", "18", "ng/dL", "RT3, REVERSE T3, REVERSE TRIIODOTHYRONINE"],
        ["Thyroid Antibodies (TPO)", "0-34", "0", "15", "IU/mL", "TPO, THYROID PEROXIDASE, ANTI-TPO"],
        # Metabolic / Lipids
        ["Total Cholesterol", "0-200", "120", "180", "mg/dL", "TOTAL CHOLESTEROL, CHOLESTEROL TOTAL"],
        ["LDL Cholesterol", "0-100", "0", "90", "mg/dL", "LDL, BAD CHOLESTEROL, LDL-C, LDL CHOLESTEROL"],
        ["HDL Cholesterol", "40-100", "50", "80", "mg/dL", "HDL, GOOD CHOLESTEROL, HDL-C, HDL CHOLESTEROL"],
        ["Triglycerides", "0-150", "0", "80", "mg/dL", "TRIGLYCERIDES, TG, TRIGS"],
        ["ApoB", "0-100", "0", "70", "mg/dL", "APOB, APOLIPOPROTEIN B"],
        ["Lp(a)", "0-30", "0", "14", "mg/dL", "LP(A), LIPOPROTEIN A, LPA"],
        ["HbA1c", "4.0-5.6", "4.0", "5.2", "%", "HBA1C, HEMOGLOBIN A1C, A1C, GLYCATED HEMOGLOBIN"],
        ["Fasting Glucose", "70-100", "72", "90", "mg/dL", "GLUCOSE, FASTING GLUCOSE, BLOOD SUGAR, FBG"],
        ["Fasting Insulin", "2.6-24.9", "2.6", "8", "uIU/mL", "INSULIN, FASTING INSULIN"],
        ["HOMA-IR", "0-2.5", "0", "1.5", "", "HOMA-IR, HOMA, INSULIN RESISTANCE"],
        # Liver
        ["ALT", "7-56", "10", "30", "U/L", "ALT, ALANINE AMINOTRANSFERASE, SGPT"],
        ["AST", "10-40", "10", "30", "U/L", "AST, ASPARTATE AMINOTRANSFERASE, SGOT"],
        ["GGT", "0-65", "10", "30", "U/L", "GGT, GAMMA-GLUTAMYL TRANSFERASE, GAMMA GT"],
        ["ALP", "44-147", "50", "100", "U/L", "ALP, ALKALINE PHOSPHATASE"],
        # Kidney
        ["Creatinine", "0.7-1.3", "0.8", "1.1", "mg/dL", "CREATININE, CREAT"],
        ["eGFR", "60-120", "90", "120", "mL/min", "EGFR, ESTIMATED GFR, GLOMERULAR FILTRATION RATE"],
        ["BUN", "6-20", "8", "16", "mg/dL", "BUN, BLOOD UREA NITROGEN, UREA"],
        ["Uric Acid", "3.0-7.0", "3.5", "5.5", "mg/dL", "URIC ACID, UA"],
        # Haematology
        ["Haematocrit", "38.3-48.6", "40", "50", "%", "HCT, HEMATOCRIT, HAEMATOCRIT, PCV"],
        ["Haemoglobin", "13.0-17.5", "14", "16.5", "g/dL", "HGB, HEMOGLOBIN, HAEMOGLOBIN, HB"],
        ["RBC", "4.5-5.5", "4.5", "5.2", "M/uL", "RBC, RED BLOOD CELLS, ERYTHROCYTES"],
        ["WBC", "4.5-11.0", "5", "8", "K/uL", "WBC, WHITE BLOOD CELLS, LEUKOCYTES"],
        ["Platelets", "150-400", "175", "300", "K/uL", "PLT, PLATELETS, PLATELET COUNT"],
        # Inflammation
        ["hs-CRP", "0-3.0", "0", "1.0", "mg/L", "CRP, HS-CRP, HIGH SENSITIVITY CRP, C-REACTIVE PROTEIN"],
        ["ESR", "0-22", "0", "10", "mm/hr", "ESR, SED RATE, ERYTHROCYTE SEDIMENTATION RATE"],
        ["Homocysteine", "0-15", "5", "10", "umol/L", "HOMOCYSTEINE, HCY"],
        # Iron / Minerals
        ["Ferritin", "30-400", "50", "150", "ug/L", "FERRITIN"],
        ["Iron", "60-170", "80", "140", "ug/dL", "IRON, SERUM IRON, FE"],
        ["TIBC", "250-370", "260", "350", "ug/dL", "TIBC, TOTAL IRON BINDING CAPACITY"],
        ["Transferrin Saturation", "20-50", "25", "40", "%", "TRANSFERRIN SAT, TSAT, IRON SATURATION"],
        ["Magnesium", "1.7-2.2", "2.0", "2.2", "mg/dL", "MAGNESIUM, MG"],
        ["Zinc", "60-130", "80", "120", "ug/dL", "ZINC, ZN"],
        # Vitamins
        ["Vitamin D", "30-100", "50", "80", "ng/mL", "VITAMIN D, 25-OH VITAMIN D, 25-HYDROXY, VIT D, 25(OH)D"],
        ["Vitamin B12", "200-900", "500", "800", "pg/mL", "VITAMIN B12, B12, COBALAMIN"],
        ["Folate", "2.7-17", "8", "15", "ng/mL", "FOLATE, FOLIC ACID, B9"],
        # Prostate
        ["PSA", "0-4.0", "0", "2.5", "ng/mL", "PSA, PROSTATE SPECIFIC ANTIGEN"],
    ]
    return pd.DataFrame(data[1:], columns=data[0])

# =========================================================
# 7) UTILS (STATUS LOGIC)
# =========================================================
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
        return None, None
    clean = str(range_str).replace("–", "-").replace(",", ".")
    parts = re.findall(r"[-+]?\d*\.\d+|\d+", clean)
    if len(parts) >= 2:
        return float(parts[0]), float(parts[1])
    return None, None

def get_status(val, master_row):
    """
    Mutually exclusive classification (checked in order):
    1) OUT OF RANGE (bad)  — outside standard reference range
    2) OPTIMAL (optimal)   — within optimal band
    3) BORDERLINE (warn)   — inside standard but outside optimal
    4) IN RANGE (ok)       — inside standard, no optimal defined
    """
    try:
        s_min, s_max = parse_range(master_row["Standard Range"])

        # parse optimal bounds as None if missing
        try:
            o_min_raw = master_row.get("Optimal Min", None)
            o_min = float(o_min_raw) if o_min_raw is not None and str(o_min_raw).strip() != "" else None
        except:
            o_min = None
        try:
            o_max_raw = master_row.get("Optimal Max", None)
            o_max = float(o_max_raw) if o_max_raw is not None and str(o_max_raw).strip() != "" else None
        except:
            o_max = None

        has_standard = s_min is not None and s_max is not None
        has_optimal = o_min is not None and o_max is not None

        if has_standard and (val < s_min or val > s_max):
            return "OUT OF RANGE", "bad", 1

        if has_optimal:
            if o_min <= val <= o_max:
                return "OPTIMAL", "optimal", 4
            return "BORDERLINE", "warn", 2

        return "IN RANGE", "ok", 3
    except Exception:
        return "UNKNOWN", "ok", 5

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

# =========================================================
# 8) CHART ENGINE (WITH LABEL/OVERLAP IMPROVEMENTS)
# =========================================================
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
    s_min = s_max = o_min = o_max = None

    if m_row is not None:
        s_min, s_max = parse_range(m_row["Standard Range"])
        unit_label = m_row["Unit"] if pd.notna(m_row["Unit"]) else "Value"
        try:
            o_min_raw = m_row.get("Optimal Min", None)
            o_min = float(o_min_raw) if o_min_raw is not None and str(o_min_raw).strip() != "" else None
        except:
            o_min = None
        try:
            o_max_raw = m_row.get("Optimal Max", None)
            o_max = float(o_max_raw) if o_max_raw is not None and str(o_max_raw).strip() != "" else None
        except:
            o_max = None

    d_max = df["NumericValue"].max()
    d_min = df["NumericValue"].min()
    highs = [d_max] + ([s_max] if s_max is not None else []) + ([o_max] if o_max is not None else [])
    y_top = max(highs) * 1.18 if max(highs) > 0 else 1
    y_bottom = min(0, d_min * 0.92)

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
            axis=alt.Axis(format="%d %b %y", labelColor="#64748B", tickColor="rgba(15,23,42,0.12)", grid=False),
        ),
        y=alt.Y(
            "NumericValue:Q",
            title=unit_label,
            scale=alt.Scale(domain=[y_bottom, y_top]),
            axis=alt.Axis(labelColor="#64748B", tickColor="rgba(15,23,42,0.12)", gridColor="rgba(15,23,42,0.06)"),
        ),
    )

    layers = []

    # Reference band (green)
    if s_min is not None and s_max is not None:
        layers.append(
            alt.Chart(pd.DataFrame({"y": [s_min], "y2": [s_max]}))
            .mark_rect(color="#16A34A", opacity=0.06)
            .encode(y="y", y2="y2")
        )

    # Optimal band (blue)
    if o_min is not None and o_max is not None:
        layers.append(
            alt.Chart(pd.DataFrame({"y": [o_min], "y2": [o_max]}))
            .mark_rect(color="#2563EB", opacity=0.06)
            .encode(y="y", y2="y2")
        )

    line = base.mark_line(color="#2563EB", strokeWidth=2.6, interpolate="monotone")

    color_scale = alt.Scale(
        domain=["bad", "warn", "optimal", "ok"],
        range=["#DC2626", "#F59E0B", "#2563EB", "#16A34A"],
    )

    points = base.mark_circle(size=72, fill="#FFFFFF", strokeWidth=2).encode(
        color=alt.Color("StatusKey:N", scale=color_scale, legend=None),
        stroke=alt.Color("StatusKey:N", scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip("Date:T", format="%d %b %Y"),
            alt.Tooltip("NumericValue:Q", title=marker),
            alt.Tooltip("StatusLabel:N", title="Status"),
        ],
    )

    layers.extend([line, points])

    # Intervention overlay (shorter labels + safer staggering)
    if not events.empty:
        ev = events.dropna(subset=["Date"]).copy()
        if not ev.empty:
            min_date, max_date = df["Date"].min(), df["Date"].max()
            date_span = max((max_date - min_date).days, 30)

            # more aggressive staggering to reduce overlaps
            staggered = calculate_stagger(ev, days_threshold=max(10, int(date_span * 0.18)))

            lane_height = (y_top - y_bottom) * 0.075
            staggered["y_text"] = y_top - (staggered["lane"] * lane_height) - ((y_top - y_bottom) * 0.05)

            s = staggered["Event"].astype(str)
            max_chars = 26
            staggered["EventShort"] = s.str.slice(0, max_chars) + s.apply(lambda x: "…" if len(x) > max_chars else "")

            ev_rule = alt.Chart(staggered).mark_rule(
                color="rgba(15,23,42,0.18)", strokeWidth=1, strokeDash=[4, 3]
            ).encode(
                x="Date:T",
                tooltip=[
                    alt.Tooltip("Date:T", format="%d %b %Y"),
                    alt.Tooltip("Event:N"),
                    alt.Tooltip("Type:N"),
                    alt.Tooltip("Notes:N"),
                ],
            )

            ev_txt = alt.Chart(staggered).mark_text(
                align="left",
                baseline="middle",
                dx=6,
                fontSize=10,
                fontWeight=700,
                color="#475569",
            ).encode(
                x="Date:T",
                y="y_text:Q",
                text="EventShort:N",
            )

            layers.extend([ev_rule, ev_txt])

    return (
        alt.layer(*layers)
        .properties(height=420, background="#FFFFFF")
        .configure_view(strokeWidth=0)
    )

# =========================================================
# 9) APP STATE + TOPBAR
# =========================================================
master = get_master_data()
patient = get_active_patient()
pid = st.session_state["active_patient"]
results, events = get_patient_data(pid)
ui = st.session_state["ui"]

last_date = last_lab_date(results)
last_date_str = last_date.strftime("%d %b %Y") if last_date is not None else "—"
patient_count = len(st.session_state["patients"])

st.markdown(
    f"""
<div class="hos-topbar">
  <div class="brand">
    <h1>HealthOS <span style="color: var(--muted); font-weight:900;">PRO</span></h1>
    <div class="sub">Doctor workflow · longitudinal labs + interventions</div>
  </div>
  <div class="meta">
    <span class="pill"><span class="dot"></span><strong>{patient.get('name','')}</strong> · {patient.get('sex','')}, {patient.get('age','')}</span>
    <span class="pill">Last lab: <strong>{last_date_str}</strong></span>
    <span class="pill">Patients: <strong>{patient_count}</strong></span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# =========================================================
# 10) SIDEBAR (ALL ACTIONS LIVE HERE — REMOVES TOP UNDERLINED BUTTONS)
# =========================================================
with st.sidebar:
    st.markdown(
        """
<div class="sb-brand">
  <div><span class="sb-brand-name">HealthOS</span><span class="sb-brand-tag">Pro</span></div>
  <div class="sb-brand-sub">Clinical dashboard</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Patient selector
    st.markdown('<div class="sb-section">Patient</div>', unsafe_allow_html=True)
    patient_list = get_patient_list()
    patient_ids = [p[0] for p in patient_list]
    patient_labels = [p[1] for p in patient_list]

    current_idx = patient_ids.index(pid) if pid in patient_ids else 0
    selected_label = st.selectbox("Patient", patient_labels, index=current_idx, label_visibility="collapsed")
    selected_pid = patient_ids[patient_labels.index(selected_label)]
    if selected_pid != pid:
        set_active_patient(selected_pid)
        # close any open panels on patient switch
        ui["open_upload"] = False
        ui["open_event"] = False
        ui["open_patient"] = False
        ui["open_add_patient"] = False
        st.rerun()

    if st.button("+ New patient", use_container_width=True):
        ui["open_add_patient"] = True
        ui["open_upload"] = False
        ui["open_event"] = False
        ui["open_patient"] = False

    # Navigation
    st.markdown('<div class="sb-section">Navigate</div>', unsafe_allow_html=True)
    nav_options = ["Consult", "Trends", "Interventions", "Patients"]
    nav = st.radio(
        "NAV",
        nav_options,
        index=nav_options.index(ui["nav"]) if ui["nav"] in nav_options else 0,
        label_visibility="collapsed",
    )
    ui["nav"] = nav

    # Actions (these replace the old top bar buttons)
    st.markdown('<div class="sb-section">Actions</div>', unsafe_allow_html=True)
    if st.button("Upload lab", use_container_width=True):
        ui["open_upload"] = True
        ui["open_event"] = False
        ui["open_patient"] = False
        ui["open_add_patient"] = False

    if st.button("Add intervention", use_container_width=True):
        ui["open_event"] = True
        ui["open_upload"] = False
        ui["open_patient"] = False
        ui["open_add_patient"] = False

    if st.button("Edit patient", use_container_width=True):
        ui["open_patient"] = True
        ui["open_upload"] = False
        ui["open_event"] = False
        ui["open_add_patient"] = False

    if st.button("Reset patient data", use_container_width=True):
        wipe_patient_data(pid)
        st.toast("Patient data reset.", icon="✅")
        st.rerun()

    st.markdown('<div class="sb-section">Developer</div>', unsafe_allow_html=True)
    ui["show_debug"] = st.toggle("Debug mode", value=ui["show_debug"])

# =========================================================
# 11) PANELS (DRAWER-LIKE)
# =========================================================
# --- Add New Patient ---
if ui["open_add_patient"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### New patient")
    st.markdown('<div class="small-muted">Add a new patient record (demo-friendly).</div>', unsafe_allow_html=True)

    with st.form("add_patient_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2.2, 1.0, 0.9, 1.3], gap="large")
        with c1:
            new_name = st.text_input("Patient name*", placeholder="e.g., John Smith")
        with c2:
            new_sex = st.selectbox("Sex", ["M", "F"])
        with c3:
            new_age = st.number_input("Age", min_value=0, max_value=120, value=30, step=1)
        with c4:
            new_mrn = st.text_input("MRN (optional)")

        c5, c6 = st.columns(2, gap="large")
        with c5:
            new_height = st.text_input("Height (cm)")
        with c6:
            new_weight = st.text_input("Weight (kg)")

        new_notes = st.text_area("Notes (optional)", height=70)

        left, right = st.columns([1, 5])
        with left:
            save = st.form_submit_button("Add", type="primary")
        with right:
            close = st.form_submit_button("Cancel")

        if save:
            if new_name.strip():
                new_pid = add_patient(
                    name=new_name.strip(),
                    sex=new_sex,
                    age=new_age,
                    mrn=new_mrn,
                    height_cm=new_height,
                    weight_kg=new_weight,
                    notes=new_notes,
                )
                set_active_patient(new_pid)
                st.toast(f"Added {new_name.strip()}.", icon="✅")
                ui["open_add_patient"] = False
                st.rerun()
            else:
                st.error("Name is required.")
        if close:
            ui["open_add_patient"] = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Edit Patient ---
if ui["open_patient"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### Edit patient — {patient.get('name', '')}")
    st.markdown('<div class="small-muted">Update details used across consult + trends.</div>', unsafe_allow_html=True)

    with st.form("patient_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([2.2, 1.0, 0.9, 1.3], gap="large")
        with c1:
            name = st.text_input("Name", value=patient.get("name", ""))
        with c2:
            sex = st.selectbox("Sex", ["M", "F"], index=0 if patient.get("sex", "M") == "M" else 1)
        with c3:
            age = st.number_input("Age", min_value=0, max_value=120, value=int(patient.get("age", 0) or 0), step=1)
        with c4:
            mrn = st.text_input("MRN", value=patient.get("mrn", ""))

        c5, c6 = st.columns(2, gap="large")
        with c5:
            height_cm = st.text_input("Height (cm)", value=str(patient.get("height_cm", "")))
        with c6:
            weight_kg = st.text_input("Weight (kg)", value=str(patient.get("weight_kg", "")))

        notes = st.text_area("Notes", value=patient.get("notes", ""), height=90)

        left, right = st.columns([1, 5])
        with left:
            save = st.form_submit_button("Save", type="primary")
        with right:
            close = st.form_submit_button("Close")

        if save:
            update_patient(
                pid,
                name=name,
                sex=sex,
                age=int(age),
                mrn=mrn,
                height_cm=height_cm,
                weight_kg=weight_kg,
                notes=notes,
            )
            st.toast("Saved.", icon="✅")
            ui["open_patient"] = False
            st.rerun()
        if close:
            ui["open_patient"] = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Upload ---
if ui["open_upload"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### Upload lab — {patient.get('name','')}")
    st.markdown('<div class="small-muted">CSV format (PDF/image pipeline later).</div>', unsafe_allow_html=True)

    up = st.file_uploader("Choose file", type=["csv"], key="lab_upload_main")
    cA, cB = st.columns([1, 6])
    with cA:
        go = st.button("Import", disabled=not bool(up), type="primary")
    with cB:
        cancel = st.button("Close", key="close_upload")

    if go and up:
        with st.spinner("Importing…"):
            msg, count = process_upload(up, pid, show_debug=ui["show_debug"])
        if msg == "Success":
            st.toast(f"Imported {count} rows.", icon="✅")
            ui["open_upload"] = False
            st.rerun()
        else:
            st.error(msg)

    if cancel:
        ui["open_upload"] = False
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Add Intervention ---
if ui["open_event"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### Add intervention — {patient.get('name','')}")

    with st.form("add_event_quick"):
        c1, c2, c3 = st.columns([1.1, 2.2, 1.2], gap="large")
        with c1:
            d = st.date_input("Date")
        with c2:
            n = st.text_input("Name", placeholder="e.g., Start statin / Stop alcohol")
        with c3:
            t = st.selectbox("Type", ["Medication", "Lifestyle", "Procedure", "Supplement"])

        note = st.text_input("Notes (optional)", placeholder="e.g., Dose, protocol, reason…")

        left, right = st.columns([1, 6])
        with left:
            add = st.form_submit_button("Add", type="primary")
        with right:
            close = st.form_submit_button("Close")

        if add:
            if str(n).strip() == "":
                st.error("Name is required.")
            else:
                add_clinical_event(pid, d, n, t, note)
                st.toast("Added.", icon="✅")
                ui["open_event"] = False
                st.rerun()

        if close:
            ui["open_event"] = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# 12) PAGE HELPERS
# =========================================================
def build_dashboard_rows(results, master, sel_date):
    subset = results[results["Date"] == sel_date].copy()
    rows = []
    counts = {"bad": 0, "warn": 0, "ok": 0, "optimal": 0}

    for _, r in subset.iterrows():
        m_row = fuzzy_match(r["Marker"], master)
        if m_row is None or pd.isna(r["NumericValue"]):
            continue

        status_label, status_key, prio = get_status(r["NumericValue"], m_row)
        counts[status_key] = counts.get(status_key, 0) + 1

        s_min, s_max = parse_range(m_row["Standard Range"])
        unit = m_row["Unit"] if pd.notna(m_row["Unit"]) else (r.get("Unit", "") or "")
        delta = calc_delta(r["CleanMarker"], results, sel_date)

        ref_str = ""
        if s_min is not None and s_max is not None:
            ref_str = f"{s_min:g}–{s_max:g} {unit}".strip()

        rows.append({
            "Marker": m_row["Biomarker"],
            "MarkerClean": r["CleanMarker"],
            "Value": r["NumericValue"],
            "Unit": unit,
            "StatusLabel": status_label,
            "StatusKey": status_key,
            "Prio": prio,
            "Ref": ref_str,
            "Delta": delta,
        })

    return rows, counts

def render_rows(title, rows):
    if not rows:
        st.markdown('<div class="card"><div class="small-muted">Nothing to show.</div></div>', unsafe_allow_html=True)
        return

    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)

    for r in sorted(rows, key=lambda x: (x["Prio"], x["Marker"])):
        delta_txt = ""
        if r["Delta"] is not None:
            arrow = "↑" if r["Delta"] > 0 else "↓"
            delta_txt = f"{arrow} {abs(r['Delta']):g} vs prev"

        ref_html = f"<span>Ref: {r['Ref']}</span>" if r["Ref"] else ""

        st.markdown(
            f"""
<div class="row">
  <div class="row-left">
    <div class="row-title">{r['Marker']}</div>
    <div class="row-sub">
      {status_chip(r['StatusKey'], r['StatusLabel'])}
      {ref_html}
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

    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# 13) PAGES
# =========================================================

# ===================
# CONSULT (SIMPLIFIED — REMOVES THE "CLUTTER" CONTROLS)
# ===================
if nav == "Consult":
    if results.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### No labs uploaded")
        st.markdown(
            f'<div class="small-muted">Use <strong>Upload lab</strong> in the sidebar to import labs for {patient.get("name","")}.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    dates = sorted(results["Date"].dropna().unique(), reverse=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    sel_date = st.selectbox("Report date", dates, format_func=lambda d: d.strftime("%d %b %Y"))
    st.markdown("</div>", unsafe_allow_html=True)

    rows, counts = build_dashboard_rows(results, master, sel_date)
    total = counts["bad"] + counts["warn"] + counts["ok"] + counts["optimal"]

    st.markdown(
        f"""
<div class="kpi-grid">
  <div class="kpi"><div class="label">Total tested</div><div class="val">{total}</div><div class="hint">Biomarkers matched</div></div>
  <div class="kpi"><div class="label">Out of range</div><div class="val" style="color:var(--bad)">{counts.get("bad",0)}</div><div class="hint">Outside reference</div></div>
  <div class="kpi"><div class="label">Borderline</div><div class="val" style="color:var(--warn)">{counts.get("warn",0)}</div><div class="hint">In range, not optimal</div></div>
  <div class="kpi"><div class="label">In range</div><div class="val" style="color:var(--ok)">{counts.get("ok",0)}</div><div class="hint">Standard reference</div></div>
  <div class="kpi"><div class="label">Optimal</div><div class="val" style="color:var(--optimal)">{counts.get("optimal",0)}</div><div class="hint">Doctor-defined optimal</div></div>
</div>
""",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="large")
    with left:
        render_rows("Attention required", [r for r in rows if r["StatusKey"] in ["bad", "warn"]])
    with right:
        render_rows("Stable / optimal", [r for r in rows if r["StatusKey"] in ["optimal", "ok"]])

# ===================
# TRENDS (CARDS HAVE TITLES + SUBTLE BORDER BY DESIGN)
# ===================
elif nav == "Trends":
    if results.empty:
        st.warning(f"No data for {patient.get('name','')}. Use Upload lab in the sidebar.")
        st.stop()

    markers = sorted(results["CleanMarker"].unique())
    defaults = markers[:7] if len(markers) > 7 else markers

    topA, topB = st.columns([3, 1.2], gap="large")
    with topA:
        sel = st.multiselect("Biomarkers", markers, default=defaults)
    with topB:
        layout = st.segmented_control("Layout", options=["Stacked", "2-column"], default="2-column")

    if not sel:
        st.info("Select at least one biomarker.")
        st.stop()

    def render_chart(marker_clean: str):
        m_row = fuzzy_match(marker_clean, master)
        display_name = m_row["Biomarker"] if m_row is not None else marker_clean

        subtitle = ""
        if m_row is not None:
            s_min, s_max = parse_range(m_row["Standard Range"])
            unit = m_row["Unit"] if pd.notna(m_row["Unit"]) else ""
            if s_min is not None and s_max is not None:
                subtitle = f"Reference: {s_min:g}–{s_max:g} {unit}".strip()

        st.markdown('<div class="card" style="padding:14px 14px 10px 14px;">', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:14px;font-weight:950;color:#0F172A;margin-bottom:2px;">{display_name}</div>',
            unsafe_allow_html=True,
        )
        if subtitle:
            st.markdown(f'<div class="small-muted" style="margin-bottom:6px;">{subtitle}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

        ch = plot_chart(marker_clean, results, events, master)
        if ch:
            st.altair_chart(ch, use_container_width=True)
        else:
            st.info(f"No numeric data for {marker_clean}")

        st.markdown("</div>", unsafe_allow_html=True)

    if layout == "Stacked":
        for m in sel:
            render_chart(m)
    else:
        for i in range(0, len(sel), 2):
            col1, col2 = st.columns(2, gap="large")
            with col1:
                render_chart(sel[i])
            with col2:
                if i + 1 < len(sel):
                    render_chart(sel[i + 1])

# ===================
# INTERVENTIONS
# ===================
elif nav == "Interventions":
    st.markdown(f"### Interventions — {patient.get('name','')}")
    st.markdown('<div class="small-muted">Appear on trend charts as vertical markers.</div>', unsafe_allow_html=True)

    if events.empty:
        st.markdown(
            f'<div class="card"><div class="small-muted">No interventions yet. Use <strong>Add intervention</strong> in the sidebar.</div></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    ev = events.dropna(subset=["Date"]).sort_values("Date", ascending=False)
    st.markdown('<div class="card">', unsafe_allow_html=True)

    for i, row in ev.iterrows():
        notes_txt = str(row.get("Notes", "") or "").strip()
        notes_html = f"<span style='color:var(--muted);'>— {notes_txt}</span>" if notes_txt else ""

        st.markdown(
            f"""
<div class="row">
  <div class="row-left">
    <div class="row-title">{row['Event']}</div>
    <div class="row-sub">
      <span class="chip ok">{row['Type']}</span>
      <span>{row['Date'].strftime('%d %b %Y')}</span>
      {notes_html}
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        colA, colB, colC = st.columns([7, 1.5, 1.0], gap="small")
        with colB:
            confirm = st.checkbox("Confirm", key=f"confirm_{i}")
        with colC:
            if st.button("Delete", key=f"del_{i}", disabled=not confirm):
                delete_event(i)
                st.toast("Deleted.", icon="🗑️")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ===================
# PATIENTS (CONTAINER-BASED — FIXES MISALIGNMENT/SPACING)
# ===================
elif nav == "Patients":
    st.markdown("### Patient roster")
    st.markdown('<div class="small-muted">Manage patients. Select to switch active patient.</div>', unsafe_allow_html=True)

    if st.button("+ Add new patient"):
        ui["open_add_patient"] = True
        st.rerun()

    plist = get_patient_list()
    if not plist:
        st.markdown('<div class="card"><div class="small-muted">No patients.</div></div>', unsafe_allow_html=True)
        st.stop()

    for p_id, _ in plist:
        p = st.session_state["patients"][p_id]
        lab_count, event_count = patient_summary_counts(p_id)
        is_active = (p_id == pid)

        with st.container():
            active_class = "active" if is_active else ""
            active_indicator = "● " if is_active else ""

            st.markdown(
                f"""
<div class="patient-item {active_class}">
  <div>
    <div class="patient-name">{active_indicator}{p.get('name','')}</div>
    <div class="patient-meta">{p.get('sex','')}, {p.get('age','')}{(' · MRN: ' + p.get('mrn','')) if p.get('mrn') else ''}</div>
  </div>
  <div style="text-align:right;">
    <div class="patient-meta">{lab_count} labs · {event_count} interventions</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns([1.2, 1.0, 1.0], gap="small")
            with c1:
                if not is_active:
                    if st.button("Select", key=f"sel_{p_id}", use_container_width=True):
                        set_active_patient(p_id)
                        ui["nav"] = "Consult"
                        ui["open_upload"] = False
                        ui["open_event"] = False
                        ui["open_patient"] = False
                        ui["open_add_patient"] = False
                        st.rerun()
                else:
                    st.markdown('<div class="small-muted" style="padding:6px 2px;">Active</div>', unsafe_allow_html=True)

            with c2:
                if st.button("Edit", key=f"edit_{p_id}", use_container_width=True):
                    set_active_patient(p_id)
                    ui["open_patient"] = True
                    st.rerun()

            with c3:
                if len(st.session_state["patients"]) > 1:
                    if st.button("Remove", key=f"delp_{p_id}", use_container_width=True):
                        delete_patient(p_id)
                        st.toast(f"Removed {p.get('name','')}.", icon="🗑️")
                        st.rerun()

            st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

# =========================================================
# 14) OPTIONAL DEBUG
# =========================================================
if ui["show_debug"]:
    st.markdown('<div class="section-title">Debug</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("Active patient:", pid)
    st.write("Patients:", list(st.session_state["patients"].keys()))
    st.write("Data rows:", len(st.session_state["data"]))
    st.write("Event rows:", len(st.session_state["events"]))
    st.markdown("</div>", unsafe_allow_html=True)
