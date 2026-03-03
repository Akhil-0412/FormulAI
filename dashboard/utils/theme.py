"""Global theme and CSS utilities for the F1 Dashboard."""

import streamlit as st

def apply_global_theme():
    """Injects the global CSS for the premium dark-mode dashboard."""
    
    st.markdown("""
        <style>
        /* Base Themes and Colors matching reference UI */
        :root {
            --bg-color-main: #0B132E;       /* Deep Navy Background */
            --bg-color-sidebar: #091024;    /* Slightly darker for sidebar */
            --bg-color-card: #141C36;       /* Elevated element color */
            --text-primary: #FFFFFF;
            --text-secondary: #8E96AD;
            --accent-red: #E80020;          /* Official Ferrari/Brand red */
            --accent-blue: #00D2BE;         /* Mercedes Teal */
            --border-color: rgba(255, 255, 255, 0.05);
            --border-radius: 12px;
        }

        /* Enforce Main Background Color */
        .stApp {
            background-color: var(--bg-color-main);
            color: var(--text-primary);
        }
        
        /* Enforce Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: var(--bg-color-sidebar) !important;
            border-right: 1px solid var(--border-color);
        }
        
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: var(--text-secondary);
            font-size: 1.1rem;
            font-weight: 500;
        }

        /* Typography */
        h1, h2, h3, h4, h5, h6 {
            color: var(--text-primary) !important;
            font-family: 'Inter', sans-serif !important;
        }
        
        .main-header {
            font-size: 2.5rem;
            font-weight: 800;
            margin-bottom: 1rem;
            letter-spacing: -0.5px;
        }
        
        /* Premium Glassmorphism Card Component */
        .f1-card {
            background: rgba(20, 28, 54, 0.4);
            border-radius: var(--border-radius);
            padding: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), box-shadow 0.3s ease, border-color 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .f1-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 1px;
            background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.2), rgba(255,255,255,0));
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .f1-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
            border-color: rgba(255, 255, 255, 0.25);
        }
        
        .f1-card:hover::before {
            opacity: 1;
        }

        /* Native metric cards override */
        div[data-testid="stMetric"] {
            background-color: var(--bg-color-card);
            padding: 1rem;
            border-radius: var(--border-radius);
            border: 1px solid var(--border-color);
        }
        
        div[data-testid="stMetricValue"] {
            font-size: 2rem !important;
            font-weight: 700 !important;
        }

        /* Custom Badges */
        .season-badge {
            background-color: rgba(255,255,255,0.05);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.85rem;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            border: 1px solid rgba(255,255,255,0.1);
            color: var(--text-secondary);
        }

        /* Team Color Variables for Dynamic Application */
        .border-rbr { border-top: 3px solid #0600EF; }
        .border-fer { border-top: 3px solid #E80020; }
        .border-mer { border-top: 3px solid #00D2BE; }
        .border-mcl { border-top: 3px solid #FF8700; }
        .border-ast { border-top: 3px solid #229971; }
        
        /* Hide default Streamlit top decoration */
        header[data-testid="stHeader"] {
            background-color: transparent !important;
        }
        
        /* Native Buttons */
        .stButton button {
            background-color: rgba(255,255,255,0.05);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            border-radius: 8px;
            transition: all 0.2s;
        }
        .stButton button:hover {
            background-color: rgba(255,255,255,0.1);
            border-color: rgba(255,255,255,0.2);
            color: white;
        }
        .stButton button[data-baseweb="button"][kind="primary"] {
            background-color: var(--accent-red);
            border-color: var(--accent-red);
            color: white;
        }
        .stButton button[data-baseweb="button"][kind="primary"]:hover {
            background-color: #ff1e3e;
            border-color: #ff1e3e;
        }

        </style>
    """, unsafe_allow_html=True)
