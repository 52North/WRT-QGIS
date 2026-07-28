"""
Default values for the Weather Routing Tool configuration.
All values are drawn from the official WRT documentation:
https://52north.github.io/WeatherRoutingTool/source/configuration.html
"""

DEFAULTS = {
    # --- Route (Page 1) ---
    "DEFAULT_MAP": "",  # bbox lat_min,lon_min,lat_max,lon_max  (derived from route if blank)
    "DEFAULT_ROUTE": "",  # lat_start,lon_start,lat_end,lon_end
    "DEPARTURE_TIME": "",  # yyyy-mm-ddThh:mmZ
    "ARRIVAL_TIME": "",  # optional
    "INTERMEDIATE_WAYPOINTS": [],  # [[lat,lon], ...]
    "ROUTE_PATH": "",
    # --- Boat (Page 2) ---
    "BOAT_LENGTH": "",
    "BOAT_BREADTH": "",
    "BOAT_TYPE": "direct_power_method",
    "BOAT_SPEED": 7.0,  # m/s
    "BOAT_FUEL_RATE": "",
    "BOAT_HBR": "",
    "BOAT_SMCR_POWER": "",
    "BOAT_SMCR_SPEED": "",
    # Advanced boat
    "BOAT_ROUGHNESS_DISTRIBUTION_LEVEL": 1,
    "BOAT_ROUGHNESS_LEVEL": 1,
    "BOAT_DRAUGHT_AFT": 10,
    "BOAT_DRAUGHT_FORE": 10,
    "BOAT_UNDER_KEEL_CLEARANCE": 20,
    "BOAT_OVERLOAD_FACTOR": 0,
    "BOAT_PROPULSION_EFFICIENCY": 0.63,
    "BOAT_SPEED_MAX": "",
    "BOAT_AOD": "",
    "BOAT_AXV": "",
    "BOAT_AYV": "",
    "BOAT_CMC": "",
    "BOAT_HC": "",
    "BOAT_BS1": "",
    "BOAT_HS1": "",
    "BOAT_HS2": "",
    "BOAT_LS1": "",
    "BOAT_LS2": "",
    "BOAT_FACTOR_CALM_WATER": 1,
    "BOAT_FACTOR_WAVE_FORCES": 1,
    "BOAT_FACTOR_WIND_FORCES": 1,
    "AIR_MASS_DENSITY": 1.2225,
    "COURSES_FILE": "",
    # --- Weather & Depth (Page 3) ---
    "WEATHER_DATA": "",
    "DEPTH_DATA": "",
    "DELTA_TIME_FORECAST": 3,
    "TIME_FORECAST": 90,
    # --- Algorithm (Page 4) ---
    "ALGORITHM_TYPE": "isofuel",
    # Isofuel / isochrone params
    "DELTA_FUEL": 3000,
    "ISOCHRONE_MAX_ROUTING_STEPS": 100,
    "ISOCHRONE_NUMBER_OF_ROUTES": 1,
    "ISOCHRONE_MINIMISATION_CRITERION": "squareddist_over_disttodest",
    "ISOCHRONE_PRUNE_GROUPS": "larger_direction",
    "ISOCHRONE_PRUNE_SECTOR_DEG_HALF": 91,
    "ISOCHRONE_PRUNE_SEGMENTS": 20,
    "ISOCHRONE_PRUNE_SYMMETRY_AXIS": "gcr",
    "ROUTER_HDGS_INCREMENTS_DEG": 6,
    "ROUTER_HDGS_SEGMENTS": 30,
    # Genetic params
    "GENETIC_NUMBER_GENERATIONS": 20,
    "GENETIC_NUMBER_OFFSPRINGS": 2,
    "GENETIC_POPULATION_SIZE": 20,
    "GENETIC_POPULATION_TYPE": "isofuel",
    "GENETIC_REPAIR_TYPE": "waypoints_infill",
    "GENETIC_MUTATION_TYPE": "random",
    "GENETIC_CROSSOVER_TYPE": "random",
    "GENETIC_CROSSOVER_PATCHER": "isofuel",
    "GENETIC_FIX_RANDOM_SEED": False,
    # GCR Slider params
    "GCR_SLIDER_ANGLE_STEP": 30,
    "GCR_SLIDER_DISTANCE_MOVE": 10000,
    "GCR_SLIDER_DYNAMIC_PARAMETERS": True,
    "GCR_SLIDER_LAND_BUFFER": 1000,
    "GCR_SLIDER_INTERPOLATE": True,
    "GCR_SLIDER_INTERP_DIST": 0.1,
    "GCR_SLIDER_INTERP_NORMALIZED": True,
    "GCR_SLIDER_MAX_POINTS": 300,
    "GCR_SLIDER_THRESHOLD": 10000,
    # Dijkstra
    "DIJKSTRA_NOF_NEIGHBORS": 1,
    "DIJKSTRA_STEP": 1,
    "DIJKSTRA_MASK_FILE": "",
    # --- Constraints (Page 5) ---
    "CONSTRAINTS_LIST": ["land_crossing_global_land_mask", "water_depth", "on_map"],
    # --- Wizard-internal state (genetic)) ---
    "_GENETIC_INTENT": "speed_waypoints",  # waypoints | speed_waypoints | speed
    "_GENETIC_SCHEDULE": "via_speed",  # via_speed | via_arrival (waypoints-only mode)
}

# Wizard-internal keys never written to the exported config.json.
INTERNAL_KEYS = {"_GENETIC_INTENT", "_GENETIC_SCHEDULE"}

BOAT_TYPE_OPTIONS = [
    ("direct_power_method", "Direct power method"),
    ("CBT", "CBT (maripower)"),
    ("speedy_isobased", "Speedy isobased (testing only)"),
]

CONSTRAINT_OPTIONS = [
    ("land_crossing_global_land_mask", "Land crossing (global land mask)"),
    ("water_depth", "Water depth"),
    ("on_map", "On map (bbox)"),
    ("via_waypoints", "Via waypoints"),
]

MINIMISATION_OPTIONS = [
    ("squareddist_over_disttodest", "Squared dist / dist-to-dest (default)"),
    ("dist", "Distance"),
]

PRUNE_GROUP_OPTIONS = [
    ("larger_direction", "Larger direction (default)"),
    ("courses", "Courses"),
    ("branch", "Branch"),
]

SYMMETRY_AXIS_OPTIONS = [
    ("gcr", "Great circle route (default)"),
    ("headings_based", "Headings based"),
]

GENETIC_POPULATION_OPTIONS = [
    ("isofuel", "Isofuel (default)"),
    ("grid_based", "Grid based"),
    ("from_geojson", "From GeoJSON"),
    ("gcrslider", "GCR slider"),
]

GENETIC_MUTATION_OPTIONS = [
    ("random", "Random (default)"),
    ("speed", "Speed"),
    ("waypoints", "Waypoints"),
    ("rndm_walk", "Random walk"),
    ("rndm_plateau", "Random plateau"),
    ("route_blend", "Route blend"),
    ("percentage_change_speed", "Percentage change speed"),
    ("gaussian_speed", "Gaussian speed"),
    ("no_mutation", "No mutation"),
]

GENETIC_CROSSOVER_OPTIONS = [
    ("random", "Random (default)"),
    ("speed", "Speed"),
    ("waypoints", "Waypoints"),
]

GENETIC_REPAIR_OPTIONS = [
    ("waypoints_infill", "Waypoints infill (default)"),
    ("constraint_violation", "Constraint violation"),
    ("no_repair", "No repair"),
]

GENETIC_CROSSOVER_PATCHER_OPTIONS = [
    ("isofuel", "Isofuel (default)"),
    ("gcr", "GCR"),
]

# Full algorithm list shown on Page 2.
ALGORITHM_OPTIONS = [
    ("isofuel", "Isofuel (default)"),
    ("genetic", "Genetic"),
    ("gcr_slider", "GCR Slider"),
    ("dijkstra", "Dijkstra"),
    ("genetic_shortest_route", "Genetic (shortest route)"),
    ("speedy_isobased", "Speedy isobased (testing only)"),
]

# Optimisation intent for the genetic algorithm.
GENETIC_INTENT_OPTIONS = [
    ("waypoints", "Waypoints only (constant speed)"),
    ("speed_waypoints", "Speed + waypoints"),
    ("speed", "Speed only (not yet implemented)"),
]

# Mutation types valid in each intent. The full GENETIC_MUTATION_OPTIONS list is
# used for the mixed (speed + waypoints) mode.
GENETIC_MUTATION_WAYPOINT_OPTIONS = [
    ("waypoints", "Waypoints"),
    ("rndm_walk", "Random walk"),
    ("rndm_plateau", "Random plateau"),
    ("route_blend", "Route blend"),
    ("no_mutation", "No mutation"),
]

GENETIC_MUTATION_SPEED_OPTIONS = [
    ("speed", "Speed"),
    ("percentage_change_speed", "Percentage change speed"),
    ("gaussian_speed", "Gaussian speed"),
]

# Crossover type forced by each intent.
GENETIC_INTENT_CROSSOVER = {
    "waypoints": "waypoints",
    "speed_waypoints": "random",
    "speed": "speed",
}

# Algorithm -> compatible boat types.
ALGO_BOAT_COMPAT = {
    "speedy_isobased": ["speedy_isobased"],
    "genetic_shortest_route": ["speedy_isobased"],
}
ALGO_BOAT_COMPAT_DEFAULT = ["direct_power_method", "CBT"]
