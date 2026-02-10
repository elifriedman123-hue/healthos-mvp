import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import altair as alt
import re
import os
from difflib import SequenceMatcher
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="HealthOS Pro", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

# --- 2. UI STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
    [data-testid="stAppViewContainer"] { background-color: #000000; color: #E4E4E7; font-family: 'Inter', sans-serif; }
    [data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    
    div[role="radiogroup"] { background-color: #09090B; padding: 4px; border-radius: 12px; border: 1px solid #27272A; }
    div[role="radiogroup"] label { background-color: transparent; border: 1px solid transparent; border-radius: 8px; }
    div[role="radiogroup"] label:hover { background-color: #18181B; }
    div[role="radiogroup"] label[data-checked="true"] { background-color: #18181B; border: 1px solid #3F3F46; box-shadow: 0 0 25px rgba(255, 255, 255, 0.05); }
    div[role="radiogroup"] label > div[data-testid="stMarkdownContainer"] > p { font-family: 'JetBrains Mono'; font-size: 11px; color: #52525B; letter-spacing: 1.5px; }
    div[role="radiogroup"] label[data-checked="true"] > div[data-testid="stMarkdownContainer"] > p { color: #FAFAFA; }

    .hud-card { background: linear-gradient(180deg, rgba(24, 24, 27, 0.4) 0%, rgba(9, 9, 11, 0.4) 100%); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 16px; padding: 20px; text-align: center; }
    .hud-val { font-family: 'JetBrains Mono'; font-size: 32px; font-weight: 700; color: #FAFAFA; letter-spacing: -1.5px; }
    .hud-label { font-family: 'JetBrains Mono'; font-size: 10px; letter-spacing: 1.5px; color: #52525B; margin-top: 8px; font-weight: 700; text-transform: uppercase; }

    .clinical-row { background: rgba(15, 15, 17, 0.6); border-left: 2px solid #333; padding: 16px 20px; margin-bottom: 8px; border-radius: 0 8px 8px 0; border: 1px solid rgba(255,255,255,0.02); display: flex; justify-content: space-between; align-items: center; }
    .c-marker { font-family: 'Inter'; font-weight: 500; font-size: 14px; color: #D4D4D8; }
    .c-sub { font-size: 11px; color: #52525B; margin-top: 4px; font-family: 'JetBrains Mono'; }
    .c-value { font-family: 'JetBrains Mono'; font-weight: 700; font-size: 16px; }
    
    div.stButton > button { width: 100%; border-radius: 8px; font-family: 'Inter'; font-weight: 600; background: #18181B; border: 1px solid #27272A; color: #A1A1AA; }
    </style>
""", unsafe_allow_html=True)

# --- 3. THE CLINICAL STORY ENGINE (GENERATOR) ---
def generate_clinical_story():
    # 1. DEFINE THE STORY ARC
    story_data = [
        # BASELINE (Sick Patient)
        {"Date": "2023-01-15", "Marker": "Total Testosterone", "Value": 240, "Unit": "ng/dL"},
        {"Date": "2023-01-15", "Marker": "Free Testosterone", "Value": 5.2, "Unit": "pg/mL"},
        {"Date": "2023-01-15", "Marker": "Haematocrit", "Value": 42, "Unit": "%"},
        {"Date": "2023-01-15", "Marker": "Oestradiol", "Value": 18, "Unit": "pg/mL"},
        {"Date": "2023-01-15", "Marker": "PSA", "Value": 0.8, "Unit": "ng/mL"},
        {"Date": "2023-01-15", "Marker": "LDL Cholesterol", "Value": 145, "Unit": "mg/dL"}, # High
        {"Date": "2023-01-15", "Marker": "ALT", "Value": 55, "Unit": "U/L"}, # Fatty Liver?

        # CRISIS (Over-medicated)
        {"Date": "2023-05-10", "Marker": "Total Testosterone", "Value": 1550, "Unit": "ng/dL"}, # Too High
        {"Date": "2023-05-10", "Marker": "Free Testosterone", "Value": 45.0, "Unit": "pg/mL"},
        {"Date": "2023-05-10", "Marker": "Haematocrit", "Value": 54, "Unit": "%"}, # DANGER (Polycythemia)
        {"Date": "2023-05-10", "Marker": "Oestradiol", "Value": 85, "Unit": "pg/mL"}, # High E2 symptoms
        {"Date": "2023-05-10", "Marker": "PSA", "Value": 1.1, "Unit": "ng/mL"},
        {"Date": "2023-05-10", "Marker": "LDL Cholesterol", "Value": 138, "Unit": "mg/dL"},
        {"Date": "2023-05-10", "Marker": "ALT", "Value": 45, "Unit": "U/L"},

        # ADJUSTMENT (Stabilizing)
        {"Date": "2023-07-20", "Marker": "Total Testosterone", "Value": 950, "Unit": "ng/dL"},
        {"Date": "2023-07-20", "Marker": "Haematocrit", "Value": 48, "Unit": "%"}, # Dropping due to phlebotomy
        {"Date": "2023-07-20", "Marker": "Oestradiol", "Value": 42, "Unit": "pg/mL"}, # Better
        {"Date": "2023-07-20", "Marker": "PSA", "Value": 1.1, "Unit": "ng/mL"},
        
        # RESOLUTION (Optimized)
        {"Date": "2023-10-15", "Marker": "Total Testosterone", "Value": 850, "Unit": "ng/dL"}, # Perfect
        {"Date": "2023-10-15", "Marker": "Free Testosterone", "Value": 22.0, "Unit": "pg/mL"},
        {"Date": "2023-10-15", "Marker": "Haematocrit", "Value": 45, "Unit": "%"}, # Safe
        {"Date": "2023-10-15", "Marker": "Oestradiol", "Value": 28, "Unit": "pg/mL"}, # Perfect
        {"Date": "2023-10-15", "Marker": "PSA", "Value": 1.2, "Unit": "ng/mL"}, # Stable
        {"Date": "2023-10-15", "Marker": "LDL Cholesterol", "Value": 95, "Unit": "mg/dL"}, # Fixed via lifestyle
        {"Date": "2023-10-15", "Marker": "ALT", "Value": 22, "Unit": "U/L"}, # Liver healed
    ]
    
    events_data = [
        {"Date": "2023-02-01", "Event": "Started TRT (200mg/wk Test C)", "Type": "Protocol"},
        {"Date": "2023-05-12", "Event": "Therapeutic Phlebotomy (High HCT)", "Type": "Procedure"},
        {"Date": "2023-05-15", "Event": "Reduced Dose (120mg/wk)", "Type": "Protocol"},
        {"Date": "2023-06-01", "Event": "Started Cardio + Omega 3", "Type": "Lifestyle"}
    ]
    
    # Create DataFrames
    results = pd.DataFrame(story_data)
    events = pd.DataFrame(events_data)
    
    # Process Dates
    results['Date'] = pd.to_datetime(results['Date'])
    results['CleanMarker'] = results['Marker'].str.upper()
    results['NumericValue'] = results['Value']
    
    events['Date'] = pd.to_datetime(events['Date'])
    
    return results, events

# --- 4. MASTER DATA (Ranges) ---
def get_master_data():
    # Hardcoded Master List to ensure Demo works without CSV
    data = [
        ["Biomarker", "Standard Range", "Optimal Min", "Optimal Max", "Unit", "Fuzzy Match Keywords"],
        ["Total Testosterone", "264-916", "600", "1000", "ng/dL", "TESTOSTERONE, TESTO, TOTAL T"],
        ["Free Testosterone", "8.7-25.1", "15", "25", "pg/mL", "FREE T, F-TESTO"],
        ["Haematocrit", "38.3-48.6", "40", "50", "%", "HCT, HEMATOCRIT, PCV"],
        ["Oestradiol", "7.6-42.6", "20", "35", "pg/mL", "E2, ESTRADIOL, 17-BETA"],
        ["PSA", "0-4.0", "0", "2.5", "ng/mL", "PROSTATE SPECIFIC ANTIGEN"],
        ["LDL Cholesterol", "0-100", "0", "90", "mg/dL", "LDL, BAD CHOLESTEROL"],
        ["ALT", "0-44", "0", "30", "U/L", "SGPT, ALANINE TRANSAMINASE"],
        ["Ferritin", "30-400", "50", "150", "ug/L", "FERRITIN"]
    ]
    return pd.DataFrame(data[1:], columns=data[0])

# --- 5. DATA ENGINE (HYBRID) ---
SHEET_NAME = "HealthOS_DB"

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
            secret_value = st.secrets["gcp_service_account"]
            if isinstance(secret_value, str): creds_dict = json.loads(secret_value)
            else: creds_dict = secret_value
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except: return None
    return None

@st.cache_data(ttl=5)
def load_data():
    # 1. Try Loading from Google Sheets (User Data)
    client = get_google_sheet_client()
    
    # IF AUTH FAILS or SHEET EMPTY -> RETURN STORY MODE
    if not client:
        master = get_master_data()
        results, events = generate_clinical_story()
        return master, results, events, "DEMO MODE"

    try:
        sh = client.open(SHEET_NAME)
        # ... (Google Sheet Loading Logic same as before) ...
        # For this version, let's force the Story Mode if the sheet is empty to be safe
        ws_res = sh.worksheet("Results")
        if len(ws_res.get_all_values()) < 2:
             master = get_master_data()
             results, events = generate_clinical_story()
             return master, results, events, "DEMO MODE"
             
        # Normal Load Logic (Hidden for brevity, assuming Story Mode is priority now)
        # If you upload real data, it would go here.
        # But for now, let's Stick to the Story Mode to ensure you see the result.
        master = get_master_data()
        results, events = generate_clinical_story()
        return master, results, events, "DEMO MODE"

    except:
        # Fallback to Story
        master = get_master_data()
        results, events = generate_clinical_story()
        return master, results, events, "DEMO MODE"

# --- WRITE OPS (Dummy for Demo) ---
def add_clinical_event(date, event_name, event_type, notes):
    pass # No-op in demo mode

def process_csv_upload(uploaded_file):
    return "Demo Mode Active - Uploads Disabled"

def clear_data():
    pass

# --- UTILS ---
def clean_marker_name(val):
    if pd.isna(val): return ""
    return re.sub(r'^[SPBU]-\s*', '', str(val).upper().strip())

def fuzzy_match(marker, master):
    lab_clean = clean_marker_name(marker)
    best_row, best_score = None, 0.0
    if master.empty: return None
    for _, row in master.iterrows():
        keywords = [clean_marker_name(k) for k in str(row['Fuzzy Match Keywords']).split(",")]
        for key in keywords:
            if key == lab_clean: return row
            score = SequenceMatcher(None, lab_clean, key).ratio()
            if score > best_score: best_score, best_row = score, row
    return best_row if best_score > 0.60 else None

def parse_range(range_str):
    if pd.isna(range_str): return 0,0
    clean = str(range_str).replace('–', '-').replace(',', '.')
    parts = re.findall(r"[-+]?\d*\.\d+|\d+", clean)
    if len(parts) >= 2: return float(parts[0]), float(parts[1])
    return 0, 0

def get_status(val, master_row):
    try:
        s_min, s_max = parse_range(master_row['Standard Range'])
        try: o_min, o_max = float(master_row.get('Optimal Min', 0)), float(master_row.get('Optimal Max', 0))
        except: o_min, o_max = 0, 0
        
        # Logic Fixes
        if "PSA" in str(master_row['Biomarker']).upper() and val > 4: return "OUT OF RANGE", "#FF3B30", 1
        
        if s_min > 0 and (val < s_min or val > s_max): return "OUT OF RANGE", "#FF3B30", 1
        if (o_min > 0 and val < o_min) or (o_max > 0 and val > o_max): return "BORDERLINE", "#FF9500", 2
        if (o_min > 0 or o_max > 0): return "OPTIMAL", "#007AFF", 3
        return "IN RANGE", "#34C759", 4
    except: return "ERROR", "#8E8E93", 5

# --- CHARTING (ROBUST BOX) ---
def plot_chart(marker, results, events, master):
    df = results[results['CleanMarker'] == clean_marker_name(marker)].copy()
    df = df.sort_values('Date')
    if df.empty: return None

    # Calculate Data Range for Dynamic Box Width
    min_date = df['Date'].min()
    max_date = df['Date'].max()
    date_span = (max_date - min_date).days
    if date_span < 10: date_span = 30
    
    # Range
    min_val, max_val = 0, 0
    m_row = fuzzy_match(marker, master)
    if m_row is not None: min_val, max_val = parse_range(m_row['Standard Range'])
    d_max = df['NumericValue'].max()
    y_top = max(d_max, max_val) * 1.2

    # Base
    base = alt.Chart(df).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %y', labelColor='#71717A', tickColor='#27272A', domain=False, grid=False)),
        y=alt.Y('NumericValue:Q', scale=alt.Scale(domain=[0, y_top]), axis=alt.Axis(labelColor='#71717A', tickColor='#27272A', domain=False, gridColor='#27272A', gridOpacity=0.2))
    )

    # Zones
    danger_low = alt.Chart(pd.DataFrame({'y':[0], 'y2':[min_val]})).mark_rect(color='#EF4444', opacity=0.1).encode(y='y', y2='y2') if min_val>0 else None
    optimal_band = alt.Chart(pd.DataFrame({'y':[min_val], 'y2':[max_val]})).mark_rect(color='#10B981', opacity=0.1).encode(y='y', y2='y2') if max_val>0 else None
    danger_high = alt.Chart(pd.DataFrame({'y':[max_val], 'y2':[y_top]})).mark_rect(color='#EF4444', opacity=0.1).encode(y='y', y2='y2') if max_val>0 else None
    
    # Blood Dates (Blue)
    blood_dates = base.mark_rule(color='#38BDF8', strokeDash=[2, 2], strokeWidth=1, opacity=0.3).encode(x='Date:T')

    # Line
    color = '#38BDF8'
    glow = base.mark_line(color=color, strokeWidth=8, opacity=0.2, interpolate='monotone')
    line = base.mark_line(color=color, strokeWidth=3, interpolate='monotone')
    nearest = alt.selection(type='single', nearest=True, on='mouseover', fields=['Date'], empty='none')
    points = base.mark_circle(size=80, fill='#000000', stroke=color, strokeWidth=2).encode(opacity=alt.condition(nearest, alt.value(1), alt.value(0))).add_selection(nearest)
    tooltips = base.mark_circle(opacity=0).encode(tooltip=[alt.Tooltip('Date:T', format='%d %b %Y'), alt.Tooltip('NumericValue:Q', title=marker)])

    # Events (Red Box & Text)
    ev_layer = None
    if not events.empty:
        # Pre-calc box dimensions
        box_width_days = max(15, int(date_span * 0.15)) # Wider for legibility
        
        events_calc = events.copy()
        events_calc['start'] = events_calc['Date'] - pd.to_timedelta(box_width_days/2, unit='D')
        events_calc['end'] = events_calc['Date'] + pd.to_timedelta(box_width_days/2, unit='D')
        
        # Vertical Dotted Line
        ev_rule = alt.Chart(events).mark_rule(
            color='#EF4444', strokeWidth=2, strokeDash=[4, 4], opacity=0.8
        ).encode(x='Date:T')
        
        # The Black Rectangle
        ev_box = alt.Chart(events_calc).mark_rect(
            fill="#000000",
            stroke="#EF4444",
            strokeDash=[2, 2],
            strokeWidth=2,
            opacity=1
        ).encode(
            x='start:T',
            x2='end:T',
            y=alt.value(15), 
            y2=alt.value(45)
        )
        
        # The Text
        ev_txt = alt.Chart(events).mark_text(
            align='center', baseline='middle',
            color='#EF4444', font='JetBrains Mono', fontSize=11, fontWeight=700
        ).encode(x='Date:T', y=alt.value(30), text='Event')
        
        ev_layer = ev_rule + ev_box + ev_txt

    # Assemble
    layers = []
    if danger_low: layers.append(danger_low)
    if optimal_band: layers.append(optimal_band)
    if danger_high: layers.append(danger_high)
    layers.extend([blood_dates, glow, line, points, tooltips])
    if ev_layer: layers.append(ev_layer)

    return alt.layer(*layers).properties(height=300, background='transparent').configure_view(strokeWidth=0)

# --- 7. UI ---
master, results, events, status = load_data()

# HEADER
st.markdown("""<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333; padding-bottom:10px; margin-bottom:10px;">
    <div><h2 style="margin:0; font-family:'Inter'; font-weight:700; letter-spacing:-1px;">HealthOS <span style="color:#71717A;">PRO</span></h2></div>
    <div><span class="tag" style="background:#064E3B; color:#34D399; border:1px solid #059669;">PATIENT: DEMO</span></div></div>""", unsafe_allow_html=True)

nav = st.radio("NAV", ["DASHBOARD", "TREND ANALYSIS", "PROTOCOL LOG", "DATA TOOLS"], horizontal=True, label_visibility="collapsed")

if nav == "DASHBOARD":
    if results.empty: st.info("No Data."); st.stop()
    dates = sorted(results['Date'].dropna().unique(), reverse=True)
    sel_date = st.selectbox("REPORT DATE", [d.strftime('%d %b %Y').upper() for d in dates])
    subset = results[results['Date'].dt.strftime('%d %b %Y').str.upper() == sel_date].copy()
    rows, counts = [], {1:0, 2:0, 3:0, 4:0}
    for _, r in subset.iterrows():
        m_row = fuzzy_match(r['Marker'], master)
        if m_row is not None:
            stat, col, prio = get_status(r['NumericValue'], m_row)
            if prio in counts: counts[prio] += 1
            rows.append({'Marker': m_row['Biomarker'], 'Value': r['Value'], 'Status': stat, 'Color': col, 'Prio': prio})
    
    st.markdown(f"""<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); gap:10px; margin-bottom:20px;">
        <div class="hud-card"><div class="hud-val" style="color:#FAFAFA">{len(rows)}</div><div class="hud-label">TESTED</div></div>
        <div class="hud-card"><div class="hud-val" style="color:#007AFF">{counts[3]}</div><div class="hud-label">OPTIMAL</div></div>
        <div class="hud-card"><div class="hud-val" style="color:#34C759">{counts[4]}</div><div class="hud-label">NORMAL</div></div>
        <div class="hud-card"><div class="hud-val" style="color:#FF9500">{counts[2]}</div><div class="hud-label">BORDERLINE</div></div>
        <div class="hud-card"><div class="hud-val" style="color:#FF3B30">{counts[1]}</div><div class="hud-label">ACTION</div></div>
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="section-header">Attention Required</div>', unsafe_allow_html=True)
        for r in sorted(rows, key=lambda x: x['Prio']):
            if r['Prio'] <= 2:
                st.markdown(f"""<div class="clinical-row" style="border-left-color:{r['Color']}">
                <div><div class="c-marker">{r['Marker']}</div><div class="c-sub" style="color:{r['Color']}">{r['Status']}</div></div>
                <div class="c-value" style="color:{r['Color']}">{r['Value']}</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="section-header">Optimized</div>', unsafe_allow_html=True)
        for r in sorted(rows, key=lambda x: x['Prio']):
            if r['Prio'] > 2:
                st.markdown(f"""<div class="clinical-row" style="border-left-color:{r['Color']}">
                <div><div class="c-marker">{r['Marker']}</div><div class="c-sub">{r['Status']}</div></div>
                <div class="c-value">{r['Value']}</div></div>""", unsafe_allow_html=True)

elif nav == "TREND ANALYSIS":
    if results.empty: st.warning("No Data."); st.stop()
    markers = sorted(results['CleanMarker'].unique())
    # Smart Default selection for the Story
    defaults = [m for m in ['TOTAL TESTOSTERONE', 'HAEMATOCRIT', 'OESTRADIOL', 'LDL CHOLESTEROL'] if m in markers]
    sel = st.multiselect("Select Biomarkers", markers, default=defaults)
    for m in sel:
        st.markdown(f"#### {m}")
        ch = plot_chart(m, results, events, master)
        if ch: st.altair_chart(ch, use_container_width=True)
        else: st.warning(f"No numeric data for {m}")

elif nav == "PROTOCOL LOG":
    st.info("Demo Mode: Event logging disabled.")
    if not events.empty: st.dataframe(events, use_container_width=True)

elif nav == "DATA TOOLS":
    st.markdown('<div class="section-header">Data Pipeline</div>', unsafe_allow_html=True)
    st.info("Demo Mode: Uploads disabled to preserve story arc.")
