# AquaTrace — AI-Powered Satellite Lake & Water Intelligence

> **“Track the Change. Trace the Source. Protect Our Water.”**

AquaTrace is an advanced, full-stack geospatial intelligence platform designed for environmental authorities, hydrologists, and water protection agencies. It transforms multi-spectral satellite imagery (Sentinel-2 MSI Level-2A) into actionable environmental intelligence: tracking water surface extent across any lake, pond, reservoir, or tank; discovering actual satellite observation passes; measuring before-and-after changes; isolating candidate chlorophyll and turbidity hotspots; detecting multi-temporal statistical anomalies; and executing terrain-based hydrological source tracing.

---

## 🌟 Key Capabilities & Upgraded Architecture

### 1. Universal Water Body Selection (Lakes, Ponds, Reservoirs, Tanks)
- **Global Search:** Search by water body name, city, district, state, coordinates, or map pin (powered by OpenStreetMap / Nominatim).
- **Classification Distinction:** Accurately labels and distinguishes **Lakes**, **Ponds**, **Reservoirs**, **Tanks**, **Lagoons**, and **Wetlands**, with fallback to *"Water body — type unverified"*.
- **User Classification Correction:** Users can verify or reclassify the detected type via a single dropdown.
- **Optional Boundaries Without Forcing:** Automatically retrieves verified GeoJSON water boundaries from OpenStreetMap. If unavailable, generates a localized bounding estimate or allows users to mark a point or upload custom GeoJSON without ever blocking analysis.
- **Quick-Load Reference Lakes:** Preserves iconic reference lakes (Lake Mead, Bellandur Lake, Lake Tahoe, Lake Urmia, Winam Gulf) for rapid benchmarking.

### 2. Functional Date Selection & Satellite Pass Explorer
- **Chronological Date Validation:** Enforces `end_date >= start_date`. Selecting an inverted range immediately renders an informative error and disables pipeline execution until corrected.
- **Real Satellite Observation Discovery:** Queries AWS Earth Search STAC (`sentinel-2-l2a`) for actual passes over the water body within the requested date window.
- **Individual Observation Selectors:** When multiple satellite scenes are found, users can select the exact **Baseline Observation** (earlier pass) and **Comparison Observation** (later pass) by product ID, UTC timestamp, and cloud cover %.
- **Nearby Date Suggestions:** If no passes meet the cloud tolerance for the requested dates, AquaTrace automatically queries nearby dates (+/- 45 days) to suggest available clear passes.
- **Transparent Mode Labeling:** Real satellite observations are labeled with `:green-background[LIVE SENTINEL-2 DATA]`; synthetic scenarios are clearly marked with `:orange-background[DEMO DATA — NOT LIVE SATELLITE ANALYSIS]`.

### 3. Before-and-After Satellite Maps
- **Dual Synchronized Panels:** Displays two dedicated map panels: **BEFORE** (Baseline pass) and **AFTER** (Comparison pass).
- **Independent Real Imagery:** Renders genuine satellite imagery and MNDWI water surface masks acquired on the two distinct observation dates.
- **Synchronized Geospatial Extents:** Both panels lock to identical coordinate bounds, map extent, and zoom levels.
- **Categorical Surface Water Shift Map:** Classifies spatial transitions into:
  - **Stable Water (Blue `#0284c7`):** Consistently open water.
  - **Water Loss / Recession (Red `#ef4444`):** Contracted shoreline or exposed bed.
  - **Water Gain / Inundation (Green `#10b981`):** Submerged shoreline or expanded surface.
  - **Land (Soft Slate `#f1f5f9`):** Non-water terrain.
- **Accurate Pixel Change Metrics:** Computes baseline area (km²), comparison area (km²), net change (km²), percentage change (%), and valid observation pixel counts.

### 4. Genuine 3D Terrain Visualization
- **Real 3D Elevation Mesh:** Integrated MapLibre GL JS with AWS Terrarium DEM raster tiles (`s3.amazonaws.com/elevation-tiles-prod/terrarium`), providing actual 3D topography (hills, valleys, and lake basins).
- **Interactive Controls:** 3D oblique tilt (58°), elevation exaggeration toggle (1.0x / 1.8x / 3.0x), 360° smooth aerial camera orbit, and centering buttons.
- **Draped Geospatial Layers:** Water boundary polygons, upstream catchment basins, and inflow pathways are draped directly over the 3D elevation mesh with glowing outlines and pulsing 3D hotspot markers.
- **Resilient Fallback:** Automatically reverts to 2D Folium or perspective basemap if 3D elevation tiles are unreachable.

### 5. Colourful, Professional Light Theme
- **Water-Inspired Palette:** Soft airy water-tinted wash (`#f0f7ff`, `#f0fdfa`) instead of stark sterile white.
- **Visual Polish:** Crisp white cards with soft ocean borders (`#bae6fd`), subtle elevation shadows, and rounded corners (`12px`).
- **Meaningful Color Accents:** Surface Area (Ocean Blue `#0284c7`), Health Score (Emerald Green `#10b981`), Hotspots (Rose Red `#f43f5e`), and Anomalies (Amber `#f59e0b`).
- **Distinct Status Banners:** Visual Red Alert (`#fff1f2`), Yellow Caution (`#fffbeb`), Green Normal (`#ecfdf5`), and Insufficient Data (`#f8fafc`) flag banners.
- **Colourful Light Plotly Charts:** All charts utilize `template="plotly_white"` with dark text (`#0f172a`) and light gridlines (`#e2e8f0`).

### 6. Signature Feature: Pollution Source Trace
1. **DBSCAN Hotspot Clustering:** Unsupervised density-based clustering isolates contiguous zones of elevated Chlorophyll-a (*NDCI*), Turbidity (*NDTI*), and Floating Vegetation (*FAI*).
2. **Shoreline Inflow Discovery:** Geometric search finds the nearest terrestrial entry point along the water perimeter.
3. **Hydrological Flow Routing:** Uses 30m Digital Elevation Models (Copernicus DEM GLO-30) and the D8 flow direction algorithm to delineate the upstream contributing catchment basin.
4. **Catchment Land-Cover Profiling:** Quantifies built-up / urban runoff proxy (NDBI), agricultural cultivation proxy, bare soil erosion proxy (BSI), and natural vegetation (NDVI).
5. **Prioritized Field Protocol:** Produces step-by-step action items with GPS target coordinates for field inspection and water sampling.

---

## 🏛️ Application Navigation & Pages

AquaTrace features a comprehensive 9-page architecture preserving all core capabilities:

1. **📊 1. Overview Dashboard:** Executive summary with active water body status, automated health flag banner, 4 KPI cards, 3D/2D map preview, historical trend chart, and observation comparison summary.
2. **🔍 2. Search & Select Water Body:** Global search for any lake, pond, reservoir, or tank with type filtering, OSM boundary preview, coordinate pin entry, or GeoJSON upload.
3. **🛰️ 3. Satellite Data & Observations:** Date range selection with validation, real STAC discovery table, observation pass selectors, and cloud cover controls.
4. **🔄 4. Water Change Comparison:** Side-by-side BEFORE and AFTER panels, categorical surface water shift map, and quantitative delta statistics.
5. **🧪 5. Pollution Signals & Hotspots:** Multi-spectral index maps (NDCI, NDTI, FAI) with LaTeX formulations and DBSCAN hotspot cluster registry.
6. **🎯 6. Pollution Source Trace:** Upstream catchment basin visualization, land-cover donut chart, inflow pressure hypothesis, and field sampling protocol.
7. **📈 7. Anomaly Monitoring:** Multi-temporal time-series evaluation, seasonal Z-score deviation flags, and data sufficiency verification badge.
8. **📄 8. PDF Reports:** One-click publication-ready ReportLab vector PDF audit report compilation and download.
9. **📚 9. Methodology & Data Sources:** Sensor band wavelengths, mathematical equations, D8 routing specifications, and scientific limitations.

---

## 🚀 Installation & Local Setup

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.14.2)
- Git

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Database Configuration
By default, AquaTrace runs out-of-the-box using local SQLite (`aquatrace.db`). To connect to a production PostgreSQL database with PostGIS:
1. Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   ```
2. Configure your `DATABASE_URL`:
   ```env
   DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/aquatrace
   ```
3. Initialize tables and seed sample lakes:
   ```bash
   python database/setup_db.py
   ```

### 4. Run Automated Tests
```bash
python -m unittest discover tests
```
*All 23 automated unit and end-to-end tests will execute and pass with status OK.*

### 5. Launch the Web Application
```bash
streamlit run app.py
```
Open your browser to: **`http://localhost:8501`**

---

## 🔬 Mathematical Formulations

- **Modified Normalized Difference Water Index (MNDWI):**
  $$\text{MNDWI} = \frac{\text{Green} - \text{SWIR1}}{\text{Green} + \text{SWIR1}} = \frac{B03 - B11}{B03 + B11}$$
- **Normalized Difference Chlorophyll Index (NDCI):**
  $$\text{NDCI} = \frac{\text{RedEdge1} - \text{Red}}{\text{RedEdge1} + \text{Red}} = \frac{B05 - B04}{B05 + B04}$$
- **Normalized Difference Turbidity Index (NDTI):**
  $$\text{NDTI} = \frac{\text{Red} - \text{Green}}{\text{Red} + \text{Green}} = \frac{B04 - B03}{B04 + B03}$$
- **Floating Algae Index (FAI):**
  $$\text{FAI} = B08 - \left[B04 + (B11 - B04) \times 0.1873\right]$$
- **Normalized Difference Built-up Index (NDBI):**
  $$\text{NDBI} = \frac{\text{SWIR1} - \text{NIR}}{\text{SWIR1} + \text{NIR}} = \frac{B11 - B08}{B11 + B08}$$
- **Bare Soil Index (BSI):**
  $$\text{BSI} = \frac{(B11 + B04) - (B08 + B02)}{(B11 + B04) + (B08 + B02)}$$

---

## ⚖️ Scientific Limitations & Legal Disclaimer
AquaTrace is an automated Earth observation decision-support tool. Spectral indicators (NDCI, NDTI, FAI) represent optical reflectance signatures consistent with photosynthetic pigments or inorganic particulates; they establish candidate screening signals for prioritized monitoring and do not constitute certified chemical identification or legal culpability without accredited in-situ grab sampling. Catchment terrain routing utilizes 30m Copernicus DEM and does not resolve underground municipal storm pipes or culverts.
