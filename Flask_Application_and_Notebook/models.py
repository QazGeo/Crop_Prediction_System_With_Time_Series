# =============================================================================
# CROP SUITABILITY MODELS
# =============================================================================
# Thresholds sourced from:
# - FAO EcoCrop database (FAO, 2000) parameters: Tmin, Topmin, Topmax, Tmax
# - FAO GAEZ v4 crop profiles
# - Literature: Ramirez-Villegas et al. (2013), Our World in Data crop temperature summaries
# - Cassava Eastern Africa response study (MDPI Agriculture, 2026)
# - ECHO Community cereal crop guides
#
# LST (Land Surface Temperature) note: LST from satellite is typically 2-5°C higher
# than air temperature. Thresholds below are adjusted accordingly.
#
# RAINFALL THRESHOLDS — METHODOLOGY NOTE:
# FAO EcoCrop stores rainfall as annual totals but evaluates suitability against
# GROWING SEASON precipitation, not a full-year average (Ramirez-Villegas et al.,
# 2013; Recocrop package documentation). Monthly thresholds in the EcoCrop model
# are derived by dividing annual totals by growing season duration in months — not 12.
#
# This system uses 16-day MODIS periods. Thresholds below are expressed as
# mm per 16-day period during the growing season, derived as:
#   threshold_16d = FAO_annual_mm / (growing_season_months × (30.44 / 16))
#
# Growing season durations used (Malawi wet season: Nov–Apr):
#   Rice:       ~5 months  → 9.4 sixteen-day periods
#   Maize:      ~4 months  → 7.6 periods
#   Cassava:    ~10 months → 18.8 periods  (long-cycle perennial tuber)
#   Groundnuts: ~4 months  → 7.6 periods
#   Sorghum:    ~4 months  → 7.6 periods
#   Millet:     ~3 months  → 5.7 periods
#
# Suitability scoring uses growing-season averages only (Nov–Apr).
# NDVI serves as a proxy for vegetation health / moisture availability (0–1 scale).

CROP_PROFILES = {
    "Rice": {
        # Rice: optimal air temp 22-30°C, absolute range 15-38°C (FAO EcoCrop)
        # Annual water needs: 800–2000 mm/year
        # Growing season ~5 months (9.4 periods):
        #   min  450 mm ÷ 9.4 ≈  48 mm/period
        #   opt_low 800 mm ÷ 9.4 ≈  85 mm/period
        #   opt_high 2000 mm ÷ 9.4 ≈ 213 mm/period
        "lst": {
            "kill_low": 17.0,
            "min": 22.0,
            "opt_low": 27.0,
            "opt_high": 33.0,
            "max": 40.0,
            "kill_high": 43.0,
        },
        "rainfall_16d": {
            "kill_low": 0.0,
            "min": 48.0,
            "opt_low": 85.0,
            "opt_high": 213.0,
            "max": 280.0,
        },
        "ndvi": {
            "min": 0.35,
            "opt_low": 0.55,
            "opt_high": 0.85,
        },
        "weights": {"lst": 0.35, "rainfall": 0.40, "ndvi": 0.25},
        "growing_season_months": 5,
    },

    "Maize": {
        # Maize: optimal air temp 25-30°C, absolute range 10-40°C (FAO EcoCrop)
        # Annual water needs: 500–800 mm/year
        # Growing season ~4 months (7.6 periods):
        #   min  180 mm ÷ 7.6 ≈  24 mm/period
        #   opt_low 500 mm ÷ 7.6 ≈  66 mm/period
        #   opt_high 800 mm ÷ 7.6 ≈ 105 mm/period
        "lst": {
            "kill_low": 12.0,
            "min": 18.0,
            "opt_low": 28.0,
            "opt_high": 35.0,
            "max": 42.0,
            "kill_high": 46.0,
        },
        "rainfall_16d": {
            "kill_low": 0.0,
            "min": 24.0,
            "opt_low": 66.0,
            "opt_high": 105.0,
            "max": 160.0,
        },
        "ndvi": {
            "min": 0.25,
            "opt_low": 0.40,
            "opt_high": 0.75,
        },
        "weights": {"lst": 0.35, "rainfall": 0.40, "ndvi": 0.25},
        "growing_season_months": 4,
    },

    "Cassava": {
        # Cassava: optimal air temp 25-29°C, tolerates up to 35°C air temp
        # Drought-tolerant: 500–1200 mm/year
        # Growing season ~10 months (18.8 periods) — long-cycle tuber:
        #   min   90 mm ÷ 18.8 ≈   5 mm/period
        #   opt_low 500 mm ÷ 18.8 ≈  27 mm/period
        #   opt_high 1200 mm ÷ 18.8 ≈  64 mm/period
        "lst": {
            "kill_low": 12.0,
            "min": 20.0,
            "opt_low": 28.0,
            "opt_high": 37.0,
            "max": 43.0,
            "kill_high": 47.0,
        },
        "rainfall_16d": {
            "kill_low": 0.0,
            "min": 5.0,
            "opt_low": 27.0,
            "opt_high": 64.0,
            "max": 110.0,
        },
        "ndvi": {
            "min": 0.15,
            "opt_low": 0.35,
            "opt_high": 0.70,
        },
        "weights": {"lst": 0.40, "rainfall": 0.35, "ndvi": 0.25},
        "growing_season_months": 10,
    },

    "Groundnuts": {
        # Groundnuts: optimal air temp 25-30°C, range 15-38°C
        # Moderate water needs: 400–700 mm/year
        # Growing season ~4 months (7.6 periods):
        #   min  135 mm ÷ 7.6 ≈  18 mm/period
        #   opt_low 400 mm ÷ 7.6 ≈  53 mm/period
        #   opt_high 700 mm ÷ 7.6 ≈  92 mm/period
        # Sensitive to waterlogging
        "lst": {
            "kill_low": 13.0,
            "min": 20.0,
            "opt_low": 28.0,
            "opt_high": 35.0,
            "max": 41.0,
            "kill_high": 45.0,
        },
        "rainfall_16d": {
            "kill_low": 0.0,
            "min": 18.0,
            "opt_low": 53.0,
            "opt_high": 92.0,
            "max": 140.0,
        },
        "ndvi": {
            "min": 0.20,
            "opt_low": 0.35,
            "opt_high": 0.65,
        },
        "weights": {"lst": 0.35, "rainfall": 0.40, "ndvi": 0.25},
        "growing_season_months": 4,
    },

    "Sorghum": {
        # Sorghum: optimal air temp 26-34°C, tolerates heat > maize
        # Drought-tolerant: 300–700 mm/year
        # Growing season ~4 months (7.6 periods):
        #   min   90 mm ÷ 7.6 ≈  12 mm/period
        #   opt_low 300 mm ÷ 7.6 ≈  39 mm/period
        #   opt_high 700 mm ÷ 7.6 ≈  92 mm/period
        "lst": {
            "kill_low": 14.0,
            "min": 19.0,
            "opt_low": 29.0,
            "opt_high": 38.0,
            "max": 44.0,
            "kill_high": 47.0,
        },
        "rainfall_16d": {
            "kill_low": 0.0,
            "min": 12.0,
            "opt_low": 39.0,
            "opt_high": 92.0,
            "max": 140.0,
        },
        "ndvi": {
            "min": 0.15,
            "opt_low": 0.30,
            "opt_high": 0.65,
        },
        "weights": {"lst": 0.40, "rainfall": 0.35, "ndvi": 0.25},
        "growing_season_months": 4,
    },

    "Millet": {
        # Pearl millet: optimal air temp 28-35°C, most heat-tolerant of the 6
        # Very drought-tolerant: 250–600 mm/year
        # Growing season ~3 months (5.7 periods):
        #   min   70 mm ÷ 5.7 ≈  12 mm/period
        #   opt_low 250 mm ÷ 5.7 ≈  44 mm/period
        #   opt_high 600 mm ÷ 5.7 ≈ 105 mm/period
        "lst": {
            "kill_low": 15.0,
            "min": 21.0,
            "opt_low": 31.0,
            "opt_high": 40.0,
            "max": 45.0,
            "kill_high": 48.0,
        },
        "rainfall_16d": {
            "kill_low": 0.0,
            "min": 12.0,
            "opt_low": 44.0,
            "opt_high": 105.0,
            "max": 155.0,
        },
        "ndvi": {
            "min": 0.10,
            "opt_low": 0.25,
            "opt_high": 0.60,
        },
        "weights": {"lst": 0.40, "rainfall": 0.35, "ndvi": 0.25},
        "growing_season_months": 3,
    },
}


def _trapezoidal_score(value, kill_low, min_val, opt_low, opt_high, max_val, kill_high=None):
    """
    Compute a suitability score [0.0, 1.0] using a trapezoidal membership function.
    This mirrors the EcoCrop fuzzy-logic approach (Ramirez-Villegas et al. 2013):
      - Below kill_low or above kill_high → 0.0 (lethal)
      - Between opt_low and opt_high → 1.0 (optimal)
      - Linear ramps between kill/min and min/opt, and opt/max and max/kill
    """
    if kill_high is not None and value >= kill_high:
        return 0.0
    if value <= kill_low:
        return 0.0
    if opt_low <= value <= opt_high:
        return 1.0
    if kill_low < value < min_val:
        return (value - kill_low) / (min_val - kill_low) * 0.2
    if min_val <= value < opt_low:
        return 0.2 + 0.8 * (value - min_val) / (opt_low - min_val)
    if opt_high < value <= max_val:
        return 0.2 + 0.8 * (max_val - value) / (max_val - opt_high)
    if kill_high is not None and max_val < value < kill_high:
        return 0.2 * (kill_high - value) / (kill_high - max_val)
    if kill_high is None and value > max_val:
        return max(0.0, 0.2 * (1.0 - (value - max_val) / max_val))
    return 0.0


def _ndvi_score(ndvi, profile_ndvi):
    """Score NDVI using a simpler 3-point trapezoid (no kill thresholds for NDVI)."""
    mn = profile_ndvi["min"]
    ol = profile_ndvi["opt_low"]
    oh = profile_ndvi["opt_high"]

    if ndvi < mn:
        return 0.0
    if ol <= ndvi <= oh:
        return 1.0
    if mn <= ndvi < ol:
        return (ndvi - mn) / (ol - mn)
    if ndvi > oh:
        return max(0.0, 1.0 - (ndvi - oh) / (1.0 - oh) * 0.5)
    return 0.0


def compute_crop_suitability(avg_lst, avg_rainfall_16d_growing_season, avg_ndvi):
    """
    Compute a suitability percentage [0–100%] for each crop using a weighted
    trapezoidal scoring function grounded in FAO EcoCrop parameters.

    IMPORTANT: avg_rainfall_16d_growing_season must be the average rainfall
    per 16-day period computed over the GROWING SEASON only (Nov–Apr for Malawi),
    not over the full forecast period. FAO EcoCrop evaluates precipitation
    suitability against growing season totals (Ramirez-Villegas et al., 2013).

    Parameters
    ----------
    avg_lst : float
        Average land surface temperature (°C) during the growing season.
    avg_rainfall_16d_growing_season : float
        Average rainfall per 16-day period during the growing season (Nov–Apr).
    avg_ndvi : float
        Average NDVI during the growing season.

    Returns
    -------
    dict : {crop_name: {
        'score': float (0–100),
        'lst_score': float (0–100),
        'rain_score': float (0–100),
        'ndvi_score': float (0–100),
        'optimal_lst': (opt_low, opt_high),
        'optimal_rain': (opt_low, opt_high),
        'optimal_ndvi': (opt_low, opt_high),
    }}
    """
    results = {}

    for crop, profile in CROP_PROFILES.items():
        lp = profile["lst"]
        rp = profile["rainfall_16d"]
        np_ = profile["ndvi"]
        w = profile["weights"]

        lst_s = _trapezoidal_score(
            avg_lst,
            lp["kill_low"], lp["min"], lp["opt_low"], lp["opt_high"],
            lp["max"], lp.get("kill_high")
        )

        rain_s = _trapezoidal_score(
            avg_rainfall_16d_growing_season,
            rp["kill_low"], rp["min"], rp["opt_low"], rp["opt_high"],
            rp["max"]
        )

        ndvi_s = _ndvi_score(avg_ndvi, np_)

        if lst_s == 0.0 or rain_s == 0.0:
            composite = 0.0
        else:
            composite = (
                w["lst"] * lst_s +
                w["rainfall"] * rain_s +
                w["ndvi"] * ndvi_s
            )

        results[crop] = {
            'score': round(composite * 100, 1),
            'lst_score': round(lst_s * 100, 1),
            'rain_score': round(rain_s * 100, 1),
            'ndvi_score': round(ndvi_s * 100, 1),
            'optimal_lst':  (lp["opt_low"],  lp["opt_high"]),
            'optimal_rain': (rp["opt_low"],  rp["opt_high"]),
            'optimal_ndvi': (np_["opt_low"], np_["opt_high"]),
        }

    return results


def rank_crops(suitability_scores):
    """Sort crops by suitability score descending. Returns list of (crop, score_dict) tuples."""
    return sorted(suitability_scores.items(), key=lambda x: x[1]['score'], reverse=True)


def get_suitability_label(score):
    """Convert numeric suitability score to a descriptive label."""
    if score >= 80:
        return "Highly Suitable"
    elif score >= 60:
        return "Suitable"
    elif score >= 40:
        return "Moderately Suitable"
    elif score >= 20:
        return "Marginally Suitable"
    else:
        return "Not Suitable"
