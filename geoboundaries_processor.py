#!/usr/bin/env python3
"""
============================================
PURPOSE: Post-process downloaded geoBoundaries data for ArcGIS Pro
INPUT: Downloaded geoBoundaries folder from geoboundaries_downloader.py
OUTPUT: Merged GeoJSONs by admin level, statistics, and ArcGIS-ready files
RUN IN: Terminal / Command Prompt / Claude Code
============================================

This script:
1. Validates downloaded data
2. Generates coverage statistics
3. Merges boundaries by admin level (optional - creates large files)
4. Exports attribute summaries for reference
5. Prepares data structure recommendations for ArcGIS Pro

Prerequisites:
- pip install geopandas pandas
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION
# ============================================

# Input directory (where geoboundaries_downloader.py saved files)
INPUT_DIR = Path("./geoboundaries_data")

# Output directory for processed files
OUTPUT_DIR = Path("./geoboundaries_processed")

# Whether to create merged global files (can be very large!)
CREATE_MERGED_FILES = False  # Set to True if you want global merged files

# Admin levels to process
ADM_LEVELS = ["ADM0", "ADM1", "ADM2", "ADM3", "ADM4", "ADM5"]


# ============================================
# VALIDATION FUNCTIONS
# ============================================

def scan_downloaded_data(input_dir: Path) -> Dict:
    """
    Scan the downloaded data and create an inventory.
    """
    logger.info("Scanning downloaded data...")
    
    inventory = {
        'continents': {},
        'countries': {},
        'by_adm_level': {level: [] for level in ADM_LEVELS},
        'files': [],
        'total_size_mb': 0
    }
    
    for continent_dir in input_dir.iterdir():
        if continent_dir.is_dir() and not continent_dir.name.startswith('.'):
            continent = continent_dir.name
            if continent not in ['boundary_catalog.json', 'download_report.txt']:
                inventory['continents'][continent] = {'countries': [], 'file_count': 0}
                
                for country_dir in continent_dir.iterdir():
                    if country_dir.is_dir():
                        country_iso = country_dir.name.split('_')[0]
                        country_files = list(country_dir.glob('*.geojson'))
                        
                        if country_files:
                            inventory['continents'][continent]['countries'].append(country_iso)
                            inventory['continents'][continent]['file_count'] += len(country_files)
                            
                            inventory['countries'][country_iso] = {
                                'path': str(country_dir),
                                'continent': continent,
                                'adm_levels': [],
                                'files': []
                            }
                            
                            for f in country_files:
                                file_size = f.stat().st_size / (1024 * 1024)  # MB
                                inventory['total_size_mb'] += file_size
                                inventory['files'].append(str(f))
                                inventory['countries'][country_iso]['files'].append(f.name)
                                
                                # Determine admin level
                                for level in ADM_LEVELS:
                                    if level in f.name:
                                        if level not in inventory['countries'][country_iso]['adm_levels']:
                                            inventory['countries'][country_iso]['adm_levels'].append(level)
                                        inventory['by_adm_level'][level].append({
                                            'iso': country_iso,
                                            'file': str(f),
                                            'size_mb': file_size
                                        })
                                        break
    
    return inventory


def generate_coverage_matrix(inventory: Dict) -> str:
    """
    Generate a coverage matrix showing which countries have which admin levels.
    """
    logger.info("Generating coverage matrix...")
    
    # Create header
    matrix = "ADMINISTRATIVE BOUNDARY COVERAGE MATRIX\n"
    matrix += "=" * 80 + "\n\n"
    matrix += f"{'Country':<40} " + " ".join(f"{level:>6}" for level in ADM_LEVELS) + "\n"
    matrix += "-" * 80 + "\n"
    
    # Sort countries by ISO
    for iso in sorted(inventory['countries'].keys()):
        country_data = inventory['countries'][iso]
        levels = country_data['adm_levels']
        
        # Get country name from path
        path_parts = country_data['path'].split('/')[-1]
        country_name = path_parts.replace('_', ' ')[4:][:35]  # Remove ISO prefix
        
        row = f"{iso} {country_name:<35} "
        for level in ADM_LEVELS:
            if level in levels:
                row += f"{'✓':>6} "
            else:
                row += f"{'-':>6} "
        
        matrix += row + "\n"
    
    # Add summary
    matrix += "\n" + "=" * 80 + "\n"
    matrix += "SUMMARY BY ADMIN LEVEL:\n"
    for level in ADM_LEVELS:
        count = len(inventory['by_adm_level'][level])
        matrix += f"  {level}: {count} countries\n"
    
    matrix += f"\nTotal Countries: {len(inventory['countries'])}\n"
    matrix += f"Total Files: {len(inventory['files'])}\n"
    matrix += f"Total Size: {inventory['total_size_mb']:.2f} MB\n"
    
    return matrix


def validate_geojson_files(inventory: Dict, sample_size: int = 10) -> List[str]:
    """
    Validate a sample of GeoJSON files to ensure they're properly formatted.
    """
    logger.info(f"Validating sample of {sample_size} GeoJSON files...")
    
    errors = []
    sample = inventory['files'][:sample_size] if len(inventory['files']) > sample_size else inventory['files']
    
    for filepath in sample:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check for required GeoJSON structure
            if 'type' not in data:
                errors.append(f"Missing 'type' field: {filepath}")
            elif data['type'] not in ['FeatureCollection', 'Feature', 'GeometryCollection']:
                errors.append(f"Invalid GeoJSON type '{data['type']}': {filepath}")
            
            if data.get('type') == 'FeatureCollection':
                if 'features' not in data:
                    errors.append(f"Missing 'features' field: {filepath}")
                elif len(data['features']) == 0:
                    errors.append(f"Empty features array: {filepath}")
                    
        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error in {filepath}: {e}")
        except Exception as e:
            errors.append(f"Error reading {filepath}: {e}")
    
    if not errors:
        logger.info("All sampled files validated successfully!")
    else:
        for error in errors:
            logger.warning(error)
    
    return errors


# ============================================
# PROCESSING FUNCTIONS
# ============================================

def create_arcgis_import_script(inventory: Dict, output_dir: Path) -> str:
    """
    Generate an ArcPy script that can be run in ArcGIS Pro to import all boundaries.
    """
    logger.info("Generating ArcGIS Pro import script...")
    
    script = '''"""
ArcGIS Pro Import Script for geoBoundaries Data
================================================
Run this script in the ArcGIS Pro Python window.

This script will:
1. Create a file geodatabase for the boundaries
2. Import all GeoJSON files organized by admin level
3. Create feature datasets for each continent
"""

import arcpy
import os
from pathlib import Path

# ============================================
# CONFIGURATION - UPDATE THESE PATHS
# ============================================

# Path to your downloaded geoBoundaries data
INPUT_FOLDER = r"C:\\path\\to\\geoboundaries_data"  # UPDATE THIS!

# Path for output geodatabase (will be created)
OUTPUT_GDB = r"C:\\path\\to\\output\\GlobalAdminBoundaries.gdb"  # UPDATE THIS!

# Coordinate system for the geodatabase (WGS 1984)
COORD_SYSTEM = arcpy.SpatialReference(4326)

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    # Create output geodatabase
    gdb_folder = os.path.dirname(OUTPUT_GDB)
    gdb_name = os.path.basename(OUTPUT_GDB)
    
    if not arcpy.Exists(OUTPUT_GDB):
        print(f"Creating geodatabase: {OUTPUT_GDB}")
        arcpy.CreateFileGDB_management(gdb_folder, gdb_name)
    
    # Create feature datasets for each admin level
    adm_levels = ["ADM0", "ADM1", "ADM2", "ADM3", "ADM4", "ADM5"]
    
    for level in adm_levels:
        fds_name = f"AdminLevel_{level}"
        fds_path = os.path.join(OUTPUT_GDB, fds_name)
        
        if not arcpy.Exists(fds_path):
            print(f"Creating feature dataset: {fds_name}")
            arcpy.CreateFeatureDataset_management(OUTPUT_GDB, fds_name, COORD_SYSTEM)
    
    # Walk through input folder and import GeoJSONs
    input_path = Path(INPUT_FOLDER)
    
    for continent_dir in input_path.iterdir():
        if continent_dir.is_dir() and not continent_dir.name.startswith('.'):
            continent = continent_dir.name
            print(f"Processing continent: {continent}")
            
            for country_dir in continent_dir.iterdir():
                if country_dir.is_dir():
                    country_iso = country_dir.name.split('_')[0]
                    
                    for geojson_file in country_dir.glob('*.geojson'):
                        # Determine admin level from filename
                        for level in adm_levels:
                            if level in geojson_file.name:
                                fds_path = os.path.join(OUTPUT_GDB, f"AdminLevel_{level}")
                                
                                # Create feature class name
                                fc_name = f"{country_iso}_{level}"
                                if "simplified" in geojson_file.name:
                                    fc_name += "_simplified"
                                
                                fc_path = os.path.join(fds_path, fc_name)
                                
                                if not arcpy.Exists(fc_path):
                                    try:
                                        print(f"  Importing: {fc_name}")
                                        arcpy.JSONToFeatures_conversion(
                                            str(geojson_file),
                                            fc_path
                                        )
                                    except Exception as e:
                                        print(f"  ERROR importing {fc_name}: {e}")
                                else:
                                    print(f"  Skipping (exists): {fc_name}")
                                
                                break
    
    print("\\nImport complete!")
    print(f"Geodatabase created at: {OUTPUT_GDB}")
    print("\\nNext steps:")
    print("1. Open the geodatabase in ArcGIS Pro")
    print("2. Add feature classes to your map")
    print("3. Use 'Merge' tool to combine countries by admin level if needed")

if __name__ == "__main__":
    main()
'''
    
    script_path = output_dir / "arcgis_import_script.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script)
    
    logger.info(f"Saved ArcGIS import script: {script_path}")
    return str(script_path)


def create_country_lookup_table(inventory: Dict, output_dir: Path) -> str:
    """
    Create a CSV lookup table with country metadata for joining.
    """
    logger.info("Creating country lookup table...")
    
    # Load the boundary catalog if it exists
    catalog_path = INPUT_DIR / "boundary_catalog.json"
    catalog_data = {}
    
    if catalog_path.exists():
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
            for entry in catalog:
                key = f"{entry.get('boundaryISO')}_{entry.get('boundaryType')}"
                catalog_data[key] = entry
    
    # Create CSV content
    csv_lines = [
        "ISO,Country,Continent,UNSDG_Region,UNSDG_Subregion,WorldBank_Income,ADM_Levels_Available"
    ]
    
    for iso, country_data in sorted(inventory['countries'].items()):
        # Get metadata from catalog
        meta_key = f"{iso}_ADM0"
        meta = catalog_data.get(meta_key, {})
        
        continent = meta.get('Continent', country_data.get('continent', 'Unknown'))
        country_name = meta.get('boundaryName', iso)
        unsdg_region = meta.get('UNSDG-region', '')
        unsdg_subregion = meta.get('UNSDG-subregion', '')
        income_group = meta.get('worldBankIncomeGroup', '')
        adm_levels = '|'.join(sorted(country_data['adm_levels']))
        
        # Escape commas in fields
        country_name = country_name.replace(',', ' ')
        income_group = income_group.replace(',', ' ')
        
        csv_lines.append(
            f"{iso},{country_name},{continent},{unsdg_region},{unsdg_subregion},{income_group},{adm_levels}"
        )
    
    csv_path = output_dir / "country_metadata.csv"
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(csv_lines))
    
    logger.info(f"Saved country lookup table: {csv_path}")
    return str(csv_path)


def generate_project_structure_recommendations(inventory: Dict) -> str:
    """
    Generate recommendations for organizing data in ArcGIS Pro.
    """
    recommendations = """
============================================
ArcGIS Pro Project Structure Recommendations
============================================

RECOMMENDED GEODATABASE STRUCTURE:
----------------------------------

GlobalAdminBoundaries.gdb/
│
├── AdminLevel_ADM0/           # Feature Dataset - Country boundaries
│   ├── Global_ADM0            # Merged all countries (optional)
│   └── [ISO]_ADM0             # Individual country boundaries
│
├── AdminLevel_ADM1/           # Feature Dataset - States/Provinces
│   ├── Global_ADM1            # Merged all ADM1 (optional - large!)
│   └── [ISO]_ADM1             # Individual country ADM1s
│
├── AdminLevel_ADM2/           # Feature Dataset - Counties/Districts
│   └── [ISO]_ADM2             # Individual country ADM2s
│
├── AdminLevel_ADM3/           # Feature Dataset - Sub-districts
│   └── [ISO]_ADM3
│
├── AdminLevel_ADM4/           # Feature Dataset - Localities
│   └── [ISO]_ADM4
│
└── AdminLevel_ADM5/           # Feature Dataset - Sub-localities
    └── [ISO]_ADM5


MAP ORGANIZATION SUGGESTIONS:
-----------------------------

For your political systems project, consider these map series:

1. GLOBAL OVERVIEW MAP
   - Use ADM0 (country boundaries)
   - Symbolize by political system type
   - Include country labels

2. FEDERAL VS UNITARY STATES
   - ADM0 for base
   - ADM1 visible for federal states
   - Compare USA, Germany, Brazil (federal) vs France, UK, Japan (unitary)

3. ADMINISTRATIVE DEPTH ANALYSIS
   - Create a choropleth showing how many admin levels each country has
   - More levels often = more complex governance

4. REGIONAL DEEP DIVES
   - Separate map frames for each continent
   - Show ADM1 and ADM2 where available
   - Highlight countries with interesting structures


SYMBOLOGY RECOMMENDATIONS:
--------------------------

For administrative boundaries:
- ADM0: Thick outline (2pt), no fill or very light fill
- ADM1: Medium outline (1pt), categorical colors by country
- ADM2: Thin outline (0.5pt), lighter version of ADM1 colors
- ADM3+: Very thin outline (0.25pt), subtle differentiation


LABELING STRATEGY:
------------------

1. ADM0 Labels:
   - Country names
   - Scale: 1:50,000,000 to 1:5,000,000
   - Font: Bold, larger size

2. ADM1 Labels:
   - State/Province names
   - Scale: 1:5,000,000 to 1:500,000
   - Font: Regular, medium size

3. ADM2+ Labels:
   - District/County names
   - Scale: 1:500,000 and larger
   - Font: Light, smaller size


PERFORMANCE TIPS:
-----------------

1. Use simplified geometries for web maps and overviews
2. Keep detailed geometries for print/close-up views
3. Create tile caches for web deployment
4. Use definition queries to limit features at small scales


ATTRIBUTION (Required for CC-BY 4.0):
-------------------------------------

Include this attribution in your maps:
"Administrative boundaries: geoBoundaries Database (www.geoboundaries.org)"

"""
    return recommendations


# ============================================
# MAIN EXECUTION
# ============================================

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║           GEOBOUNDARIES POST-PROCESSOR                       ║
    ║                                                              ║
    ║  Validates, analyzes, and prepares data for ArcGIS Pro       ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Scan downloaded data
    logger.info("Step 1: Scanning downloaded data...")
    if not INPUT_DIR.exists():
        logger.error(f"Input directory not found: {INPUT_DIR}")
        logger.info("Please run geoboundaries_downloader.py first!")
        return
    
    inventory = scan_downloaded_data(INPUT_DIR)
    
    # Save inventory
    inventory_path = OUTPUT_DIR / "data_inventory.json"
    with open(inventory_path, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, indent=2, default=str)
    logger.info(f"Saved inventory: {inventory_path}")
    
    # Step 2: Generate coverage matrix
    logger.info("Step 2: Generating coverage matrix...")
    coverage_matrix = generate_coverage_matrix(inventory)
    
    matrix_path = OUTPUT_DIR / "coverage_matrix.txt"
    with open(matrix_path, 'w', encoding='utf-8') as f:
        f.write(coverage_matrix)
    print(coverage_matrix)
    
    # Step 3: Validate sample files
    logger.info("Step 3: Validating GeoJSON files...")
    validation_errors = validate_geojson_files(inventory)
    
    if validation_errors:
        error_path = OUTPUT_DIR / "validation_errors.txt"
        with open(error_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(validation_errors))
        logger.warning(f"Validation errors saved to: {error_path}")
    
    # Step 4: Generate ArcGIS import script
    logger.info("Step 4: Generating ArcGIS Pro import script...")
    arcgis_script = create_arcgis_import_script(inventory, OUTPUT_DIR)
    
    # Step 5: Create lookup table
    logger.info("Step 5: Creating country metadata lookup table...")
    lookup_table = create_country_lookup_table(inventory, OUTPUT_DIR)
    
    # Step 6: Generate recommendations
    logger.info("Step 6: Generating project structure recommendations...")
    recommendations = generate_project_structure_recommendations(inventory)
    
    rec_path = OUTPUT_DIR / "arcgis_recommendations.txt"
    with open(rec_path, 'w', encoding='utf-8') as f:
        f.write(recommendations)
    
    # Final summary
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    PROCESSING COMPLETE                        ║
    ╚══════════════════════════════════════════════════════════════╝
    
    Output Files Created:
    ---------------------
    1. {inventory_path}
       - Complete inventory of downloaded files
       
    2. {matrix_path}
       - Coverage matrix showing ADM levels per country
       
    3. {arcgis_script}
       - Python script to import data into ArcGIS Pro
       
    4. {lookup_table}
       - CSV with country metadata for table joins
       
    5. {rec_path}
       - Project structure and symbology recommendations
    
    NEXT STEPS:
    -----------
    1. Open ArcGIS Pro
    2. Update paths in arcgis_import_script.py
    3. Run the script in ArcGIS Pro Python window
    4. Build your political systems map!
    
    """)


if __name__ == "__main__":
    main()
