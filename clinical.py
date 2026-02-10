import streamlit as st
import pandas as pd
import altair as alt
import re
from difflib import SequenceMatcher
from io import StringIO

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="HealthOS Pro", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

# --- 2. SESSION STATE ---
if 'data' not in st.session_state:
    st.session_state['data'] = pd.DataFrame(columns=['Date', 'Marker', 'Value', 'Unit'])
if 'events' not in st.session_state:
    st.session_state['events'] = pd.DataFrame(columns=['Date', 'Event', 'Type', 'Notes'])

# --- 3. STYLING ---
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

# --- 4. DATA LOGIC ---
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

def get_data():
    results = st.session_state['data'].copy()
    events = st.session_state['events'].copy()
    
    if not results.empty:
        results['Date'] = results['Date'].apply(parse_flexible_date)
        results['CleanMarker'] = results['Marker'].apply(clean_marker_name)
        results['NumericValue'] = results['Value'].apply(clean_numeric_value)
        # Deduplicate
        results['Fingerprint'] = results['Date'].astype(str) + "_" + results['CleanMarker'] + "_" + results['NumericValue'].astype(str)
        results = results.drop_duplicates(subset=['Fingerprint'], keep='last')
    
    if not events.empty:
        events['Date'] = events['Date'].apply(parse_flexible_date)
        
    return results, events

def process_upload(uploaded_file):
    try:
        try: df_new = pd.read_csv(uploaded_file, sep=None, engine='python')
        except:
            uploaded_file.seek(0)
            df_new = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
        
        with st.expander("🔍 Debug: View Raw Upload", expanded=True):
            st.dataframe(df_new.head())

        df_new.columns = df_new.columns.str.strip().str.lower()
        rename_dict = {}
        for c in df_new.columns:
            if any(x in c for x in ['marker', 'biomarker', 'test', 'name', 'analyte']): rename_dict[c] = 'Marker'
            elif any(x in c for x in ['result', 'reading', 'value', 'concentration']): rename_dict[c] = 'Value'
            elif any(x in c for x in ['time', 'collected', 'date']): rename_dict[c] = 'Date'
            elif any(x in c for x in ['unit']): rename_dict[c] = 'Unit'

        df_new = df_new.rename(columns=rename_dict)
        needed = ['Date', 'Marker', 'Value']
        missing = [x for x in needed if x not in df_new.columns]
        if missing: return f"❌ Missing columns: {missing}. Found: {df_new.columns.tolist()}", 0

        if 'Unit' not in df_new.columns: df_new['Unit'] = ""
        df_new = df_new[needed + ['Unit']]
        st.session_state['data'] = pd.concat([st.session_state['data'], df_new], ignore_index=True)
        return "Success", len(df_new)

    except Exception as e: return f"Error: {str(e)}", 0

def add_clinical_event(date, name, type, note):
    new_event = pd.DataFrame([{"Date": str(date), "Event": name, "Type": type, "Notes": note}])
    st.session_state['events'] = pd.concat([st.session_state['events'], new_event], ignore_index=True)

def wipe_db():
    st.session_state['data'] = pd.DataFrame(columns=['Date', 'Marker', 'Value', 'Unit'])
    st.session_state['events'] = pd.DataFrame(columns=['Date', 'Event', 'Type', 'Notes'])

# --- 5. MASTER RANGES ---
def get_master_data():
    data = [
        ["Biomarker", "Standard Range", "Optimal Min", "Optimal Max", "Unit", "Fuzzy Match Keywords"],
        ["Total Testosterone", "264-916", "600", "1000", "ng/dL", "TOTAL TESTOSTERONE, TOTAL T, TESTOSTERONE"],
        ["Free Testosterone", "8.7-25.1", "15", "25", "pg/mL", "FREE TESTOSTERONE, FREE T, F-TESTO"],
        ["Haematocrit", "38.3-48.6", "40", "50", "%", "HCT, HEMATOCRIT, PCV"],
        ["Oestradiol", "7.6-42.6", "20", "35", "pg/mL", "E2, ESTRADIOL, 17-BETA"],
        ["PSA", "0-4.0", "0", "2.5", "ng/mL", "PROSTATE SPECIFIC ANTIGEN"],
        ["LDL Cholesterol", "0-100", "0", "90", "mg/dL", "LDL, BAD CHOLESTEROL"],
        ["Ferritin", "30-400", "50", "150", "ug/L", "FERRITIN"]
    ]
    return pd.DataFrame(data[1:], columns=data[0])

# --- 6. UTILS (STRICT MATCHING) ---
def fuzzy_match(marker, master):
    lab_clean = clean_marker_name(marker)
    # 1. Exact Match First
    for _, row in master.iterrows():
        keywords = [clean_marker_name(k) for k in str(row['Fuzzy Match Keywords']).split(",")]
        if lab_clean in keywords: return row
    # 2. Strict Fuzzy
    best_row, best_score = None, 0.0
    for _, row in master.iterrows():
        keywords = [clean_marker_name(k) for k in str(row['Fuzzy Match Keywords']).split(",")]
        for key in keywords:
            score = SequenceMatcher(None, lab_clean, key).ratio()
            if score > best_score: best_score, best_row = score, row
    return best_row if best_score > 0.85 else None # High threshold for accuracy

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

# --- 7. CHART ENGINE (FLATTENED) ---
def calculate_stagger(events_df, days_threshold=20):
    if events_df.empty: return events_df
    events_df = events_df.sort_values('Date').copy()
    events_df['lane'] = 0
    lane_end_dates = {}
    safe_min = pd.Timestamp("1900-01-01")
    for idx, row in events_df.iterrows():
        current_date = row['Date']
        assigned = False
        lane = 0
        while not assigned:
            last_date = lane_end_dates.get(lane, safe_min)
            if (current_date - last_date).days > days_threshold:
                events_df.at[idx, 'lane'] = lane
                lane_end_dates[lane] = current_date
                assigned = True
            else: lane += 1
    # Scale 0-10
    events_df['y_top'] = 9.5 - (events_df['lane'] * 1.5)
    events_df['y_bottom'] = events_df['y_top'] - 1.0
    events_df['y_text'] = events_df['y_top'] - 0.5
    return events_df

def plot_chart(marker, results, events, master):
    df = results[results['CleanMarker'] == clean_marker_name(marker)].copy()
    df = df.dropna(subset=['NumericValue', 'Date']).sort_values('Date')
    if df.empty: return None

    # Params
    min_date, max_date = df['Date'].min(), df['Date'].max()
    date_span = (max_date - min_date).days
    if date_span < 10: date_span = 30
    
    min_val, max_val = 0, 0
    m_row = fuzzy_match(marker, master)
    if m_row is not None: min_val, max_val = parse_range(m_row['Standard Range'])
    d_max = df['NumericValue'].max()
    y_top = max(d_max, max_val) * 1.2

    # --- UNIVERSE 1: CLINICAL DATA ---
    base = alt.Chart(df).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %y', labelColor='#71717A', tickColor='#27272A', domain=False, grid=False)),
        y=alt.Y('NumericValue:Q', scale=alt.Scale(domain=[0, y_top]), axis=alt.Axis(labelColor='#71717A', tickColor='#27272A', domain=False, gridColor='#27272A', gridOpacity=0.2))
    )

    danger_low = alt.Chart(pd.DataFrame({'y':[0], 'y2':[min_val]})).mark_rect(color='#EF4444', opacity=0.1).encode(y='y', y2='y2') if min_val>0 else None
    optimal_band = alt.Chart(pd.DataFrame({'y':[min_val], 'y2':[max_val]})).mark_rect(color='#10B981', opacity=0.1).encode(y='y', y2='y2') if max_val>0 else None
    danger_high = alt.Chart(pd.DataFrame({'y':[max_val], 'y2':[y_top]})).mark_rect(color='#EF4444', opacity=0.1).encode(y='y', y2='y2') if max_val>0 else None
    blood_dates = base.mark_rule(color='#38BDF8', strokeDash=[2, 2], strokeWidth=1, opacity=0.3).encode(x='Date:T')
    glow = base.mark_line(color='#38BDF8', strokeWidth=8, opacity=0.2, interpolate='monotone')
    line = base.mark_line(color='#38BDF8', strokeWidth=3, interpolate='monotone')
    nearest = alt.selection(type='single', nearest=True, on='mouseover', fields=['Date'], empty='none')
    points = base.mark_circle(size=80, fill='#000000', stroke='#38BDF8', strokeWidth=2).encode(opacity=alt.condition(nearest, alt.value(1), alt.value(0))).add_selection(nearest)
    tooltips = base.mark_circle(opacity=0).encode(tooltip=[alt.Tooltip('Date:T', format='%d %b %Y'), alt.Tooltip('NumericValue:Q', title=marker)])

    clinical_layers = []
    if danger_low: clinical_layers.append(danger_low)
    if optimal_band: clinical_layers.append(optimal_band)
    if danger_high: clinical_layers.append(danger_high)
    clinical_layers.extend([blood_dates, glow, line, points, tooltips])
    
    # Create the "Clinical Layer" object
    chart_clinical = alt.layer(*clinical_layers)

    # --- UNIVERSE 2: EVENT DATA ---
    if not events.empty:
        staggered_events = calculate_stagger(events, days_threshold=int(date_span*0.15))
        box_width_days = max(15, int(date_span * 0.12))
        staggered_events['start'] = staggered_events['Date'] - pd.to_timedelta(box_width_days/2, unit='D')
        staggered_events['end'] = staggered_events['Date'] + pd.to_timedelta(box_width_days/2, unit='D')

        # Dotted Line (Uses Pixel height, so safe)
        ev_rule = alt.Chart(staggered_events).mark_rule(color='#EF4444', strokeWidth=1, strokeDash=[4, 4], opacity=0.5).encode(
            x='Date:T', y=alt.value(0), y2=alt.value(350)
        )
        
        # Boxes (Scale 0-10)
        ev_box = alt.Chart(staggered_events).mark_rect(
            fill="#000000", stroke="#EF4444", strokeDash=[2, 2], strokeWidth=2, opacity=1
        ).encode(
            x='start:T', x2='end:T',
            y=alt.Y('y_top:Q', scale=alt.Scale(domain=[0, 10]), axis=None),
            y2=alt.Y('y_bottom:Q', scale=alt.Scale(domain=[0, 10]), axis=None)
        )
        
        # Text (Scale 0-10)
        ev_txt = alt.Chart(staggered_events).mark_text(
            align='center', baseline='middle', color='#EF4444', font='JetBrains Mono', fontSize=10, fontWeight=700
        ).encode(
            x='Date:T',
            y=alt.Y('y_text:Q', scale=alt.Scale(domain=[0, 10]), axis=None),
            text='Event'
        )
        
        # Create the "Event Layer" object
        chart_events = alt.layer(ev_rule, ev_box, ev_txt)
        
        # MERGE with Independent Scales
        return alt.layer(chart_clinical, chart_events).resolve_scale(y='independent').properties(height=320, background='transparent').configure_view(strokeWidth=0)

    # Fallback if no events
    return chart_clinical.properties(height=320, background='transparent').configure_view(strokeWidth=0)

# --- 8. UI ---
master = get_master_data()
results, events = get_data()

st.markdown("""<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333; padding-bottom:10px; margin-bottom:10px;">
    <div><h2 style="margin:0; font-family:'Inter'; font-weight:700; letter-spacing:-1px;">HealthOS <span style="color:#71717A;">PRO</span></h2></div>
    <div><span class="tag" style="background:#064E3B; color:#34D399; border:1px solid #059669;">PATIENT: DEMO</span></div></div>""", unsafe_allow_html=True)

nav = st.radio("NAV", ["DASHBOARD", "TREND ANALYSIS", "PROTOCOL LOG", "DATA TOOLS"], horizontal=True, label_visibility="collapsed")

if nav == "DASHBOARD":
    if results.empty: st.info("No Data loaded. Go to 'DATA TOOLS' to upload CSV."); st.stop()
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
    defaults = [m for m in ['TOTAL TESTOSTERONE', 'HAEMATOCRIT', 'PSA', 'FERRITIN', 'LDL CHOLESTEROL'] if m in markers]
    sel = st.multiselect("Select Biomarkers", markers, default=defaults)
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
        with c3: t = st.selectbox("Type", ["Medication", "Lifestyle", "Procedure"])
        if st.form_submit_button("Add Event"):
            add_clinical_event(d, n, t, "")
            st.success("Added"); st.rerun()
    if not events.empty: st.dataframe(events, use_container_width=True)

elif nav == "DATA TOOLS":
    st.markdown('<div class="section-header">Data Pipeline</div>', unsafe_allow_html=True)
    up = st.file_uploader("Upload CSV", type=['csv'])
    if up and st.button("Process Batch"):
        msg, count = process_upload(up)
        if msg=="Success": st.success(f"Processed {count} rows. Please refresh."); st.rerun()
        else: st.error(msg)
        
    st.markdown("---")
    if st.button("⚠️ WIPE SESSION"):
        wipe_db()
        st.warning("Wiped."); st.rerun()
