# geoBoundaries Global Download Toolkit

Download administrative boundary data for **every country in the world** at all available administrative levels (ADM0-ADM5) for use in ArcGIS Pro.

## Project Purpose

Create a comprehensive global administrative divisions map for producing videos and infographics about how administrative divisions relate to political systems worldwide.

## Data Source

**geoBoundaries** (https://www.geoboundaries.org/)
- The world's largest open database of political administrative boundaries
- **License:** CC-BY 4.0 (gbOpen) - free to use with attribution
- **Coverage:** 200+ countries, ADM0-ADM5 where available
- **Quality:** Academic-grade, regularly updated

## What You'll Get

After running these scripts, you'll have:

| Admin Level | Description | Example |
|-------------|-------------|---------|
| ADM0 | Country boundaries | United States outline |
| ADM1 | First-level subdivisions | US States, French Régions |
| ADM2 | Second-level subdivisions | US Counties, French Départements |
| ADM3 | Third-level subdivisions | US Townships, French Cantons |
| ADM4 | Fourth-level subdivisions | French Communes |
| ADM5 | Fifth-level subdivisions | Rare - neighborhood level |

## Prerequisites

```bash
# Python 3.8+
pip install requests

# For post-processing (optional but recommended)
pip install geopandas pandas
```

## Quick Start

### Step 1: Download All Data

```bash
# Run the downloader
python geoboundaries_downloader.py
```

**What happens:**
1. Queries geoBoundaries API for all available boundaries
2. Downloads GeoJSON files for every country at every level
3. Organizes files by continent → country
4. Creates a download report

**Estimated time:** 2-4 hours (depending on connection)
**Estimated size:** 5-15 GB

### Step 2: Process & Validate

```bash
# Run the processor
python geoboundaries_processor.py
```

**What happens:**
1. Validates all downloaded files
2. Creates coverage matrix (which countries have which levels)
3. Generates ArcGIS Pro import script
4. Creates country metadata CSV

### Step 3: Import to ArcGIS Pro

1. Open the generated `arcgis_import_script.py`
2. Update the `INPUT_FOLDER` and `OUTPUT_GDB` paths
3. Open ArcGIS Pro → Python window
4. Paste and run the script

## File Structure After Download

```
geoboundaries_data/
├── boundary_catalog.json      # Complete API metadata
├── download_report.txt        # Download summary
│
├── Africa/
│   ├── AGO_Angola/
│   │   ├── AGO_ADM0.geojson
│   │   ├── AGO_ADM1.geojson
│   │   └── AGO_ADM2.geojson
│   ├── BEN_Benin/
│   │   └── ...
│   └── ...
│
├── Asia/
│   ├── CHN_China/
│   │   ├── CHN_ADM0.geojson
│   │   ├── CHN_ADM1.geojson
│   │   ├── CHN_ADM2.geojson
│   │   └── CHN_ADM3.geojson
│   └── ...
│
├── Europe/
│   ├── FRA_France/
│   │   ├── FRA_ADM0.geojson
│   │   ├── FRA_ADM1.geojson
│   │   ├── FRA_ADM2.geojson
│   │   ├── FRA_ADM3.geojson
│   │   ├── FRA_ADM4.geojson
│   │   └── FRA_ADM5.geojson   # France has all 6 levels!
│   └── ...
│
└── ...
```

## Configuration Options

Edit the top of `geoboundaries_downloader.py`:

```python
# Change download location
DOWNLOAD_DIR = Path("./geoboundaries_data")

# Download only specific levels
ADM_LEVELS = ["ADM0", "ADM1", "ADM2"]  # Skip ADM3-5

# Get simplified geometries (smaller files)
DOWNLOAD_FORMAT = "simplified"  # or "geojson" or "all"

# Adjust download speed
MAX_WORKERS = 3       # Parallel downloads (be nice to the server)
REQUEST_DELAY = 0.5   # Seconds between requests
```

## Countries with Deep Administrative Hierarchies

Based on geoBoundaries data, these countries typically have the most administrative levels:

| Country | Levels | Notes |
|---------|--------|-------|
| 🇫🇷 France | ADM0-5 | Regions → Départements → Arrondissements → Cantons → Communes |
| 🇷🇼 Rwanda | ADM0-4 | Provinces → Districts → Sectors → Cells |
| 🇵🇭 Philippines | ADM0-4 | Regions → Provinces → Municipalities → Barangays |
| 🇰🇷 South Korea | ADM0-4 | Provinces → Districts → Sub-districts → Neighborhoods |
| 🇨🇳 China | ADM0-3 | Provinces → Prefectures → Counties |
| 🇺🇸 USA | ADM0-2 | States → Counties |
| 🇬🇧 UK | ADM0-2 | Countries → Districts |

## ArcGIS Pro Workflow

### Recommended Geodatabase Structure

```
GlobalAdminBoundaries.gdb/
├── AdminLevel_ADM0/    # Country outlines
├── AdminLevel_ADM1/    # States/Provinces
├── AdminLevel_ADM2/    # Counties/Districts
├── AdminLevel_ADM3/    # Sub-districts
├── AdminLevel_ADM4/    # Localities
└── AdminLevel_ADM5/    # Neighborhoods
```

### Symbology Tips

- **ADM0:** 2pt outline, no fill (or very light)
- **ADM1:** 1pt outline, categorical colors
- **ADM2:** 0.5pt outline, lighter colors
- **ADM3+:** 0.25pt outline, subtle differentiation

### Creating a Political Systems Map

1. **Import all ADM0 boundaries** (country level)
2. **Join with political system data** (parliamentary, presidential, federal, unitary, etc.)
3. **Symbolize by political system type**
4. **Add ADM1/ADM2 for selected countries** to show internal structure
5. **Create map layouts** for videos/infographics

## Attribution (Required!)

When using this data, include:

```
Administrative boundaries: geoBoundaries Database (www.geoboundaries.org)
Licensed under CC-BY 4.0
```

## Troubleshooting

### Download interrupted?
Just run the script again - it skips files that already exist.

### Missing countries?
Some small territories may not be in geoBoundaries. Check the download report.

### Large file sizes?
Use `DOWNLOAD_FORMAT = "simplified"` for smaller, web-friendly files.

### ArcGIS import errors?
Some GeoJSON files may have encoding issues. The validation step will flag these.

## API Reference

The scripts use this API endpoint:
```
https://www.geoboundaries.org/api/current/gbOpen/[ISO]/[ADM]/
```

- Replace `[ISO]` with 3-letter country code or `ALL`
- Replace `[ADM]` with level (ADM0-ADM5) or `ALL`

## Support

- **geoBoundaries:** https://www.geoboundaries.org/
- **API Documentation:** https://www.geoboundaries.org/api.html
- **Report data issues:** https://github.com/wmgeolab/geoBoundaries

---

Created for educational GIS project exploring global political administrative systems.
