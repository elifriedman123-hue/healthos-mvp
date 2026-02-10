import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import altair as alt
import re
import os

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
    [data-testid="stAppViewContainer"] { background-color: #000000; color: #E4E4E7; font-family: 'Inter', sans-serif; }
    [data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    
    /* NAV BAR */
    div[role="radiogroup"] { background-color: #09090B; padding: 4px; border-radius: 12px; border: 1px solid #27272A; }
    div[role="radiogroup"] label { background-color: transparent; border: 1px solid transparent; border-radius: 8px; }
    div[role="radiogroup"] label:hover { background-color: #18181B; }
    div[role="radiogroup"] label[data-checked="true"] { background-color: #18181B; border: 1px solid #3F3F46; box-shadow: 0 0 25px rgba(255, 255, 255, 0.05); }
    div[role="radiogroup"] label > div[data-testid="stMarkdownContainer"] > p { font-family: 'JetBrains Mono'; font-size: 11px; color: #52525B; letter-spacing: 1.5px; }
    div[role="radiogroup"] label[data-checked="true"] > div[data-testid="stMarkdownContainer"] > p { color: #FAFAFA; }

    /* CARDS */
    .hud-card { background: linear-gradient(180deg, rgba(24, 24, 27, 0.4) 0%, rgba(9, 9, 11, 0.4) 100%); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 16px; padding: 20px; text-align: center; }
    .hud-val { font-family: 'JetBrains Mono'; font-size: 32px; font-weight: 700; color: #FAFAFA; letter-spacing: -1.5px; }
    .hud-label { font-family: 'JetBrains Mono'; font-size: 10px; letter-spacing: 1.5px; color: #52525B; margin-top: 8px; font-weight: 700; text-transform: uppercase; }

    /* ROWS */
    .clinical-row { background: rgba(15, 15, 17, 0.6); border-left: 2px solid #333; padding: 16px 20px; margin-bottom: 8px; border-radius: 0 8px 8px 0; border: 1px solid rgba(255,255,255,0.02); display: flex; justify-content: space-between; align-items: center; }
    .c-marker { font-family: 'Inter'; font-weight: 500; font-size: 14px; color: #D4D4D8; }
    .c-sub { font-size: 11px; color: #52525B; margin-top: 4px; font-family: 'JetBrains Mono'; }
    .c-value { font-family: 'JetBrains Mono'; font-weight: 700; font-size: 16px; }
    
    div.stButton > button { width: 100%; border-radius: 8px; font-family: 'Inter'; font-weight: 600; background: #18181B; border: 1px solid #27272A; color: #A1A1AA; }
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
            if isinstance(secret_value, str): creds_dict = json.loads(secret_value)
            else: creds_dict = secret_value
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except: return None
    return None

# --- ROBUST CLEANERS ---
def clean_numeric_value(val):
    if pd.isna(val) or str(val).strip() == "": return None
    s = str(val).strip().replace(',', '').replace(' ', '')
    s = s.replace('µ', 'u').replace('ug/L', '').replace('ng/mL', '').replace('mg/dL', '')
    s = s.replace('<', '').replace('>', '')
    match = re.search(r"[-+]?\d*\.\d+|\d+", s)
    if match:
        try: return float(match.group())
        except: return None
    return None

def clean_marker_name(val):
    if pd.isna(val): return ""
    return re.sub(r'^[SPBU]-\s*', '', str(val).upper().strip())

def parse_flexible_date(date_str):
    if pd.isna(date_str) or str(date_str).strip() == "": return pd.NaT
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y.%m.%d']
    for fmt in formats:
        try: return pd.to_datetime(date_str, format=fmt)
        except: continue
    return pd.to_datetime(date_str, errors='coerce')

# --- LOAD & SELF-HEAL ---
@st.cache_data(ttl=5)
def load_data():
    # SAFETY INIT: Always create empty DFs first
    master = pd.DataFrame()
    results = pd.DataFrame(columns=['Date', 'Marker', 'Value', 'NumericValue', 'CleanMarker'])
    events = pd.DataFrame(columns=['Date', 'Event'])
    
    client = get_google_sheet_client()
    if not client: return master, results, events, "Auth Failed"
    
    try:
        sh = client.open(SHEET_NAME)
        
        # Master
        try:
            ws_master = sh.worksheet("Master")
            m_data = ws_master.get_all_values()
            if len(m_data) > 1:
                master = pd.DataFrame(m_data[1:], columns=m_data[0])
        except: pass 

        # Results (With Self-Healing)
        try:
            ws_res = sh.worksheet("Results")
            data = ws_res.get_all_values()
            if len(data) > 1:
                results = pd.DataFrame(data[1:], columns=data[0])
                results.columns = [c.strip() for c in results.columns] 
                
                # 1. Parse & Clean
                results['DateObj'] = results['Date'].apply(parse_flexible_date)
                results['CleanMarker'] = results['Marker'].apply(clean_marker_name)
                results['NumericValue'] = results['Value'].apply(clean_numeric_value)
                
                # 2. FINGERPRINT & DEDUPLICATE
                results['Fingerprint'] = results['DateObj'].astype(str) + "_" + results['CleanMarker'] + "_" + results['NumericValue'].astype(str)
                results = results.drop_duplicates(subset=['Fingerprint'], keep='last')
                
                # 3. Finalize
                results['Date'] = results['DateObj']
        except: pass

        # Events
        try:
            ws_ev = sh.worksheet("Events")
            ev_data = ws_ev.get_all_values()
            if len(ev_data) > 1:
                events = pd.DataFrame(ev_data[1:], columns=ev_data[0])
                events['Date'] = events['Date'].apply(parse_flexible_date)
        except: 
            # Init Events if missing
            try:
                ws_ev = sh.add_worksheet("Events", 1000, 5)
                ws_ev.append_row(["Date", "Event", "Type", "Notes"])
            except: pass

        return master, results, events, "OK"
    except Exception as e: 
        return master, results, events, str(e)

# --- WRITE OPS ---
def add_clinical_event(date, event_name, event_type, notes):
    client = get_google_sheet_client()
    if not client: return
    try:
        sh = client.open(SHEET_NAME)
        try: ws = sh.worksheet("Events")
        except: ws = sh.add_worksheet("Events", 1000, 5)
        ws.append_row([str(date), event_name, event_type, notes])
        st.cache_data.clear()
    except: pass

def clear_data():
    client = get_google_sheet_client()
    if not client: return
    try:
        sh = client.open(SHEET_NAME)
        try: sh.worksheet("Results").clear(); sh.worksheet("Results").append_row(['Marker', 'Value', 'Unit', 'Flag', 'Date', 'Source'])
        except: pass
        try: sh.worksheet("Events").clear(); sh.worksheet("Events").append_row(["Date", "Event", "Type", "Notes"])
        except: pass
        st.cache_data.clear()
    except: pass

def process_csv_upload(uploaded_file):
    try:
        try: df_new = pd.read_csv(uploaded_file)
        except: uploaded_file.seek(0); df_new = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
            
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
        
        db_cols = ['Marker', 'Value', 'Unit', 'Flag', 'Date', 'Source']
        for c in db_cols: 
            if c not in df_new.columns: df_new[c] = ""
        df_new = df_new[db_cols]

        client = get_google_sheet_client()
        if not client: return "Auth Error"
        
        sh = client.open(SHEET_NAME)
        try: 
            ws = sh.worksheet("Results")
            existing = pd.DataFrame(ws.get_all_values()[1:], columns=db_cols)
        except: 
            ws = sh.add_worksheet("Results", 1000, 10); ws.append_row(db_cols)
            existing = pd.DataFrame(columns=db_cols)

        combined = pd.concat([existing, df_new], ignore_index=True)
        
        # Parse for Deduplication
        combined['clean_date'] = combined['Date'].apply(parse_flexible_date).astype(str)
        combined['clean_marker'] = combined['Marker'].apply(clean_marker_name)
        combined['clean_val'] = combined['Value'].apply(clean_numeric_value).astype(str)
        combined['fingerprint'] = combined['clean_date'] + combined['clean_marker'] + combined['clean_val']
        
        final = combined.drop_duplicates(subset=['fingerprint'], keep='last')
        final = final[db_cols] 
        
        ws.clear()
        ws.append_row(db_cols)
        ws.append_rows(final.astype(str).values.tolist())
        
        st.cache_data.clear()
        return "Success"
    except Exception as e: return f"Error: {str(e)}"

# --- UTILS ---
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
        
        if "PSA" in str(master_row['Biomarker']).upper() and val > 4: return "OUT OF RANGE", "#FF3B30", 1
        
        if s_min > 0 and (val < s_min or val > s_max): return "OUT OF RANGE", "#FF3B30", 1
        if (o_min > 0 and val < o_min) or (o_max > 0 and val > o_max): return "BORDERLINE", "#FF9500", 2
        if (o_min > 0 or o_max > 0): return "OPTIMAL", "#007AFF", 3
        return "IN RANGE", "#34C759", 4
    except: return "ERROR", "#8E8E93", 5

# --- CHARTING ---
def plot_chart(marker, results, events, master):
    df = results[results['CleanMarker'] == clean_marker_name(marker)].copy()
    df = df.dropna(subset=['NumericValue', 'Date']).sort_values('Date')
    if df.empty: return None

    min_val, max_val = 0, 0
    m_row = fuzzy_match(marker, master)
    if m_row is not None: min_val, max_val = parse_range(m_row['Standard Range'])
    
    d_max = df['NumericValue'].max()
    y_top = max(d_max, max_val) * 1.2

    base = alt.Chart(df).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%d %b %y', labelColor='#71717A', tickColor='#27272A', domain=False, grid=False)),
        y=alt.Y('NumericValue:Q', scale=alt.Scale(domain=[0, y_top]), axis=alt.Axis(labelColor='#71717A', tickColor='#27272A', domain=False, gridColor='#27272A', gridOpacity=0.2))
    )

    danger_low = alt.Chart(pd.DataFrame({'y':[0], 'y2':[min_val]})).mark_rect(color='#EF4444', opacity=0.1).encode(y='y', y2='y2') if min_val>0 else None
    danger_high = alt.Chart(pd.DataFrame({'y':[max_val], 'y2':[y_top]})).mark_rect(color='#EF4444', opacity=0.1).encode(y='y', y2='y2') if max_val>0 else None

    color = '#38BDF8'
    glow = base.mark_line(color=color, strokeWidth=8, opacity=0.2, interpolate='monotone')
    line = base.mark_line(color=color, strokeWidth=3, interpolate='monotone')
    area = base.mark_area(color=alt.Gradient(gradient='linear', stops=[alt.GradientStop(color, 0), alt.GradientStop('rgba(0,0,0,0)', 1)], x1=1, x2=1, y1=1, y2=0), opacity=0.2, interpolate='monotone')
    
    nearest = alt.selection(type='single', nearest=True, on='mouseover', fields=['Date'], empty='none')
    points = base.mark_circle(size=80, fill='#000000', stroke=color, strokeWidth=2).encode(opacity=alt.condition(nearest, alt.value(1), alt.value(0))).add_selection(nearest)
    
    tooltips = base.mark_circle(opacity=0).encode(tooltip=[alt.Tooltip('Date:T', format='%d %b %Y'), alt.Tooltip('NumericValue:Q', title=marker)])

    ev_layer = None
    if not events.empty:
        ev_rule = alt.Chart(events).mark_rule(color='#F97316', strokeWidth=2, strokeDash=[4,4]).encode(x='Date:T')
        ev_bub = alt.Chart(events).mark_point(filled=True, fill='#09090B', stroke='#F97316', size=1500, shape='circle').encode(x='Date:T', y=alt.value(30))
        ev_txt = alt.Chart(events).mark_text(color='#F97316', fontSize=10, fontWeight=700).encode(x='Date:T', y=alt.value(30), text='Event')
        ev_layer = ev_rule + ev_bub + ev_txt

    final = glow + area + line + points + tooltips
    if danger_low: final = danger_low + final
    if danger_high: final = danger_high + final
    if ev_layer: final = final + ev_layer
    
    return final.properties(height=300, background='transparent').configure_view(strokeWidth=0)

# --- 7. UI LOGIC ---
master, results, events, status = load_data()

# HEADER
st.markdown("""<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333; padding-bottom:10px; margin-bottom:10px;">
    <div><h2 style="margin:0; font-family:'Inter'; font-weight:700; letter-spacing:-1px;">HealthOS <span style="color:#71717A;">PRO</span></h2></div>
    <div><span class="tag" style="background:#064E3B; color:#34D399; border:1px solid #059669;">PATIENT: DEMO</span></div></div>""", unsafe_allow_html=True)

if status != "OK":
    st.error(f"⚠️ System Offline: {status}")
    st.info("Check your 'service_account.json' or Streamlit Secrets.")
    st.stop()

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
    sel = st.multiselect("Select Biomarkers", markers, default=[m for m in ['TOTAL TESTOSTERONE', 'HAEMATOCRIT', 'PSA', 'FERRITIN'] if m in markers])
    for m in sel:
        st.markdown(f"#### {m}")
        ch = plot_chart(m, results, events, master)
        if ch: st.altair_chart(ch, use_container_width=True)
        else: st.warning(f"No numeric data for {m}")

elif nav == "PROTOCOL LOG":
    with st.form("add_event"):
        c1, c2, c3 = st.columns([1,2,1])
        with c1: d = st.date_input("Date")
        with c2: n = st.text_input("Event Name")
        with c3: t = st.selectbox("Type", ["Medication", "Lifestyle"])
        if st.form_submit_button("Add Event"):
            add_clinical_event(d, n, t, "")
            st.success("Added"); st.rerun()
    if not events.empty: st.dataframe(events, use_container_width=True)

elif nav == "DATA TOOLS":
    st.markdown('<div class="section-header">Data Pipeline</div>', unsafe_allow_html=True)
    up = st.file_uploader("Upload CSV", type=['csv'])
    if up and st.button("Process"):
        msg = process_csv_upload(up)
        if msg=="Success": st.success("Done"); st.rerun()
        else: st.error(msg)
    if st.button("⚠️ WIPE DATABASE"):
        clear_data()
        st.warning("Wiped."); st.rerun()
