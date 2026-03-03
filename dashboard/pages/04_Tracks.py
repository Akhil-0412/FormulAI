import pandas as pd
from data.db import query_df
from utils.theme import apply_global_theme
import base64
from pathlib import Path

# Helper function to encode local image for HTML injection
def get_image_as_base64(path):
    if path and Path(path).exists():
        ext = Path(path).suffix.lower()
        mime = "image/png"
        if ext == ".avif":
            mime = "image/avif"
        elif ext in [".jpg", ".jpeg"]:
            mime = "image/jpeg"
        with open(path, "rb") as f:
            data = f.read()
            return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    return None

ASSETS_DIR = Path(__file__).parent.parent / "assets"

apply_global_theme()
st.markdown('<h1 class="main-header">🌍 Race Places</h1>', unsafe_allow_html=True)
st.markdown("Information about the iconic circuits on the calendar.")
st.divider()

df_tracks = query_df("SELECT DISTINCT circuit_name as Circuit, country as Country FROM races ORDER BY circuit_name")
if not df_tracks.empty:
    selected_track = st.selectbox("Select a Circuit", df_tracks['Circuit'].tolist())
    
    country = df_tracks[df_tracks['Circuit'] == selected_track]['Country'].iloc[0]
    
    # Search for matching track image in assets/Circuit
    circuit_dir = ASSETS_DIR / "Circuit"
    track_path = None
    if circuit_dir.exists():
        # Clean terms for matching
        search_terms = [
            country.lower().replace(" ", ""),
            selected_track.split()[0].lower().replace(" ", "")
        ]
        
        for f in circuit_dir.glob("*.*"):
            fname = f.name.lower()
            if any(term in fname for term in search_terms):
                track_path = f
                break
    
    track_b64 = get_image_as_base64(track_path) if track_path else None
    
    st.markdown(f"### {selected_track}, {country}")
    
    if track_b64:
        st.markdown(f'''
        <div style="background: rgba(20, 28, 54, 0.4); backdrop-filter: blur(16px); padding: 2rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 4px 20px rgba(0,0,0,0.2); text-align: center;">
            <img src="{track_b64}" style="max-width: 100%; height: auto; object-fit: contain; max-height: 400px; filter: drop-shadow(0px 10px 15px rgba(0,0,0,0.5));" />
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.info("Track map asset not found.")
        
    st.divider()
    st.dataframe(df_tracks, hide_index=True, use_container_width=True)
else:
    st.info("No track data available.")
