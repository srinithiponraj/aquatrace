import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, relationship

def current_utc_time():
    return datetime.datetime.now(datetime.timezone.utc)

Base = declarative_base()

class Lake(Base):
    __tablename__ = "lakes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False, unique=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    centroid_lat = Column(Float, nullable=False)
    centroid_lon = Column(Float, nullable=False)
    typical_area_km2 = Column(Float, nullable=True)
    boundary_geojson = Column(Text, nullable=False)
    created_at = Column(DateTime, default=current_utc_time)

    # Relationships
    observations = relationship("SatelliteObservation", back_populates="lake", cascade="all, delete-orphan")
    analyses = relationship("AnalysisRun", back_populates="lake", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "region": self.region,
            "centroid_lat": self.centroid_lat,
            "centroid_lon": self.centroid_lon,
            "typical_area_km2": self.typical_area_km2,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lake_id = Column(Integer, ForeignKey("lakes.id"), nullable=False)
    satellite_platform = Column(String(50), nullable=False)  # Sentinel-2A, Sentinel-2B, Sentinel-1
    product_id = Column(String(200), nullable=False)
    acquisition_date = Column(DateTime, nullable=False)
    cloud_cover = Column(Float, nullable=True)
    data_source = Column(String(100), nullable=False)  # Planetary Computer STAC, AWS STAC, DEMO DATA
    assets_metadata = Column(Text, nullable=True)
    is_demo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=current_utc_time)

    lake = relationship("Lake", back_populates="observations")

    def to_dict(self):
        return {
            "id": self.id,
            "lake_id": self.lake_id,
            "satellite_platform": self.satellite_platform,
            "product_id": self.product_id,
            "acquisition_date": self.acquisition_date.strftime("%Y-%m-%d"),
            "cloud_cover": self.cloud_cover,
            "data_source": self.data_source,
            "is_demo": self.is_demo
        }

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lake_id = Column(Integer, ForeignKey("lakes.id"), nullable=False)
    baseline_obs_id = Column(Integer, ForeignKey("satellite_observations.id"), nullable=False)
    comparison_obs_id = Column(Integer, ForeignKey("satellite_observations.id"), nullable=True)
    run_timestamp = Column(DateTime, default=current_utc_time)

    baseline_water_area_km2 = Column(Float, nullable=False)
    comparison_water_area_km2 = Column(Float, nullable=True)
    water_area_change_km2 = Column(Float, nullable=True)
    water_area_change_pct = Column(Float, nullable=True)
    mndwi_threshold = Column(Float, default=0.0)

    # Health score
    health_score = Column(Float, nullable=True)
    health_score_grade = Column(String(20), nullable=True)
    quality_status = Column(String(50), default="High Confidence")
    valid_pixel_pct = Column(Float, default=100.0)

    config_json = Column(Text, nullable=True)

    lake = relationship("Lake", back_populates="analyses")
    baseline_obs = relationship("SatelliteObservation", foreign_keys=[baseline_obs_id])
    comparison_obs = relationship("SatelliteObservation", foreign_keys=[comparison_obs_id])
    hotspots = relationship("PollutionHotspot", back_populates="analysis", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="analysis", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "lake_id": self.lake_id,
            "lake_name": self.lake.name if self.lake else None,
            "run_timestamp": self.run_timestamp.strftime("%Y-%m-%d %H:%M"),
            "baseline_date": self.baseline_obs.acquisition_date.strftime("%Y-%m-%d") if self.baseline_obs else None,
            "comparison_date": self.comparison_obs.acquisition_date.strftime("%Y-%m-%d") if self.comparison_obs else None,
            "baseline_water_area_km2": self.baseline_water_area_km2,
            "comparison_water_area_km2": self.comparison_water_area_km2,
            "water_area_change_km2": self.water_area_change_km2,
            "water_area_change_pct": self.water_area_change_pct,
            "health_score": self.health_score,
            "health_score_grade": self.health_score_grade,
            "quality_status": self.quality_status
        }

class PollutionHotspot(Base):
    __tablename__ = "pollution_hotspots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False)
    indicator_type = Column(String(50), nullable=False)  # NDCI_ALGAE, NDTI_TURBIDITY, FAI_FLOATING_VEG
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    area_hectares = Column(Float, nullable=False)
    pixel_count = Column(Integer, nullable=False)
    mean_indicator_value = Column(Float, nullable=False)
    max_indicator_value = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False)  # Low, Moderate, High, Severe
    inspection_priority = Column(String(20), nullable=False)  # Immediate, Elevated, Routine
    confidence_score = Column(Float, default=0.85)
    geometry_geojson = Column(Text, nullable=True)

    analysis = relationship("AnalysisRun", back_populates="hotspots")
    source_trace = relationship("SourceTraceResult", back_populates="hotspot", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "indicator_type": self.indicator_type,
            "center_lat": round(self.center_lat, 5),
            "center_lon": round(self.center_lon, 5),
            "area_hectares": round(self.area_hectares, 2),
            "pixel_count": self.pixel_count,
            "mean_indicator_value": round(self.mean_indicator_value, 4),
            "max_indicator_value": round(self.max_indicator_value, 4),
            "severity": self.severity,
            "inspection_priority": self.inspection_priority,
            "confidence_score": round(self.confidence_score, 2)
        }

class SourceTraceResult(Base):
    __tablename__ = "source_trace_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotspot_id = Column(Integer, ForeignKey("pollution_hotspots.id"), nullable=False)
    candidate_entry_lat = Column(Float, nullable=False)
    candidate_entry_lon = Column(Float, nullable=False)
    contributing_area_km2 = Column(Float, nullable=False)
    built_up_pct = Column(Float, nullable=False)
    agriculture_pct = Column(Float, nullable=False)
    bare_soil_pct = Column(Float, nullable=False)
    vegetation_pct = Column(Float, nullable=False)
    primary_source_pressure = Column(String(100), nullable=False)
    terrain_method = Column(String(100), nullable=False)
    is_fallback = Column(Boolean, default=False)
    inspection_recommendation = Column(Text, nullable=False)
    watershed_geojson = Column(Text, nullable=True)

    hotspot = relationship("PollutionHotspot", back_populates="source_trace")

    def to_dict(self):
        return {
            "id": self.id,
            "hotspot_id": self.hotspot_id,
            "candidate_entry_lat": round(self.candidate_entry_lat, 5),
            "candidate_entry_lon": round(self.candidate_entry_lon, 5),
            "contributing_area_km2": round(self.contributing_area_km2, 2),
            "built_up_pct": round(self.built_up_pct, 1),
            "agriculture_pct": round(self.agriculture_pct, 1),
            "bare_soil_pct": round(self.bare_soil_pct, 1),
            "vegetation_pct": round(self.vegetation_pct, 1),
            "primary_source_pressure": self.primary_source_pressure,
            "terrain_method": self.terrain_method,
            "is_fallback": self.is_fallback,
            "inspection_recommendation": self.inspection_recommendation
        }

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False)
    title = Column(String(200), nullable=False)
    file_path = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=current_utc_time)
    report_metadata = Column(Text, nullable=True)

    analysis = relationship("AnalysisRun", back_populates="reports")
