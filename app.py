import streamlit as st
import sqlite3
import pandas as pd
import requests
from bs4 import BeautifulSoup
from google import genai

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="BP Remediation Sentinel", layout="wide")

# FIX: Changed to st.html or corrected st.markdown syntax
st.html("""
    <style>
    .main { background-color: #f5f7f9; }
    [data-testid="stMetricValue"] {
        background-color: #ffffff; 
        padding: 10px; 
        border-radius: 10px; 
        border: 1px solid #e0e0e0;
        color: #00A1DE;
    }
    </style>
    """)

# --- 2. API CONFIGURATION ---
# Accessing secrets from the Streamlit Cloud dashboard
if "GEMINI_API_KEY" not in st.secrets:
    st.error("🚨 GEMINI_API_KEY not found in Secrets! Please add it in the Streamlit Cloud 'Advanced Settings'.")
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
        # Using Gemini 1.5 Flash for high speed and reliability
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"AI Research Error: {str(e)}"

def agent_auditor(draft, raw_data):
    prompt = f"""
    You are a Regulatory Auditor. Compare the 'DRAFT REPORT' to the 'RAW SQL DATA'.
    Identify any numbers, dates, or chemicals in the draft that are NOT in the raw data.
    Rewrite the report to be 100% factually grounded based ONLY on the raw data.
    
    RAW SQL DATA: {raw_data}
    DRAFT REPORT: {draft}
    """
    try:
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"AI Audit Error: {str(e)}"

# --- 5. NATIVE PYTHON SCRAPER (Streamlit Cloud Compatible) ---
def scrape_webpage(url):
    """Uses BeautifulSoup to extract text without needing Linux browser drivers."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) BP-Compliance-Agent/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pull text from headings and paragraphs
        text_elements = soup.find_all(['h1', 'h2', 'h3', 'p', 'li'])
        content = "\n".join([elem.get_text(strip=True) for elem in text_elements])
        
        return content if content else "No readable content found."
    except Exception as e:
        return f"Scraping Error: {str(e)}"

# --- 6. USER INTERFACE ---
st.sidebar.title("🛢️ BP Remediation Hub")

# Sidebar selection
df_sites = run_query("SELECT DISTINCT facility FROM sites")
all_sites = df_sites['facility'].tolist() if not df_sites.empty else []
selected_site = st.sidebar.selectbox("Focus Facility", ["All Sites"] + all_sites)

tab1, tab2, tab3 = st.tabs(["💬 AI Agent", "📊 Status Dashboard", "🌐 Web Scraper"])

# --- TAB 1: AI AGENT ---
with tab1:
    st.subheader(f"BP AI Analysis: {selected_site}")
    
    if selected_site == "All Sites":
        context_df = run_query("SELECT * FROM sites")
    else:
        context_df = run_query("SELECT * FROM sites WHERE facility = ?", (selected_site,))
    
    user_input = st.text_input("Ask the BP Agent (e.g., 'What are the current PFAS levels at Whiting?')")
    
    if user_input:
        if context_df.empty:
            st.warning("No database records found. Please ensure 'remediation.db' is uploaded.")
        else:
            with st.spinner("Agent is researching and auditing data..."):
                raw_json = context_df.to_json()
                
                # Double-Agent Workflow
                draft = agent_researcher(user_input, raw_json)
                audited_report = agent_auditor(draft, raw_json)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.info("📝 **AI Initial Draft**")
                    st.write(draft)
                with c2:
                    st.success("✔️ **Audited Compliance Report**")
                    st.write(audited_report)

# --- TAB 2: DASHBOARD ---
with tab2:
    df = run_query("SELECT * FROM sites")
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Facilities", len(df))
        col2.metric("Active Remediations", len(df[df['phase'].str.contains("Active", na=False)]))
        col3.metric("Database Version", "2026.Q1")
        
        st.write("### Facility Data Records")
        st.dataframe(df, use_container_width=True)
    else:
        st.error("The database file 'remediation.db' was not found or is empty.")

# --- TAB 3: WEB SCRAPER ---
with tab3:
    st.subheader("Regulatory Intelligence Scraper")
    url = st.text_input("Enter EPA or Regulatory URL", "https://www.epa.gov/pfas")
    
    if st.button("Scrape & Analyze"):
        with st.spinner("Fetching external data..."):
            scraped_text = scrape_webpage(url)
            
            if "Error" in scraped_text:
                st.error(scraped_text)
            else:
                st.write("### Scraped Content Preview")
                st.text_area("Source Markdown", scraped_text[:2000], height=200)
                
                with st.spinner("Gemini is summarizing impact..."):
                    summary = agent_researcher("Summarize the following regulatory text and its impact on BP:", scraped_text[:4000])
                    st.markdown("### 📋 AI Regulatory Summary")
                    st.write(summary)

st.sidebar.markdown("---")
st.sidebar.caption("BP Remediation Sentinel v3.1 | Python 3.14")