import os
import random

# Simulated carbon intensity adapter
# Can be replaced with external API (e.g., Electricity Maps, WattTime) in the future
def get_carbon_intensity() -> int:
    """Get current carbon intensity (simulated).
    
    Returns:
        Carbon intensity value in gCO2/kWh.
        If CARBON_FIXED env var is set and > 0, returns that value.
        Otherwise returns a random value between 100 and 600.
    """
    carbon_fixed = os.getenv("CARBON_FIXED")
    if carbon_fixed and int(carbon_fixed) > 0:
        return int(carbon_fixed)
    else:
        return random.randint(100, 600)

