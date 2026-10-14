import os
import json
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL, IS_POSTGRES, SAMPLE_LAKES_DIR
from utils.logger import logger
from utils.geo_utils import parse_geojson, get_geometry_centroid, calculate_polygon_area_km2
from database.models import Base, Lake

# Initialize Engine
try:
    if IS_POSTGRES:
        logger.info(f"Connecting to PostgreSQL/PostGIS database: {DATABASE_URL}")
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
        # Attempt to verify or enable postgis extension if permissions allow
        with engine.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
                logger.info("PostGIS extension confirmed.")
            except Exception as e:
                logger.warning(f"Could not initialize PostGIS extension (might already exist or insufficient privileges): {e}")
    else:
        logger.info(f"Using SQLite database engine: {DATABASE_URL}")
        engine = create_engine(DATABASE_URL, echo=False)
except Exception as err:
    logger.error(f"Failed to connect to specified DATABASE_URL ({DATABASE_URL}): {err}. Falling back to SQLite.")
    fallback_path = os.path.join(os.path.dirname(__file__), "..", "aquatrace.db")
    engine = create_engine(f"sqlite:///{fallback_path}", echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create all tables and seed sample lakes if empty."""
    Base.metadata.create_all(bind=engine)
    seed_sample_lakes()

@contextmanager
def get_db():
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def seed_sample_lakes():
    """Seed initial sample lakes from data/sample_lakes/ if not already present."""
    with get_db() as db:
        for file_path in SAMPLE_LAKES_DIR.glob("*.geojson"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                props = data.get("properties", {})
                name = props.get("name")
                if not name:
                    continue
                
                # Check if already exists
                existing = db.query(Lake).filter(Lake.name == name).first()
                if existing:
                    continue

                geom = parse_geojson(data)
                if not geom:
                    continue

                lat, lon = get_geometry_centroid(geom)
                area_km2 = props.get("typical_area_km2") or calculate_polygon_area_km2(geom)

                lake = Lake(
                    name=name,
                    country=props.get("country", "Unknown"),
                    region=props.get("region", "Global"),
                    centroid_lat=lat,
                    centroid_lon=lon,
                    typical_area_km2=area_km2,
                    boundary_geojson=json.dumps(geom)
                )
                db.add(lake)
                logger.info(f"Seeded sample lake: {name} ({lat:.4f}, {lon:.4f})")
            except Exception as e:
                logger.warning(f"Failed to seed lake from {file_path.name}: {e}")

def get_database_status():
    """Return dict describing database engine and connection state."""
    is_pg = engine.url.drivername.startswith("postgres")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
            connected = True
    except Exception:
        connected = False

    return {
        "engine": "PostgreSQL + PostGIS" if is_pg else "SQLite Development Fallback",
        "connected": connected,
        "is_postgres": is_pg,
        "url_masked": str(engine.url) if not is_pg else f"postgresql://***:***@{engine.url.host}:{engine.url.port or 5432}/{engine.url.database}"
    }
