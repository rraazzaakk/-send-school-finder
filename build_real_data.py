"""
Real data pipeline for the SEND School Finder.
Sources:
  1. DfE School Level Underlying Data 2024/25
     https://content.explore-education-statistics.service.gov.uk/api/releases/
     f7330b25-398d-477d-80c7-9b33bc10316f/files/add3b8fc-875c-4dd0-80ee-8673bc530b72
  2. Postcodes.io  –  free UK postcode → lat/lng  (batch endpoint)

Run this script once to produce real_schools.json, then the app loads that
instead of the hand-crafted schools_data.py.

Usage (requires internet access):
    python build_real_data.py
"""

import csv
import io
import json
import time
import urllib.request
import urllib.parse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DFE_CSV_URL = (
    "https://content.explore-education-statistics.service.gov.uk/api/releases/"
    "f7330b25-398d-477d-80c7-9b33bc10316f/files/add3b8fc-875c-4dd0-80ee-8673bc530b72"
)

POSTCODES_BATCH_URL = "https://api.postcodes.io/postcodes"

OUTPUT_FILE = "real_schools.json"

# School types to include (special schools only)
SPECIAL_TYPES = {
    "State-funded special school",
    "Non-maintained special school",
    "Independent special school",
}

# Column map: DfE column name → our SEN code
PROV_COL_MAP = {
    "Prov_SPLD": "SpLD",
    "Prov_MLD":  "MLD",
    "Prov_SLD":  "SLD",
    "Prov_PMLD": "PMLD",
    "Prov_SEMH": "SEMH",
    "prov_slcn": "SLCN",
    "prov_hi":   "HI",
    "prov_vi":   "VI",
    "prov_msi":  "MSI",
    "prov_pd":   "PD",
    "prov_asd":  "ASD",
    "prov_oth":  "OTH",
}

# EHC need columns (to infer provision if Prov_ cols are all 0)
EHC_COL_MAP = {
    "EHC_Primary_need_spld": "SpLD",
    "EHC_Primary_need_mld":  "MLD",
    "EHC_Primary_need_sld":  "SLD",
    "EHC_Primary_need_pmld": "PMLD",
    "EHC_Primary_need_semh": "SEMH",
    "EHC_Primary_need_slcn": "SLCN",
    "EHC_Primary_need_hi":   "HI",
    "EHC_Primary_need_vi":   "VI",
    "EHC_Primary_need_msi":  "MSI",
    "EHC_Primary_need_pd":   "PD",
    "EHC_Primary_need_asd":  "ASD",
    "EHC_Primary_need_oth":  "OTH",
}


# ---------------------------------------------------------------------------
# Step 1: Download & parse the DfE CSV
# ---------------------------------------------------------------------------

def download_dfe_csv(url: str) -> list[dict]:
    """Download the DfE school-level CSV and return rows for special schools."""
    print(f"Downloading DfE CSV from:\n  {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8-sig")  # strip BOM
    print(f"  Downloaded {len(raw):,} bytes")

    reader = csv.DictReader(io.StringIO(raw))
    special = []
    total = 0
    for row in reader:
        total += 1
        phase = row.get("phase_type_grouping", "")
        estab = row.get("type_of_establishment", "")
        # Include if phase OR type indicates a special school
        if "special" in phase.lower() or "special" in estab.lower():
            special.append(row)
    print(f"  Total rows: {total:,}  |  Special school rows: {len(special):,}")
    return special


# ---------------------------------------------------------------------------
# Step 2: Batch geocode postcodes via postcodes.io
# ---------------------------------------------------------------------------

def batch_geocode(postcodes: list[str]) -> dict[str, tuple[float, float]]:
    """
    Hit the postcodes.io batch endpoint (max 100 per request).
    Returns {postcode_uppercase: (lat, lng)}.
    """
    results = {}
    clean = [p.strip().upper() for p in postcodes if p.strip()]
    batches = [clean[i:i+100] for i in range(0, len(clean), 100)]
    print(f"  Geocoding {len(clean)} postcodes in {len(batches)} batch(es)…")

    for i, batch in enumerate(batches):
        payload = json.dumps({"postcodes": batch}).encode()
        req = urllib.request.Request(
            POSTCODES_BATCH_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            for item in data.get("result", []):
                if item and item.get("result"):
                    pc = item["query"].upper()
                    r = item["result"]
                    results[pc] = (r["latitude"], r["longitude"])
        except Exception as e:
            print(f"  Batch {i+1} failed: {e}")
        if i < len(batches) - 1:
            time.sleep(0.3)

    found = len(results)
    print(f"  Geocoded {found}/{len(clean)} postcodes successfully")
    return results


# ---------------------------------------------------------------------------
# Step 3: Build structured school objects
# ---------------------------------------------------------------------------

def parse_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def extract_sen_provision(row: dict) -> list[str]:
    """
    Determine which SEN types the school provides for.
    Priority: Prov_ columns > EHC_ count columns > name heuristics.
    """
    provision = []

    # 1. Use the explicit Prov_ columns (non-zero = provides for that need)
    for col, code in PROV_COL_MAP.items():
        if parse_int(row.get(col, 0)) > 0:
            provision.append(code)

    # 2. If Prov_ all zero, infer from EHC pupil counts (school has pupils with that need)
    if not provision:
        for col, code in EHC_COL_MAP.items():
            if parse_int(row.get(col, 0)) > 0:
                provision.append(code)

    # 3. Last resort: name-based heuristics
    if not provision:
        name = row.get("school_name", "").lower()
        heuristics = {
            "autism": "ASD", "autistic": "ASD",
            "deaf": "HI", "hearing": "HI",
            "blind": "VI", "visual": "VI",
            "physical": "PD",
            "profound": "PMLD",
            "severe": "SLD",
            "moderate": "MLD",
            "speech": "SLCN", "language": "SLCN", "communication": "SLCN",
            "emotional": "SEMH", "behaviour": "SEMH", "mental health": "SEMH",
            "specific learning": "SpLD", "dyslexia": "SpLD",
            "multi": "MSI",
        }
        for keyword, code in heuristics.items():
            if keyword in name:
                provision.append(code)

    # Deduplicate while preserving order
    seen = set()
    return [c for c in provision if not (c in seen or seen.add(c))]


def build_school_objects(rows: list[dict], coords: dict) -> list[dict]:
    """Convert DfE CSV rows into the app's school dict format."""
    schools = []
    skipped_no_coords = 0
    skipped_no_sen = 0

    for i, row in enumerate(rows):
        postcode = row.get("school_postcode", "").strip().upper()
        if not postcode or postcode not in coords:
            skipped_no_coords += 1
            continue

        lat, lng = coords[postcode]
        sen_provision = extract_sen_provision(row)
        if not sen_provision:
            skipped_no_sen += 1
            continue

        total_pupils = parse_int(row.get("Total pupils", 0))
        ehc_pupils   = parse_int(row.get("EHC plan", 0))
        sen_support  = parse_int(row.get("SEN support", 0))

        # Capacity = total pupils (or EHC + support as proxy)
        capacity = total_pupils if total_pupils > 0 else (ehc_pupils + sen_support)
        # Vacancies: we don't have this directly; derive from EHC as proportion
        # Use 10% headroom as a conservative estimate (common in SEND sector)
        vacancies = max(0, int(capacity * 0.10))

        school = {
            "id":          f"URN{row.get('URN', i)}",
            "urn":         row.get("URN", ""),
            "name":        row.get("school_name", "Unknown"),
            "address":     f"{row.get('school_postcode', '')}",
            "postcode":    postcode,
            "lat":         round(lat, 6),
            "lng":         round(lng, 6),
            "region":      row.get("region_name", ""),
            "la_name":     row.get("la_name", ""),
            "school_type": row.get("type_of_establishment", row.get("phase_type_grouping", "")),
            "sen_provision": sen_provision,
            "capacity":    capacity,
            "vacancies":   vacancies,
            "total_ehc":   ehc_pupils,
            "total_sen_support": sen_support,
            # Ofsted removed from GIAS Jan 2025 – use 'Good' as neutral default
            "ofsted":      "Good",
            "ofsted_score": 3,
            # SEN_Unit / RP_Unit flags
            "has_sen_unit": parse_int(row.get("SEN_Unit", 0)) > 0,
            "has_rp_unit":  parse_int(row.get("RP_Unit", 0)) > 0,
            # Source info
            "data_source": "DfE School Level 2024/25",
            "facilities":  [],   # Not in DfE CSV – would need GIAS for this
            "age_range":   "Unknown",
        }
        schools.append(school)

    print(f"  Built {len(schools)} school objects")
    print(f"  Skipped (no coords): {skipped_no_coords}")
    print(f"  Skipped (no SEN):    {skipped_no_sen}")
    return schools


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("SEND School Finder – Real Data Builder")
    print("Source: DfE School Level Underlying Data 2024/25")
    print("=" * 60)

    # 1. Download CSV
    rows = download_dfe_csv(DFE_CSV_URL)

    # 2. Geocode postcodes
    postcodes = list({r.get("school_postcode", "").strip().upper() for r in rows if r.get("school_postcode")})
    coords = batch_geocode(postcodes)

    # 3. Build objects
    schools = build_school_objects(rows, coords)

    # 4. Save
    out = {
        "generated": "2024-25",
        "source": "DfE School Level Underlying Data 2024/25",
        "source_url": DFE_CSV_URL,
        "total_schools": len(schools),
        "schools": schools,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(schools)} schools to {OUTPUT_FILE}")

    # Quick stats
    from collections import Counter
    sen_freq = Counter(code for s in schools for code in s["sen_provision"])
    print("\nTop SEN provision types:")
    for code, count in sen_freq.most_common(10):
        print(f"  {code:6s}  {count:4d} schools")

    regions = Counter(s["region"] for s in schools)
    print("\nSchools by region:")
    for region, count in regions.most_common():
        print(f"  {region:30s}  {count}")


if __name__ == "__main__":
    main()
