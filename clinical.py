import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import altair as alt
import os
from datetime import datetime

# --- 1. CONFIGURATION (CLINICAL DASHBOARD) ---
st.set_page_config(page_title="HealthOS Clinical", layout="wide", initial_sidebar_state="expanded")

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
            secret_value = st.secrets["gcp_service_account"]
            if isinstance(secret_value, str):
                creds_dict = json.loads(secret_value)
            else:
                creds_dict = secret_value
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except: return None
    else: return None

# --- 2. DATA ENGINE ---
SHEET_NAME = "HealthOS_DB"

@st.cache_data(ttl=5)
def load_data():
    client = get_google_sheet_client()
    if not client: return None, None, "Auth Failed"
    try:
        sh = client.open(SHEET_NAME)
        
        # 1. LAB RESULTS
        try:
            ws_res = sh.worksheet("Results")
            data = ws_res.get_all_values()
            results = pd.DataFrame(data[1:], columns=data[0])
            results['Date'] = pd.to_datetime(results['Date'], errors='coerce')
            results['NumericValue'] = pd.to_numeric(results['Value'], errors='coerce')
        except: results = pd.DataFrame()

        # 2. CLINICAL EVENTS (INTERVENTIONS)
        try:
            ws_ev = sh.worksheet("Events")
            ev_data = ws_ev.get_all_values()
            events = pd.DataFrame(ev_data[1:], columns=ev_data[0])
            events['Date'] = pd.to_datetime(events['Date'], errors='coerce')
        except: 
            # Auto-create if missing
            ws_ev = sh.add_worksheet("Events", 1000, 5)
            ws_ev.append_row(["Date", "Event", "Type", "Notes"])
            events = pd.DataFrame(columns=["Date", "Event", "Type", "Notes"])

        return results, events, "OK"
    except Exception as e: return None, None, str(e)

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

# --- 3. UPLOAD ENGINE (SMART ENCODING) ---
def process_csv_upload(uploaded_file):
    try:
        # 1. Try reading with standard UTF-8 first
        try:
            df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            # 2. If that fails (due to symbols like µ), try ISO-8859-1
            uploaded_file.seek(0) # Reset file pointer
            df = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
            
        # Basic validation
        req = ['Date', 'Marker', 'Value']
        if not all(col in df.columns for col in req): return "Invalid CSV Format: Missing Date, Marker, or Value columns"
        
        client = get_google_sheet_client()
        sh = client.open(SHEET_NAME)
        
        # Check if "Results" worksheet exists, create if not
        try:
            ws = sh.worksheet("Results")
        except:
            ws = sh.add_worksheet("Results", 1000, 10)
            ws.append_row(REQUIRED_COLUMNS)

        # Append to sheet
        # Convert df to list of lists and ensure all data is string converted to avoid serialization issues
        data_to_upload = df.astype(str).values.tolist()
        ws.append_rows(data_to_upload)
        st.cache_data.clear()
        return "Success"
    except Exception as e: return f"Error: {str(e)}"


# --- 4. VISUALIZATION ENGINE (FIXED) ---
def plot_clinical_trend(marker_name, results_df, events_df):
    # Filter data
    chart_data = results_df[results_df['Marker'] == marker_name].copy()
    if chart_data.empty: return None
    
    # Base Chart Definition
    base = alt.Chart(chart_data).encode(
        x=alt.X('Date:T', title='Timeline'),
        y=alt.Y('NumericValue:Q', title=marker_name),
        tooltip=['Date', 'Value', 'Source']
    )
    
    # 1. The Line (FIXED SYNTAX HERE)
    line = base.mark_line(
        color='#007AFF', 
        strokeWidth=3,
        point=alt.OverlayMarkDef(color='#007AFF', size=60) # Moved inside mark_line
    )

    # 2. Event Lines (Vertical Rules)
    if not events_df.empty:
        rules = alt.Chart(events_df).mark_rule(color='red', strokeWidth=2, strokeDash=[5,5]).encode(
            x='Date:T',
            tooltip=['Event', 'Notes']
        )
        
        # Labels for Events
        text = alt.Chart(events_df).mark_text(
            align='left', baseline='middle', dx=5, color='white', angle=270
        ).encode(
            x='Date:T',
            text='Event',
            y=alt.value(20) # Position at top
        )
        
        return (line + rules + text).properties(height=300).interactive()
    
    return line.properties(height=300).interactive()

# --- 5. MAIN APP ---
results_df, events_df, status = load_data()

st.sidebar.header("👨‍⚕️ Clinical OS")
mode = st.sidebar.radio("Mode", ["Patient View", "Protocol Manager", "Data Ingestion"])

if mode == "Data Ingestion":
    st.title("📂 Data Ingestion")
    st.markdown("Upload lab PDFs or bulk CSVs here.")
    
    up_file = st.file_uploader("Upload CSV (Demo Data)", type=['csv'])
    if up_file:
        if st.button("Process Batch"):
            msg = process_csv_upload(up_file)
            if msg == "Success": st.success("Data Ingested"); st.rerun()
            else: st.error(msg)
            
    if st.button("⚠️ CLEAR ALL DATA (Reset Demo)"):
        clear_data()
        st.warning("Database Wiped.")
        st.rerun()

elif mode == "Protocol Manager":
    st.title("⚡ Protocol & Intervention Timeline")
    
    # Input Form
    with st.form("event_form"):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: e_date = st.date_input("Date")
        with c2: e_name = st.text_input("Intervention (e.g., 'Started 100mg TRT')")
        with c3: e_type = st.selectbox("Type", ["Medication", "Lifestyle", "Procedure", "Note"])
        e_note = st.text_area("Clinical Notes")
        
        if st.form_submit_button("Add to Timeline"):
            add_clinical_event(e_date, e_name, e_type, e_note)
            st.success("Event Logged")
            st.rerun()

    st.divider()
    st.subheader("History")
    if not events_df.empty:
        st.dataframe(events_df, use_container_width=True)
    else:
        st.info("No interventions recorded yet.")

elif mode == "Patient View":
    if results_df.empty: st.warning("No Patient Data. Go to 'Data Ingestion' to upload CSV."); st.stop()
    
    st.title("📈 Longitudinal Analysis")
    
    # Filter for the "Big 3" TRT Markers (plus others)
    markers = sorted(results_df['Marker'].unique())
    # Default selection if available
    defaults = [m for m in ["Total Testosterone", "Haematocrit", "Oestradiol"] if m in markers]
    
    selected_markers = st.multiselect("Select Biomarkers to Track:", markers, default=defaults)
    
    for m in selected_markers:
        st.markdown(f"### {m}")
        chart = plot_clinical_trend(m, results_df, events_df)
        if chart:
            st.altair_chart(chart, use_container_width=True)
        st.divider()
