#!/usr/bin/env python3
"""
Split the Asia search index by country for better web performance.
"""

import json
from pathlib import Path
from collections import defaultdict

OUTPUT_DIR = Path("/Users/paulstrootman/Desktop/StagingFolder")

# Load the Asia search index
print("Loading search-index-Asia.json...")
with open(OUTPUT_DIR / "search-index-Asia.json", 'r', encoding='utf-8') as f:
    asia_data = json.load(f)

asia_index = asia_data["index"]
print(f"Loaded {len(asia_index):,} Asia search entries")

# Split by country (ISO code)
country_indices = defaultdict(list)

for entry in asia_index:
    iso = entry.get("iso", "UNKNOWN")
    country_indices[iso].append(entry)

# Create Asia subdirectory for country indices
asia_search_dir = OUTPUT_DIR / "search-index-Asia"
asia_search_dir.mkdir(exist_ok=True)

# Write country-specific search indices
print("\nWriting country search indices for Asia...")
country_manifest = {}

for iso, entries in sorted(country_indices.items()):
    output_file = asia_search_dir / f"search-index-{iso}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"index": entries}, f, ensure_ascii=False)
    size_kb = output_file.stat().st_size / 1024
    size_mb = size_kb / 1024

    if size_mb >= 1:
        print(f"  {iso}: {len(entries):,} entries ({size_mb:.1f} MB)")
    else:
        print(f"  {iso}: {len(entries):,} entries ({size_kb:.1f} KB)")

    country_manifest[iso] = {
        "file": f"search-index-Asia/{output_file.name}",
        "count": len(entries)
    }

# Update the main manifest
print("\nUpdating search-index-manifest.json...")
with open(OUTPUT_DIR / "search-index-manifest.json", 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Replace Asia entry with country breakdown
manifest["continents"]["Asia"] = {
    "splitByCountry": True,
    "countries": country_manifest,
    "totalCount": len(asia_index)
}

with open(OUTPUT_DIR / "search-index-manifest.json", 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

# Remove the old monolithic Asia search index
old_asia_index = OUTPUT_DIR / "search-index-Asia.json"
if old_asia_index.exists():
    old_asia_index.unlink()
    print(f"Removed old {old_asia_index.name}")

print("\nDone! Asia search index is now split by country.")
