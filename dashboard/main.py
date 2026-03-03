"""Main Entrypoint for the Multipage F1 Dashboard."""

import streamlit as st
from utils.theme import apply_global_theme

# App configuration must be the first Streamlit command
st.set_page_config(
    page_title="Formula 1 Dashboard",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply our custom F1 Dark Theme
apply_global_theme()

st.markdown('<h1 class="main-header">Formula 1 Data Center</h1>', unsafe_allow_html=True)
st.markdown("Welcome to the unified intelligence dashboard. Navigate using the sidebar to explore 2026 data, historical analytics, and predictive modeling.", unsafe_allow_html=True)

# Main Dashboard Layout
from pathlib import Path
import base64

ASSETS_DIR = Path(__file__).parent / "assets"
hero_path = ASSETS_DIR / "hero_bg.jpg"

if hero_path.exists():
    with open(hero_path, "rb") as f:
        hero_b64 = base64.b64encode(f.read()).decode()
    st.markdown(f"""
    <div style="background-image: linear-gradient(rgba(11, 19, 46, 0.7), rgba(11, 19, 46, 1)), url(data:image/jpeg;base64,{hero_b64});
                background-size: cover; background-position: center; border-radius: 16px; padding: 3rem; margin-bottom: 2rem; border: 1px solid var(--border-color);">
        <h2 style="font-size: 2.5rem; margin-bottom: 0.5rem;">2026 Season Opener</h2>
        <p style="font-size: 1.2rem; color: #ddd;">The new era of regulations begins here.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background: rgba(20, 28, 54, 0.4); backdrop-filter: blur(16px); padding: 3rem; border-radius: 16px; 
                margin-bottom: 2rem; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 8px 32px rgba(0,0,0,0.3); position: relative; overflow: hidden;">
        <div style="position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle, rgba(0,210,190,0.1) 0%, rgba(20,28,54,0) 60%); pointer-events: none;"></div>
        <h2 style="font-size: 2.5rem; margin-bottom: 0.5rem; position: relative; z-index: 1;">2026 Season Opener</h2>
        <p style="font-size: 1.2rem; color: #8E96AD; position: relative; z-index: 1;">The new era of regulations begins here.</p>
    </div>
    """, unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

# Future: Replace with live dynamic queries
with col1:
    st.markdown("""
    <div class="f1-card border-rbr">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.5rem;">Current Leader</h4>
        <h2 style="margin-bottom: 0;">Max Verstappen</h2>
        <p style="color: var(--accent-blue); font-weight: bold; margin-top: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
            Red Bull Racing
        </p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="f1-card border-fer">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.5rem;">Last Race Winner</h4>
        <h2 style="margin-bottom: 0;">Charles Leclerc</h2>
        <p style="color: var(--accent-red); font-weight: bold; margin-top: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
            Ferrari
        </p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="f1-card" style="border-top: 3px solid white;">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.5rem;">Next Race</h4>
        <h2 style="margin-bottom: 0;">Bahrain GP</h2>
        <p style="color: #bbb; font-weight: bold; margin-top: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
            2026 Season Opener
        </p>
    </div>
    """, unsafe_allow_html=True)
