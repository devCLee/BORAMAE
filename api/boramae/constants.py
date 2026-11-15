"""Named constants shared by the API. Frozen from wave 2: report a needed change."""

# Area radius (FR-04, PRD "User flows").
RADIUS_MIN_KM = 10
RADIUS_MAX_KM = 300
RADIUS_DEFAULT_KM = 25

# No-trend fallback: nearest significant areas within this distance (FR-19).
NEARBY_MAX_KM = 1000

# List sizes of 3: proposed variables (FR-03), board drivers and responses (FR-18),
# nearby areas (FR-19) and scan hits.
MAX_PROPOSED_VARIABLES = 3
MAX_BOARD_DRIVERS = 3
MAX_BOARD_RESPONSES = 3
MAX_NEARBY_AREAS = 3
MAX_SCAN_HITS = 3

# Trend-grid box over East Asia, in degrees (PRD "Earth-system context").
GRID_BOX_LON_MIN = 100.0
GRID_BOX_LON_MAX = 150.0
GRID_BOX_LAT_MIN = 20.0
GRID_BOX_LAT_MAX = 50.0

# ponytail: no document fixes the radius; the mean Earth radius for the haversine
# distance. Use a geodesic distance if 0.5% matters at the 1,000 km bound.
EARTH_RADIUS_KM = 6371.0

RESULT_KINDS = ("trend", "caseboard", "scan")
KEY_HEX_LEN = 32
# ponytail: placeholder parse text cap (TRD Q-22, Q-23 leave the limits open).
MAX_PARSE_CHARS = 500

# A catalog ID is the POWER variable name (PRD line 530).
VARIABLE_IDS = (
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "PRECSNO",
    "SNODP",
    "FRSNO",
    "RH2M",
    "TQV",
    "GWETTOP",
    "GWETROOT",
    "EVLAND",
    "FROST_DAYS",
    "WS10M",
    "TS",
    "CDD18_3",
    "HDD18_3",
    "FRSEAICE",
    "TO3",
    "PBLTOP",
)

# PRD "Metric library".
METRIC_IDS = (
    "annual_mean",
    "annual_total",
    "seasonal_mean",
    "seasonal_total",
    "first_date",
    "last_date",
    "threshold_days",
    "rx1day",
    "season_onset",
    "season_length",
    "degree_days",
    "frost_free_length",
    "spell_length",
    "snow_free_date",
    "one_date_value",
    "spi3_months",
    "rainy_season_length",
    "snow_share",
)

# Intents of the investigation spec (FR-03).
INTENT_IDS = (
    "mean_change",
    "extremes_count",
    "extremes_intensity",
    "timing",
    "duration",
    "comparison",
    "place_first",
    "variable_first",
    "cause",
)
