import streamlit as st
import pandas as pd
import altair as alt
import re
import uuid
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
# 2) SESSION STATE (SINGLE SOURCE OF TRUTH)
# ---------------------------
# Patients registry: dict of patient_id -> patient info
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

# Lab data: now includes patient_id column
if "data" not in st.session_state:
    st.session_state["data"] = pd.DataFrame(columns=["PatientID", "Date", "Marker", "Value", "Unit"])

# Events/interventions: now includes patient_id column
if "events" not in st.session_state:
    st.session_state["events"] = pd.DataFrame(columns=["PatientID", "Date", "Event", "Type", "Notes"])

if "ui" not in st.session_state:
    st.session_state["ui"] = {
        "nav": "🩺 Consult",
        "show_debug": False,
        "open_upload": False,
        "open_event": False,
        "open_patient": False,
        "open_add_patient": False,
    }

# ---------------------------
# 3) PATIENT HELPERS
# ---------------------------
def get_active_patient():
    pid = st.session_state["active_patient"]
    return st.session_state["patients"].get(pid, None)

def set_active_patient(pid):
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
        # Remove associated data
        st.session_state["data"] = st.session_state["data"][
            st.session_state["data"]["PatientID"] != pid
        ].reset_index(drop=True)
        st.session_state["events"] = st.session_state["events"][
            st.session_state["events"]["PatientID"] != pid
        ].reset_index(drop=True)
        # Switch to another patient if available
        if st.session_state["patients"]:
            st.session_state["active_patient"] = list(st.session_state["patients"].keys())[0]

def get_patient_list():
    """Returns list of (id, display_name) sorted by name."""
    items = []
    for pid, p in st.session_state["patients"].items():
        label = p["name"]
        if p.get("age"):
            label += f" • {p['sex']}, {p['age']}"
        if p.get("mrn"):
            label += f" • MRN: {p['mrn']}"
        items.append((pid, label))
    return sorted(items, key=lambda x: x[1])


# ---------------------------
# 4) THEME (CSS)
# ---------------------------
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
  margin: 8px 0 6px 0; font-size: 13px; font-weight: 900;
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
.brand h1{ margin:0; font-size: 20px; letter-spacing:-0.02em; color: var(--text); font-weight: 900; }
.brand .sub{ margin:0; font-size: 12px; color: var(--muted); }
.meta{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
.pill{
  display:inline-flex; align-items:center; gap:8px;
  padding: 8px 10px; border-radius: 999px;
  border: 1px solid var(--border); background: #FFFFFF;
  color: var(--text); font-size: 12px;
}
.pill strong{ font-weight: 900; }
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
.kpi .label{ font-size: 12px; color: var(--muted); margin-bottom: 6px; font-weight: 800; }
.kpi .val{ font-size: 28px; color: var(--text); font-weight: 950; letter-spacing: -0.03em; }
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
.row-title{ font-size: 13px; font-weight: 900; color: var(--text); }
.row-sub{ font-size: 11px; color: var(--muted); display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.row-right{ text-align:right; display:flex; flex-direction:column; gap:4px; }
.row-val{ font-size: 14px; font-weight: 950; color: var(--text); }
.row-delta{ font-size: 11px; color: var(--muted); }

/* Patient list items */
.patient-item{
  display:flex; justify-content:space-between; align-items:center;
  padding: 10px 12px; border-radius: 14px;
  border: 1px solid var(--border);
  background: #FFFFFF;
  cursor: pointer;
  transition: all 0.15s ease;
}
.patient-item:hover{
  border-color: rgba(37,99,235,0.25);
  background: rgba(37,99,235,0.03);
}
.patient-item.active{
  border-color: rgba(37,99,235,0.35);
  background: rgba(37,99,235,0.06);
}
.patient-item + .patient-item{ margin-top: 6px; }
.patient-name{ font-size: 13px; font-weight: 900; color: var(--text); }
.patient-meta{ font-size: 11px; color: var(--muted); }

/* Chips */
.chip{
  display:inline-flex; align-items:center; padding: 4px 8px;
  border-radius: 999px; border: 1px solid var(--border);
  background: var(--chip-bg); font-size: 11px; font-weight: 900;
}
.chip.optimal{ color: var(--optimal); }
.chip.ok{ color: var(--ok); }
.chip.warn{ color: var(--warn); }
.chip.bad{ color: var(--bad); }

/* Buttons (default) */
div.stButton > button{
  border-radius: 12px !important;
  border: 1px solid var(--border) !important;
  background: #FFFFFF !important;
  color: var(--text) !important;
  font-weight: 900 !important;
  padding: 0.6rem 0.9rem !important;
}
div.stButton > button:hover{
  border-color: rgba(37,99,235,0.35) !important;
  color: var(--primary) !important;
}

/* Primary buttons */
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
  border-radius: 14px !important;
}
[data-baseweb="select"] > div {
  background: #FFFFFF !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 14px !important;
  box-shadow: 0 8px 30px rgba(15,23,42,0.04) !important;
}
[data-baseweb="select"] * { color: #0F172A !important; font-weight: 800; }
[data-baseweb="select"] svg { color: #64748B !important; }
ul[role="listbox"]{
  background: #FFFFFF !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  border-radius: 14px !important;
  box-shadow: 0 18px 60px rgba(15,23,42,0.12) !important;
}
ul[role="listbox"] li{ color: #0F172A !important; }
ul[role="listbox"] li:hover{ background: rgba(37,99,235,0.06) !important; }

/* Reduce whitespace */
[data-testid="stVerticalBlock"] { gap: 0.55rem; }
h3 { margin-top: 0.55rem !important; margin-bottom: 0.35rem !important; }

/* Premium Sidebar */
[data-testid="stSidebar"] {
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  width: 270px !important;
}
[data-testid="stSidebar"] > div:first-child { width: 270px !important; }
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
.sidebar-brand .logo-line{ display:flex; align-items:center; justify-content:space-between; }
.sidebar-brand .logo{ font-weight: 950; letter-spacing:-0.02em; color: var(--text); font-size: 16px; }
.sidebar-brand .tag{
  font-size: 11px; font-weight: 950;
  padding: 4px 8px; border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(15,23,42,0.03);
  color: var(--muted);
}
.sidebar-brand .mini{ font-size: 11px; color: var(--muted); line-height: 1.2; }

.sidebar-section{
  font-size: 11px;
  font-weight: 950;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 10px 0 6px 6px;
}

/* Sidebar radio -> iOS list */
[data-testid="stSidebar"] .stRadio div[role="radiogroup"]{ gap: 6px; }
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
  font-weight: 950 !important;
  font-size: 13px !important;
}

/* File uploader */
[data-testid="stFileUploaderDropzone"]{
  background: #FFFFFF !important;
  border: 1px dashed rgba(15,23,42,0.18) !important;
  border-radius: 16px !important;
  padding: 14px !important;
  box-shadow: var(--shadow) !important;
}
[data-testid="stFileUploaderDropzone"] *{ color: #0F172A !important; }

/* Charts */
.vega-embed, .vega-embed details, .vega-embed summary { border-radius: 14px !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------
# 5) DATA LOGIC
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

def get_patient_data(patient_id):
    """Get lab results and events for a specific patient."""
    all_results = st.session_state["data"].copy()
    all_events = st.session_state["events"].copy()

    # Filter to active patient
    results = all_results[all_results["PatientID"] == patient_id].copy() if not all_results.empty else all_results
    events = all_events[all_events["PatientID"] == patient_id].copy() if not all_events.empty else all_events

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
        df_new["PatientID"] = patient_id  # Tag with patient ID
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


# ---------------------------
# 6) MASTER RANGES
# ---------------------------
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


# ---------------------------
# 7) UTILS
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

def patient_summary_counts(patient_id, master):
    """Quick count of labs and events for a patient (used in patient list)."""
    all_data = st.session_state["data"]
    all_events = st.session_state["events"]
    lab_count = len(all_data[all_data["PatientID"] == patient_id]) if not all_data.empty else 0
    event_count = len(all_events[all_events["PatientID"] == patient_id]) if not all_events.empty else 0
    return lab_count, event_count


# ---------------------------
# 8) CHART ENGINE
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
                fontWeight=700,
                color="#0F172A",
            ).encode(
                x="Date:T",
                y="y_text:Q",
                text="EventShort:N",
            )

            layers.extend([ev_rule, ev_txt])

    return alt.layer(*layers).properties(height=480, background="#FFFFFF").configure_view(strokeWidth=0)


# ---------------------------
# 9) UI SHELL
# ---------------------------
master = get_master_data()
patient = get_active_patient()
pid = st.session_state["active_patient"]
results, events = get_patient_data(pid)
ui = st.session_state["ui"]

last_date = last_lab_date(results)
last_date_str = last_date.strftime("%d %b %Y") if last_date is not None else "—"

# Patient count for display
patient_count = len(st.session_state["patients"])

st.markdown(
    f"""
<div class="hos-topbar">
  <div class="brand">
    <h1>HealthOS <span style="color: var(--muted); font-weight:900;">PRO</span></h1>
    <div class="sub">Doctor workflow • longitudinal labs + interventions</div>
  </div>
  <div class="meta">
    <span class="pill"><span class="dot"></span><strong>{patient.get('name','Patient')}</strong> • {patient.get('sex','')}, {patient.get('age','')}</span>
    <span class="pill">Last Lab: <strong>{last_date_str}</strong></span>
    <span class="pill">Patients: <strong>{patient_count}</strong></span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------
# 10) SIDEBAR
# ---------------------------
with st.sidebar:
    st.markdown(
        """
<div class="sidebar-brand">
  <div class="logo-line">
    <div class="logo">HealthOS</div>
    <div class="tag">PRO</div>
  </div>
  <div class="mini">Clean clinical UI • consult-first</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # --- Patient Selector ---
    st.markdown('<div class="sidebar-section">Active patient</div>', unsafe_allow_html=True)
    patient_list = get_patient_list()
    patient_ids = [p[0] for p in patient_list]
    patient_labels = [p[1] for p in patient_list]

    current_idx = patient_ids.index(pid) if pid in patient_ids else 0
    selected_label = st.selectbox(
        "Patient",
        patient_labels,
        index=current_idx,
        label_visibility="collapsed",
    )
    selected_pid = patient_ids[patient_labels.index(selected_label)]
    if selected_pid != pid:
        set_active_patient(selected_pid)
        st.rerun()

    # Add patient button
    if st.button("➕ New patient", use_container_width=True):
        ui["open_add_patient"] = True
        ui["open_upload"] = False
        ui["open_event"] = False
        ui["open_patient"] = False

    # --- Navigation ---
    st.markdown('<div class="sidebar-section">Navigate</div>', unsafe_allow_html=True)
    nav = st.radio(
        "NAV",
        ["🩺 Consult", "📈 Trends", "💊 Interventions", "👥 Patients"],
        index=["🩺 Consult", "📈 Trends", "💊 Interventions", "👥 Patients"].index(ui["nav"]) if ui["nav"] in ["🩺 Consult", "📈 Trends", "💊 Interventions", "👥 Patients"] else 0,
        label_visibility="collapsed",
    )
    ui["nav"] = nav

    # --- Quick actions ---
    st.markdown('<div class="sidebar-section">Quick actions</div>', unsafe_allow_html=True)
    qa1, qa2 = st.columns(2)
    with qa1:
        if st.button("⬆️ Upload", use_container_width=True):
            ui["open_upload"] = True
            ui["open_event"] = False
            ui["open_patient"] = False
            ui["open_add_patient"] = False
    with qa2:
        if st.button("💊 Add", use_container_width=True):
            ui["open_event"] = True
            ui["open_upload"] = False
            ui["open_patient"] = False
            ui["open_add_patient"] = False

    qb1, qb2 = st.columns(2)
    with qb1:
        if st.button("👤 Edit patient", use_container_width=True):
            ui["open_patient"] = True
            ui["open_upload"] = False
            ui["open_event"] = False
            ui["open_add_patient"] = False
    with qb2:
        if st.button("↩️ Reset", use_container_width=True):
            wipe_patient_data(pid)
            st.toast("Patient data reset.", icon="✅")
            st.rerun()

    st.markdown('<div class="sidebar-section">Demo tools</div>', unsafe_allow_html=True)
    ui["show_debug"] = st.toggle("Developer debug", value=ui["show_debug"])
    st.markdown('<div class="small-muted">Keep off during doctor demos.</div>', unsafe_allow_html=True)


# ---------------------------
# 11) PANELS (UPLOAD / EVENT / PATIENT / ADD PATIENT)
# ---------------------------

# --- Add New Patient Panel ---
if ui["open_add_patient"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### New patient")
    st.markdown('<div class="small-muted">Add a patient to your roster.</div>', unsafe_allow_html=True)

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
            new_height = st.text_input("Height (cm)", placeholder="e.g., 178")
        with c6:
            new_weight = st.text_input("Weight (kg)", placeholder="e.g., 82")

        new_notes = st.text_area("Clinical notes (optional)", height=80)

        left, right = st.columns([1, 5])
        with left:
            save = st.form_submit_button("Add patient", type="primary")
        with right:
            close = st.form_submit_button("Cancel", type="secondary")

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
                st.error("Patient name is required.")

        if close:
            ui["open_add_patient"] = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Edit Patient Panel ---
if ui["open_patient"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Edit patient")
    st.markdown(f'<div class="small-muted">Editing: {patient.get("name", "")}</div>', unsafe_allow_html=True)

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

        notes = st.text_area("Clinical notes…", value=patient.get("notes", ""), height=110)

        left, right = st.columns([1, 5])
        with left:
            save = st.form_submit_button("Save", type="primary")
        with right:
            close = st.form_submit_button("Close", type="secondary")

        if save:
            update_patient(pid, name=name, sex=sex, age=int(age), mrn=mrn,
                           height_cm=height_cm, weight_kg=weight_kg, notes=notes)
            st.toast("Patient updated.", icon="✅")
            ui["open_patient"] = False
            st.rerun()

        if close:
            ui["open_patient"] = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Upload Panel ---
if ui["open_upload"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Upload lab")
    st.markdown(f'<div class="small-muted">Uploading for: <strong>{patient.get("name","")}</strong>. CSV for now — PDF/image pipeline coming.</div>', unsafe_allow_html=True)

    up = st.file_uploader("Choose file", type=["csv"], key="lab_upload_main")

    cA, cB = st.columns([1, 6])
    with cA:
        go = st.button("Import", disabled=not bool(up))
    with cB:
        cancel = st.button("Close", key="close_upload")

    if go and up:
        with st.spinner("Importing…"):
            msg, count = process_upload(up, pid, show_debug=ui["show_debug"])
        if msg == "Success":
            st.toast(f"Imported {count} rows for {patient.get('name','')}.", icon="✅")
            ui["open_upload"] = False
            st.rerun()
        else:
            st.error(msg)

    if cancel:
        ui["open_upload"] = False
        st.rerun()

    if ui["show_debug"]:
        st.markdown("---")
        with st.expander("Debug"):
            if st.button("Wipe patient data (debug)"):
                wipe_patient_data(pid)
                st.warning("Wiped.")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Add Intervention Panel ---
if ui["open_event"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Add intervention")
    st.markdown(f'<div class="small-muted">For: <strong>{patient.get("name","")}</strong>. These overlay on biomarker trend charts.</div>', unsafe_allow_html=True)

    with st.form("add_event_quick"):
        c1, c2, c3 = st.columns([1.1, 2.2, 1.2], gap="large")
        with c1:
            d = st.date_input("Date")
        with c2:
            n = st.text_input("Event name", placeholder="e.g., Start statin / Start TRT / Stop alcohol")
        with c3:
            t = st.selectbox("Type", ["Medication", "Lifestyle", "Procedure", "Supplement"])

        note = st.text_input("Notes (optional)", placeholder="e.g., 200mg/week Test Cyp")

        left, right = st.columns([1, 6])
        with left:
            add = st.form_submit_button("Add", type="primary")
        with right:
            close = st.form_submit_button("Close", type="secondary")

        if add:
            add_clinical_event(pid, d, n, t, note)
            st.toast("Intervention added.", icon="✅")
            ui["open_event"] = False
            st.rerun()
        if close:
            ui["open_event"] = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------
# 12) PAGES
# ---------------------------
def build_dashboard_rows(results, master, sel_date):
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

    return rows, counts

def render_rows(title, rows):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)

    if not rows:
        st.markdown('<div class="small-muted">Nothing to show for this report date.</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for r in sorted(rows, key=lambda x: (x["Prio"], x["Marker"])):
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

    st.markdown("</div>", unsafe_allow_html=True)


# ===================
# CONSULT PAGE
# ===================
if nav == "🩺 Consult":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Consult view")
    st.markdown(f'<div class="small-muted">Patient: <strong>{patient.get("name","")}</strong> — fast consult-ready summary.</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if results.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### No labs yet")
        st.markdown(f'<div class="small-muted">Use <strong>⬆️ Upload</strong> in the sidebar to import labs for {patient.get("name","")}.</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    dates = sorted(results["Date"].dropna().unique(), reverse=True)
    sel_date = st.selectbox("Report date", dates, format_func=lambda d: d.strftime("%d %b %Y"))

    rows, counts = build_dashboard_rows(results, master, sel_date)

    # Active interventions summary
    active_interventions = []
    if not events.empty:
        ev_before = events[events["Date"] <= sel_date].sort_values("Date", ascending=False)
        active_interventions = ev_before.head(3).to_dict("records")

    intervention_html = ""
    if active_interventions:
        pills = " ".join(
            f'<span class="chip ok">{e.get("Event","")}</span>' for e in active_interventions
        )
        intervention_html = f"""
  <div class="kpi"><div class="label">Active interventions</div><div style="margin-top:6px;">{pills}</div><div class="hint">Most recent</div></div>
"""
    else:
        intervention_html = """
  <div class="kpi"><div class="label">Active interventions</div><div class="val" style="font-size:16px; color:var(--muted);">None</div><div class="hint">Add via sidebar</div></div>
"""

    st.markdown(
        f"""
<div class="kpi-grid">
  <div class="kpi"><div class="label">Total tested</div><div class="val">{len(rows)}</div><div class="hint">Biomarkers detected</div></div>
  <div class="kpi"><div class="label">Optimal</div><div class="val" style="color:var(--optimal)">{counts.get("optimal",0)}</div><div class="hint">Within optimal band</div></div>
  <div class="kpi"><div class="label">In range</div><div class="val" style="color:var(--ok)">{counts.get("ok",0)}</div><div class="hint">Within reference</div></div>
  <div class="kpi"><div class="label">Borderline</div><div class="val" style="color:var(--warn)">{counts.get("warn",0)}</div><div class="hint">Watch & adjust</div></div>
  {intervention_html}
</div>
""",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="large")
    with left:
        render_rows("⚠️ Attention required", [r for r in rows if r["StatusKey"] in ["bad", "warn"]])
    with right:
        render_rows("✅ Stable / optimized", [r for r in rows if r["StatusKey"] in ["optimal", "ok"]])


# ===================
# TRENDS PAGE
# ===================
elif nav == "📈 Trends":
    if results.empty:
        st.warning(f"No data loaded for {patient.get('name','')}. Use ⬆️ Upload in the sidebar.")
        st.stop()

    markers = sorted(results["CleanMarker"].unique())
    # Smart defaults: show whatever markers this patient actually has
    defaults = markers[:7] if len(markers) > 7 else markers

    topA, topB, topC = st.columns([2.2, 1.2, 1.6], gap="large")
    with topA:
        sel = st.multiselect("Select biomarkers", markers, default=defaults)
    with topB:
        layout = st.segmented_control("Layout", options=["Stacked", "2-column"], default="2-column")
    with topC:
        compare_mode = st.toggle(
            "Compare two markers",
            value=len(sel) >= 2,
            help="Shows two charts side-by-side at the top for quick clinical comparison."
        )

    if not sel:
        st.info("Select at least one biomarker.")
        st.stop()

    pair = []
    if compare_mode and len(sel) >= 2:
        c1, c2 = st.columns(2, gap="large")
        with c1:
            p1 = st.selectbox("Compare: left", sel, index=0)
        with c2:
            p2 = st.selectbox("Compare: right", sel, index=1 if len(sel) > 1 else 0)
        if p1 and p2 and p1 != p2:
            pair = [p1, p2]

    def render_chart(marker_clean: str):
        m_row = fuzzy_match(marker_clean, master)
        subtitle = ""
        if m_row is not None:
            s_min, s_max = parse_range(m_row["Standard Range"])
            unit = m_row["Unit"] if pd.notna(m_row["Unit"]) else ""
            subtitle = f"Ref: {s_min:g}–{s_max:g} {unit}".strip()

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">{marker_clean}</div>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<div class="small-muted">{subtitle}</div>', unsafe_allow_html=True)

        ch = plot_chart(marker_clean, results, events, master)
        if ch:
            st.altair_chart(ch, use_container_width=True)
        else:
            st.info(f"No numeric data for {marker_clean}")
        st.markdown("</div>", unsafe_allow_html=True)

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


# ===================
# INTERVENTIONS PAGE
# ===================
elif nav == "💊 Interventions":
    st.markdown("### Interventions")
    st.markdown(f'<div class="small-muted">For: <strong>{patient.get("name","")}</strong> — these appear on trend charts as vertical markers.</div>', unsafe_allow_html=True)

    if events.empty:
        st.markdown(f'<div class="card"><div class="small-muted">No interventions for {patient.get("name","")} yet. Use <strong>💊 Add</strong> in the sidebar.</div></div>', unsafe_allow_html=True)
        st.stop()

    ev = events.dropna(subset=["Date"]).sort_values("Date", ascending=False)
    st.markdown('<div class="card">', unsafe_allow_html=True)

    for i, row in ev.iterrows():
        notes_txt = f' — {row["Notes"]}' if row.get("Notes") and str(row["Notes"]).strip() else ""
        st.markdown(
            f"""
<div class="row">
  <div class="row-left">
    <div class="row-title">{row['Event']}</div>
    <div class="row-sub">
      <span class="chip ok">{row['Type']}</span>
      <span>{row['Date'].strftime('%d %b %Y')}</span>
      <span style="color: var(--muted);">{notes_txt}</span>
    </div>
  </div>
  <div class="row-right"></div>
</div>
""",
            unsafe_allow_html=True,
        )

        colA, colB, colC = st.columns([7, 1.7, 1.0], gap="small")
        with colB:
            confirm = st.checkbox("Confirm", key=f"confirm_{i}")
        with colC:
            if st.button("Delete", key=f"del_{i}", disabled=not confirm):
                delete_event(i)
                st.toast("Deleted.", icon="🗑️")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ===================
# PATIENTS PAGE (NEW)
# ===================
elif nav == "👥 Patients":
    st.markdown("### Patient roster")
    st.markdown('<div class="small-muted">Manage your patients. Click to switch active patient.</div>', unsafe_allow_html=True)

    st.markdown("")  # spacing

    # Add patient button at top
    if st.button("➕ Add new patient", use_container_width=False):
        ui["open_add_patient"] = True
        st.rerun()

    st.markdown("")

    patient_list = get_patient_list()

    if not patient_list:
        st.markdown('<div class="card"><div class="small-muted">No patients yet.</div></div>', unsafe_allow_html=True)
        st.stop()

    st.markdown('<div class="card">', unsafe_allow_html=True)

    for p_id, p_label in patient_list:
        p = st.session_state["patients"][p_id]
        lab_count, event_count = patient_summary_counts(p_id, master)
        is_active = p_id == pid

        active_class = "active" if is_active else ""
        active_dot = '<span class="dot" style="width:6px;height:6px;border-radius:999px;background:var(--primary);display:inline-block;margin-right:4px;"></span>' if is_active else ""

        st.markdown(
            f"""
<div class="patient-item {active_class}">
  <div>
    <div class="patient-name">{active_dot}{p.get('name','')}</div>
    <div class="patient-meta">{p.get('sex','')}, {p.get('age','')} {('• MRN: ' + p.get('mrn','')) if p.get('mrn') else ''}</div>
  </div>
  <div style="text-align:right;">
    <div class="patient-meta">{lab_count} lab results • {event_count} interventions</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        # Action buttons for each patient
        col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 1.5], gap="small")
        with col2:
            if not is_active:
                if st.button("Select", key=f"sel_{p_id}", use_container_width=True):
                    set_active_patient(p_id)
                    ui["nav"] = "🩺 Consult"
                    st.rerun()
        with col3:
            if st.button("Edit", key=f"edit_{p_id}", use_container_width=True):
                set_active_patient(p_id)
                ui["open_patient"] = True
                st.rerun()
        with col4:
            if len(st.session_state["patients"]) > 1:
                if st.button("Delete", key=f"delp_{p_id}", use_container_width=True):
                    delete_patient(p_id)
                    st.toast(f"Deleted {p.get('name','')}.", icon="🗑️")
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
