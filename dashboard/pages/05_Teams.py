"""F1 Teams Grid View."""

import streamlit as st
from utils.theme import apply_global_theme

from utils.theme import apply_global_theme

apply_global_theme()
st.markdown('<h1 class="main-header">🏎️ Constructor Teams</h1>', unsafe_allow_html=True)
st.markdown("Explore the 2026 Grid.")
st.divider()

teams_data = [
    {"name": "Red Bull Racing", "chassis": "RB20", "border": "border-rbr", "drivers": ["VER", "LAW"]},
    {"name": "Mercedes", "chassis": "W17", "border": "border-mer", "drivers": ["RUS", "ANTONELLI"]},
    {"name": "Ferrari", "chassis": "SF-26", "border": "border-fer", "drivers": ["LEC", "HAM"]},
    {"name": "McLaren", "chassis": "MCL40", "border": "border-mcl", "drivers": ["NOR", "PIA"]},
    {"name": "Aston Martin", "chassis": "AMR26", "border": "border-ast", "drivers": ["ALO", "STR"]},
    {"name": "Alpine", "chassis": "A526", "border": "", "drivers": ["GAS", "DOO"]},
    {"name": "Williams", "chassis": "FW48", "border": "", "drivers": ["ALB", "SAI"]},
    {"name": "Haas", "chassis": "VF-25", "border": "", "drivers": ["OAR", "BEA"]},
    {"name": "RB", "chassis": "VCARB 02", "border": "", "drivers": ["TSU", "HAD"]},
    {"name": "Audi", "chassis": "R26", "border": "", "drivers": ["HUL", "BOR"]},
    {"name": "Cadillac", "chassis": "TBC", "border": "", "drivers": ["TBC", "TBC"]},
]

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

# Create chunks of 4 for the grid rows
for i in range(0, len(teams_data), 4):
    cols = st.columns(4)
    chunk = teams_data[i:i+4]
    for j, team in enumerate(chunk):
        with cols[j]:
            # Map team names to exact folder names
            folder_name_map = {
                "Red Bull Racing": "Red Bull Racing",
                "Mercedes": "Mercedes",
                "Ferrari": "Ferrari",
                "McLaren": "McLaren",
                "Aston Martin": "Aston Martin",
                "Alpine": "Alpine",
                "Williams": "Williams",
                "Haas": "Haas F1 Team",
                "RB": "Racing Bulls",
                "Audi": "Audi",
                "Cadillac": "Cadillac"
            }
            team_folder = ASSETS_DIR / "Teams" / folder_name_map.get(team['name'], team['name'])
            
            car_path, logo_path, drv1_path, drv2_path = None, None, None, None
            if team_folder.exists():
                car_files = list(team_folder.glob("*car*.*"))
                logo_files = list(team_folder.glob("*logo*.*"))
                if car_files: car_path = car_files[0]
                if logo_files: logo_path = logo_files[0]
                
                # Simple heuristic for drivers: any file that isn't car or logo
                # and contains part of the driver's name or code
                drv_files = [f for f in team_folder.glob("*.*") if "car" not in f.name.lower() and "logo" not in f.name.lower()]
                if len(drv_files) >= 2:
                    drv1_path, drv2_path = drv_files[0], drv_files[1]
                elif len(drv_files) == 1:
                    drv1_path = drv_files[0]

            car_b64 = get_image_as_base64(car_path) if car_path else None
            logo_b64 = get_image_as_base64(logo_path) if logo_path else None
            drv1_b64 = get_image_as_base64(drv1_path) if drv1_path else None
            drv2_b64 = get_image_as_base64(drv2_path) if drv2_path else None
            
            # HTML generation
            logo_html = f'<img src="{logo_b64}" style="height: 30px; object-fit: contain; margin-bottom: 0.5rem;" />' if logo_b64 else ''
            
            if car_b64:
                car_html = f'<div style="text-align: center; margin: 1rem 0;"><img src="{car_b64}" style="width: 100%; max-height: 120px; object-fit: contain;" /></div>'
            else:
                car_html = f'<div style="text-align: center; margin: 2rem 0; opacity: 0.3;">🖼️<br><small>Awaiting {team["chassis"]} Asset</small></div>'
            
            def render_driver_badge(name, b64):
                if b64:
                    return f'<span class="season-badge"><img src="{b64}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; object-position: top; margin-right: 4px;" /> {name}</span>'
                return f'<span class="season-badge">{name}</span>'
            
            st.markdown(f"""
            <div class="f1-card {team['border']}" style="min-height: 240px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <h3 style="margin-bottom: 0;">{team['name']}</h3>
                            <p style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0;">{team['chassis']}</p>
                        </div>
                        {logo_html}
                    </div>
                </div>
                
                {car_html}
                
                <div style="display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: auto;">
                    {render_driver_badge(team['drivers'][0], drv1_b64)}
                    {render_driver_badge(team['drivers'][1], drv2_b64)}
                </div>
            </div>
            """, unsafe_allow_html=True)

