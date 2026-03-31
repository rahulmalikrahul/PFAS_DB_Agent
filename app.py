import streamlit as st
import sqlite3
import pandas as pd
import requests
from bs4 import BeautifulSoup
from google import genai

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="BP Remediation Sentinel", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_status_code=True)

# --- 2. API CONFIGURATION ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("🚨 Missing GEMINI_API_KEY in Streamlit Secrets! Please add it in the Cloud deployment settings.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# --- 3. DATABASE ENGINE ---
DB_FILE = 'remediation.db'

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def run_query(query, params=()):
    try:
        with get_db_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

# --- 4. THE AGENT BRAINS ---
def agent_researcher(user_query, context_data):
    prompt = f"""
    You are a BP Environmental Compliance Expert. 
    Using the provided site data, answer the user's request professionally.
    
    SITE DATA:
    {context_data}
    
    USER REQUEST:
    {user_query}
    """
    try:
        response = client.models.generate_content(model="gemini-3-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

def agent_auditor(draft, raw_data):
    prompt = f"""
    You are a Regulatory Auditor. Compare the 'DRAFT REPORT' to the 'RAW SQL DATA'.
    Identify any numbers, dates, or chemicals in the draft that are NOT in the raw data.
    Rewrite the report to be 100% factually grounded.
    
    RAW SQL DATA: {raw_data}
    DRAFT REPORT: {draft}
    """
    try:
        response = client.models.generate_content(model="gemini-3-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 5. NATIVE PYTHON SCRAPER ---
def scrape_webpage(url):
    """Bypasses Linux dependency issues by using pure Python."""
    try:
        # Mask as a standard browser to prevent getting blocked
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract meaningful text, ignoring scripts and styles
        text_elements = soup.find_all(['h1', 'h2', 'h3', 'p', 'li'])
        content = "\n".join([elem.get_text(strip=True) for elem in text_elements])
        
        return content if content else "No readable text found on this page."
    except Exception as e:
        return f"Scraping failed: {str(e)}"

# --- 6. USER INTERFACE ---
st.sidebar.title("🛢️ BP Remediation Control")

# Load data for sidebar selection safely
df_sites = run_query("SELECT DISTINCT facility FROM sites")
all_sites = df_sites['facility'].tolist() if not df_sites.empty else []
selected_site = st.sidebar.selectbox("Select Facility Focus", ["All Sites"] + all_sites)

tab1, tab2, tab3 = st.tabs(["💬 AI Analysis", "📊 Dashboard", "🌐 Regulatory Scraper"])

# --- TAB 1: AI ANALYSIS ---
with tab1:
    st.subheader(f"Analysis for: {selected_site}")
    
    if selected_site == "All Sites":
        context_df = run_query("SELECT * FROM sites")
    else:
        context_df = run_query("SELECT * FROM sites WHERE facility = ?", (selected_site,))
    
    user_input = st.text_input("Ask the BP Agent (e.g., 'Summarize PFAS risks')")
    
    if user_input:
        if context_df.empty:
            st.warning("No data available to analyze.")
        else:
            with st.spinner("Generating Verified Report..."):
                raw_context = context_df.to_json()
                research_draft = agent_researcher(user_input, raw_context)
                final_report = agent_auditor(research_draft, raw_context)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info("💡 **Researcher Draft**")
                    st.write(research_draft)
                with col2:
                    st.success("✅ **Audited Compliance Report**")
                    st.write(final_report)

# --- TAB 2: DASHBOARD ---
with tab2:
    df = run_query("SELECT * FROM sites")
    if not df.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Sites", len(df))
        m2.metric("Active Phases", len(df[df['phase'].str.contains("Active", case=False, na=False)]))
        m3.metric("Last DB Update", str(df['updated'].max())[:10])
        
        st.write("### Remediation Status by Facility")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Database is empty or missing. Did you upload remediation.db?")

# --- TAB 3: SCRAPER ---
with tab3:
    st.subheader("External Regulatory Monitor")
    target_url = st.text_input("Enter URL (EPA or News link)", "https://www.epa.gov/pfas")
    
    if st.button("Extract Content"):
        with st.spinner("Scraping webpage..."):
            scraped_content = scrape_webpage(target_url)
            st.text_area("Extracted Text", scraped_content[:3000] + "\n\n...[Truncated for display]", height=300)
            
            if "Scraping failed" not in scraped_content:
                if st.button("Summarize this for BP Compliance"):
                    with st.spinner("Analyzing impact..."):
                        summary = agent_researcher("Summarize the regulatory impact of this text for BP:", scraped_content[:5000])
                        st.write(summary)