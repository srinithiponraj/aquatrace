import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
SAMPLE_LAKES_DIR = DATA_DIR / "sample_lakes"
STATIC_DIR = BASE_DIR / "static"
REPORTS_DIR = DATA_DIR / "reports"

# Ensure directories exist
for p in [DATA_DIR, CACHE_DIR, SAMPLE_LAKES_DIR, STATIC_DIR, REPORTS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# Database Configuration
# Defaults to SQLite if PostgreSQL is not configured, with honest indication in the app.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'aquatrace.db'}")
IS_POSTGRES = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

# Satellite STAC & Catalog API endpoints
PLANETARY_COMPUTER_STAC_URL = os.getenv(
    "PLANETARY_COMPUTER_STAC_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
)
EARTH_SEARCH_STAC_URL = os.getenv(
    "EARTH_SEARCH_STAC_URL", "https://earth-search.aws.element84.com/v1"
)
CDSE_STAC_URL = os.getenv(
    "CDSE_STAC_URL", "https://stac.dataspace.copernicus.eu/v1"
)
CDSE_ODATA_URL = os.getenv(
    "CDSE_ODATA_URL", "https://catalogue.dataspace.copernicus.eu/odata/v1"
)
CDSE_AUTH_URL = os.getenv(
    "CDSE_AUTH_URL", "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)
# Backend authentication credentials (kept server-side in .env, never exposed to frontend)
CDSE_CLIENT_ID = os.getenv("CDSE_CLIENT_ID", "")
CDSE_CLIENT_SECRET = os.getenv("CDSE_CLIENT_SECRET", "")
PC_API_KEY = os.getenv("PC_API_KEY", "")
CARTO_API_KEY = os.getenv("CARTO_API_KEY", "")

# DEM Provider configuration (Copernicus DEM 30m / SRTM)
DEM_PROVIDER = os.getenv("DEM_PROVIDER", "copernicus-dem-glo-30")

# App Brand Info
APP_NAME = "AquaTrace"
APP_TITLE = "AquaTrace — AI-Powered Satellite Lake Intelligence"
APP_TAGLINE = "Track the Change. Trace the Source. Protect Our Water."
APP_VERSION = "1.0.0"

# Spectral index wavelengths and parameters
# Sentinel-2 Band mapping:
# B02: Blue (490 nm)
# B03: Green (560 nm)
# B04: Red (665 nm)
# B05: Red Edge 1 (705 nm)
# B06: Red Edge 2 (740 nm)
# B07: Red Edge 3 (783 nm)
# B08: NIR (842 nm)
# B11: SWIR 1 (1610 nm)
# B12: SWIR 2 (2190 nm)
DEFAULT_MNDWI_WATER_THRESHOLD = 0.0
DEFAULT_NDCI_BLOOM_THRESHOLD = 0.12
DEFAULT_NDTI_TURBIDITY_THRESHOLD = 0.05
DEFAULT_FAI_ALGAE_THRESHOLD = 0.08
DEFAULT_HOTSPOT_MIN_PIXELS = 4
DEFAULT_HOTSPOT_DBSCAN_EPS = 3.0  # pixel distance
DEFAULT_HOTSPOT_DBSCAN_MIN_SAMPLES = 3
