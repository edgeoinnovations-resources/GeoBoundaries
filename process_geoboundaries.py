#!/usr/bin/env python3
"""
GeoBoundaries Data Processing Script

Processes GeoBoundaries GeoJSON files for web deployment:
1. Validates and repairs geometries
2. Simplifies geometries for web performance
3. Renames files with proper administrative terminology
4. Generates configuration files (terminology.json, countries.json, search-index.json, content.json)
"""

import os
import json
import logging
from pathlib import Path
from collections import defaultdict

import geopandas as gpd
from shapely.geometry import mapping, shape
from shapely.validation import make_valid
from shapely.ops import unary_union

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SOURCE_DIR = Path("/Users/paulstrootman/Desktop/GeoBoundaries/geoboundaries_data")
OUTPUT_DIR = Path("/Users/paulstrootman/Desktop/StagingFolder")

# Simplification tolerances (in degrees)
SIMPLIFICATION_TOLERANCE = {
    "ADM0": 0.001,  # ~100m
    "ADM1": 0.001,  # ~100m
    "ADM2": 0.0005, # ~50m
    "ADM3": 0.0005, # ~50m
    "ADM4": 0.0002, # ~20m
    "ADM5": 0.0002, # ~20m
}

# Continent folder mapping
CONTINENT_MAPPING = {
    "Africa": "Africa",
    "Asia": "Asia",
    "Europe": "Europe",
    "Latin_America_and_the_Caribbean": "LatinAmericaCaribbean",
    "Northern_America": "NorthernAmerica",
    "Oceania": "Oceania",
    "Undefined": "Undefined",
}

# Disputed territories
DISPUTED_TERRITORIES = ["TWN", "PSE", "XKX"]

# Default view coordinates for countries with distant territories
DEFAULT_VIEW_OVERRIDES = {
    "USA": {"center": [-98.5795, 39.8283], "zoom": 4},
    "FRA": {"center": [2.2137, 46.2276], "zoom": 5},
    "GBR": {"center": [-3.4359, 55.3781], "zoom": 5},
    "RUS": {"center": [37.6173, 55.7558], "zoom": 3},
    "CAN": {"center": [-106.3468, 56.1304], "zoom": 3},
    "AUS": {"center": [133.7751, -25.2744], "zoom": 4},
    "CHN": {"center": [104.1954, 35.8617], "zoom": 4},
    "BRA": {"center": [-51.9253, -14.2350], "zoom": 4},
    "IDN": {"center": [113.9213, -0.7893], "zoom": 4},
    "NZL": {"center": [174.8859, -40.9006], "zoom": 5},
    "DNK": {"center": [9.5018, 56.2639], "zoom": 6},
    "NLD": {"center": [5.2913, 52.1326], "zoom": 7},
    "CHL": {"center": [-71.5430, -35.6751], "zoom": 4},
}

# Administrative terminology lookup
ADMIN_TERMINOLOGY = {
    # AFRICA
    "DZA": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Commune"},
    "AGO": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Municipality", "ADM3": "Commune"},
    "BEN": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Commune", "ADM3": "Arrondissement"},
    "BWA": {"ADM0": "Country", "ADM1": "District", "ADM2": "Subdistrict"},
    "BFA": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Province", "ADM3": "Department"},
    "BDI": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Commune", "ADM3": "Colline"},
    "CPV": {"ADM0": "Country", "ADM1": "Island", "ADM2": "Municipality"},
    "CMR": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Department", "ADM3": "Subdivision"},
    "CAF": {"ADM0": "Country", "ADM1": "Prefecture", "ADM2": "Subprefecture", "ADM3": "Commune", "ADM5": "Village"},
    "TCD": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Department"},
    "COM": {"ADM0": "Country", "ADM1": "AutonomousIsland", "ADM2": "Prefecture", "ADM3": "Commune"},
    "COG": {"ADM0": "Country", "ADM1": "Department", "ADM2": "District"},
    "CIV": {"ADM0": "Country", "ADM1": "District", "ADM2": "Region", "ADM3": "Department"},
    "COD": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Territory"},
    "DJI": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "EGY": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "District"},
    "GNQ": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District"},
    "ERI": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "SWZ": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Tinkhundla"},
    "ETH": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Zone", "ADM3": "Woreda"},
    "GAB": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Department"},
    "GMB": {"ADM0": "Country", "ADM1": "LocalGovernmentArea", "ADM2": "District", "ADM3": "Ward"},
    "GHA": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "GIN": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Prefecture", "ADM3": "Subprefecture"},
    "GNB": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Sector"},
    "KEN": {"ADM0": "Country", "ADM1": "County", "ADM2": "Subcounty", "ADM3": "Ward"},
    "LSO": {"ADM0": "Country", "ADM1": "District", "ADM2": "Constituency"},
    "LBR": {"ADM0": "Country", "ADM1": "County", "ADM2": "District"},
    "LBY": {"ADM0": "Country", "ADM1": "Municipality"},
    "MDG": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District", "ADM3": "Commune", "ADM4": "Fokontany"},
    "MWI": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District", "ADM3": "TraditionalAuthority"},
    "MLI": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Circle", "ADM3": "Commune"},
    "MRT": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Department"},
    "MUS": {"ADM0": "Country", "ADM1": "District"},
    "MYT": {"ADM0": "Territory", "ADM4": "Commune"},
    "MAR": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Province"},
    "MOZ": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "AdministrativePost"},
    "NAM": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Constituency"},
    "NER": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Department", "ADM3": "Commune"},
    "NGA": {"ADM0": "Country", "ADM1": "State", "ADM2": "LocalGovernmentArea"},
    "RWA": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Sector", "ADM4": "Cell", "ADM5": "Village"},
    "REU": {"ADM0": "Territory", "ADM3": "Arrondissement", "ADM4": "Commune"},
    "SHN": {"ADM0": "Territory"},
    "STP": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District"},
    "SEN": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Department", "ADM3": "Arrondissement"},
    "SYC": {"ADM0": "Country", "ADM1": "IslandGroup", "ADM2": "Island", "ADM3": "District"},
    "SLE": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Chiefdom", "ADM4": "Section"},
    "SOM": {"ADM0": "Country", "ADM1": "FederalMemberState", "ADM2": "Region"},
    "ZAF": {"ADM0": "Country", "ADM1": "Province", "ADM2": "DistrictMunicipality", "ADM3": "LocalMunicipality", "ADM4": "Ward"},
    "SSD": {"ADM0": "Country", "ADM1": "State", "ADM2": "County"},
    "SDN": {"ADM0": "Country", "ADM1": "State", "ADM2": "Locality"},
    "TGO": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Prefecture"},
    "TUN": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "Delegation", "ADM3": "Sector"},
    "UGA": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District", "ADM3": "County", "ADM4": "Subcounty"},
    "TZA": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District", "ADM3": "Ward"},
    "ZMB": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District"},
    "ZWE": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Ward"},

    # ASIA
    "AFG": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District"},
    "ARM": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Municipality"},
    "AZE": {"ADM0": "Country", "ADM1": "District", "ADM2": "Municipality"},
    "BHR": {"ADM0": "Country", "ADM1": "Governorate"},
    "BGD": {"ADM0": "Country", "ADM1": "Division", "ADM2": "District", "ADM3": "Upazila", "ADM4": "Union"},
    "BTN": {"ADM0": "Country", "ADM1": "District", "ADM2": "Block"},
    "BRN": {"ADM0": "Country", "ADM1": "District", "ADM2": "Subdistrict"},
    "KHM": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Commune"},
    "CHN": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Prefecture", "ADM3": "County"},
    "CYP": {"ADM0": "Country", "ADM1": "District", "ADM2": "Municipality"},
    "PRK": {"ADM0": "Country", "ADM1": "Province", "ADM2": "County"},
    "GEO": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Municipality"},
    "IND": {"ADM0": "Country", "ADM1": "State", "ADM2": "District", "ADM3": "Subdistrict", "ADM4": "Block", "ADM5": "Village"},
    "IDN": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Regency"},
    "IRN": {"ADM0": "Country", "ADM1": "Province", "ADM2": "County", "ADM3": "District", "ADM4": "RuralDistrict"},
    "IRQ": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "District"},
    "ISR": {"ADM0": "Country", "ADM1": "District", "ADM2": "Subdistrict"},
    "JPN": {"ADM0": "Country", "ADM1": "Prefecture", "ADM2": "Municipality"},
    "JOR": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "District"},
    "KAZ": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "KWT": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "Area"},
    "KGZ": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "LAO": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District"},
    "LBN": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "District"},
    "MYS": {"ADM0": "Country", "ADM1": "State", "ADM2": "District", "ADM3": "Subdistrict"},
    "MDV": {"ADM0": "Country", "ADM1": "Atoll", "ADM2": "Island"},
    "MNG": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District"},
    "MMR": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District", "ADM3": "Township"},
    "NPL": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Municipality"},
    "OMN": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "Wilayat"},
    "PAK": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Tehsil"},
    "PSE": {"ADM0": "Territory", "ADM1": "Governorate", "ADM2": "Municipality"},
    "PHL": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Province", "ADM3": "Municipality"},
    "QAT": {"ADM0": "Country", "ADM1": "Municipality"},
    "KOR": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District"},
    "SAU": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Governorate"},
    "SGP": {"ADM0": "Country", "ADM1": "PlanningArea", "ADM2": "Subzone"},
    "LKA": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "DivisionalSecretariat"},
    "SYR": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "District"},
    "TWN": {"ADM0": "Country", "ADM1": "SpecialMunicipality", "ADM2": "District"},
    "TJK": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "THA": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Subdistrict"},
    "TLS": {"ADM0": "Country", "ADM1": "Municipality", "ADM2": "AdministrativePost", "ADM3": "Suco"},
    "TUR": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District"},
    "TKM": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "ARE": {"ADM0": "Country", "ADM1": "Emirate"},
    "UZB": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "VNM": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Commune"},
    "YEM": {"ADM0": "Country", "ADM1": "Governorate", "ADM2": "District"},

    # EUROPE
    "ALB": {"ADM0": "Country", "ADM1": "County", "ADM2": "Municipality"},
    "AND": {"ADM0": "Country", "ADM1": "Parish"},
    "AUT": {"ADM0": "Country", "ADM1": "State", "ADM2": "District"},
    "BLR": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "BEL": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Province", "ADM3": "Municipality"},
    "BIH": {"ADM0": "Country", "ADM1": "Entity", "ADM2": "Canton", "ADM3": "Municipality"},
    "BGR": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Municipality"},
    "HRV": {"ADM0": "Country", "ADM1": "County", "ADM2": "Municipality"},
    "CZE": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District"},
    "DNK": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Municipality"},
    "EST": {"ADM0": "Country", "ADM1": "County", "ADM2": "Municipality"},
    "FIN": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Municipality"},
    "FRA": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Department", "ADM3": "Arrondissement", "ADM4": "Canton", "ADM5": "Commune"},
    "DEU": {"ADM0": "Country", "ADM1": "State", "ADM2": "District", "ADM3": "Municipality"},
    "GIB": {"ADM0": "Territory"},
    "GRC": {"ADM0": "Country", "ADM1": "AdministrativeRegion", "ADM2": "RegionalUnit", "ADM3": "Municipality"},
    "HUN": {"ADM0": "Country", "ADM1": "County", "ADM2": "District"},
    "ISL": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Municipality"},
    "IRL": {"ADM0": "Country", "ADM1": "Province", "ADM2": "County"},
    "ITA": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Province", "ADM3": "Municipality"},
    "XKX": {"ADM0": "Country", "ADM1": "District", "ADM2": "Municipality"},
    "LVA": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Municipality"},
    "LIE": {"ADM0": "Country", "ADM1": "Municipality"},
    "LTU": {"ADM0": "Country", "ADM1": "County", "ADM2": "Municipality"},
    "LUX": {"ADM0": "Country", "ADM1": "Canton", "ADM2": "Commune"},
    "MLT": {"ADM0": "Country", "ADM1": "LocalCouncil"},
    "MDA": {"ADM0": "Country", "ADM1": "District", "ADM2": "Municipality"},
    "MCO": {"ADM0": "Country", "ADM1": "Ward"},
    "MNE": {"ADM0": "Country", "ADM1": "Municipality"},
    "NLD": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Municipality"},
    "MKD": {"ADM0": "Country", "ADM1": "Municipality"},
    "NOR": {"ADM0": "Country", "ADM1": "County", "ADM2": "Municipality"},
    "POL": {"ADM0": "Country", "ADM1": "Voivodeship", "ADM2": "County", "ADM3": "Commune"},
    "PRT": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District", "ADM3": "Municipality"},
    "ROU": {"ADM0": "Country", "ADM1": "County", "ADM2": "Municipality"},
    "RUS": {"ADM0": "Country", "ADM1": "FederalSubject", "ADM2": "District"},
    "SMR": {"ADM0": "Country", "ADM1": "Municipality"},
    "SRB": {"ADM0": "Country", "ADM1": "District", "ADM2": "Municipality"},
    "SVK": {"ADM0": "Country", "ADM1": "Region", "ADM2": "District", "ADM3": "Municipality", "ADM4": "CadastralArea"},
    "SVN": {"ADM0": "Country", "ADM1": "StatisticalRegion", "ADM2": "Municipality"},
    "ESP": {"ADM0": "Country", "ADM1": "AutonomousCommunity", "ADM2": "Province", "ADM3": "Municipality"},
    "SWE": {"ADM0": "Country", "ADM1": "County", "ADM2": "Municipality", "ADM3": "Parish"},
    "CHE": {"ADM0": "Country", "ADM1": "Canton", "ADM2": "District", "ADM3": "Municipality"},
    "UKR": {"ADM0": "Country", "ADM1": "Oblast", "ADM2": "Raion", "ADM3": "Hromada"},
    "GBR": {"ADM0": "Country", "ADM1": "Country", "ADM2": "Region", "ADM3": "District"},

    # LATIN AMERICA AND CARIBBEAN
    "AIA": {"ADM0": "Territory"},
    "ATG": {"ADM0": "Country", "ADM1": "Parish"},
    "ARG": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Department"},
    "ABW": {"ADM0": "Country"},
    "BHS": {"ADM0": "Country", "ADM1": "District", "ADM2": "Subdivision"},
    "BRB": {"ADM0": "Country", "ADM1": "Parish"},
    "BLZ": {"ADM0": "Country", "ADM1": "District", "ADM2": "Constituency"},
    "BOL": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Province", "ADM3": "Municipality"},
    "BES": {"ADM0": "Territory"},
    "BRA": {"ADM0": "Country", "ADM1": "State", "ADM2": "Municipality"},
    "VGB": {"ADM0": "Territory"},
    "CYM": {"ADM0": "Territory"},
    "CHL": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Province", "ADM3": "Commune"},
    "COL": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Municipality"},
    "CRI": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Canton", "ADM3": "District"},
    "CUB": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Municipality"},
    "CUW": {"ADM0": "Country"},
    "DMA": {"ADM0": "Country", "ADM1": "Parish"},
    "DOM": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Municipality"},
    "ECU": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Canton"},
    "SLV": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Municipality"},
    "FLK": {"ADM0": "Territory"},
    "GUF": {"ADM0": "Territory", "ADM3": "Commune"},
    "GRD": {"ADM0": "Country", "ADM1": "Parish"},
    "GLP": {"ADM0": "Territory", "ADM4": "Commune"},
    "GTM": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Municipality"},
    "GUY": {"ADM0": "Country", "ADM1": "Region", "ADM2": "NeighbourhoodCouncil"},
    "HTI": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Arrondissement", "ADM3": "Commune"},
    "HND": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Municipality"},
    "JAM": {"ADM0": "Country", "ADM1": "Parish", "ADM2": "Constituency", "ADM3": "Community"},
    "MTQ": {"ADM0": "Territory", "ADM3": "Arrondissement", "ADM4": "Commune"},
    "MEX": {"ADM0": "Country", "ADM1": "State", "ADM2": "Municipality"},
    "MSR": {"ADM0": "Territory"},
    "NIC": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Municipality"},
    "PAN": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "Corregimiento"},
    "PRY": {"ADM0": "Country", "ADM1": "Department", "ADM2": "District"},
    "PER": {"ADM0": "Country", "ADM1": "Region", "ADM2": "Province"},
    "PRI": {"ADM0": "Territory", "ADM2": "Municipality", "ADM3": "Barrio"},
    "BLM": {"ADM0": "Territory"},
    "KNA": {"ADM0": "Country", "ADM1": "Parish"},
    "LCA": {"ADM0": "Country", "ADM1": "District", "ADM2": "Quarter"},
    "VCT": {"ADM0": "Country", "ADM1": "Parish"},
    "SUR": {"ADM0": "Country", "ADM1": "District", "ADM2": "Resort"},
    "TTO": {"ADM0": "Country", "ADM1": "Region"},
    "TCA": {"ADM0": "Territory"},
    "VIR": {"ADM0": "Territory", "ADM3": "Subdistrict"},
    "URY": {"ADM0": "Country", "ADM1": "Department", "ADM2": "Municipality"},
    "VEN": {"ADM0": "Country", "ADM1": "State", "ADM2": "Municipality"},

    # NORTHERN AMERICA
    "BMU": {"ADM0": "Territory"},
    "CAN": {"ADM0": "Country", "ADM1": "Province", "ADM2": "CensusDivision", "ADM3": "CensusSubdivision"},
    "GRL": {"ADM0": "Territory", "ADM1": "Municipality"},
    "USA": {"ADM0": "Country", "ADM1": "State", "ADM2": "County"},
    "SPM": {"ADM0": "Territory", "ADM1": "Commune"},

    # OCEANIA
    "ASM": {"ADM0": "Territory", "ADM3": "Village"},
    "AUS": {"ADM0": "Country", "ADM1": "State", "ADM2": "LocalGovernmentArea"},
    "COK": {"ADM0": "Territory"},
    "FJI": {"ADM0": "Country", "ADM1": "Division", "ADM2": "Province", "ADM3": "District", "ADM4": "Village"},
    "PYF": {"ADM0": "Territory"},
    "GUM": {"ADM0": "Territory", "ADM2": "Village"},
    "KIR": {"ADM0": "Country", "ADM1": "District", "ADM2": "IslandCouncil"},
    "MHL": {"ADM0": "Country", "ADM1": "Municipality"},
    "FSM": {"ADM0": "Country", "ADM1": "State", "ADM2": "Municipality"},
    "NRU": {"ADM0": "Country", "ADM1": "District"},
    "NCL": {"ADM0": "Territory"},
    "NZL": {"ADM0": "Country", "ADM1": "Region", "ADM2": "TerritorialAuthority", "ADM3": "Ward"},
    "NIU": {"ADM0": "Territory", "ADM1": "Village"},
    "MNP": {"ADM0": "Territory", "ADM2": "Municipality"},
    "PLW": {"ADM0": "Country", "ADM1": "State", "ADM2": "Hamlet"},
    "PNG": {"ADM0": "Country", "ADM1": "Province", "ADM2": "District", "ADM3": "LocalLevelGovernmentArea"},
    "PCN": {"ADM0": "Territory"},
    "WSM": {"ADM0": "Country", "ADM1": "District", "ADM2": "Subdistrict"},
    "SLB": {"ADM0": "Country", "ADM1": "Province", "ADM2": "Constituency", "ADM3": "Ward", "ADM4": "CensusUnit"},
    "TKL": {"ADM0": "Territory"},
    "TON": {"ADM0": "Country", "ADM1": "Division", "ADM2": "District"},
    "TUV": {"ADM0": "Country", "ADM1": "IslandCouncil", "ADM2": "CouncilArea", "ADM3": "ElectoralDistrict"},
    "VUT": {"ADM0": "Country", "ADM1": "Province", "ADM2": "AreaCouncil", "ADM3": "Ward"},
    "WLF": {"ADM0": "Territory"},

    # UNDEFINED
    "ATA": {"ADM0": "Continent"},
}

# Country name lookup from the boundary catalog
COUNTRY_NAMES = {}


def load_country_names():
    """Load country names from boundary catalog."""
    global COUNTRY_NAMES
    catalog_path = SOURCE_DIR / "boundary_catalog.json"
    if catalog_path.exists():
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
            for entry in catalog:
                iso = entry.get("boundaryISO")
                name = entry.get("boundaryName")
                if iso and name and iso not in COUNTRY_NAMES:
                    COUNTRY_NAMES[iso] = name
    logger.info(f"Loaded {len(COUNTRY_NAMES)} country names from catalog")


def get_terminology(iso: str, level: str) -> str:
    """Get the administrative terminology for a given ISO code and level."""
    if iso in ADMIN_TERMINOLOGY and level in ADMIN_TERMINOLOGY[iso]:
        return ADMIN_TERMINOLOGY[iso][level]
    # Fallback to generic ADM level
    return level


def to_pascal_case(term: str) -> str:
    """Convert a term to PascalCase for file naming."""
    # Remove spaces and special characters
    return ''.join(word.capitalize() for word in term.replace(' ', '').split())


def validate_and_fix_geometry(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Validate and fix invalid geometries."""
    fixed_geometries = []
    for geom in gdf.geometry:
        if geom is None:
            fixed_geometries.append(None)
        elif not geom.is_valid:
            try:
                fixed = make_valid(geom)
                fixed_geometries.append(fixed)
            except Exception as e:
                logger.warning(f"Could not fix geometry: {e}")
                fixed_geometries.append(geom)
        else:
            fixed_geometries.append(geom)

    gdf = gdf.copy()
    gdf['geometry'] = fixed_geometries
    return gdf


def simplify_geometries(gdf: gpd.GeoDataFrame, level: str) -> gpd.GeoDataFrame:
    """Simplify geometries based on admin level tolerance."""
    tolerance = SIMPLIFICATION_TOLERANCE.get(level, 0.0005)
    gdf = gdf.copy()
    gdf['geometry'] = gdf.geometry.simplify(tolerance, preserve_topology=True)
    return gdf


def calculate_centroid(gdf: gpd.GeoDataFrame) -> tuple:
    """Calculate the centroid of a GeoDataFrame."""
    try:
        # Combine all geometries and calculate centroid
        combined = unary_union(gdf.geometry)
        centroid = combined.centroid
        return [round(centroid.x, 4), round(centroid.y, 4)]
    except Exception as e:
        logger.warning(f"Could not calculate centroid: {e}")
        return [0, 0]


def calculate_zoom_level(gdf: gpd.GeoDataFrame) -> int:
    """Estimate an appropriate zoom level based on the bounding box."""
    try:
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        max_dimension = max(width, height)

        # Approximate zoom levels based on dimension
        if max_dimension > 100:
            return 2
        elif max_dimension > 50:
            return 3
        elif max_dimension > 20:
            return 4
        elif max_dimension > 10:
            return 5
        elif max_dimension > 5:
            return 6
        elif max_dimension > 2:
            return 7
        elif max_dimension > 1:
            return 8
        elif max_dimension > 0.5:
            return 9
        else:
            return 10
    except Exception:
        return 5


def process_geojson_file(input_path: Path, output_path: Path, level: str) -> dict:
    """Process a single GeoJSON file and return feature info for search index."""
    features_info = []

    try:
        # Read GeoJSON
        gdf = gpd.read_file(input_path)

        # Validate and fix geometries
        gdf = validate_and_fix_geometry(gdf)

        # Remove any rows with null geometries
        gdf = gdf[gdf.geometry.notna()]

        if len(gdf) == 0:
            logger.warning(f"No valid geometries in {input_path}")
            return features_info

        # Simplify geometries
        gdf = simplify_geometries(gdf, level)

        # Ensure WGS84 CRS
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        elif gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")

        # Extract ISO from filename
        iso = input_path.stem.split('_')[0]
        term = get_terminology(iso, level)

        # Collect feature info for search index
        for idx, row in gdf.iterrows():
            shape_name = row.get('shapeName', '')
            if shape_name:
                try:
                    centroid = row.geometry.centroid
                    center = [round(centroid.x, 4), round(centroid.y, 4)]
                except Exception:
                    center = [0, 0]

                # Build hierarchy (simplified - just the unit name and country)
                country_name = COUNTRY_NAMES.get(iso, iso)
                hierarchy = [shape_name]
                if level != "ADM0":
                    hierarchy.append(country_name)

                feature_id = f"{iso}_{level}_{shape_name.replace(' ', '_').replace('/', '_')}"
                features_info.append({
                    "id": feature_id,
                    "name": shape_name,
                    "type": term,
                    "level": level,
                    "iso": iso,
                    "hierarchy": hierarchy,
                    "center": center
                })

        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to GeoJSON
        gdf.to_file(output_path, driver='GeoJSON')

        logger.info(f"Processed: {input_path.name} -> {output_path.name} ({len(gdf)} features)")

    except Exception as e:
        logger.error(f"Error processing {input_path}: {e}")

    return features_info


def process_all_countries():
    """Process all countries and generate output files."""

    # Load country names
    load_country_names()

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Data structures for config files
    terminology_data = {}
    countries_list = []
    search_index = []
    content_data = {}

    # Statistics
    total_files = 0
    processed_files = 0

    # Process each continent
    for source_continent, output_continent in CONTINENT_MAPPING.items():
        source_continent_path = SOURCE_DIR / source_continent
        output_continent_path = OUTPUT_DIR / output_continent

        if not source_continent_path.exists():
            logger.warning(f"Continent folder not found: {source_continent}")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing continent: {source_continent} -> {output_continent}")
        logger.info(f"{'='*60}")

        # Get all country folders
        country_folders = [f for f in source_continent_path.iterdir()
                         if f.is_dir() and not f.name.startswith('.')]

        for country_folder in sorted(country_folders):
            # Extract ISO code from folder name (e.g., "USA_United_States_of_America" -> "USA")
            folder_name = country_folder.name
            iso = folder_name.split('_')[0]
            country_name = COUNTRY_NAMES.get(iso, '_'.join(folder_name.split('_')[1:]).replace('_', ' '))

            # Get all GeoJSON files
            geojson_files = list(country_folder.glob("*.geojson"))
            if not geojson_files:
                logger.warning(f"No GeoJSON files in {country_folder}")
                continue

            logger.info(f"\nProcessing: {iso} - {country_name}")

            # Create output country folder
            output_country_path = output_continent_path / iso
            output_country_path.mkdir(parents=True, exist_ok=True)

            # Initialize terminology entry
            is_disputed = iso in DISPUTED_TERRITORIES
            terminology_entry = {
                "name": country_name + (" (Disputed Territory)" if is_disputed else ""),
                "continent": output_continent,
                "disputed": is_disputed,
                "defaultView": {},
                "levels": {}
            }

            # Content entry
            content_data[iso] = {}

            # Track ADM0 for default view calculation
            adm0_gdf = None

            # Process each GeoJSON file
            for geojson_file in sorted(geojson_files):
                total_files += 1

                # Extract admin level (e.g., "USA_ADM1.geojson" -> "ADM1")
                level = geojson_file.stem.split('_')[-1]

                # Get terminology
                term = get_terminology(iso, level)
                pascal_term = to_pascal_case(term)

                # Create output filename
                output_filename = f"{iso}_{level}_{pascal_term}.geojson"
                output_path = output_country_path / output_filename

                # Process the file
                features_info = process_geojson_file(geojson_file, output_path, level)

                if output_path.exists():
                    processed_files += 1

                    # Add to terminology
                    terminology_entry["levels"][level] = {
                        "term": term,
                        "file": output_filename
                    }

                    # Add to content structure
                    content_data[iso][level] = {}

                    # Add features to search index
                    search_index.extend(features_info)

                    # Store ADM0 for default view
                    if level == "ADM0":
                        try:
                            adm0_gdf = gpd.read_file(output_path)
                        except Exception:
                            pass

            # Calculate default view
            if iso in DEFAULT_VIEW_OVERRIDES:
                terminology_entry["defaultView"] = DEFAULT_VIEW_OVERRIDES[iso]
            elif adm0_gdf is not None and len(adm0_gdf) > 0:
                center = calculate_centroid(adm0_gdf)
                zoom = calculate_zoom_level(adm0_gdf)
                terminology_entry["defaultView"] = {
                    "center": center,
                    "zoom": zoom
                }
            else:
                # Try to calculate from any available level
                for level_key in terminology_entry["levels"]:
                    try:
                        level_file = output_country_path / terminology_entry["levels"][level_key]["file"]
                        if level_file.exists():
                            gdf = gpd.read_file(level_file)
                            center = calculate_centroid(gdf)
                            zoom = calculate_zoom_level(gdf)
                            terminology_entry["defaultView"] = {
                                "center": center,
                                "zoom": zoom
                            }
                            break
                    except Exception:
                        continue

            # Add to terminology data
            if terminology_entry["levels"]:
                terminology_data[iso] = terminology_entry

                # Add to countries list
                display_name = country_name
                if is_disputed:
                    display_name += " (Disputed Territory)"
                countries_list.append({
                    "iso": iso,
                    "name": display_name,
                    "disputed": is_disputed
                })

    # Sort countries alphabetically
    countries_list.sort(key=lambda x: x["name"])

    # Write terminology.json
    terminology_path = OUTPUT_DIR / "terminology.json"
    with open(terminology_path, 'w', encoding='utf-8') as f:
        json.dump(terminology_data, f, indent=2, ensure_ascii=False)
    logger.info(f"\nWritten: {terminology_path}")

    # Write countries.json
    countries_path = OUTPUT_DIR / "countries.json"
    with open(countries_path, 'w', encoding='utf-8') as f:
        json.dump(countries_list, f, indent=2, ensure_ascii=False)
    logger.info(f"Written: {countries_path}")

    # Write search-index.json
    search_path = OUTPUT_DIR / "search-index.json"
    with open(search_path, 'w', encoding='utf-8') as f:
        json.dump({"index": search_index}, f, indent=2, ensure_ascii=False)
    logger.info(f"Written: {search_path}")

    # Write content.json
    content_path = OUTPUT_DIR / "content.json"
    with open(content_path, 'w', encoding='utf-8') as f:
        json.dump(content_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Written: {content_path}")

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info(f"PROCESSING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total GeoJSON files found: {total_files}")
    logger.info(f"Successfully processed: {processed_files}")
    logger.info(f"Countries processed: {len(terminology_data)}")
    logger.info(f"Search index entries: {len(search_index)}")
    logger.info(f"Output directory: {OUTPUT_DIR}")


def run_quality_checks():
    """Run quality checks on the output."""
    logger.info(f"\n{'='*60}")
    logger.info("RUNNING QUALITY CHECKS")
    logger.info(f"{'='*60}")

    issues = []

    # Check configuration files
    config_files = ["terminology.json", "countries.json", "search-index.json", "content.json"]
    for config_file in config_files:
        config_path = OUTPUT_DIR / config_file
        if config_path.exists():
            size_kb = config_path.stat().st_size / 1024
            logger.info(f"  {config_file}: {size_kb:.1f} KB")
            try:
                with open(config_path, 'r') as f:
                    json.load(f)
                logger.info(f"    Valid JSON")
            except json.JSONDecodeError as e:
                issues.append(f"{config_file}: Invalid JSON - {e}")
        else:
            issues.append(f"{config_file}: Missing")

    # Check GeoJSON files
    total_geojson = 0
    valid_geojson = 0
    size_warnings = []

    for geojson_file in OUTPUT_DIR.rglob("*.geojson"):
        total_geojson += 1
        size_kb = geojson_file.stat().st_size / 1024

        # Check size
        level = geojson_file.stem.split('_')[1] if '_' in geojson_file.stem else ""
        max_sizes = {"ADM0": 500, "ADM1": 1000, "ADM2": 2000, "ADM3": 3000, "ADM4": 3000, "ADM5": 3000}
        max_size = max_sizes.get(level, 2000)

        if size_kb > max_size:
            size_warnings.append(f"{geojson_file.relative_to(OUTPUT_DIR)}: {size_kb:.1f} KB (exceeds {max_size} KB)")

        # Validate GeoJSON
        try:
            gdf = gpd.read_file(geojson_file)
            if len(gdf) > 0:
                valid_geojson += 1
            else:
                issues.append(f"{geojson_file.relative_to(OUTPUT_DIR)}: Empty GeoDataFrame")
        except Exception as e:
            issues.append(f"{geojson_file.relative_to(OUTPUT_DIR)}: Invalid - {e}")

    logger.info(f"\nGeoJSON files: {valid_geojson}/{total_geojson} valid")

    if size_warnings:
        logger.warning(f"\nSize warnings ({len(size_warnings)}):")
        for warning in size_warnings[:10]:
            logger.warning(f"  {warning}")
        if len(size_warnings) > 10:
            logger.warning(f"  ... and {len(size_warnings) - 10} more")

    if issues:
        logger.error(f"\nIssues found ({len(issues)}):")
        for issue in issues:
            logger.error(f"  {issue}")
    else:
        logger.info("\nNo critical issues found!")

    return len(issues) == 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process GeoBoundaries data for web deployment")
    parser.add_argument("--check-only", action="store_true", help="Only run quality checks")
    args = parser.parse_args()

    if args.check_only:
        run_quality_checks()
    else:
        process_all_countries()
        run_quality_checks()
