"""
Matching engine for the SEND School Identification System.

Three-stage pipeline:
  1. SEN profile filter  – hard filter: keep only schools that cover ALL stated needs
  2. Distance ranking    – haversine distance from user postcode (Dijkstra proxy)
  3. Composite scoring   – weighted sum of need_match, proximity, capacity, ofsted
"""
import math
from schools_data import SCHOOLS, FACILITY_LABELS, SEN_LABELS, OFSTED_ORDER

# ---------------------------------------------------------------------------
# Stage 1 – Geographic utilities
# ---------------------------------------------------------------------------

def haversine(lat1, lng1, lat2, lng2):
    """Return great-circle distance in miles between two coordinate pairs."""
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Stage 2 – SEN profile matching
# ---------------------------------------------------------------------------

def match_sen(school, requested_needs):
    """
    Returns a dict with:
      matched   – True if school covers ALL requested needs
      match_score – fraction of requested needs covered (0–1)
      missing   – list of SEN codes not covered
      extra     – SEN codes the school covers beyond what was requested
    """
    requested = set(requested_needs)
    provision = set(school["sen_provision"])
    covered = requested & provision
    missing = list(requested - provision)
    extra = list(provision - requested)
    match_score = len(covered) / len(requested) if requested else 1.0
    return {
        "matched": len(missing) == 0,
        "match_score": match_score,
        "missing": missing,
        "extra": extra,
        "covered": list(covered),
    }


# ---------------------------------------------------------------------------
# Stage 3 – Composite scoring
# ---------------------------------------------------------------------------

def composite_score(school, distance_miles, match_score, weights):
    """
    Compute a 0–1 composite suitability score.

    Sub-scores (all normalised 0–1):
      need_match  – fraction of requested SEN needs covered
      proximity   – inverse-distance score; max at 0 mi, ~0 beyond 200 mi
      capacity    – vacancy ratio (vacancies / capacity)
      ofsted      – normalised Ofsted rating (Outstanding=1, Inadequate=0.25)

    weights is a dict: {need_match, proximity, capacity, ofsted} summing to 1.
    """
    # Proximity: exponential decay, half-score at ~50 miles
    proximity_score = math.exp(-distance_miles / 72.0)

    # Capacity: proportion of capacity still available
    cap = school["capacity"]
    vac = school["vacancies"]
    capacity_score = min(1.0, vac / max(cap * 0.2, 1))  # normalise against 20% headroom

    # Ofsted
    ofsted_raw = OFSTED_ORDER.get(school["ofsted"], 2)
    ofsted_score = (ofsted_raw - 1) / 3.0  # maps 1–4 → 0.0–1.0

    # Weighted composite
    w = weights
    score = (
        w.get("need_match", 0.40) * match_score
        + w.get("proximity", 0.30) * proximity_score
        + w.get("capacity", 0.15) * capacity_score
        + w.get("ofsted", 0.15) * ofsted_score
    )
    return {
        "composite": round(score, 4),
        "sub_scores": {
            "need_match": round(match_score, 4),
            "proximity": round(proximity_score, 4),
            "capacity": round(capacity_score, 4),
            "ofsted": round(ofsted_score, 4),
        },
    }


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search_schools(
    user_lat,
    user_lng,
    requested_needs,
    weights=None,
    max_distance=None,
    require_full_match=True,
    facility_filter=None,
    max_results=20,
    schools_override=None,
):
    """
    Full three-stage search pipeline.

    Parameters
    ----------
    user_lat, user_lng   : float  – resolved home coordinates
    requested_needs      : list   – SEN codes (e.g. ["ASD", "SEMH"])
    weights              : dict   – scoring weights (defaults below)
    max_distance         : float  – km cutoff (None = no limit)
    require_full_match   : bool   – if True, only fully-matched schools returned
    facility_filter      : list   – optional required facility codes
    max_results          : int

    Returns
    -------
    list of result dicts, sorted by composite score descending
    """
    if weights is None:
        weights = {"need_match": 0.40, "proximity": 0.30, "capacity": 0.15, "ofsted": 0.15}

    school_list = schools_override if schools_override is not None else SCHOOLS
    results = []

    for school in school_list:
        # --- distance ---
        dist = haversine(user_lat, user_lng, school["lat"], school["lng"])

        if max_distance and dist > max_distance:
            continue

        # --- SEN match ---
        sen_result = match_sen(school, requested_needs)
        if require_full_match and not sen_result["matched"]:
            continue

        # --- facility filter (optional) ---
        if facility_filter:
            school_facilities = set(school.get("facilities", []))
            if not set(facility_filter).issubset(school_facilities):
                continue

        # --- composite score ---
        score_result = composite_score(school, dist, sen_result["match_score"], weights)

        # --- build result ---
        results.append({
            "school": school,
            "distance_miles": round(dist, 1),
            "sen_match": sen_result,
            "scoring": score_result,
        })

    # Sort by composite score descending
    results.sort(key=lambda r: r["scoring"]["composite"], reverse=True)

    return results[:max_results]


# ---------------------------------------------------------------------------
# Helpers for the API
# ---------------------------------------------------------------------------

def serialise_result(r, rank):
    s = r["school"]
    facilities = [FACILITY_LABELS.get(f, f) for f in s.get("facilities", [])]
    sen_provision_labelled = {code: SEN_LABELS.get(code, code) for code in s["sen_provision"]}
    covered_labelled = [SEN_LABELS.get(c, c) for c in r["sen_match"]["covered"]]
    missing_labelled = [SEN_LABELS.get(m, m) for m in r["sen_match"]["missing"]]
    capacity_pct = round(s["vacancies"] / s["capacity"] * 100) if s.get("capacity") else 0

    return {
        "rank": rank,
        "id": s["id"],
        "urn": s.get("urn", ""),
        "name": s["name"],
        "address": s.get("address", s.get("postcode", "")),
        "la_name": s.get("la_name", ""),
        "lat": s["lat"],
        "lng": s["lng"],
        "school_type": s.get("school_type", ""),
        "age_range": s.get("age_range", ""),
        "region": s.get("region", ""),
        "sen_provision": s["sen_provision"],
        "sen_provision_labelled": sen_provision_labelled,
        "capacity": s.get("capacity", 0),
        "vacancies": s.get("vacancies", 0),
        "capacity_pct": capacity_pct,
        "ofsted": s.get("ofsted", "Good"),
        "facilities": facilities,
        "has_sen_unit": s.get("has_sen_unit", False),
        "has_rp_unit": s.get("has_rp_unit", False),
        "distance_miles": r["distance_miles"],
        "composite_score": round(r["scoring"]["composite"] * 100, 1),
        "sub_scores": {k: round(v * 100, 1) for k, v in r["scoring"]["sub_scores"].items()},
        "full_match": r["sen_match"]["matched"],
        "covered_needs": covered_labelled,
        "missing_needs": missing_labelled,
        "data_source": s.get("data_source", "Modelled"),
    }


def get_stats(results, requested_needs):
    """Return summary statistics for the search results."""
    full_matches = sum(1 for r in results if r["sen_match"]["matched"])
    if results:
        avg_dist = round(sum(r["distance_miles"] for r in results) / len(results), 1)
        best_score = round(results[0]["scoring"]["composite"] * 100, 1)
        outstanding = sum(1 for r in results if r["school"]["ofsted"] == "Outstanding")
        with_vacancies = sum(1 for r in results if r["school"]["vacancies"] > 0)
    else:
        avg_dist = best_score = outstanding = with_vacancies = 0

    return {
        "total": len(results),
        "full_matches": full_matches,
        "avg_distance_miles": avg_dist,
        "best_score": best_score,
        "outstanding_count": outstanding,
        "with_vacancies": with_vacancies,
    }
