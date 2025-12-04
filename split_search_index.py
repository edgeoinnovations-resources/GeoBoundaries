#!/usr/bin/env python3
"""
Split the search-index.json by continent for better web performance.
"""

import json
from pathlib import Path
from collections import defaultdict

OUTPUT_DIR = Path("/Users/paulstrootman/Desktop/StagingFolder")

# Load terminology to get continent mapping for each ISO
print("Loading terminology.json...")
with open(OUTPUT_DIR / "terminology.json", 'r', encoding='utf-8') as f:
    terminology = json.load(f)

# Build ISO to continent mapping
iso_to_continent = {}
for iso, data in terminology.items():
    iso_to_continent[iso] = data.get("continent", "Undefined")

print(f"Loaded {len(iso_to_continent)} country mappings")

# Load the full search index
print("Loading search-index.json (this may take a moment)...")
with open(OUTPUT_DIR / "search-index.json", 'r', encoding='utf-8') as f:
    search_data = json.load(f)

full_index = search_data["index"]
print(f"Loaded {len(full_index)} search entries")

# Split by continent
continent_indices = defaultdict(list)
unmapped_count = 0

for entry in full_index:
    iso = entry.get("iso", "")
    continent = iso_to_continent.get(iso, "Undefined")
    continent_indices[continent].append(entry)

# Write continent-specific search indices
print("\nWriting continent search indices...")
for continent, entries in sorted(continent_indices.items()):
    output_file = OUTPUT_DIR / f"search-index-{continent}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"index": entries}, f, indent=2, ensure_ascii=False)
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"  {continent}: {len(entries):,} entries ({size_mb:.1f} MB)")

# Create a manifest file listing all continent indices
manifest = {
    "continents": {}
}
for continent, entries in sorted(continent_indices.items()):
    manifest["continents"][continent] = {
        "file": f"search-index-{continent}.json",
        "count": len(entries)
    }

manifest_file = OUTPUT_DIR / "search-index-manifest.json"
with open(manifest_file, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
print(f"\nWritten manifest: {manifest_file}")

# Remove the old monolithic search-index.json
old_index = OUTPUT_DIR / "search-index.json"
if old_index.exists():
    old_index.unlink()
    print(f"Removed old {old_index.name}")

print("\nDone! Search indices are now split by continent.")
