import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import io
import time
import re
import os
import altair as alt
import google.generativeai as genai
from difflib import SequenceMatcher
from datetime import datetime
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="HealthOS", layout="wide", initial_sidebar_state="expanded")

# --- AUTHENTICATION ---
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    current_dir = os.path.dirname(os.path.abspath(__file__))
    key_file_path = os.path.join(current_dir, "service_account.json")
    if os.path.exists(key_file_path):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(key_file_path, scope)
            return gspread.authorize(creds)
        except: return None
    elif "gcp_service_account" in st.secrets:
        try:
            # Handle both string (TOML) and dict (JSON) formats
            secret_value = st.secrets["gcp_service_account"]
            if isinstance(secret_value, str):
                creds_dict = json.loads(secret_value)
            else:
                creds_dict = secret_value
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except: return None
    else: return None

# --- API SETUP ---
MY_API_KEY = "AIzaSyDr9aILsF4LbU5c2tjeCwWdINEOZ2Pqn8o"
try:
    if "GOOGLE_API_KEY" in st.secrets:
        MY_API_KEY = st.secrets["GOOGLE_API_KEY"]
except: pass
genai.configure(api_key=MY_API_KEY)

# --- MODEL SETUP ---
generation_config = GenerationConfig(temperature=0.0)
try:
    model = genai.GenerativeModel('gemini-3-flash-preview', generation_config=generation_config)
except:
    model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=generation_config)

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# --- 2. STYLING (TRUE APPLE AESTHETIC) ---
st.markdown("""
    <style>
    /* Global Reset */
    [data-testid="stAppViewContainer"] { background-color: #000000; color: #F5F5F7; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    [data-testid="stSidebar"] { background-color: #1C1C1E; border-right: 1px solid #2C2C2E; }
    
    /* Apple Header */
    .ios-header { font-size: 14px; text-transform: uppercase; color: #8E8E93; font-weight: 600; margin-top: 30px; margin-bottom: 8px; padding-left: 16px; }
    
    /* Apple Grouped Table Container */
    .ios-card { background-color: #1C1C1E; border-radius: 12px; overflow: hidden; margin-bottom: 20px; border: 1px solid #2C2C2E; }
    
    /* Apple Table Row */
    .ios-row { display: flex; justify-content: space-between; align-items: center; padding: 16px 16px; border-bottom: 1px solid #2C2C2E; transition: background 0.2s; }
    .ios-row:last-child { border-bottom: none; }
    .ios-row:hover { background-color: #2C2C2E; }

    /* Text Styles */
    .marker-name { font-size: 17px; font-weight: 500; color: #FFFFFF; width: 35%; }
    .data-col { font-size: 16px; color: #FFFFFF; width: 20%; text-align: right; font-variant-numeric: tabular-nums; border-left: 1px solid #2C2C2E; padding-right: 10px; }
    .arrow-bad { color: #FF3B30; font-size: 14px; margin-left: 4px; font-weight: bold; }
    .arrow-good { color: #34C759; font-size: 14px; margin-left: 4px; font-weight: bold; }
    
    /* Status Pills */
    .pill { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; }
    .p-green { background-color: #34C759; box-shadow: 0 0 8px rgba(52, 199, 89, 0.4); }
    .p-orange { background-color: #FF9500; box-shadow: 0 0 8px rgba(255, 149, 0, 0.4); }
    .p-red { background-color: #FF3B30; box-shadow: 0 0 8px rgba(255, 59, 48, 0.4); }
    .p-blue { background-color: #007AFF; box-shadow: 0 0 8px rgba(0, 122, 255, 0.4); }

    /* Legend Styles */
    .legend-container { display: flex; flex-wrap: wrap; gap: 15px; padding: 10px 0 20px 5px; border-bottom: 1px solid #2C2C2E; margin-bottom: 20px; }
    .legend-item { display: flex; align-items: center; font-size: 13px; color: #8E8E93; font-weight: 500; }

    /* Restored Dashboard Styles */
    .glass-card { background: rgba(28, 28, 30, 0.6); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; padding: 24px; margin-bottom: 8px; box-shadow: 0 4px 24px rgba(0,0,0,0.2); }
    .stat-box { text-align: center; padding: 15px; border-radius: 16px; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255,255,255,0.05); }
    .stat-num { font-size: 32px; font-weight: 700; margin: 0; }
    .stat-label { font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; opacity: 0.8; }
    .ai-report-box { background: linear-gradient(135deg, rgba(28, 28, 30, 0.9) 0%, rgba(10, 10, 12, 0.95) 100%); border: 1px solid rgba(0, 122, 255, 0.3); border-radius: 24px; padding: 30px; margin-bottom: 30px; }

    div.stButton > button { width: 100%; border-radius: 12px; background-color: rgba(255, 255, 255, 0.05); color: #aaa; border: 1px solid rgba(255, 255, 255, 0.1); font-size: 12px; margin-bottom: 24px; padding: 4px 0; }
    div.stButton > button:hover { background-color: rgba(255, 255, 255, 0.15); color: white; border-color: #007AFF; }
    div[data-baseweb="select"] > div { background-color: rgba(255,255,255,0.1) !important; color: white !important; border: none; }
    input, textarea { background-color: rgba(255,255,255,0.1) !important; color: white !important; border: none; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA HANDLING ---
SHEET_NAME = "HealthOS_DB"
MASTER_FILE_LOCAL = "Biomarker_Master_Elite.csv"
REQUIRED_COLUMNS = ['Marker', 'Value', 'Unit', 'Flag', 'Date', 'Source']

@st.cache_data(ttl=10)
def load_data():
    client = get_google_sheet_client()
    if not client: return None, None, {}, "Auth Failed"
    try:
        sh = client.open(SHEET_NAME)
        # MASTER
        try:
            ws_master = sh.worksheet("Master")
            m_data = ws_master.get_all_values()
            if len(m_data) > 1: master = pd.DataFrame(m_data[1:], columns=m_data[0])
            else: raise Exception("Empty")
        except:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            master_path = os.path.join(current_dir, MASTER_FILE_LOCAL)
            if os.path.exists(master_path): master = pd.read_csv(master_path)
            else: master = pd.DataFrame(columns=["Biomarker", "Fuzzy Match Keywords", "Standard Range", "Optimal Min", "Optimal Max", "Unit", "Plain-English Meaning"])
        master = master.fillna("")
        if 'Fuzzy Match Keywords' in master.columns: master['Fuzzy Match Keywords'] = master['Fuzzy Match Keywords'].astype(str)
        if 'Unit' in master.columns: master['Unit'] = master['Unit'].fillna("")

        # RESULTS
        try:
            ws_res = sh.worksheet("Results")
            data = ws_res.get_all_values()
            if not data: results = pd.DataFrame(columns=REQUIRED_COLUMNS)
            else:
                headers = data[0]
                rows = data[1:]
                results = pd.DataFrame(rows, columns=headers) if "Marker" in headers else pd.DataFrame(rows, columns=REQUIRED_COLUMNS[:len(rows[0])])
        except gspread.exceptions.WorksheetNotFound:
            ws_res = sh.add_worksheet("Results", 1000, 10)
            ws_res.append_row(REQUIRED_COLUMNS)
            results = pd.DataFrame(columns=REQUIRED_COLUMNS)
        for col in REQUIRED_COLUMNS:
            if col not in results.columns: results[col] = ""

        # PROFILE
        try:
            ws_prof = sh.worksheet("Profile")
            p_data = ws_prof.get_all_values()
            profile = {r[0]: r[1] for r in p_data if len(r) >= 2}
        except: profile = {}

        # PROCESS
        if not results.empty:
            results['Date'] = pd.to_datetime(results['Date'], errors='coerce')
            results = results.dropna(subset=['Date'])
            results = results.dropna(subset=['Value'])
            results = results[results['Value'].astype(str).str.strip() != ""]
            results['NumericValue'] = pd.to_numeric(results['Value'], errors='coerce')
            
        return master, results, profile, "OK"
    except Exception as e: return None, None, {}, str(e)

def smart_save_to_sheet(new_df):
    client = get_google_sheet_client()
    sh = client.open(SHEET_NAME)
    try: ws = sh.worksheet("Results")
    except: ws = sh.add_worksheet("Results", 1000, 10)
    existing_data = ws.get_all_values()
    if not existing_data:
        ws.append_row(REQUIRED_COLUMNS)
        existing_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    else:
        headers = existing_data[0]
        rows = existing_data[1:]
        existing_df = pd.DataFrame(rows, columns=headers)
    for col in REQUIRED_COLUMNS:
        if col not in new_df.columns: new_df[col] = ""
    new_df = new_df[REQUIRED_COLUMNS].copy()
    new_df['Date'] = new_df['Date'].astype(str)
    target_dates = new_df['Date'].unique()
    final_df = existing_df[~existing_df['Date'].isin(target_dates)]
    final_df = pd.concat([final_df, new_df], ignore_index=True)
    final_df = final_df.fillna("").astype(str)
    ws.clear()
    ws.append_row(REQUIRED_COLUMNS)
    ws.append_rows(final_df.values.tolist())
    st.cache_data.clear()
    if len(target_dates) > 0: st.session_state['auto_select_date'] = target_dates[0]

def save_profile_to_sheet(new_profile):
    client = get_google_sheet_client()
    sh = client.open(SHEET_NAME)
    try: ws = sh.worksheet("Profile")
    except: ws = sh.add_worksheet(title="Profile", rows=100, cols=2)
    rows = [[k, str(v)] for k, v in new_profile.items()]
    ws.clear()
    ws.update(values=rows)
    st.cache_data.clear()

def clear_database():
    client = get_google_sheet_client()
    sh = client.open(SHEET_NAME)
    ws = sh.worksheet("Results")
    ws.clear()
    ws.append_row(REQUIRED_COLUMNS)
    st.cache_data.clear()

# --- 4. ENGINE ---
def process_uploaded_image(uploaded_file):
    try:
        mime_type = uploaded_file.type
        file_data = {"mime_type": mime_type, "data": uploaded_file.getvalue()}
        prompt = f"""Act as a Medical Document Scanner. EXTRACT structured data.
        
        CRITICAL RULES:
        1. **MANDATORY SEARCH:** Look closely for these markers (they may be abbreviated or in a separate column):
           - MCHC
           - White Cell Count / WCC / Leucocytes / Leukocytes
           - Free T3 / FT3
           - Free T4 / FT4
           - SHBG / Sex Hormone Binding Globulin
           - Non-HDL Cholesterol
        
        2. **UNIT LOGIC:**
           - If a row has TWO values (e.g., 55% and 4.50), use the ABSOLUTE count (usually the smaller number like 4.50).
           - IGNORE the % value.
        
        3. **FORMAT:**
           - Extract 'Report Date' (YYYY-MM-DD).
           - Extract 'Marker', 'Value', 'Unit'.
        
        OUTPUT: Clean CSV with headers: Marker, Value, Unit, Flag, Date"""
        
        response = model.generate_content([prompt, file_data], safety_settings=safety_settings)
        if not response.parts: return None, "AI empty."
        csv_text = response.text.replace('```csv', '').replace('```', '').strip()
        df = pd.read_csv(io.StringIO(csv_text), on_bad_lines='skip')
        df.columns = [c.strip() for c in df.columns]
        rename_map = {'Test': 'Marker', 'Result': 'Value', 'Results': 'Value', 'Units': 'Unit', 'Ref Range': 'Flag', 'Reference': 'Flag'}
        new_cols = {c: rename_map[k] for c in df.columns for k in rename_map if c.lower() == k.lower()}
        df = df.rename(columns=new_cols)
        if 'Marker' not in df.columns or 'Value' not in df.columns: return None, "Structure failed."
        df['Value'] = df['Value'].astype(str).str.extract(r'(\d+\.?\d*)')[0]
        df = df.dropna(subset=['Value'])
        df['Source'] = 'Lab Report'
        return df, "Success"
    except Exception as e: return None, str(e)

# --- 5. LOGIC (CATEGORIZATION & UNIFICATION) ---
def smart_clean(marker):
    m = str(marker).upper()
    return re.sub(r'^[SPBU]-\s*', '', m.replace("SERUM", "").replace("PLASMA", "").replace("BLOOD", "").replace("TOTAL", "").strip())

# EXPANDED CATEGORY MAP (THE FIX FOR "OTHER")
CATEGORY_MAP = {
    "❤️ Lipids & Heart": ["CHOLESTEROL", "HDL", "LDL", "TRIG", "APOB", "LIPOPROTEIN", "NON-HDL", "RATIO", "HOMOCYST", "CRP", "HS-CRP"],
    "🧬 Hormones": ["TESTOSTERONE", "OESTRADIOL", "PROGESTERONE", "DHEA", "SHBG", "FSH", "LH", "CORTISOL", "PROLACTIN"],
    "🦋 Thyroid": ["TSH", "T3", "T4", "FT3", "FT4"],
    "⚡ Metabolic": ["GLUCOSE", "INSULIN", "HBA1C", "SUGAR"],
    "🩸 Blood Health": ["HAEMOGLOBIN", "RED CELL", "WHITE CELL", "PLATELET", "NEUTROPHIL", "LYMPHOCYTE", "MONOCYTE", "EOSINOPHIL", "BASOPHIL", "MCH", "MCV", "RDW", "HCT", "HAEMATOCRIT", "LEUCOCYTE", "ERYTHROCYTE"],
    "🦴 Vitamins & Minerals": ["VITAMIN", "MAGNESIUM", "IRON", "FERRITIN", "ZINC", "TRANSFERRIN", "SATURATION", "CALCIUM"],
    "🍺 Liver Health": ["ALT", "AST", "GGT", "BILIRUBIN", "ALBUMIN", "GLOBULIN", "PROTEIN", "ALKALINE", "PHOSPHATASE"],
    "💧 Kidney & Electrolytes": ["CREATININE", "UREA", "EGFR", "URIC ACID", "SODIUM", "POTASSIUM", "CHLORIDE", "CO2", "BICARBONATE", "ANION GAP"]
}

def get_category(marker_name):
    clean = smart_clean(marker_name)
    for cat, keywords in CATEGORY_MAP.items():
        for k in keywords:
            if k in clean: return cat
    return "📝 Other Biomarkers"

def unify_marker_names(marker):
    clean = smart_clean(marker)
    
    # 1. RATIO GUARD
    if "RATIO" in clean: return "Cholesterol/HDL Ratio"
    
    # 2. FREE TESTO GUARD
    if "FREE" in clean and "TESTO" in clean: return "Free Testosterone"
    
    # 3. TESTOSTERONE (TOTAL) FIX
    if "TESTOSTERONE" in clean: return "Total Testosterone"
    
    # 4. NON-HDL GUARD
    if "NON-HDL" in clean or "NON HDL" in clean: return "Non-HDL Cholesterol"
    
    # 5. Standard Mapping
    if "LDL" in clean: return "LDL Cholesterol"
    if "HDL" in clean: return "HDL Cholesterol"
    if "CHOLESTEROL" in clean: return "Total Cholesterol"
    if "TRIG" in clean: return "Triglycerides"
    if "VITAMIN D" in clean or "25 OH" in clean: return "Vitamin D"
    if "LEUCOCYTE" in clean or "WHITE CELL" in clean: return "White Cell Count"
    if "ERYTHROCYTE" in clean or "RED CELL" in clean: return "Red Cell Count"
    if "PLATELET" in clean: return "Platelets"
    
    return marker.title()

def fuzzy_match(marker, master):
    lab_clean = smart_clean(marker)
    best_row, best_score = None, 0.0
    for _, row in master.iterrows():
        keywords = [smart_clean(k) for k in str(row['Fuzzy Match Keywords']).split(",")]
        for key in keywords:
            if "NON" in lab_clean and "NON" not in key: continue
            if "NON" not in lab_clean and "NON" in key: continue
            if key == lab_clean: return row
            if lab_clean.startswith(key) and len(key) > 2: return row
            score = SequenceMatcher(None, lab_clean, key).ratio()
            if score > best_score: best_score, best_row = score, row
    return best_row if best_score > 0.60 else None

def parse_range(range_str):
    if pd.isna(range_str): return 0,0
    clean = str(range_str).replace('–', '-').replace(',', '.')
    clean = re.sub(r'(?<=\d)\s(?=\d)', '', clean)
    if "<" in clean:
        val = re.findall(r"[-+]?\d*\.\d+|\d+", clean)
        if val: return 0.0, float(val[0])
    parts = re.findall(r"[-+]?\d*\.\d+|\d+", clean)
    if len(parts) >= 2: return float(parts[0]), float(parts[1])
    if len(parts) == 1: return 0.0, float(parts[0]) 
    return 0, 0

def get_detailed_status(val, master_row, marker_name):
    try:
        clean_name = smart_clean(marker_name)
        if "HBA1C" in clean_name and val > 20 and "%" in str(master_row['Unit']): val = (val * 0.0915) + 2.15
        
        s_min, s_max = parse_range(master_row['Standard Range'])
        try: o_min = float(str(master_row['Optimal Min']).replace(',', '.'))
        except: o_min = 0.0
        try: o_max = float(str(master_row['Optimal Max']).replace(',', '.'))
        except: o_max = 0.0

        # --- HARDCODED FLOORS ---
        if "VITAMIN D" in clean_name: 
            if o_min == 0: o_min = 50.0
        if "DHEA" in clean_name: 
            if o_min == 0: o_min = 6.0 

        wbc_types = ["NEUTROPHIL", "LYMPHOCYTE", "MONOCYTE", "EOSINOPHIL", "BASOPHIL"]
        if any(x in clean_name for x in wbc_types) and s_max > 0 and val > (s_max * 5):
             return "PERCENTAGE", "#8E8E93", "c-grey", "", f"{val}%", 5

        # GRADING
        unit = str(master_row['Unit']) if pd.notna(master_row['Unit']) else ""
        rng_str = f"{s_min} - {s_max} {unit}"

        if s_min > 0 and (val < (s_min/10) or val > (s_max*10)): return "UNIT MISMATCH", "#8E8E93", "c-grey", "?", f"{rng_str}", 5
        if s_min > 0 and val < s_min: return "OUT OF RANGE", "#FF3B30", "c-red", "LOW", rng_str, 1
        if s_max > 0 and val > s_max: return "OUT OF RANGE", "#FF3B30", "c-red", "HIGH", rng_str, 1
        
        # --- HDL TRAP (FORCE ORANGE) ---
        if "HDL" in clean_name and "NON" not in clean_name:
            if val < 1.4: return "BORDERLINE", "#FF9500", "c-orange", "LOW END", rng_str, 2

        has_optimal = (o_min > 0 or o_max > 0)
        check_min = o_min if o_min > 0 else s_min
        check_max = o_max if o_max > 0 else s_max
        if has_optimal and val >= check_min and val <= check_max: return "OPTIMAL", "#007AFF", "c-blue", "ELITE", rng_str, 3

        # Surgical Orange
        no_buffer_list = ["TRIG", "CHOLESTEROL", "LDL", "UREA", "CREATININE"]
        if any(x in clean_name for x in no_buffer_list): return "IN RANGE", "#34C759", "c-green", "OK", rng_str, 4

        higher_is_better = ["VITAMIND", "VITAMIN D", "DHEA", "TESTOSTERONE", "MAGNESIUM", "B12", "FOLATE", "HDL", "FERRITIN"]
        if any(x in clean_name for x in higher_is_better):
            if o_min > 0 and val < o_min: return "BORDERLINE", "#FF9500", "c-orange", "LOW END", rng_str, 2
        
        range_span = s_max - s_min
        buffer = range_span * 0.025 if range_span > 0 else 0
        if buffer > 0:
            if val < (s_min + buffer): return "BORDERLINE", "#FF9500", "c-orange", "LOW END", rng_str, 2
            if val > (s_max - buffer): return "BORDERLINE", "#FF9500", "c-orange", "HIGH END", rng_str, 2

        return "IN RANGE", "#34C759", "c-green", "OK", rng_str, 4
    except: return "ERROR", "#8E8E93", "c-grey", "", "Error", 5

def filter_best_matches(processed_rows):
    df = pd.DataFrame(processed_rows)
    if df.empty: return df
    df['SortOrder'] = df['Priority']
    df = df.sort_values('SortOrder')
    df = df.drop_duplicates(subset=['Marker'], keep='first')
    return df

# --- 7. AI GENERATORS ---
def format_profile_for_ai(profile):
    bio = profile.get('bio_context', 'No narrative provided.')
    supps = profile.get('supplements', 'None')
    training = str(profile.get('training_type', 'General'))
    train_freq = profile.get('train_freq', 'Unknown')
    return f"""- **Demographics:** {profile.get('age', 'N/A')} / {profile.get('gender', 'N/A')}
    - **Biometrics:** {profile.get('height', 'N/A')}cm / {profile.get('weight', 'N/A')}kg
    - **Lifestyle:** Smoke: {profile.get('smoke', 'N/A')} | Drink: {profile.get('alcohol', 'N/A')}
    - **Training:** {training} ({train_freq} sessions/week)
    - **Goals:** {profile.get('goals')}
    - **Supplements:** {supps}
    - **User Narrative:** "{bio}" """

def generate_deep_dive(marker, value, status, profile):
    prompt = f"""You are HealthOS, a physiological coach. Explain '{marker}' (Level: {value}, Status: {status}).
    *** CLIENT *** {format_profile_for_ai(profile)}
    *** TASK *** 1. Analogy. 2. Why it matters. 3. Analysis. 4. Fix (3 habits).
    TONE: Calm, educational."""
    try:
        response = model.generate_content(prompt, safety_settings=safety_settings)
        return response.text if response.parts else "Unavailable."
    except: return "Unavailable."

def generate_snapshot_report(df_view, date_str, profile, history_df):
    current_date_obj = pd.to_datetime(date_str)
    past_labs = history_df[history_df['Date'] < current_date_obj]
    data_summary = ""
    abnormal_markers_found = []
    clean_view = df_view[df_view['Status'] != 'PERCENTAGE']
    
    for _, row in clean_view.iterrows():
        marker = row['Marker']
        val_now = row['Value']
        status = row['Status']
        line = f"- {marker}: {val_now} ({status})\n"
        data_summary += line
        if status in ["OUT OF RANGE", "BORDERLINE"]:
            abnormal_markers_found.append(f"{marker} ({val_now})")

    related_map = {"LDL": ["APOB", "LIPOPROTEIN"], "CHOLESTEROL": ["APOB"], "TRIGLYCERIDES": ["INSULIN"], "GLUCOSE": ["HBA1C"], "TESTOSTERONE": ["SHBG", "LH"], "TSH": ["T3", "T4"], "FERRITIN": ["IRON", "CRP"]}
    connected_insights = ""
    for abnormal_entry in abnormal_markers_found:
        m_name = abnormal_entry.split(' (')[0]
        clean_abnormal = smart_clean(m_name)
        for trigger_key, related_targets in related_map.items():
            if trigger_key in clean_abnormal:
                for target in related_targets:
                    match_in_history = history_df[history_df['Marker'].apply(lambda x: smart_clean(x) == smart_clean(target) or target in smart_clean(x))]
                    if not match_in_history.empty:
                        last_rel = match_in_history.sort_values('Date').iloc[-1]
                        connected_insights += f"NOTE: {m_name} is flagged. But {last_rel['Marker']} was {last_rel['Value']} on {last_rel['Date'].strftime('%Y-%m-%d')}. USE THIS CONTEXT.\n"

    abnormal_list_str = ", ".join(abnormal_markers_found) if abnormal_markers_found else "None"
    user_context = format_profile_for_ai(profile)
    
    prompt = f"""You are HealthOS, an elite physiological performance analyst.
    Analyze this lab report from **{date_str}**.
    *** CLIENT PROFILE & CONTEXT *** {user_context}
    *** LAB DATA *** {data_summary}
    *** HISTORY CONTEXT *** {connected_insights}
    *** INSTRUCTIONS ***
    1. **Narrative:** Connect the dots.
    2. **Areas of Focus:** Discuss ONLY the abnormal markers: {abnormal_list_str}.
    3. **HIGH-RESOLUTION PROTOCOL (Mandatory):**
       Create a specific plan to fix these markers: {abnormal_list_str}.
       * **A. Dietary Intervention:** Specific foods/macros.
       * **B. Exercise Protocol:** Specific adjustments to training.
       * **C. Lifestyle Optimization:** Habits.
       * **D. Targeted Supplementation:** Specific non-prescription compounds.
       * **E. Follow-Up Testing:** Re-test plan.
    TONE: Calm, analytical, professional."""
    try:
        response = model.generate_content(prompt, safety_settings=safety_settings)
        return response.text if response.parts else "AI Analysis Unavailable."
    except Exception as e: return f"Error: {e}"

# --- HELPER ---
def safe_parse_list(val):
    if not val: return []
    try:
        if isinstance(val, str) and val.startswith("[") and val.endswith("]"): return eval(val)
        return []
    except: return []

# --- 8. MAIN APP ---
st.sidebar.title("HealthOS")
master_df, results_df, user_profile, msg = load_data()

# --- AUTH SAFETY STOP ---
if master_df is None: 
    st.error(f"Database Connection Failed: {msg}")
    st.info("Please check your Secrets configuration in Streamlit Cloud.")
    st.stop()

# SELECTOR
unique_dates = sorted(results_df['Date'].dropna().unique(), reverse=True)
date_options = [d.strftime('%Y-%m-%d') for d in unique_dates if pd.notna(d)]
if date_options:
    default_idx = 0
    if 'auto_select_date' in st.session_state:
        target = st.session_state.pop('auto_select_date')
        if target in date_options: default_idx = date_options.index(target)
    st.sidebar.markdown("### 🗓️ Active Record")
    selected_label = st.sidebar.selectbox("Select Lab:", date_options, index=default_idx)
else: selected_label = None

page = st.sidebar.radio("Navigation", ["👤 My Profile", "Lab Snapshot", "Trend Analysis"])

# UPLOAD
with st.sidebar.expander("📤 Upload New Lab"):
    uploaded_lab = st.file_uploader("Drag & Drop Lab Image", type=['png', 'jpg', 'jpeg', 'pdf'])
    if uploaded_lab and st.button("Process & Digitize"):
        with st.spinner("AI Reading..."):
            new_df, status = process_uploaded_image(uploaded_lab)
            if new_df is not None:
                smart_save_to_sheet(new_df)
                st.success(f"✅ Saved markers!"); time.sleep(1.5); st.rerun()
            else: st.error(status)

with st.sidebar.expander("🗑️ Admin Zone"):
    if st.button("⚠️ Wipe Database"): clear_database(); st.warning("Cleared."); time.sleep(1); st.rerun()

# PAGE 1
if page == "👤 My Profile":
    st.markdown("### 🏥 Medical & Lifestyle Intake")
    with st.form("p_form"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: age = st.number_input("Age", value=int(user_profile.get("age", 30)))
        with c2: gender = st.selectbox("Gender", ["Male", "Female"], index=["Male", "Female"].index(user_profile.get("gender", "Male")))
        with c3: height = st.text_input("Height (cm)", value=user_profile.get("height", ""))
        with c4: weight = st.text_input("Weight (kg)", value=user_profile.get("weight", ""))
        
        c5, c6, c7 = st.columns(3)
        with c5:
            smoke_opts = ["Never Smoked", "Former Smoker", "Current Smoker (Social)", "Current Smoker (Daily)"]
            curr_smoke = user_profile.get("smoke", "Never Smoked")
            smoke = st.selectbox("Smoking", smoke_opts, index=smoke_opts.index(curr_smoke) if curr_smoke in smoke_opts else 0)
        with c6:
            alc_opts = ["None", "Social (1-2/wk)", "Moderate (3-7/wk)", "Heavy (10+/wk)"]
            curr_alc = user_profile.get("alcohol", "Social (1-2/wk)")
            alcohol = st.selectbox("Alcohol", alc_opts, index=alc_opts.index(curr_alc) if curr_alc in alc_opts else 1)
        with c7:
            work_opts = ["Sedentary", "Light Active", "Active"]
            curr_work = user_profile.get("work_activity", "Sedentary")
            work_activity = st.selectbox("Work", work_opts, index=work_opts.index(curr_work) if curr_work in work_opts else 0)

        c8, c9 = st.columns(2)
        with c8:
            train_opts = ["Sedentary", "General Wellness", "Hypertrophy (Muscle)", "Strength", "Endurance", "Hybrid"]
            curr_train = user_profile.get("training_type", "General Wellness")
            if "[" in curr_train: curr_train = "General Wellness"
            training_type = st.selectbox("Training Style", train_opts, index=train_opts.index(curr_train) if curr_train in train_opts else 1)
        with c9:
            train_freq = st.slider("Sessions/Week", 0, 14, int(user_profile.get("train_freq", 3)))

        saved_goals = safe_parse_list(user_profile.get("goals", "[]"))
        valid_goals = [g for g in saved_goals if g in ["Longevity", "Muscle Gain", "Fat Loss", "Cognitive", "Heart Health"]]
        goals = st.multiselect("Goals", ["Longevity", "Muscle Gain", "Fat Loss", "Cognitive", "Heart Health"], default=valid_goals)
        
        supplements = st.text_area("💊 Supplements & Meds:", value=user_profile.get("supplements", ""))
        bio_context = st.text_area("📝 Bio-Narrative:", value=user_profile.get("bio_context", ""))
        
        if st.form_submit_button("💾 Save Profile"):
            save_profile_to_sheet({
                "age": age, "gender": gender, "height": height, "weight": weight,
                "smoke": smoke, "alcohol": alcohol, "work_activity": work_activity,
                "training_type": training_type, "train_freq": train_freq,
                "goals": str(goals), "supplements": supplements, "bio_context": bio_context
            })
            st.success("Saved!"); time.sleep(1); st.rerun()

# PAGE 2
elif page == "Lab Snapshot":
    if not selected_label: st.info("Database empty."); st.stop()
    snapshot = results_df[results_df['Date'].astype(str).str.startswith(selected_label)].copy()
    processed_rows, stats = [], {"Blue": 0, "Green": 0, "Orange": 0, "Red": 0, "Mismatch": 0}
    
    for _, row in snapshot.iterrows():
        master = fuzzy_match(row['Marker'], master_df)
        if master is not None:
            val = row['NumericValue'] if pd.notna(row.get('NumericValue')) else row['Value']
            status, color, css, direction, rng, prio = get_detailed_status(val, master, master['Biomarker'])
            
            if status == "PERCENTAGE" or status == "UNIT MISMATCH": pass
            elif "OPTIMAL" in status: stats["Blue"] += 1
            elif "IN RANGE" in status: stats["Green"] += 1
            elif "BORDERLINE" in status: stats["Orange"] += 1
            elif "OUT OF RANGE" in status: stats["Red"] += 1
            
            processed_rows.append({"Marker": master['Biomarker'], "Value": row['Value'], "Status": status, "Color": color, "Class": css, "Range": rng, "Meaning": master['Plain-English Meaning'], "Priority": prio, "Source": row['Source'], "Direction": direction})
    
    df_view = filter_best_matches(processed_rows)
    df_display = df_view[~df_view['Status'].isin(['PERCENTAGE', 'UNIT MISMATCH'])]

    if df_display.empty: st.warning("No matched biomarkers."); st.stop()

    st.markdown(f"### 🔬 Record: {selected_label}")
    cols = st.columns(6)
    metrics = [("Tested", len(df_display), "white"), ("Optimal", stats['Blue'], "#007AFF"), ("In Range", stats['Green'], "#34C759"), ("Borderline", stats['Orange'], "#FF9500"), ("Out of Range", stats['Red'], "#FF3B30"), ("Unit Error", stats['Mismatch'], "#8E8E93")]
    for i, (l, v, c) in enumerate(metrics):
        with cols[i]: st.markdown(f"""<div class="glass-card stat-box"><h1 class="stat-num" style="color:{c};">{v}</h1><div class="stat-label" style="color:{c};">{l}</div></div>""", unsafe_allow_html=True)

    if st.button("🧠 Analyze Lab & History"):
        with st.spinner("Analyzing..."):
            st.session_state.ai_report = generate_snapshot_report(df_view, selected_label, user_profile, results_df)
    if st.session_state.get('ai_report'):
        with st.expander("🧠 HealthOS Intelligence Report", expanded=True):
            st.markdown(f"""<div class="ai-report-box">{st.session_state.ai_report}</div>""", unsafe_allow_html=True)

    st.divider()
    c_warn, c_good = st.columns(2)
    with c_warn:
        st.subheader("⚠️ Attention Needed")
        bad_df = df_display[df_display['Priority'].isin([1, 2])]
        if bad_df.empty: st.markdown("✅ No Issues")
        for idx, r in bad_df.sort_values('Priority').iterrows():
            st.markdown(f"""<div class="glass-card" style="border-left:4px solid {r['Color']}"><div style="display:flex;justify-content:space-between"><div><span class="{r['Class']}" style="font-size:10px;font-weight:bold">{r['Status']}</span><h3 style="margin:5px 0 0 0">{r['Marker']}</h3><p style="color:#aaa;font-size:12px">Range: {r['Range']}</p></div><div style="text-align:right"><h2 style="margin:0;color:{r['Color']}">{r['Value']}</h2></div></div><div style="margin-top:8px;font-size:12px;color:#ccc">{r['Meaning']}</div></div>""", unsafe_allow_html=True)
            k = f"b_warn_{idx}_{r['Marker']}"
            if st.button(f"🎓 Explain {r['Marker']}", key=k): st.session_state[f"d_{k}"] = True
            if st.session_state.get(f"d_{k}"):
                if f"e_{k}" not in st.session_state:
                    with st.spinner("..."): st.session_state[f"e_{k}"] = generate_deep_dive(r['Marker'], r['Value'], r['Status'], user_profile)
                with st.expander("Details", expanded=True):
                    st.write(st.session_state[f"e_{k}"])
                    if st.button("Close", key=f"c_{k}"): st.session_state[f"d_{k}"] = False; st.rerun()

    with c_good:
        st.subheader("✅ Optimized")
        good_df = df_display[df_display['Priority'].isin([3, 4])]
        for idx, r in good_df.sort_values('Priority').iterrows():
            st.markdown(f"""<div class="glass-card" style="border-left:4px solid {r['Color']}"><div style="display:flex;justify-content:space-between"><div><span class="{r['Class']}" style="font-size:10px;font-weight:bold">{r['Status']}</span><h3 style="margin:5px 0 0 0">{r['Marker']}</h3></div><div style="text-align:right"><h2 style="margin:0;color:{r['Color']}">{r['Value']}</h2></div></div><div style="margin-top:8px;font-size:12px;color:#ccc">{r['Meaning']}</div></div>""", unsafe_allow_html=True)

# PAGE 3 - TREND HEATMAP
elif page == "Trend Analysis":
    if results_df.empty: st.info("Database empty."); st.stop()
    st.markdown("### 📈 Health Heatmap")
    
    # LEGEND
    st.markdown("""
    <div class="legend-container">
        <div class="legend-item"><span class="pill p-blue"></span>Optimal</div>
        <div class="legend-item"><span class="pill p-green"></span>Normal</div>
        <div class="legend-item"><span class="pill p-orange"></span>Borderline</div>
        <div class="legend-item"><span class="pill p-red"></span>Out of Range</div>
        <div class="legend-item" style="margin-left:10px"><span style="color:#34C759;font-weight:bold">↑↓</span> Improving</div>
        <div class="legend-item"><span style="color:#FF3B30;font-weight:bold">↑↓</span> Worsening</div>
    </div>
    """, unsafe_allow_html=True)
    
    unique_dates = sorted(results_df['Date'].dropna().unique(), reverse=False)
    
    results_df['UnifiedMarker'] = results_df['Marker'].apply(lambda x: unify_marker_names(x))
    results_df['Category'] = results_df['UnifiedMarker'].apply(lambda x: get_category(x))
    
    categories = sorted(results_df['Category'].unique())
    if "📝 Other Biomarkers" in categories:
        categories.remove("📝 Other Biomarkers")
        categories.append("📝 Other Biomarkers")

    # SMART ARROW LOGIC (BINARY COLORING)
    HIGHER_IS_BETTER = ["HDL Cholesterol", "Vitamin D", "Total Testosterone", "Free Testosterone", "Magnesium", "Vitamin B12", "Folate", "Ferritin", "Iron", "Haemoglobin", "Red Cell Count"]

    for cat in categories:
        st.markdown(f"<div class='ios-header'>{cat}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='ios-card'>", unsafe_allow_html=True)
        
        cat_df = results_df[results_df['Category'] == cat]
        pivot = cat_df.pivot_table(index='UnifiedMarker', columns='Date', values='Value', aggfunc='first')
        
        for marker in pivot.index:
            col_html = ""
            prev_val = None
            
            for date in unique_dates:
                val = pivot.loc[marker, date] if date in pivot.columns else None
                display_val = "-"
                pill_class = ""
                
                if pd.notna(val):
                    try:
                        num_val = float(val)
                        arrow = ""
                        
                        if prev_val is not None:
                            if marker in HIGHER_IS_BETTER:
                                if num_val > prev_val: arrow = "<span class='arrow-good'>↑</span>"
                                elif num_val < prev_val: arrow = "<span class='arrow-bad'>↓</span>"
                            else: # Default: Lower is Better
                                if num_val > prev_val: arrow = "<span class='arrow-bad'>↑</span>"
                                elif num_val < prev_val: arrow = "<span class='arrow-good'>↓</span>"
                        
                        display_val = f"{val}{arrow}"
                        
                        master = fuzzy_match(marker, master_df)
                        if master is not None:
                            status, _, _, _, _, _ = get_detailed_status(num_val, master, master['Biomarker'])
                            if "OPTIMAL" in status: pill_class = "p-blue"
                            elif "IN RANGE" in status: pill_class = "p-green"
                            elif "BORDERLINE" in status: pill_class = "p-orange"
                            elif "OUT OF RANGE" in status: pill_class = "p-red"
                        
                        prev_val = num_val
                    except: display_val = str(val)
                
                pill_html = f"<span class='pill {pill_class}'></span>" if pill_class else ""
                col_html += f"<div class='data-col'>{pill_html}{display_val}</div>"
            
            st.markdown(f"""<div class='ios-row'><div class='marker-name'>{marker}</div>{col_html}</div>""", unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)
