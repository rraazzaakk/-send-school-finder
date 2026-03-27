"""
data_loader.py  –  unified school data access layer

Priority order:
  1. real_schools.json  (produced by build_real_data.py from DfE 2024/25 CSV)
  2. schools_data.py    (hand-modelled fallback, same schema)

Callers import `get_schools()` and never touch the source directly.
"""
import json
import os

_REAL_DATA_PATH = os.path.join(os.path.dirname(__file__), "real_schools.json")

# cached after first load
_schools_cache = None
_data_source    = None


def get_schools() -> list[dict]:
    global _schools_cache, _data_source
    if _schools_cache is not None:
        return _schools_cache

    if os.path.exists(_REAL_DATA_PATH):
        try:
            with open(_REAL_DATA_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
            _schools_cache = payload["schools"]
            _data_source = f"DfE School Level Underlying Data 2024/25 ({payload['total_schools']} schools)"
            print(f"[data_loader] Loaded REAL data: {len(_schools_cache)} schools from real_schools.json")
            return _schools_cache
        except Exception as e:
            print(f"[data_loader] Could not load real_schools.json ({e}), falling back to modelled data")

    # Fallback
    from schools_data import SCHOOLS
    _schools_cache = SCHOOLS
    _data_source = "Modelled data (45 schools) — run build_real_data.py to use real DfE data"
    print(f"[data_loader] Using MODELLED data: {len(_schools_cache)} schools")
    return _schools_cache


def get_data_source() -> str:
    get_schools()   # ensure loaded
    return _data_source or "Unknown"


def reload():
    """Force reload (useful after CSV upload)."""
    global _schools_cache, _data_source
    _schools_cache = None
    _data_source   = None
    return get_schools()


# ---------------------------------------------------------------------------
# In-process CSV ingestion  (called by the Flask /api/upload endpoint)
# ---------------------------------------------------------------------------

import csv
import io

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


def _parse_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _extract_sen(row):
    provision = []
    for col, code in PROV_COL_MAP.items():
        if _parse_int(row.get(col, 0)) > 0:
            provision.append(code)
    if not provision:
        for col, code in EHC_COL_MAP.items():
            if _parse_int(row.get(col, 0)) > 0:
                provision.append(code)
    if not provision:
        name = row.get("school_name", "").lower()
        mapping = {
            "autism": "ASD", "autistic": "ASD",
            "deaf": "HI", "hearing": "HI",
            "blind": "VI", "visual": "VI",
            "physical": "PD",
            "profound": "PMLD",
            "severe": "SLD",
            "moderate": "MLD",
            "speech": "SLCN", "language": "SLCN",
            "emotional": "SEMH", "behaviour": "SEMH",
            "dyslexia": "SpLD",
            "multi": "MSI",
        }
        for kw, code in mapping.items():
            if kw in name:
                provision.append(code)
    seen = set()
    return [c for c in provision if not (c in seen or seen.add(c))]


def ingest_csv_bytes(csv_bytes: bytes, coords_map: dict) -> dict:
    """
    Parse DfE CSV bytes, filter special schools, merge coordinates,
    save real_schools.json and reload cache.

    coords_map: {POSTCODE_UPPER: (lat, lng)}
    Returns summary dict.
    """
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    schools = []
    stats = {"total_rows": 0, "special_rows": 0, "geocoded": 0, "no_coords": 0, "no_sen": 0}

    for row in reader:
        stats["total_rows"] += 1
        phase = row.get("phase_type_grouping", "")
        estab = row.get("type_of_establishment", "")
        if "special" not in phase.lower() and "special" not in estab.lower():
            continue
        stats["special_rows"] += 1

        postcode = row.get("school_postcode", "").strip().upper()
        if not postcode or postcode not in coords_map:
            stats["no_coords"] += 1
            continue

        lat, lng = coords_map[postcode]
        sen = _extract_sen(row)
        if not sen:
            stats["no_sen"] += 1
            continue

        total = _parse_int(row.get("Total pupils", 0))
        ehc   = _parse_int(row.get("EHC plan", 0))
        sup   = _parse_int(row.get("SEN support", 0))
        cap   = total if total > 0 else (ehc + sup)
        vac   = max(0, int(cap * 0.10))

        schools.append({
            "id":           f"URN{row.get('URN', '')}",
            "urn":          row.get("URN", ""),
            "name":         row.get("school_name", "Unknown"),
            "address":      postcode,
            "postcode":     postcode,
            "lat":          round(lat, 6),
            "lng":          round(lng, 6),
            "region":       row.get("region_name", ""),
            "la_name":      row.get("la_name", ""),
            "school_type":  row.get("type_of_establishment", phase),
            "sen_provision": sen,
            "capacity":     cap,
            "vacancies":    vac,
            "total_ehc":    ehc,
            "total_sen_support": sup,
            "ofsted":       "Good",
            "ofsted_score": 3,
            "has_sen_unit": _parse_int(row.get("SEN_Unit", 0)) > 0,
            "has_rp_unit":  _parse_int(row.get("RP_Unit", 0)) > 0,
            "data_source":  "DfE School Level 2024/25",
            "facilities":   [],
            "age_range":    "Unknown",
        })
        stats["geocoded"] += 1

    payload = {
        "generated":     "2024-25",
        "source":        "DfE School Level Underlying Data 2024/25",
        "source_url":    "https://explore-education-statistics.service.gov.uk/find-statistics/special-educational-needs-in-england/2024-25",
        "total_schools": len(schools),
        "schools":       schools,
    }
    with open(_REAL_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    reload()
    stats["schools_saved"] = len(schools)
    return stats
