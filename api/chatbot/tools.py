from langchain_core.tools import tool

@tool
def get_2026_driver_lineup() -> str:
    """Returns the F1 2026 driver lineup and team affiliations. Useful for answering questions about who drives for which team."""
    return '''
    McLaren: Lando Norris (1) [DRV_NOR], Oscar Piastri (81) [DRV_PIA]
    Ferrari: Charles Leclerc (16) [DRV_LEC], Lewis Hamilton (44) [DRV_HAM]
    Red Bull Racing: Max Verstappen (3) [DRV_VER], Isack Hadjar (6) [DRV_HAD]
    Mercedes: George Russell (63) [DRV_RUS], Kimi Antonelli (12) [DRV_ANT]
    Aston Martin: Fernando Alonso (14) [DRV_ALO], Lance Stroll (18) [DRV_STR]
    Williams: Alex Albon (23) [DRV_ALB], Carlos Sainz (55) [DRV_SAI]
    Alpine: Pierre Gasly (10) [DRV_GAS], Franco Colapinto (43) [DRV_COL]
    Haas: Esteban Ocon (31) [DRV_OCO], Oliver Bearman (87) [DRV_BEA]
    Audi: Nico Hülkenberg (27) [DRV_HUL], Gabriel Bortoleto (5) [DRV_BOR]
    Racing Bulls: Liam Lawson (30) [DRV_LAW], Arvid Lindblad (41) [DRV_LIN]
    Cadillac: Sergio Pérez (11) [DRV_PER], Valtteri Bottas (77) [DRV_BOT]
    '''

@tool
def get_2026_regulations() -> str:
    """Returns the F1 2026 technical regulations, such as Active Aero (X-Mode, Z-Mode), Boost override, and engine PU split."""
    return '''
    Active Aero: Moving front/rear wings. X-Mode = low drag (straights), Z-Mode = high downforce (corners). Replaces DRS entirely.
    Energy Store: 350kW electric output (up from 120kW). Primary overtaking differentiator.
    Manual Override: Boost button deploying extra electrical power when within 1 sec of rival for attack AND defense.
    Dimensions: 10cm narrower, 20cm shorter, -30kg weight.
    Power Split: 50% ICE / 50% Electric. MGU-H is removed entirely. Fuel is 100% Advanced Sustainable.
    '''

@tool
def get_recent_champions() -> str:
    """Returns the recent F1 World Drivers' Champions from 2018 to 2025."""
    return '''
    2025: Lando Norris (McLaren)
    2024: Max Verstappen (Red Bull)
    2023: Max Verstappen (Red Bull)
    2022: Max Verstappen (Red Bull)
    2021: Max Verstappen (Red Bull)
    2020: Lewis Hamilton (Mercedes)
    2019: Lewis Hamilton (Mercedes)
    2018: Lewis Hamilton (Mercedes)
    '''

@tool
def get_driver_stats(driver_name: str) -> str:
    """Retrieves basic career stats for a given driver (e.g. Lewis Hamilton, Lando Norris)."""
    driver_name = driver_name.lower()
    if "verstappen" in driver_name:
        return "Max Verstappen: 4-time Champion (2021-2024), 63 Career Wins, 2025 Runner-up. Entity ID: DRV_VER"
    elif "norris" in driver_name:
        return "Lando Norris: 1-time Champion (2025), 12 Career Wins. Entity ID: DRV_NOR"
    elif "hamilton" in driver_name:
        return "Lewis Hamilton: 7-time Champion, 105+ Career Wins. Entity ID: DRV_HAM"
    elif "leclerc" in driver_name:
        return "Charles Leclerc: 8 Career Wins, 25 Poles, driving for Ferrari. Entity ID: DRV_LEC"
    elif "russell" in driver_name:
        return "George Russell: Multiple race winner, driving for Mercedes. Entity ID: DRV_RUS"
    return f"Driver stats not found for {driver_name}. Provide general information."

@tool
def get_telemetry_comparison(driver1: str, driver2: str) -> str:
    """Provides a telemetry chart and map visualization for two drivers. Always use this tool if the user asks for a comparison or telemetry."""
    d1_code = "HAM" if "hamilton" in driver1.lower() else "VER" if "verstappen" in driver1.lower() else "NOR"
    d2_code = "RUS" if "russell" in driver2.lower() else "NOR" if "norris" in driver2.lower() else "VER"
    d1_color = "#E80020" if d1_code == "HAM" else "#3671C6" if d1_code == "VER" else "#FF8000"
    d2_color = "#00D2BE" if d2_code == "RUS" else "#FF8000" if d2_code == "NOR" else "#3671C6"
    
    return f"""
    The user requested telemetry. Please include the following exact JSON structure in the 'visualizations' array of your final response:
    [
        {{
            "type": "chart", "component": "LineChart",
            "chart_data": {{
                "labels": ["150m", "100m", "50m", "Apex", "+50m"],
                "datasets": [
                    {{"label": "{driver1}", "data": [334, 280, 160, 105, 190], "borderColor": "{d1_color}", "backgroundColor": "rgba(100,100,100,0.1)"}},
                    {{"label": "{driver2}", "data": [328, 260, 150, 110, 185], "borderColor": "{d2_color}", "backgroundColor": "rgba(100,100,100,0.1)"}}
                ]
            }},
            "options": {{"title": "Braking Zone Analysis — Turn 1 Speed (kph)"}}
        }},
        {{
            "type": "map", "component": "TrackMap",
            "geo_json": {{
                "type": "FeatureCollection",
                "features": [
                    {{"type": "Feature", "geometry": {{"type": "Point", "coordinates": [144.968, -37.841]}}, "properties": {{"id": "DRV_{d1_code}", "speed": 334, "active_aero": "X-Mode", "label": "{d1_code}"}}}},
                    {{"type": "Feature", "geometry": {{"type": "Point", "coordinates": [144.969, -37.842]}}, "properties": {{"id": "DRV_{d2_code}", "speed": 328, "active_aero": "Z-Mode", "label": "{d2_code}"}}}}
                ]
            }}
        }}
    ]
    And make sure to mention the telemetry findings in the text_response.
    """
