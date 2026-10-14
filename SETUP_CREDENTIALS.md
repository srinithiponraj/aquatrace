# AquaTrace — Server-Side Satellite Credentials & Data Configuration

AquaTrace connects to public Earth observation data architectures to analyze multi-spectral satellite passes over inland lakes, ponds, reservoirs, and tanks.

---

## 1. Supported Satellite Data Sources

AquaTrace operates in a tiered architecture designed to function out-of-the-box without requiring end-users to enter API keys:

### Tier 1: Public STAC Endpoints (Zero Authentication Required)
- **Copernicus Data Space Ecosystem (CDSE) STAC Catalogue** (`https://stac.dataspace.copernicus.eu/v1`):
  - Collection: `sentinel-2-l2a`
  - Provides open, public, unauthenticated search for all global Sentinel-2 Level-2A acquisitions with sub-pixel multi-spectral accuracy and real-time cloud metadata.
  - **Status:** Active & default in AquaTrace. Zero API keys or tokens required for search.
- **AWS Earth Search STAC & Open S3 Archive** (`https://earth-search.aws.element84.com/v1`):
  - Collection: `sentinel-2-l2a`
  - Provides direct public access to Sentinel-2 Level-2A surface reflectance imagery, full-resolution Cloud-Optimized GeoTIFFs (COGs), and true-color thumbnails.
  - **Status:** Active & default in AquaTrace. No API key needed.
- **Microsoft Planetary Computer STAC** (`https://planetarycomputer.microsoft.com/api/stac/v1`):
  - Collection: `sentinel-2-l2a`
  - Provides public STAC metadata and rendered preview assets over HTTPS.
  - **Status:** Active automatic fallback. No API key needed for previews.

### Tier 2: Copernicus Data Space Ecosystem (CDSE) Backend Authentication (Optional)
If your organization requires direct authenticated downloads of full SAFE packages or Sentinel Hub OData assets from the official European Copernicus Data Space Ecosystem (CDSE), configure backend OAuth credentials in `.env`:

1. Register at [dataspace.copernicus.eu](https://dataspace.copernicus.eu/).
2. Navigate to your Account Dashboard and create an **OAuth2 Client ID** and **Client Secret**.
3. Create or update your `.env` file in the project root:
   ```env
   # Copernicus Data Space Ecosystem (CDSE) Backend Credentials
   CDSE_CLIENT_ID=your_cdse_client_id_here
   CDSE_CLIENT_SECRET=your_cdse_client_secret_here
   ```
4. **Security Guarantee:** AquaTrace strictly processes credentials on the Python server backend. Credentials are never sent to the browser, rendered in frontend HTML, exposed to JavaScript, or committed to GitHub (`.gitignore` protects `.env`).

### Tier 3: Microsoft Planetary Computer Subscription Key (Optional)
For high-rate batch downloading of raw full-resolution Sentinel-2 COG assets:
```env
PC_API_KEY=your_planetary_computer_api_key_here
```

---

## 2. Basemap & Tile Services (Zero API Key Watermarks)

To ensure maps never display "API key required" watermarks (such as those from unauthenticated CARTO or commercial providers), AquaTrace exclusively uses verified keyless basemaps:

- **Reference Satellite Basemap:** Esri World Imagery (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`) — free public access without API keys.
- **Clean Topographic Basemap:** Esri World Topo Map (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}`) — clean, high-contrast light theme without API keys.
- **OpenStreetMap Basemap:** OpenStreetMap Standard (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) — open community standard without API keys.
- **3D Digital Elevation Tiles:** AWS Terrarium DEM (`https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`) — public elevation tiles without API keys.
- **Genuine Satellite Overlay:** True Sentinel-2 Level-2A multi-spectral captures are rendered directly as localized rasters onto the Before and After maps with verified acquisition timestamps and cloud cover percentages.

---

## 3. Offline Demonstration Mode

If external network connectivity is restricted, toggle **Enable Offline Demo Mode** in the sidebar. This uses calibrated, locally synthesized demonstration scenarios explicitly labeled as **DEMO DATA**.
