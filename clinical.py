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

# --- 2. CINEMATIC UI STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

    /* GLOBAL RESET */
    [data-testid="stAppViewContainer"] { background-color: #000000; color: #E4E4E7; font-family: 'Inter', sans-serif; }
    [data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }

    /* NAVIGATION */
    [data-testid="stRadio"] > label { display: none; }
    div[role="radiogroup"] {
        flex-direction: row;
        background-color: #09090B;
        padding: 4px;
        border-radius: 12px;
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
        padding: 10px 16px;
        text-align: center;
        transition: all 0.2s ease;
        justify-content: center;
    }
    div[role="radiogroup"] label > div:first-child { display: none; } 
    
    div[role="radiogroup"] label > div[data-testid="stMarkdownContainer"] > p {
        font-family: 'JetBrains Mono', monospace !important; 
        font-weight: 700;
        font-size: 11px;
        margin: 0;
        color: #52525B; 
        text-transform: uppercase !important; 
        letter-spacing: 1.5px; 
        white-space: nowrap;
    }
    
    div[role="radiogroup"] label:hover { background-color: #18181B; cursor: pointer; }
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #18181B;
        border: 1px solid #3F3F46;
        box-shadow: 0 0 25px rgba(255, 255, 255, 0.05);
    }
    div[role="radiogroup"] label[data-checked="true"] > div[data-testid="stMarkdownContainer"] > p { color: #FAFAFA; }

    /* DROPDOWN */
    div[data-baseweb="select"] > div {
        background-color: #09090B !important;
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

    /* CARDS & ROWS */
    .hud-card {
        background: linear-gradient(180deg, rgba(24, 24, 27, 0.4) 0%, rgba(9, 9, 11, 0.4) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    .hud-val { font-family: 'JetBrains Mono', monospace; font-size: 32px; font-weight: 700; color: #FAFAFA; letter-spacing: -1.5px; }
    .hud-label { font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: #52525B; margin-top: 8px; font-weight: 700; }

    .clinical-row {
        background: rgba(15, 15, 17, 0.6);
        border-left: 2px solid #333;
        padding: 16px 20px;
        margin-bottom: 8px;
        border-radius: 0px 8px 8px 0px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border: 1px solid rgba(255,255,255,0.02);
    }
    .c-marker { font-family: 'Inter', sans-serif; font-weight: 500; font-size: 14px; color: #D4D4D8; letter-spacing: 0.2px; }
    .c-sub { font-size: 11px; color: #52525B; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }
    .c-value { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 16px; }
    
    .section-header {
        font-family: 'JetBrains Mono', monospace; 
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 2px;
        color: #3F3F46;
        margin-bottom: 20px;
        border-bottom: 1px solid #18181B;
        padding-bottom: 8px;
        margin-top: 20px;
    }
    
    div.stButton > button { width: 100%; border-radius: 8px; font-family: 'Inter', sans-serif; font-weight: 600; background: #18181B; border: 1px solid #27272A; color: #A1A1AA; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA ENGINE ---
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

# --- UPDATED CLEANER (HANDLES "µ" and "PSA" issues) ---
def clean_numeric_value(val):
    if pd.isna(val) or val == "": return None
    # Convert to string and handle standard replacements
    s = str(val).strip().replace(',', '').replace(' ', '')
    # Handle the specific µ symbol which often breaks things
    s = s.replace('µ', 'u').replace('ug/L', '').replace('ng/mL', '')
    
    # Remove inequality signs
    s = s.replace('<', '').replace('>', '')
    
    # Find the number
    match = re.search(r"[-+]?\d*\.\d+|\d+", s)
    if match:
        try: return float(match.group())
        except: return None
    return None

@st.cache_data(ttl=5)
def load_data():
    client = get_google_sheet_client()
    if not client: return None, None, None, "Auth Failed"
    try:
        sh = client.open(SHEET_NAME)
        
        try:
            ws_master = sh.worksheet("Master")
            m_data = ws_master.get_all_values()
            master = pd.DataFrame(m_data[1:], columns=m_data[0]) if len(m_data) > 1 else pd.DataFrame()
        except:
            master = pd.DataFrame() 

        try:
            ws_res = sh.worksheet("Results")
            data = ws_res.get_all_values()
            results = pd.DataFrame(data[1:], columns=data[0])
            results.columns = [c.strip() for c in results.columns] 
            
            # Deduplicate
            results = results.drop_duplicates(subset=['Date', 'Marker', 'Value'])
            
            # Robust Date Parsing
            results['Date'] = pd.to_datetime(results['Date'], errors='coerce', dayfirst=True) 
            
            # Robust Number Cleaning
            results['NumericValue'] = results['Value'].apply(clean_numeric_value)
            
        except: results = pd.DataFrame()

        try:
            ws_ev = sh.worksheet("Events")
            ev_data = ws_ev.get_all_values()
            events = pd.DataFrame(ev_data[1:], columns=ev_data[0])
            events['Date'] = pd.to_datetime(events['Date'], errors='coerce', dayfirst=True)
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

def process_csv_upload(uploaded_file):
    try:
        try: df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
            
        col_map = {'Biomarker': 'Marker', 'Test': 'Marker', 'Name': 'Marker', 'Result': 'Value', 'Reading': 'Value', 'Time': 'Date', 'Collected': 'Date'}
        df = df.rename(columns=col_map)
        
        db_columns = ['Marker', 'Value', 'Unit', 'Flag', 'Date', 'Source']
        for col in db_columns:
            if col not in df.columns: df[col] = "" 
            
        df_final = df[db_columns]
        
        client = get_google_sheet_client()
        sh = client.open(SHEET_NAME)
        try: ws = sh.worksheet("Results")
        except: ws = sh.add_worksheet("Results", 1000, 10); ws.append_row(db_columns)

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

        if s_min > 0 and val < s_min: return "OUT OF RANGE", "#F87171", "c-red", rng_str, 1
        if s_max > 0 and val > s_max: return "OUT OF RANGE", "#F87171", "c-red", rng_str, 1
        
        has_optimal = (o_min > 0 or o_max > 0)
        check_min = o_min if o_min > 0 else s_min
        check_max = o_max if o_max > 0 else s_max
        if has_optimal and val >= check_min and val <= check_max: return "OPTIMAL", "#22D3EE", "c-blue", rng_str, 3
        return "IN RANGE", "#34D399", "c-green", rng_str, 4
    except: return "ERROR", "#71717A", "c-grey", "Error", 5

# --- 6. CINEMATIC CHART ENGINE (RED ZONES + HIGH VIS EVENTS) ---
def plot_clinical_trend(marker_name, results_df, events_df, master_df):
    clean_target = smart_clean(marker_name)
    results_df['MatchKey'] = results_df['Marker'].apply(smart_clean)
    chart_data = results_df[results_df['MatchKey'] == clean_target].copy()
    chart_data = chart_data.dropna(subset=['NumericValue', 'Date']).sort_values('Date')
    
    if chart_data.empty: return "EMPTY"

    # Range
    min_val, max_val = 0, 0
    master_row = fuzzy_match(marker_name, master_df)
    if master_row is not None:
        min_val, max_val = parse_range(master_row['Standard Range'])

    # Y-Axis padding calculation to ensure Red Zones are visible
    data_max = chart_data['NumericValue'].max()
    y_top = max(data_max, max_val) * 1.2
    y_bottom = 0

    # 1. Base
    base = alt.Chart(chart_data).encode(
        x=alt.X('Date:T', title=None, axis=alt.Axis(
            format='%d %b %y', 
            labelColor='#71717A', 
            labelFont='JetBrains Mono',
            tickColor='#27272A', 
            domain=False, 
            gridColor='#27272A',
            gridOpacity=0.2
        )),
        y=alt.Y('NumericValue:Q', title=None, scale=alt.Scale(domain=[y_bottom, y_top]), axis=alt.Axis(
            labelColor='#71717A', 
            labelFont='JetBrains Mono',
            tickColor='#27272A', 
            domain=False, 
            gridColor='#27272A',
            gridOpacity=0.2
        ))
    )

    # 2. RED DANGER ZONES (The fix for "Danger")
    # Low Danger Zone (0 to min_val)
    danger_low = alt.Chart(pd.DataFrame({'y': [0], 'y2': [min_val]})).mark_rect(
        color='#EF4444', opacity=0.1 # Red
    ).encode(y='y', y2='y2') if min_val > 0 else None

    # High Danger Zone (max_val to Top)
    danger_high = alt.Chart(pd.DataFrame({'y': [max_val], 'y2': [y_top]})).mark_rect(
        color='#EF4444', opacity=0.1 # Red
    ).encode(y='y', y2='y2') if max_val > 0 else None

    # 3. Chart Line
    theme_color = '#38BDF8'
    glow = base.mark_line(color=theme_color, strokeWidth=8, opacity=0.2, interpolate='monotone')
    line = base.mark_line(color=theme_color, strokeWidth=3, interpolate='monotone')
    
    area = base.mark_area(
        line=False,
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color=theme_color, offset=0), alt.GradientStop(color='rgba(0,0,0,0)', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        ),
        opacity=0.15,
        interpolate='monotone'
    )

    # 4. Interactive Points
    nearest = alt.selection(type='single', nearest=True, on='mouseover', fields=['Date'], empty='none')
    points = base.mark_circle(size=80, fill='#000000', stroke=theme_color, strokeWidth=2).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
    ).add_selection(nearest)

    # 5. Tooltips
    tooltips = base.mark_circle(opacity=0).encode(
        tooltip=[
            alt.Tooltip('Date:T', format='%d %b %Y'),
            alt.Tooltip('NumericValue:Q', title=marker_name),
            alt.Tooltip('Source')
        ]
    ).add_selection(nearest)

    # 6. HIGH-VIS EVENTS (The fix for "Clear Interventions")
    event_layer = None
    if not events_df.empty:
        # Thick Orange Line
        ev_rule = alt.Chart(events_df).mark_rule(
            color='#F97316', strokeWidth=2, strokeDash=[4,4], opacity=0.8
        ).encode(x='Date:T')
        
        # Big Orange Bubble
        ev_bubble = alt.Chart(events_df).mark_point(
            filled=True, fill='#09090B', stroke='#F97316', size=1500, shape='circle', strokeWidth=2
        ).encode(x='Date:T', y=alt.value(30)) 

        # Bold Label inside bubble
        ev_text = alt.Chart(events_df).mark_text(
            align='center', baseline='middle',
            color='#F97316', font='JetBrains Mono', fontSize=11, fontWeight=800, dy=0
        ).encode(x='Date:T', y=alt.value(30), text='Event')
        
        event_layer = ev_rule + ev_bubble + ev_text

    # Assemble
    final = glow + area + line + points + tooltips
    if danger_low: final = danger_low + final
    if danger_high: final = danger_high + final
    if event_layer: final = final + event_layer
    
    return final.properties(height=320, background='transparent').configure_view(strokeWidth=0)

# --- 7. MAIN APP ---
master_df, results_df, events_df, status = load_data()

# HEADER
st.markdown("""
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1E1E20; padding-bottom:15px; margin-bottom:20px;">
    <div>
        <h2 style="margin:0; font-family:'Inter'; font-weight:700; letter-spacing:-0.5px; font-size:20px;">HealthOS <span style="color:#52525B; font-weight:400;">PRO</span></h2>
    </div>
    <div style="text-align:right;">
         <span class="tag" style="background:#0F172A; color:#38BDF8; border:1px solid #0EA5E9;">PATIENT: DEMO</span>
    </div>
</div>
""", unsafe_allow_html=True)

# TOP NAVIGATION (CAPS FORCED)
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
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#22D3EE">{stats['Blue']}</div><div class="hud-label">OPTIMAL</div></div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#34D399">{stats['Green']}</div><div class="hud-label">NORMAL</div></div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#FBBF24">{stats['Orange']}</div><div class="hud-label">BORDERLINE</div></div>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="hud-card"><div class="hud-val" style="color:#F87171">{stats['Red']}</div><div class="hud-label">ABNORMAL</div></div>""", unsafe_allow_html=True)
    
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
        if chart == "EMPTY":
            st.warning(f"No valid numeric data found for {m}.")
        elif chart: 
            st.altair_chart(chart, use_container_width=True)
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
