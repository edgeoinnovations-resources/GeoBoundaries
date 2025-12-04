#!/usr/bin/env python3
"""
============================================
PURPOSE: Download all geoBoundaries administrative boundary data
         for every country at every administrative level (ADM0-ADM5)
INPUT: Internet connection and target download directory
OUTPUT: Organized folder structure with GeoJSON files for all countries
RUN IN: Terminal / Command Prompt / Claude Code
============================================

This script downloads administrative boundaries from geoBoundaries.org
for creating a comprehensive global administrative divisions map.

Author: Generated for educational GIS project
License: Script is free to use; downloaded data follows CC-BY 4.0 (gbOpen)
"""

import os
import json
import time
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION - MODIFY THESE AS NEEDED
# ============================================

# Where to save downloaded files
DOWNLOAD_DIR = Path("./geoboundaries_data")

# Release type: 'gbOpen' (CC-BY 4.0), 'gbHumanitarian' (UN OCHA), 'gbAuthoritative' (UN SALB)
RELEASE_TYPE = "gbOpen"

# Administrative levels to download (ADM0=country, ADM1=states/provinces, etc.)
ADM_LEVELS = ["ADM0", "ADM1", "ADM2", "ADM3", "ADM4", "ADM5"]

# File format to download: 'geojson', 'simplified', 'shapefile', or 'all'
DOWNLOAD_FORMAT = "geojson"  # Options: 'geojson', 'simplified', 'shapefile', 'all'

# Number of parallel downloads (be respectful to the server)
MAX_WORKERS = 3

# Delay between requests in seconds (to avoid overwhelming the server)
REQUEST_DELAY = 0.5

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5

# API base URL
API_BASE = "https://www.geoboundaries.org/api/current"


# ============================================
# MAIN FUNCTIONS
# ============================================

def get_all_boundaries() -> List[Dict[str, Any]]:
    """
    Fetch metadata for all available boundaries from the API.
    Returns a list of boundary metadata dictionaries.
    """
    url = f"{API_BASE}/{RELEASE_TYPE}/ALL/ALL/"
    logger.info(f"Fetching boundary catalog from: {url}")
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                logger.info(f"Found {len(data)} boundaries in catalog")
                return data
            else:
                logger.error(f"Unexpected API response format: {type(data)}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Failed to fetch boundary catalog after all retries")
                raise
    
    return []


def filter_boundaries(boundaries: List[Dict], adm_levels: List[str]) -> List[Dict]:
    """
    Filter boundaries to only include specified administrative levels.
    """
    filtered = [b for b in boundaries if b.get('boundaryType') in adm_levels]
    logger.info(f"Filtered to {len(filtered)} boundaries for levels: {adm_levels}")
    return filtered


def get_download_urls(boundary: Dict, download_format: str) -> Dict[str, str]:
    """
    Extract download URLs from boundary metadata based on requested format.
    """
    urls = {}
    
    if download_format in ['geojson', 'all']:
        if boundary.get('gjDownloadURL'):
            urls['geojson'] = boundary['gjDownloadURL']
    
    if download_format in ['simplified', 'all']:
        if boundary.get('simplifiedGeometryGeoJSON'):
            urls['simplified'] = boundary['simplifiedGeometryGeoJSON']
    
    if download_format in ['shapefile', 'all']:
        if boundary.get('staticDownloadLink'):
            urls['shapefile'] = boundary['staticDownloadLink']
    
    return urls


def create_folder_structure(boundary: Dict, base_dir: Path) -> Path:
    """
    Create organized folder structure for a boundary.
    Structure: base_dir/continent/country_iso/
    """
    continent = boundary.get('Continent', 'Unknown').replace(' ', '_')
    iso = boundary.get('boundaryISO', 'UNK')
    country_name = boundary.get('boundaryName', 'Unknown').replace(' ', '_').replace('/', '_')
    
    # Create path: continent/ISO_CountryName/
    folder = base_dir / continent / f"{iso}_{country_name}"
    folder.mkdir(parents=True, exist_ok=True)
    
    return folder


def download_file(url: str, filepath: Path, description: str) -> bool:
    """
    Download a single file with retry logic.
    """
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Downloading: {description}")
            response = requests.get(url, timeout=120, stream=True)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"✓ Saved: {filepath.name}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"✗ Failed to download: {description}")
                return False
    
    return False


def download_boundary(boundary: Dict, base_dir: Path, download_format: str) -> Dict[str, Any]:
    """
    Download all requested files for a single boundary.
    Returns a summary of the download results.
    """
    iso = boundary.get('boundaryISO', 'UNK')
    adm_level = boundary.get('boundaryType', 'UNK')
    country = boundary.get('boundaryName', 'Unknown')
    boundary_id = boundary.get('boundaryID', 'unknown')
    
    result = {
        'boundary_id': boundary_id,
        'country': country,
        'iso': iso,
        'adm_level': adm_level,
        'success': [],
        'failed': []
    }
    
    # Create folder structure
    folder = create_folder_structure(boundary, base_dir)
    
    # Get download URLs
    urls = get_download_urls(boundary, download_format)
    
    if not urls:
        logger.warning(f"No download URLs found for {iso} {adm_level}")
        return result
    
    # Download each file type
    for file_type, url in urls.items():
        # Determine file extension
        if file_type == 'shapefile':
            ext = 'zip'
        elif 'geojson' in file_type.lower() or file_type == 'simplified':
            ext = 'geojson'
        else:
            ext = 'json'
        
        # Create filename
        if file_type == 'simplified':
            filename = f"{iso}_{adm_level}_simplified.{ext}"
        else:
            filename = f"{iso}_{adm_level}.{ext}"
        
        filepath = folder / filename
        
        # Skip if already exists
        if filepath.exists():
            logger.info(f"⊘ Skipping (exists): {filepath.name}")
            result['success'].append(file_type)
            continue
        
        # Download
        description = f"{country} ({iso}) {adm_level} - {file_type}"
        if download_file(url, filepath, description):
            result['success'].append(file_type)
        else:
            result['failed'].append(file_type)
        
        # Be nice to the server
        time.sleep(REQUEST_DELAY)
    
    return result


def save_metadata(boundaries: List[Dict], base_dir: Path):
    """
    Save the complete boundary metadata catalog for reference.
    """
    metadata_file = base_dir / "boundary_catalog.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(boundaries, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved metadata catalog: {metadata_file}")


def generate_summary_report(results: List[Dict], base_dir: Path):
    """
    Generate a summary report of the download process.
    """
    report_file = base_dir / "download_report.txt"
    
    total = len(results)
    successful = sum(1 for r in results if r['success'] and not r['failed'])
    partial = sum(1 for r in results if r['success'] and r['failed'])
    failed = sum(1 for r in results if not r['success'])
    
    # Count by admin level
    by_level = {}
    for r in results:
        level = r['adm_level']
        if level not in by_level:
            by_level[level] = {'success': 0, 'partial': 0, 'failed': 0}
        if r['success'] and not r['failed']:
            by_level[level]['success'] += 1
        elif r['success'] and r['failed']:
            by_level[level]['partial'] += 1
        else:
            by_level[level]['failed'] += 1
    
    # Count by continent
    by_continent = {}
    for r in results:
        # We'd need boundary metadata for this - skip for now
        pass
    
    report = f"""
============================================
GEOBOUNDARIES DOWNLOAD REPORT
============================================

Total Boundaries Processed: {total}
- Fully Successful: {successful}
- Partially Successful: {partial}
- Failed: {failed}

BY ADMINISTRATIVE LEVEL:
"""
    
    for level in sorted(by_level.keys()):
        stats = by_level[level]
        report += f"  {level}: {stats['success']} success, {stats['partial']} partial, {stats['failed']} failed\n"
    
    report += """
============================================
FAILED DOWNLOADS:
"""
    
    for r in results:
        if r['failed']:
            report += f"  - {r['iso']} {r['adm_level']} ({r['country']}): {', '.join(r['failed'])}\n"
    
    report += """
============================================
DATA USAGE NOTES:
- License: CC-BY 4.0 (gbOpen) - Attribution required
- Citation: geoBoundaries Global Database of Political Administrative Boundaries
- Website: https://www.geoboundaries.org/
============================================
"""
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"Saved download report: {report_file}")
    print(report)


def main():
    """
    Main execution function.
    """
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║           GEOBOUNDARIES BULK DOWNLOADER                      ║
    ║                                                              ║
    ║  Downloading administrative boundaries for all countries     ║
    ║  Source: geoboundaries.org (CC-BY 4.0)                      ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Create base download directory
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Download directory: {DOWNLOAD_DIR.absolute()}")
    
    # Step 1: Fetch all available boundaries
    logger.info("Step 1: Fetching boundary catalog...")
    boundaries = get_all_boundaries()
    
    if not boundaries:
        logger.error("No boundaries found. Exiting.")
        return
    
    # Step 2: Filter to requested admin levels
    logger.info("Step 2: Filtering boundaries...")
    boundaries = filter_boundaries(boundaries, ADM_LEVELS)
    
    # Step 3: Save metadata catalog
    logger.info("Step 3: Saving metadata catalog...")
    save_metadata(boundaries, DOWNLOAD_DIR)
    
    # Step 4: Download all boundaries
    logger.info(f"Step 4: Downloading {len(boundaries)} boundaries...")
    logger.info(f"Format: {DOWNLOAD_FORMAT}")
    logger.info(f"Workers: {MAX_WORKERS}")
    
    results = []
    
    # Use thread pool for parallel downloads
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_boundary, b, DOWNLOAD_DIR, DOWNLOAD_FORMAT): b
            for b in boundaries
        }
        
        for i, future in enumerate(as_completed(futures), 1):
            boundary = futures[future]
            try:
                result = future.result()
                results.append(result)
                
                # Progress update
                if i % 10 == 0 or i == len(boundaries):
                    logger.info(f"Progress: {i}/{len(boundaries)} boundaries processed")
                    
            except Exception as e:
                logger.error(f"Error processing {boundary.get('boundaryID')}: {e}")
                results.append({
                    'boundary_id': boundary.get('boundaryID', 'unknown'),
                    'country': boundary.get('boundaryName', 'Unknown'),
                    'iso': boundary.get('boundaryISO', 'UNK'),
                    'adm_level': boundary.get('boundaryType', 'UNK'),
                    'success': [],
                    'failed': ['error']
                })
    
    # Step 5: Generate summary report
    logger.info("Step 5: Generating summary report...")
    generate_summary_report(results, DOWNLOAD_DIR)
    
    logger.info("Download complete!")


# ============================================
# UTILITY FUNCTIONS FOR POST-DOWNLOAD USE
# ============================================

def list_downloaded_boundaries(base_dir: Path = DOWNLOAD_DIR) -> Dict[str, List[str]]:
    """
    Utility to list all downloaded boundaries organized by country.
    Useful for verification after download.
    """
    inventory = {}
    
    for continent_dir in base_dir.iterdir():
        if continent_dir.is_dir() and not continent_dir.name.startswith('.'):
            for country_dir in continent_dir.iterdir():
                if country_dir.is_dir():
                    files = [f.name for f in country_dir.glob('*.geojson')]
                    if files:
                        inventory[country_dir.name] = files
    
    return inventory


def get_country_coverage_report(base_dir: Path = DOWNLOAD_DIR) -> str:
    """
    Generate a report showing which admin levels are available per country.
    """
    inventory = list_downloaded_boundaries(base_dir)
    
    report = "Country Coverage Report\n" + "=" * 60 + "\n"
    
    for country, files in sorted(inventory.items()):
        levels = []
        for f in files:
            for level in ADM_LEVELS:
                if level in f:
                    levels.append(level)
        
        levels = sorted(set(levels))
        report += f"{country}: {', '.join(levels)}\n"
    
    return report


if __name__ == "__main__":
    main()
