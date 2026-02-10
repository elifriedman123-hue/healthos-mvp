import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import altair as alt
import os
import re
from difflib import SequenceMatcher
from datetime import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="HealthOS Pro", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

# --- 2. UI STYLING (The "Cool" Terminal Look - Preserved) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

    /* GLOBAL RESET */
    [data-testid="stAppViewContainer"] { background-color: #09090B; color: #E4E4E7; font-family: 'Inter', sans-serif; }
    [data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 1.5rem; padding-bottom: 5rem; }

    /* --- NAVIGATION BAR --- */
    [data-testid="stRadio"] > label { display: none; }
    div[role="radiogroup"] {
        flex-direction: row;
        background-color: #18181B;
        padding: 4px;
        border-radius: 10px;
        border: 1px solid #27272A;
        width: 100%;
        overflow-x: auto;
        white-space: nowrap;
    }
    div[role="radiogroup"] label {
        flex: 1;
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        margin: 0 2px;
        padding: 8px 16px;
        text-align: center;
        transition: all 0.2s ease;
        justify-content: center;
    }
    div[role="radiogroup"] label > div:first-child { display: none; } 
    
    div[role="radiogroup"] label > div[data-testid="stMarkdownContainer"] > p {
        font-family: 'JetBrains Mono', monospace !important; 
        font-weight: 700;
        font-size: 12px;
        margin: 0;
        color: #71717A; 
        text-transform: uppercase !important; 
        letter-spacing: 1px;
        white-space: nowrap;
    }
    
    div[role="radiogroup"] label:hover { background-color: #27272A; cursor: pointer; }
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #27272A;
        border: 1px solid #3F3F46;
    }
    div[role="radiogroup"] label[data-checked="true"] > div[data-testid="stMarkdownContainer"] > p { color: #FAFAFA; }

    /* --- DROPDOWN --- */
    div[data-baseweb="select"] > div {
        background-color: #18181B !important;
        border-color: #27272A !important;
        color: #FAFAFA !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] span {
        font-family: 'JetBrains Mono', monospace !important; 
        color: #FAFAFA !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        font-size: 13px !important;
    }
    .stSelectbox label { display: none; }

    /* --- HUD CARD --- */
    .hud-card {
        background: linear-gradient(145deg, rgba(39, 39, 42, 0.4) 0%, rgba(24, 24, 27, 0.4) 100%);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    .hud-val { font-family: 'JetBrains Mono', monospace; font-size: 32px; font-weight: 700; color: #FAFAFA; letter-spacing: -1px; }
    .hud-label { font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #A1A1AA; margin-top: 6px; font-weight: 700; }

    /* --- CLINICAL ROW --- */
    .clinical-row {
        background: rgba(255, 255, 255, 0.03);
        border-left: 4px solid #333;
        padding: 16px 20px;
        margin-bottom: 8px;
        border-radius: 4px 12px 12px 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .c-marker { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 15px; color: #F4F4F5; }
    .c-sub { font-size: 11px; color: #71717A; margin-top: 2px; }
    .c-value { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 18px; }
    
    /* HEADERS */
    .section-header {
        font-family: 'JetBrains Mono', monospace; 
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #52525B;
        margin-bottom: 15px;
        border-bottom: 1px solid #27272A;
        padding-bottom: 5px;
        margin-top: 10px;
    }

    div.stButton > button { width: 100%; border-radius: 8px; font-family: 'Inter', sans-serif; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA ENGINE (SMART MERGE UPGRADE) ---
SHEET_NAME = "HealthOS_DB"
MASTER_FILE_LOCAL = "Biomarker_Master_Elite.csv"

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
            if isinstance(secret_value, str):
                creds_dict = json.loads(secret_value)
            else:
                creds_dict = secret_value
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except: return None
    else: return None

# Cleaner
def clean_numeric_value(val):
    if pd.isna(val): return None
    s = str(val).strip().replace(',', '')
    s = s.replace('µg/L', '').replace('ng/mL', '').replace('<', '').replace('>', '')
    try:
        return float(re.findall(r"[-+]?\d*\.\d+|\d+", s)[0])
    except:
        return None

# Load Data
@st.cache_data(ttl=5)
def load_data():
    client = get_google_sheet_client()
    if not client: return None, None, None, "Auth Failed"
    try:
        sh = client.open(SHEET_NAME)
        
        # Master
        try:
            ws_master = sh.worksheet("Master")
            m_data = ws_master.get_all_values()
            master = pd.DataFrame(m_data[1:], columns=m_data[0]) if len(m_data) > 1 else pd.DataFrame()
        except: master = pd.DataFrame()

        # Results
        try:
            ws_res = sh.worksheet("Results")
            data = ws_res.get_all_values()
            results = pd.DataFrame(data[1:], columns=data[0])
            results['Date'] = pd.to_datetime(results['Date'], errors='coerce')
            results['NumericValue'] = results['Value'].apply(clean_numeric_value)
            
            # VIEW-LEVEL DEDUPLICATION (Safety Net)
            results = results.drop_duplicates(subset=['Date', 'Marker', 'Value'])
            
        except: results = pd.DataFrame()

        # Events
        try:
            ws_ev = sh.worksheet("Events")
            ev_data = ws_ev.get_all_values()
            events = pd.DataFrame(ev_data[1:], columns=ev_data[0])
            events['Date'] = pd.to_datetime(events['Date'], errors='coerce')
        except: 
            ws_ev = sh.add_worksheet("Events", 1000, 5)
            ws_ev.append_row(["Date", "Event", "Type", "Notes"])
            events = pd.DataFrame(columns=["Date", "Event", "Type", "Notes"])

        return master, results, events, "OK"
    except Exception as e: return None, None, None, str(e)

def add_clinical_event(date, event_name, event_type, notes):
    client = get_google_sheet_client()
    sh = client.open(SHEET_NAME)
    try: ws = sh.worksheet("Events")
    except: ws = sh.add_worksheet("Events", 1000, 5)
    ws.append_row([str(date), event_name, event_type, notes])
    st.cache_data.clear()

def clear_data():
    client = get_google_sheet_client()
    sh = client.open(SHEET_NAME)
    try: sh.worksheet("Results").clear(); sh.worksheet("Results").append_row(['Marker', 'Value', 'Unit', 'Flag', 'Date', 'Source'])
    except: pass
    try: sh.worksheet("Events").clear(); sh.worksheet("Events").append_row(["Date", "Event", "Type", "Notes"])
    except: pass
    st.cache_data.clear()

# --- THE SMART MERGE FIX ---
def process_csv_upload(uploaded_file):
    try:
        # 1. Read New Data
        try: df_new = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df_new = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
            
        # 2. Standardize Columns
        col_map = {c: c.lower() for c in df_new.columns}
        df_new.columns = df_new.columns.str.lower()
        
        rename_dict = {}
        for c in df_new.columns:
            if c in ['biomarker', 'test', 'name', 'analyte']: rename_dict[c] = 'Marker'
            elif c in ['result', 'reading', 'value', 'concentration']: rename_dict[c] = 'Value'
            elif c in ['time', 'collected', 'date', 'date collected']: rename_dict[c] = 'Date'
            elif c in ['unit', 'units']: rename_dict[c] = 'Unit'
            elif c in ['flag', 'status']: rename_dict[c] = 'Flag'
        df_new = df_new.rename(columns=rename_dict)
        
        db_columns = ['Marker', 'Value', 'Unit', 'Flag', 'Date', 'Source']
        for col in db_columns:
            if col not in df_new.columns: df_new[col] = "" 
        df_new = df_new[db_columns]

        # 3. Fetch Existing Data
        client = get_google_sheet_client()
        sh = client.open(SHEET_NAME)
        try: 
            ws = sh.worksheet("Results")
            existing_data = ws.get_all_values()
            if len(existing_data) > 1:
                df_old = pd.DataFrame(existing_data[1:], columns=existing_data[0])
            else:
                df_old = pd.DataFrame(columns=db_columns)
        except: 
            ws = sh.add_worksheet("Results", 1000, 10)
            ws.append_row(db_columns)
            df_old = pd.DataFrame(columns=db_columns)

        # 4. MERGE & DEDUPLICATE (The Magic Step)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        # Drop strict duplicates (Date + Marker + Value match)
        df_final = df_combined.drop_duplicates(subset=['Date', 'Marker', 'Value'], keep='last')
        
        # 5. Overwrite Sheet (Clean DB)
        ws.clear()
        ws.append_row(db_columns)
        ws.append_rows(df_final.astype(str).values.tolist())
        
        st.cache_data.clear()
        return "Success"
    except Exception as e: return f"Error: {str(e)}"

# --- 5. LOGIC ---
def smart_clean(marker):
    return re.sub(r'^[SPBU]-\s*', '', str(marker).upper().replace("SERUM", "").replace("PLASMA", "").replace("BLOOD", "").replace("TOTAL", "").strip())

def fuzzy_match(marker, master):
    lab_clean = smart_clean(marker)
    best_row, best_score = None, 0.0
    if master.empty: return None
    for _, row in master.iterrows():
        keywords = [smart_clean(k) for k in str(row['Fuzzy Match Keywords']).split(",")]
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

def get_detailed_status(val, master_row, marker_name):
    try:
        s_min, s_max = parse_range(master_row['Standard Range'])
        try: o_min = float(str(master_row['Optimal Min']).replace(',', '.'))
        except: o_min = 0.0
        try: o_max = float(str(master_row['Optimal Max']).replace(',', '.'))
        except: o_max = 0.0

        clean_name = smart_clean(marker_name)
        if "VITAMIN D" in clean_name and o_min == 0: o_min = 50.0
        unit = str(master_row['Unit']) if pd.notna(master_row['Unit']) else ""
        rng_str = f"{s_min} - {s_max} {unit}"

        if s_min > 0 and val < s_min: return "OUT OF RANGE", "#FF3B30", "c-red", rng_str, 1
        if s_max > 0 and val > s_max: return "OUT OF RANGE", "#FF3B30", "c-red", rng_str, 1
        
        has_optimal = (o_min > 0 or o_max > 0)
        check_min = o_min if o_min > 0 else s_min
        check_max = o_max if o_max > 0 else s_max
        if has_optimal and val >= check_min and val <= check_max: return "OPTIMAL", "#007AFF", "c-blue", rng_str, 3
        return "IN RANGE", "#34C759", "c-green", rng_str, 4
    except: return "ERROR", "#8E8E93", "c-grey", "Error", 5

# --- 6. CHART ENGINE ---
def plot_clinical_trend(marker_name, results_df, events_df, master_df):
    chart_data = results_df[results_df['Marker'] == marker_name].copy()
    # Simple sort and drop
    chart_data = chart_data.dropna(subset=['NumericValue']).sort_values('Date')
    
    if chart_data.empty: return None

    # Range
    min_val, max_val = 0, 0
    master_row = fuzzy_match(marker_name, master_df)
    if master_row is not None:
        min_val, max_val = parse_range(master_row['Standard Range'])

    # 1. Base
    base = alt.Chart(chart_data).encode(
        x=alt.X('Date:T', title=None, axis=alt.Axis(format='%d %b %Y', labelColor='#71717A', tickColor='#27272A', domain=False)),
        y=alt.Y('NumericValue:Q', title=None, scale=alt.Scale(zero=False, padding=20), axis=alt.Axis(labelColor='#71717A', tickColor='#27272A', domain=False)),
        tooltip=[
            alt.Tooltip('Date:T', format='%d %b %Y'),
            alt.Tooltip('NumericValue:Q', title=marker_name),
            alt.Tooltip('Source')
        ]
    )

    # 2. Bands
    bands = alt.Chart(pd.DataFrame({'y': [min_val], 'y2': [max_val]})).mark_rect(
        color='#10B981', opacity=0.08
    ).encode(y='y', y2='y2') if max_val > 0 else None

    # 3. Area (Gradient)
    area = base.mark_area(
        line={'color': '#3B82F6'},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='#3B82F6', offset=0), alt.GradientStop(color='rgba(59, 130, 246, 0)', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        ),
        opacity=0.4
    )

    # 4. Line
    line = base.mark_line(color='#3B82F6', strokeWidth=3)

    # 5. Points
    points = base.mark_circle(size=80, fill='#18181B', stroke='#3B82F6', strokeWidth=2)

    # 6. Interactive
    nearest = alt.selection(type='single', nearest=True, on='mouseover', fields=['Date'], empty='none')
    rules = base.mark_rule(color='#52525B', strokeWidth=1).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
    ).add_selection(nearest)

    # 7. Events
    event_layer = None
    if not events_df.empty:
        ev_rule = alt.Chart(events_df).mark_rule(
            color='#F43F5E', strokeWidth=1.5, strokeDash=[4,4]
        ).encode(x='Date:T', tooltip=['Event', 'Notes'])
        
        ev_text = alt.Chart(events_df).mark_text(
            align='left', baseline='middle', dx=5, dy=-80,
            color='#F43F5E', angle=0, fontSize=10, fontWeight=600
        ).encode(x='Date:T', text='Event')
        event_layer = ev_rule + ev_text

    final = line + points + area + rules
    if bands: final = bands + final
    if event_layer: final = final + event_layer

    return final.properties(height=320).configure_view(strokeWidth=0).interactive()

# --- 7. MAIN APP ---
master_df, results_df, events_df, status = load_data()

# HEADER
st.markdown("""
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333; padding-bottom:10px; margin-bottom:10px;">
    <div>
        <h2 style="margin:0; font-family:'Inter'; font-weight:700; letter-spacing:-1px;">HealthOS <span style="color:#71717A; font-weight:400;">Clinical</span></h2>
    </div>
    <div style="text-align:right;">
         <span class="tag" style="background:#064E3B; color:#34D399; border:1px solid #059669;">Patient: Demo Mode</span>
    </div>
</div>
""", unsafe_allow_html=True)

# TOP NAVIGATION (HARDCODED CAPS FORCED)
mode = st.radio("Navigation", ["DASHBOARD", "TREND ANALYSIS", "PROTOCOL LOG", "DATA TOOLS"], horizontal=True, label_visibility="collapsed")

# MODE 1: DASHBOARD
if mode == "DASHBOARD":
    if results_df.empty: 
        st.info("No Data Loaded. Go to 'Data Tools' to upload."); st.stop()
    
    unique_dates = sorted(results_df['Date'].dropna().unique(), reverse=True)
    date_options = [d.strftime('%d %b %Y').upper() for d in unique_dates if pd.notna(d)]
    date_map = {d.strftime('%d %b %Y').upper(): d.strftime('%Y-%m-%d') for d in unique_dates if pd.notna(d)}

    c_sel, _ = st.columns([1, 3])
    with c_sel:
        st.caption("REPORT DATE")
        selected_display = st.selectbox("View Report:", date_options, label_visibility="collapsed")
        selected_db_val = date_map.get(selected_display)
    
    snapshot = results_df[results_df['Date'].astype(str).str.startswith(selected_db_val)].copy()
    processed_rows, stats = [], {"Blue": 0, "Green": 0, "Orange": 0, "Red": 0}
    
    for _, row in snapshot.iterrows():
        master = fuzzy_match(row['Marker'], master_df)
        if master is not None:
            val = row['NumericValue'] if pd.notna(row.get('NumericValue')) else row['Value']
            status, color, css, rng, prio = get_detailed_status(val, master, master['Biomarker'])
            
            if "OPTIMAL" in status: stats["Blue"] += 1
            elif "IN RANGE" in status: stats["Green"] += 1
            elif "BORDERLINE" in status: stats["Orange"] += 1
            elif "OUT OF RANGE" in status: stats["Red"] += 1
            
            processed_rows.append({"Marker": master['Biomarker'], "Value": row['Value'], "Status": status, "Color": color, "Range": rng, "Priority": prio})
    
    df_display = pd.DataFrame(processed_rows)
    if df_display.empty: st.warning("No matched biomarkers."); st.stop()

    # HUD GRID
    st.markdown("""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 30px; margin-top: 10px;">
    """, unsafe_allow_html=True)
    
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#FAFAFA">{len(df_display)}</div><div class="hud-label">TOTAL TESTED</div></div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#3B82F6">{stats['Blue']}</div><div class="hud-label">OPTIMAL</div></div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#34D399">{stats['Green']}</div><div class="hud-label">NORMAL</div></div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#F59E0B">{stats['Orange']}</div><div class="hud-label">BORDERLINE</div></div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#EF4444">{stats['Red']}</div><div class="hud-label">ABNORMAL</div></div>""", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # LISTS
    c_warn, c_good = st.columns(2)
    with c_warn:
        st.markdown('<div class="section-header">Attention Required</div>', unsafe_allow_html=True)
        bad_df = df_display[df_display['Priority'].isin([1, 2])].sort_values('Priority', ascending=True)
        if bad_df.empty: st.caption("No markers flagged.")
        for _, r in bad_df.iterrows():
            st.markdown(f"""
            <div class="clinical-row" style="border-left-color: {r['Color']}">
                <div>
                    <div class="c-marker">{r['Marker']}</div>
                    <div class="c-sub" style="color:{r['Color']}">{r['Status']} • Range: {r['Range']}</div>
                </div>
                <div class="c-value" style="color:{r['Color']}">{r['Value']}</div>
            </div>""", unsafe_allow_html=True)

    with c_good:
        st.markdown('<div class="section-header">Optimized Markers</div>', unsafe_allow_html=True)
        good_df = df_display[df_display['Priority'].isin([3, 4])].sort_values('Priority', ascending=True)
        for _, r in good_df.iterrows():
            st.markdown(f"""
            <div class="clinical-row" style="border-left-color: {r['Color']}">
                <div>
                    <div class="c-marker">{r['Marker']}</div>
                    <div class="c-sub">{r['Status']}</div>
                </div>
                <div class="c-value" style="color:{r['Color']}">{r['Value']}</div>
            </div>""", unsafe_allow_html=True)

# MODE 2: TRENDS
elif mode == "TREND ANALYSIS":
    st.markdown('<div class="section-header">Longitudinal Analysis</div>', unsafe_allow_html=True)
    if results_df.empty: st.warning("No Data."); st.stop()
    
    markers = sorted(results_df['Marker'].unique())
    defaults = [m for m in ["Total Testosterone", "Haematocrit", "Oestradiol"] if m in markers]
    selected_markers = st.multiselect("Select Biomarkers:", markers, default=defaults)
    
    for m in selected_markers:
        st.markdown(f"#### {m}")
        chart = plot_clinical_trend(m, results_df, events_df, master_df)
        if chart: st.altair_chart(chart, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

# MODE 3: PROTOCOL
elif mode == "PROTOCOL LOG":
    st.markdown('<div class="section-header">Intervention Log</div>', unsafe_allow_html=True)
    with st.form("event_form"):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: e_date = st.date_input("Date")
        with c2: e_name = st.text_input("Intervention")
        with c3: e_type = st.selectbox("Type", ["Medication", "Lifestyle", "Procedure"])
        e_note = st.text_area("Clinical Notes")
        if st.form_submit_button("Log Event"):
            add_clinical_event(e_date, e_name, e_type, e_note)
            st.success("Event Logged"); st.rerun()

    if not events_df.empty: 
        st.dataframe(events_df, use_container_width=True, height=300)

# MODE 4: INGESTION
elif mode == "DATA TOOLS":
    st.markdown('<div class="section-header">Data Pipeline</div>', unsafe_allow_html=True)
    up_file = st.file_uploader("Upload CSV", type=['csv'])
    if up_file and st.button("Process Batch"):
        msg = process_csv_upload(up_file)
        if msg == "Success": st.success("Ingestion Complete"); st.rerun()
        else: st.error(msg)
            
    if st.button("⚠️ CLEAR ALL RECORDS"):
        clear_data()
        st.warning("Database Wiped."); st.rerun()
