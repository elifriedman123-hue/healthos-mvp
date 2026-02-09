import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import altair as alt
import os
import re
from difflib import SequenceMatcher

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="HealthOS Clinical", layout="wide", initial_sidebar_state="expanded")

# --- 2. STYLING ---
st.markdown("""
    <style>
    /* Global Reset */
    [data-testid="stAppViewContainer"] { background-color: #000000; color: #F5F5F7; }
    [data-testid="stSidebar"] { background-color: #1C1C1E; border-right: 1px solid #2C2C2E; }
    
    /* Card Design */
    .glass-card { 
        background: rgba(28, 28, 30, 0.6); 
        backdrop-filter: blur(20px); 
        border: 1px solid rgba(255,255,255,0.1); 
        border-radius: 20px; 
        padding: 20px; 
        margin-bottom: 10px; 
        box-shadow: 0 4px 24px rgba(0,0,0,0.2); 
    }
    .marker-title { margin: 0; font-size: 16px; font-weight: 600; color: white; }
    .marker-value { margin: 0; font-size: 24px; font-weight: 700; }
    .marker-sub { margin-top: 4px; font-size: 11px; color: #8E8E93; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* Stat Grid */
    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; margin-bottom: 20px; }
    .stat-box { text-align: center; padding: 15px 5px; border-radius: 16px; background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255,255,255,0.05); }
    .stat-num { font-size: 24px; font-weight: 700; margin: 0; color: white; }
    .stat-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; opacity: 0.7; color: white; }
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

@st.cache_data(ttl=5)
def load_data():
    client = get_google_sheet_client()
    if not client: return None, None, None, "Auth Failed"
    try:
        sh = client.open(SHEET_NAME)
        
        try:
            ws_master = sh.worksheet("Master")
            m_data = ws_master.get_all_values()
            if len(m_data) > 1: master = pd.DataFrame(m_data[1:], columns=m_data[0])
            else: master = pd.DataFrame()
        except:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            master_path = os.path.join(current_dir, MASTER_FILE_LOCAL)
            if os.path.exists(master_path): master = pd.read_csv(master_path)
            else: master = pd.DataFrame()

        try:
            ws_res = sh.worksheet("Results")
            data = ws_res.get_all_values()
            results = pd.DataFrame(data[1:], columns=data[0])
            results['Date'] = pd.to_datetime(results['Date'], errors='coerce')
            results['NumericValue'] = pd.to_numeric(results['Value'], errors='coerce')
        except: results = pd.DataFrame()

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

def process_csv_upload(uploaded_file):
    try:
        try: df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
            
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

# --- 5. LOGIC & VISUALIZATION ---
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
    clean = re.sub(r'(?<=\d)\s(?=\d)', '', clean)
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

        # 1. Red (Out of Range)
        if s_min > 0 and val < s_min: return "OUT OF RANGE", "#FF3B30", "c-red", rng_str, 1
        if s_max > 0 and val > s_max: return "OUT OF RANGE", "#FF3B30", "c-red", rng_str, 1
        
        # 2. Orange (Borderline)
        higher_is_better = ["VITAMIND", "VITAMIN D", "DHEA", "TESTOSTERONE", "MAGNESIUM", "B12", "FOLATE", "HDL", "FERRITIN"]
        if any(x in clean_name for x in higher_is_better):
            if o_min > 0 and val < o_min: return "BORDERLINE", "#FF9500", "c-orange", rng_str, 2
        
        if "HDL" in clean_name and "NON" not in clean_name and val < 1.4:
            return "BORDERLINE", "#FF9500", "c-orange", rng_str, 2
            
        range_span = s_max - s_min
        buffer = range_span * 0.025 if range_span > 0 else 0
        if buffer > 0:
            if val < (s_min + buffer): return "BORDERLINE", "#FF9500", "c-orange", rng_str, 2
            if val > (s_max - buffer): return "BORDERLINE", "#FF9500", "c-orange", rng_str, 2

        # 3. Blue (Optimal)
        has_optimal = (o_min > 0 or o_max > 0)
        check_min = o_min if o_min > 0 else s_min
        check_max = o_max if o_max > 0 else s_max
        if has_optimal and val >= check_min and val <= check_max: return "OPTIMAL", "#007AFF", "c-blue", rng_str, 3
        
        # 4. Green (Normal)
        return "IN RANGE", "#34C759", "c-green", rng_str, 4
    except: return "ERROR", "#8E8E93", "c-grey", "Error", 5

# --- VISUALIZATION ENGINE (UPGRADED) ---
def plot_clinical_trend(marker_name, results_df, events_df, master_df):
    chart_data = results_df[results_df['Marker'] == marker_name].copy()
    if chart_data.empty: return None

    # Get Range for Reference Band
    min_val, max_val = 0, 0
    master_row = fuzzy_match(marker_name, master_df)
    if master_row is not None:
        min_val, max_val = parse_range(master_row['Standard Range'])

    # 1. Base Layer (The Data)
    base = alt.Chart(chart_data).encode(
        x=alt.X('Date:T', title=None, axis=alt.Axis(format='%d %b %Y', labelColor='#8E8E93', tickColor='#2C2C2E', domain=False)),
        y=alt.Y('NumericValue:Q', title=None, scale=alt.Scale(zero=False, padding=20), axis=alt.Axis(labelColor='#8E8E93', tickColor='#2C2C2E', domain=False)),
        tooltip=[
            alt.Tooltip('Date:T', format='%d %b %Y'),
            alt.Tooltip('NumericValue:Q', title=marker_name),
            alt.Tooltip('Source')
        ]
    )

    # 2. Reference Band (The "Safety Corridor")
    bands = alt.Chart(pd.DataFrame({'y': [min_val], 'y2': [max_val]})).mark_rect(
        color='#34C759', opacity=0.1
    ).encode(y='y', y2='y2') if max_val > 0 else None

    # 3. Gradient Area (The "Modern Look")
    area = base.mark_area(
        line={'color': '#007AFF'},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='#007AFF', offset=0), alt.GradientStop(color='rgba(0, 122, 255, 0)', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        ),
        interpolate='monotone',
        opacity=0.3
    )

    # 4. The Line (Thick & Smooth)
    line = base.mark_line(
        color='#007AFF', 
        strokeWidth=3, 
        interpolate='monotone'
    )

    # 5. The Points (Interactive White Dots)
    points = base.mark_circle(
        size=80, 
        fill='white', 
        stroke='#007AFF', 
        strokeWidth=2, 
        opacity=1
    )

    # 6. Events (Interventions)
    event_layer = None
    if not events_df.empty:
        # Vertical Rule
        rules = alt.Chart(events_df).mark_rule(
            color='#FF3B30', 
            strokeWidth=1.5, 
            strokeDash=[4,4]
        ).encode(
            x='Date:T', 
            tooltip=['Event', 'Notes']
        )
        
        # Text Label (Rotated & Styled)
        text = alt.Chart(events_df).mark_text(
            align='left', 
            baseline='middle', 
            dx=7, 
            dy=-100,
            color='#FF3B30', 
            angle=0,
            fontSize=11,
            fontWeight='bold'
        ).encode(
            x='Date:T', 
            text='Event'
        )
        event_layer = rules + text

    # Assemble Chart
    final_chart = line + points + area
    if bands: final_chart = bands + final_chart
    if event_layer: final_chart = final_chart + event_layer

    return final_chart.properties(height=350).configure_view(strokeWidth=0).interactive()

# --- 6. MAIN APP ---
master_df, results_df, events_df, status = load_data()

st.sidebar.header("👨‍⚕️ Clinical OS")
mode = st.sidebar.radio("Navigation", ["Patient Overview", "Trends (TRT View)", "Protocol Manager", "Data Ingestion"])

# MODE 1: PATIENT DASHBOARD
if mode == "Patient Overview":
    if results_df.empty: st.warning("No Data."); st.stop()
    
    unique_dates = sorted(results_df['Date'].dropna().unique(), reverse=True)
    date_options = [d.strftime('%Y-%m-%d') for d in unique_dates if pd.notna(d)]
    selected_label = st.selectbox("Select Lab Report:", date_options)
    
    snapshot = results_df[results_df['Date'].astype(str).str.startswith(selected_label)].copy()
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

    # Metrics Grid
    st.markdown("""<div class="stat-grid">""", unsafe_allow_html=True)
    metrics = [
        ("Total Tested", len(df_display), "white"), 
        ("Optimal", stats['Blue'], "#007AFF"), 
        ("Normal", stats['Green'], "#34C759"), 
        ("Borderline", stats['Orange'], "#FF9500"), 
        ("Abnormal", stats['Red'], "#FF3B30")
    ]
    grid_html = ""
    for l, v, c in metrics:
        grid_html += f"""<div class="stat-box"><div class="stat-num" style="color:{c};">{v}</div><div class="stat-label" style="color:{c};">{l}</div></div>"""
    st.markdown(grid_html + "</div>", unsafe_allow_html=True)
    
    st.divider()
    
    c_warn, c_good = st.columns(2)
    with c_warn:
        st.subheader("⚠️ Attention")
        bad_df = df_display[df_display['Priority'].isin([1, 2])].sort_values('Priority', ascending=True)
        if bad_df.empty: st.markdown("✅ No Issues")
        for _, r in bad_df.iterrows():
            st.markdown(f"""
            <div class="glass-card" style="border-left:4px solid {r['Color']}">
                <div class="marker-title">{r['Marker']}</div>
                <div class="marker-sub" style="color:{r['Color']}">{r['Status']} (Range: {r['Range']})</div>
                <div class="marker-value" style="color:{r['Color']}; text-align:right">{r['Value']}</div>
            </div>""", unsafe_allow_html=True)

    with c_good:
        st.subheader("✅ Optimized")
        good_df = df_display[df_display['Priority'].isin([3, 4])].sort_values('Priority', ascending=True)
        for _, r in good_df.iterrows():
            st.markdown(f"""
            <div class="glass-card" style="border-left:4px solid {r['Color']}">
                <div class="marker-title">{r['Marker']}</div>
                <div class="marker-sub" style="color:{r['Color']}">{r['Status']}</div>
                <div class="marker-value" style="color:{r['Color']}; text-align:right">{r['Value']}</div>
            </div>""", unsafe_allow_html=True)

# MODE 2: THE "TRT" TRENDS
elif mode == "Trends (TRT View)":
    if results_df.empty: st.warning("No Data."); st.stop()
    st.title("📈 Longitudinal Analysis")
    
    markers = sorted(results_df['Marker'].unique())
    defaults = [m for m in ["Total Testosterone", "Haematocrit", "Oestradiol"] if m in markers]
    selected_markers = st.multiselect("Select Biomarkers:", markers, default=defaults)
    
    for m in selected_markers:
        st.markdown(f"### {m}")
        # PASSING MASTER_DF FOR RANGES NOW
        chart = plot_clinical_trend(m, results_df, events_df, master_df)
        if chart: st.altair_chart(chart, use_container_width=True)
        st.divider()

# MODE 3: PROTOCOL MANAGER
elif mode == "Protocol Manager":
    st.title("⚡ Intervention Timeline")
    with st.form("event_form"):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: e_date = st.date_input("Date")
        with c2: e_name = st.text_input("Intervention")
        with c3: e_type = st.selectbox("Type", ["Medication", "Lifestyle", "Procedure"])
        e_note = st.text_area("Clinical Notes")
        if st.form_submit_button("Add to Timeline"):
            add_clinical_event(e_date, e_name, e_type, e_note)
            st.success("Event Logged"); st.rerun()

    if not events_df.empty: st.dataframe(events_df, use_container_width=True)

# MODE 4: DATA INGESTION
elif mode == "Data Ingestion":
    st.title("📂 Data Ingestion")
    up_file = st.file_uploader("Upload Lab CSV", type=['csv'])
    if up_file and st.button("Process Batch"):
        msg = process_csv_upload(up_file)
        if msg == "Success": st.success("Data Ingested"); st.rerun()
        else: st.error(msg)
            
    if st.button("⚠️ CLEAR ALL DATA"):
        clear_data()
        st.warning("Database Wiped."); st.rerun()
