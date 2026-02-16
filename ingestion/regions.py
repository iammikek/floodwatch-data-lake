REGION_BBOX = {
    "BRI": "-2.75,51.40,-2.45,51.55",
    "SOM": "-3.90,50.90,-2.20,51.40",
    "DOR": "-2.96,50.50,-1.70,51.00",
    "DEV": "-4.75,50.20,-2.95,51.25",
    "CON": "-5.80,49.90,-4.00,50.80",
}

# Approximate search centers and radii (km) for EA 'near' queries
REGION_NEAR = {
    # Bristol: M5/M4, Avonmouth, Severn estuary
    "BRI": {"lat": 51.4545, "long": -2.5879, "dist": 40},
    # Somerset: Somerset Levels, Muchelney cut-off risk, River Parrett, A361
    "SOM": {"lat": 51.03, "long": -2.90, "dist": 60},
    # Devon: A38, A30, A303, Exeter, Torbay, Plymouth, River Exe/Tamar
    "DEV": {"lat": 50.70, "long": -3.60, "dist": 100},
    # Cornwall: A30, A38, coastal and river flood risk
    "CON": {"lat": 50.42, "long": -4.90, "dist": 120},
    # Dorset: fallback for our South West coverage
    "DOR": {"lat": 50.78, "long": -2.00, "dist": 60},
}

# Outward postcode prefixes for scoping and reporting
REGION_OUTCODES = {
    "SOM": ["BA", "TA"],
    "BRI": ["BS"],
    "DEV": ["EX", "TQ", "PL"],
    "CON": ["TR"],
    # "DOR": ["DT", "BH"],  # optional, not in the provided scope statement
}
