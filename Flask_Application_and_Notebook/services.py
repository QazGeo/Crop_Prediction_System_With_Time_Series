import matplotlib
matplotlib.use('Agg')  # MUST be before importing matplotlib.pyplot

import io
import os
import warnings

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from statsmodels.tsa.statespace.sarimax import SARIMAX

from reportlab.lib import colors as rl_colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

from models import (
    compute_crop_suitability,
    get_suitability_label,
    rank_crops,
)

warnings.filterwarnings('ignore')

# Create required directories on import
os.makedirs('static/images/forecasts', exist_ok=True)
os.makedirs('models', exist_ok=True)

# Module-level cache
_cached_data = None
_cached_region_mapping = None


# GROWING SEASON CONSTANTS
# Malawi's wet/planting season runs November through April.
# Suitability scoring follows FAO EcoCrop methodology which evaluates
# precipitation against growing season totals, not annual averages
# (Ramirez-Villegas et al., 2013). All averages passed to compute_crop_suitability
# must be filtered to these months before computing the mean.
GROWING_SEASON_MONTHS = [11, 12, 1, 2, 3, 4]  # Nov, Dec, Jan, Feb, Mar, Apr


def get_growing_season_averages(forecasts):
    """
    Return mean rainfall, NDVI, and LST computed over growing season months only
    (November through April). This matches FAO EcoCrop's approach of evaluating
    precipitation suitability against growing season conditions rather than
    full-year averages which are dragged down by dry-season zeros.

    Parameters
    ----------
    forecasts : pd.DataFrame with DatetimeIndex and columns
                RAINFALL_MM, NDVI_VALUE, LST_VALUE

    Returns
    -------
    tuple: (avg_rainfall, avg_ndvi, avg_temp)
           Returns full-period averages as fallback if no growing-season rows found.
    """
    mask = forecasts.index.month.isin(GROWING_SEASON_MONTHS)
    growing = forecasts[mask]

    if growing.empty:
        # Fallback: should not happen over a 5-year forecast but guard against it
        return (
            forecasts['RAINFALL_MM'].mean(),
            forecasts['NDVI_VALUE'].mean(),
            forecasts['LST_VALUE'].mean(),
        )

    return (
        growing['RAINFALL_MM'].mean(),
        growing['NDVI_VALUE'].mean(),
        growing['LST_VALUE'].mean(),
    )


# DATA LOADING

def load_data_optimized():
    """Load and parse CSV data using pandas."""
    try:
        combined_df = pd.read_csv('../Crop_Prediction_System_With_Time_Series/Flask_Application_and_Notebook/combined_with_plants.csv')
        combined_df['DATE'] = pd.to_datetime(combined_df['DATE'], format='%m/%d/%Y', errors='coerce')
        combined_df = combined_df.dropna(subset=['DATE', 'RAINFALL_MM', 'NDVI_VALUE', 'LST_VALUE'])

        numeric_cols = ['RAINFALL_MM', 'NDVI_VALUE', 'LST_VALUE']
        for col in numeric_cols:
            combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce')

        combined_df = combined_df.dropna(subset=numeric_cols)
        combined_df = combined_df.reset_index(drop=True)

        print(f"✅ Data loaded successfully. Total records: {len(combined_df)}")
        return combined_df

    except FileNotFoundError:
        print("❌ Error: File 'combined_with_plants.csv' not found.")
        return None
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None


def get_cached_data():
    """Return (combined_df, region_mapping), loading from disk only once."""
    global _cached_data, _cached_region_mapping
    if _cached_data is None:
        _cached_data = load_data_optimized()
        if _cached_data is not None:
            _cached_region_mapping = create_region_mapping(_cached_data)
    return _cached_data, _cached_region_mapping


# REGION / COUNTRY MAPPING

def create_region_mapping(combined_df):
    """Create a mapping of GID_2 codes to human-readable region names."""
    unique_gids = combined_df['GID_2'].unique()

    malawi_regions = {
        'MWI.1.1_1': 'Northern Region - Chitipa',
        'MWI.1.2_1': 'Northern Region - Karonga',
        'MWI.1.3_1': 'Northern Region - Rumphi',
        'MWI.2.1_1': 'Central Region - Kasungu',
        'MWI.2.2_1': 'Central Region - Nkhotakota',
        'MWI.2.3_1': 'Central Region - Ntchisi',
        'MWI.2.4_1': 'Central Region - Dowa',
        'MWI.2.5_1': 'Central Region - Salima',
        'MWI.2.6_1': 'Central Region - Lilongwe',
        'MWI.2.7_1': 'Central Region - Mchinji',
        'MWI.3.1_1': 'Southern Region - Mangochi',
        'MWI.3.2_1': 'Southern Region - Machinga',
        'MWI.3.3_1': 'Southern Region - Zomba',
        'MWI.3.4_1': 'Southern Region - Chiradzulu',
        'MWI.3.5_1': 'Southern Region - Blantyre',
        'MWI.3.6_1': 'Southern Region - Mwanza',
        'MWI.3.7_1': 'Southern Region - Thyolo',
        'MWI.3.8_1': 'Southern Region - Mulanje',
        'MWI.3.9_1': 'Southern Region - Phalombe',
        'MWI.4.1_1': 'Southern Region - Chikwawa',
        'MWI.4.2_1': 'Southern Region - Nsanje',
        'MWI.4.3_1': 'Southern Region - Balaka',
        'MWI.4.4_1': 'Southern Region - Neno',
    }

    return {gid: malawi_regions.get(gid, f"Region {gid}") for gid in unique_gids}


def get_available_options(combined_df):
    """Get available countries and regions for user selection."""
    combined_df = combined_df.copy()
    combined_df['country_code'] = combined_df['GID_2'].str.slice(0, 3)
    country_mapping = {'MWI': 'Malawi'}
    available_countries = {
        code: country_mapping.get(code, f"Country_{code}")
        for code in combined_df['country_code'].unique()
        if code in country_mapping
    }
    return available_countries, create_region_mapping(combined_df)


# DATA PREPARATION

def prepare_data_for_forecast(combined_df, selection):
    """Prepare time-series data based on user selection."""
    if selection['type'] == 'country':
        country_code = selection['value']
        mask = combined_df['GID_2'].str.startswith(country_code)
        country_data = combined_df[mask]

        if country_data.empty:
            print(f"❌ No data found for country code: {country_code}")
            return None

        aggregated_data = (
            country_data.groupby('DATE')
            .agg({'RAINFALL_MM': 'mean', 'NDVI_VALUE': 'mean', 'LST_VALUE': 'mean'})
            .sort_index()
        )

        print(f"✅ Prepared country-level data for {selection['name']}")
        print(f"   Time range: {aggregated_data.index.min()} to {aggregated_data.index.max()}")
        print(f"   Total records: {len(aggregated_data)}")
        return aggregated_data

    else:
        region_gid = selection['value']
        mask = combined_df['GID_2'] == region_gid
        region_data = combined_df[mask].sort_values('DATE')

        if region_data.empty:
            print(f"❌ No data found for region: {region_gid}")
            return None

        region_data = region_data.set_index('DATE')[['RAINFALL_MM', 'NDVI_VALUE', 'LST_VALUE']]
        print(f"✅ Prepared region-level data for {selection['name']}")
        print(f"   Time range: {region_data.index.min()} to {region_data.index.max()}")
        print(f"   Total records: {len(region_data)}")
        return region_data


# FORECAST EVALUATION (Walk-Forward / Time Series Split)

def evaluate_forecast_accuracy(combined_df, n_splits=3, sample_regions=5):
    """
    Evaluate SARIMAX forecast accuracy using walk-forward (time series split) validation.

    Parameters
    ----------
    combined_df : pd.DataFrame
    n_splits : int
        Number of walk-forward folds.
    sample_regions : int
        Number of regions to evaluate (for speed).

    Returns
    -------
    dict with MAE, RMSE, MAPE per variable, averaged across folds and regions.
    """
    print("\n" + "=" * 60)
    print("📈 WALK-FORWARD FORECAST EVALUATION")
    print("=" * 60)
    print(f"Method: Time Series Split ({n_splits} folds) across {sample_regions} sampled regions")

    all_regions = combined_df['GID_2'].unique()
    np.random.seed(42)
    eval_regions = np.random.choice(all_regions, size=min(sample_regions, len(all_regions)), replace=False)

    metrics_per_var = {
        'RAINFALL_MM': {'mae': [], 'rmse': [], 'mape': None},  # MAPE skipped for rainfall
        'NDVI_VALUE':  {'mae': [], 'rmse': [], 'mape': []},
        'LST_VALUE':   {'mae': [], 'rmse': [], 'mape': []},
    }

    tscv = TimeSeriesSplit(n_splits=n_splits)

    for region in eval_regions:
        region_data = (
            combined_df[combined_df['GID_2'] == region]
            .sort_values('DATE')
            .set_index('DATE')[['RAINFALL_MM', 'NDVI_VALUE', 'LST_VALUE']]
            .dropna()
        )

        if len(region_data) < 24:
            print(f"  ⚠ Skipping {region}: insufficient data ({len(region_data)} points)")
            continue

        for variable in ['RAINFALL_MM', 'NDVI_VALUE', 'LST_VALUE']:
            series = region_data[variable]
            series = _prepare_series_index(series)
            indices = np.arange(len(series))

            for train_idx, test_idx in tscv.split(indices):
                train = series.iloc[train_idx]
                test = series.iloc[test_idx]

                if len(train) < 20 or len(test) < 2:
                    continue

                try:
                    import warnings as _w
                    from statsmodels.tools.sm_exceptions import ConvergenceWarning
                    with _w.catch_warnings():
                        _w.simplefilter('ignore', ConvergenceWarning)

                        max_safe_seasonal = max(2, len(train) // 4)
                        seasonal_period = min(23, max_safe_seasonal)

                        if seasonal_period < 4:
                            model = SARIMAX(
                                train,
                                order=(1, 1, 1),
                                enforce_stationarity=False,
                                enforce_invertibility=False
                            )
                        else:
                            model = SARIMAX(
                                train,
                                order=(1, 1, 1),
                                seasonal_order=(1, 1, 1, seasonal_period),
                                enforce_stationarity=False,
                                enforce_invertibility=False
                            )
                        fitted = model.fit(disp=False, maxiter=200)
                        preds = fitted.get_forecast(steps=len(test)).predicted_mean

                    actuals = test.values
                    predicted = preds.values

                    mae = mean_absolute_error(actuals, predicted)
                    rmse = np.sqrt(mean_squared_error(actuals, predicted))

                    series_std = series.std()
                    if mae > series_std * 20:
                        continue

                    metrics_per_var[variable]['mae'].append(mae)
                    metrics_per_var[variable]['rmse'].append(rmse)

                    if metrics_per_var[variable]['mape'] is not None:
                        threshold = max(series.mean() * 0.01, 1e-6)
                        valid_mask = np.abs(actuals) > threshold
                        if valid_mask.sum() > 0:
                            mape = np.mean(
                                np.abs((actuals[valid_mask] - predicted[valid_mask])
                                       / actuals[valid_mask])
                            ) * 100
                            if mape < 500:
                                metrics_per_var[variable]['mape'].append(mape)

                except Exception:
                    pass

    summary = {}
    print("\n📊 Results (averaged across folds and regions):")
    print("-" * 68)
    print(f"{'Variable':<20} {'MAE':>8} {'RMSE':>8} {'MAPE':>10}  {'Interpretation'}")
    print("-" * 68)

    interpretations = {
        'RAINFALL_MM': lambda mae, rmse: (
            "Good" if rmse < 5 else "Moderate" if rmse < 10 else "High error — rainfall is volatile"
        ),
        'NDVI_VALUE': lambda mae, rmse: (
            "Good" if mae < 0.05 else "Moderate" if mae < 0.15 else "High — NDVI varies seasonally"
        ),
        'LST_VALUE': lambda mae, rmse: (
            "Good" if mae < 2 else "Moderate" if mae < 5 else "High — wide temp range in data"
        ),
    }

    for var, m in metrics_per_var.items():
        avg_mae  = np.mean(m['mae'])  if m['mae']  else float('nan')
        avg_rmse = np.mean(m['rmse']) if m['rmse'] else float('nan')
        mape_list = m['mape']
        avg_mape = np.mean(mape_list) if (mape_list is not None and len(mape_list) > 0) else float('nan')
        summary[var] = {'mae': avg_mae, 'rmse': avg_rmse, 'mape': avg_mape}

        label = var.replace('_VALUE', '').replace('_MM', ' (mm)')
        mape_str = "N/A*" if var == 'RAINFALL_MM' else (
            f"{avg_mape:.1f}%" if not np.isnan(avg_mape) else "N/A"
        )
        interp = interpretations[var](avg_mae, avg_rmse) if not np.isnan(avg_mae) else "—"
        print(f"{label:<20} {avg_mae:>8.3f} {avg_rmse:>8.3f} {mape_str:>10}  {interp}")

    print("-" * 68)
    print("  * MAPE excluded for Rainfall — ~50% of readings are 0mm (dry season).")
    print("✅ Evaluation complete.\n")
    return summary


# SARIMAX FORECASTING

def _prepare_series_index(series):
    """
    Ensure the series has a clean DatetimeIndex with frequency set.
    SARIMAX emits a ValueWarning when the index frequency is unrecognised.
    Setting freq='16D' explicitly prevents this.
    """
    series = series.copy()
    if not isinstance(series.index, pd.DatetimeIndex):
        series.index = pd.to_datetime(series.index)
    try:
        series.index.freq = pd.tseries.frequencies.to_offset('16D')
    except Exception:
        series = series.asfreq('16D', method='ffill')
    return series


def load_or_train_sarimax_model(series, model_name, periods=115):
    """Load a pre-trained SARIMAX model if available, otherwise train and save."""
    model_path = f"models/{model_name}.joblib"

    try:
        model = joblib.load(model_path)
        print(f"✅ Loaded pre-trained model: {model_name}")
        return model
    except Exception:
        print(f"⚠ No pre-trained model found. Training new model: {model_name}")

    series = series.dropna()
    series = _prepare_series_index(series)

    if len(series) < 24:
        print("⚠ Insufficient data for SARIMAX")
        return None

    seasonal_period = 23  # 365 / 16 ≈ 23 periods per year

    model = SARIMAX(
        series,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, seasonal_period),
        enforce_stationarity=False,
        enforce_invertibility=False
    )

    print(f"⏳ Fitting SARIMAX model for {model_name}...")
    fitted_model = model.fit(disp=False)
    print(f"✅ Model training completed for {model_name}")

    joblib.dump(fitted_model, model_path)
    print(f"✅ Model saved: {model_name}")

    return fitted_model


def sarimax_forecast(series, periods=115, model_name="default"):
    """Run SARIMAX forecast for a single variable series."""
    try:
        series = series.dropna()
        series = _prepare_series_index(series)

        if len(series) < 24:
            print("⚠ Insufficient data for SARIMAX")
            return None, None, None

        fitted_model = load_or_train_sarimax_model(series, model_name, periods)
        if fitted_model is None:
            return None, None, None

        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter('ignore')
            forecast_result = fitted_model.get_forecast(steps=periods)
            forecast_mean = forecast_result.predicted_mean

        last_date = series.index[-1]
        future_dates = pd.date_range(last_date + pd.Timedelta(days=16), periods=periods, freq='16D')

        forecast_series = pd.Series(forecast_mean.values, index=future_dates)

        # Growth factor: CI starts tight and fans out over the forecast horizon
        n_steps = len(forecast_series)
        growth = np.linspace(0.5, 2.0, n_steps)
        hist_std = series.std()
        hist_mean = series.mean()

        if 'rainfall' in model_name.lower() or 'rain' in model_name.lower():
            # Rainfall CI left intentionally wider — high variability is real
            # and worth communicating to the user
            half_width = hist_std * growth
            forecast_series = forecast_series.clip(lower=0.0)
            lower_bound = (forecast_series - half_width).clip(lower=0.0)
            upper_bound = forecast_series + half_width

        elif 'ndvi' in model_name.lower():
            # FIX 1: Prevent SARIMAX drift — if the model trends too far from
            # the historical mean, nudge it back. NDVI cannot realistically
            # trend to zero over 5 years in a vegetated region.
            forecast_series = forecast_series.clip(
                lower=hist_mean - hist_std,
                upper=hist_mean + hist_std
            )
            forecast_series = forecast_series.clip(lower=0.0, upper=1.0)
            half_width = 0.5 * hist_std * growth
            lower_bound = (forecast_series - half_width).clip(lower=0.0, upper=1.0)
            upper_bound = (forecast_series + half_width).clip(lower=0.0, upper=1.0)

        elif 'lst' in model_name.lower():
            # FIX 2: Hard physical floor at 15°C LST for Malawi — temperatures
            # cannot realistically drop below this even at elevation.
            # series.min() - 5 was too permissive for volatile regions.
            half_width = 0.5 * hist_std * growth
            lower_bound = (forecast_series - half_width).clip(lower=15.0)
            upper_bound = (forecast_series + half_width).clip(upper=series.max() + 5)

        else:
            # Fallback for any other variable
            half_width = hist_std * growth
            lower_bound = forecast_series - half_width
            upper_bound = forecast_series + half_width

        return forecast_series, lower_bound, upper_bound

    except Exception as e:
        print(f"⚠ SARIMAX failed: {e}")
        return None, None, None


def run_forecast(data, selection, forecast_years=5):
    """Run the full SARIMAX forecasting pipeline for a region."""
    periods = int(365 * forecast_years / 16)
    if periods <= 0:
        periods = 60

    print(f"\n🔮 Forecasting for {selection['name']} ({forecast_years} years) using SARIMAX...")

    region_id = selection['name'].replace(' ', '_').lower()

    rainfall_forecast, rain_lower, rain_upper = sarimax_forecast(
        data['RAINFALL_MM'], periods, f"rainfall_{region_id}"
    )
    ndvi_forecast, ndvi_lower, ndvi_upper = sarimax_forecast(
        data['NDVI_VALUE'], periods, f"ndvi_{region_id}"
    )
    lst_forecast, lst_lower, lst_upper = sarimax_forecast(
        data['LST_VALUE'], periods, f"lst_{region_id}"
    )

    if rainfall_forecast is None or ndvi_forecast is None or lst_forecast is None:
        print("❌ Forecasting failed due to insufficient data or errors.")
        return None, None

    forecasts = pd.DataFrame({
        'RAINFALL_MM': rainfall_forecast.values,
        'NDVI_VALUE': ndvi_forecast.values,
        'LST_VALUE': lst_forecast.values
    }, index=rainfall_forecast.index)

    confidence_intervals = {
        'rainfall': {'lower': rain_lower, 'upper': rain_upper},
        'ndvi':     {'lower': ndvi_lower, 'upper': ndvi_upper},
        'lst':      {'lower': lst_lower,  'upper': lst_upper},
    }

    return forecasts, confidence_intervals


# PLOTTING

def plot_results(historical_data, forecasts, ci_dict, selection):
    """
    Plot and save forecast results with confidence intervals.
    X-axis shows individual months (MMM YYYY) so seasonal patterns are clearly visible.
    Growing season months (Nov–Apr) are shaded on each panel.
    """
    import matplotlib.dates as mdates

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(18, 13))
    colors = ['#2E86AB', '#A23B72', '#F18F01']

    all_dates = pd.concat([
        pd.Series(historical_data.index),
        pd.Series(forecasts.index)
    ])
    x_min = all_dates.min()
    x_max = all_dates.max()

    def shade_growing_seasons(ax):
        """Shade Nov–Apr growing season bands across the full date range."""
        year_start = x_min.year
        year_end = x_max.year + 1
        for yr in range(year_start, year_end + 1):
            # Nov–Dec of yr
            band_start = pd.Timestamp(yr, 11, 1)
            band_end   = pd.Timestamp(yr + 1, 4, 30)
            if band_end < x_min or band_start > x_max:
                continue
            band_start = max(band_start, x_min)
            band_end   = min(band_end, x_max)
            ax.axvspan(band_start, band_end, alpha=0.07, color='green', zorder=0)

    # Configure x-axis: monthly major ticks, quarterly labels
    month_locator   = mdates.MonthLocator(interval=1)
    quarter_locator = mdates.MonthLocator(bymonth=[1, 4, 7, 10])
    date_format     = mdates.DateFormatter('%b %Y')

    def style_xaxis(ax, show_label=False):
        ax.xaxis.set_major_locator(month_locator)
        ax.xaxis.set_minor_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(date_format)
        # Only draw a label at Jan, Apr, Jul, Oct to avoid overcrowding
        ax.xaxis.set_major_locator(quarter_locator)
        ax.xaxis.set_major_formatter(date_format)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)
        ax.set_xlim(x_min, x_max)
        if show_label:
            ax.set_xlabel('Month', fontweight='bold')
        ax.grid(True, which='major', alpha=0.3)
        ax.grid(True, which='minor', alpha=0.1, linestyle=':')

    # Add a vertical line at the historical/forecast boundary
    forecast_start = forecasts.index[0]

    # --- Panel 1: Rainfall ---
    shade_growing_seasons(ax1)
    ax1.plot(historical_data.index, historical_data['RAINFALL_MM'],
             label='Historical', linewidth=1.8, color=colors[0], alpha=0.85)
    ax1.plot(forecasts.index, forecasts['RAINFALL_MM'],
             label='Forecast', linewidth=2.5, color=colors[0])
    ax1.fill_between(forecasts.index,
                     ci_dict['rainfall']['lower'], ci_dict['rainfall']['upper'],
                     color=colors[0], alpha=0.18, label='95% CI')
    ax1.axvline(forecast_start, color='gray', linestyle='--', linewidth=1, alpha=0.7,
                label='Forecast start')
    ax1.set_ylabel('Rainfall (mm / 16 days)', fontweight='bold')
    ax1.legend(loc='upper right', fontsize=8)
    style_xaxis(ax1)

    # --- Panel 2: NDVI ---
    shade_growing_seasons(ax2)
    ax2.plot(historical_data.index, historical_data['NDVI_VALUE'],
             label='Historical', linewidth=1.8, color=colors[1], alpha=0.85)
    ax2.plot(forecasts.index, forecasts['NDVI_VALUE'],
             label='Forecast', linewidth=2.5, color=colors[1])
    ax2.fill_between(forecasts.index,
                     ci_dict['ndvi']['lower'], ci_dict['ndvi']['upper'],
                     color=colors[1], alpha=0.18, label='95% CI')
    ax2.axvline(forecast_start, color='gray', linestyle='--', linewidth=1, alpha=0.7)
    ax2.set_ylabel('NDVI', fontweight='bold')
    ax2.legend(loc='upper right', fontsize=8)
    style_xaxis(ax2)

    # --- Panel 3: LST ---
    shade_growing_seasons(ax3)
    ax3.plot(historical_data.index, historical_data['LST_VALUE'],
             label='Historical', linewidth=1.8, color=colors[2], alpha=0.85)
    ax3.plot(forecasts.index, forecasts['LST_VALUE'],
             label='Forecast', linewidth=2.5, color=colors[2])
    ax3.fill_between(forecasts.index,
                     ci_dict['lst']['lower'], ci_dict['lst']['upper'],
                     color=colors[2], alpha=0.18, label='95% CI')
    ax3.axvline(forecast_start, color='gray', linestyle='--', linewidth=1, alpha=0.7)
    ax3.set_ylabel('Temperature (°C)', fontweight='bold')
    ax3.legend(loc='upper right', fontsize=8)
    style_xaxis(ax3, show_label=True)

    # Legend note for growing season shading
    from matplotlib.patches import Patch
    season_patch = Patch(facecolor='green', alpha=0.15, label='Growing season (Nov–Apr)')
    fig.legend(handles=[season_patch], loc='lower center', ncol=1,
               fontsize=8, framealpha=0.8, bbox_to_anchor=(0.5, -0.01))

    plt.suptitle(f'5-Year Climate Forecast — {selection["name"]}\n'
                 f'Historical (Jan 2022–Feb 2025) | Forecast (Mar 2025–Feb 2030)',
                 fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()

    filename = f"static/images/forecasts/forecast_{selection['name'].replace(' ', '_').lower()}.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"✅ Forecast plot saved to: {filename}")
    plt.close(fig)


# SUMMARY GENERATION

def generate_summary(forecasts, selection, forecast_eval_metrics=None):
    """Generate and print a forecast summary with crop recommendations."""
    print("\n" + "=" * 60)
    print(f"📊 FORECAST SUMMARY: {selection['name']}")
    print("=" * 60)

    # Use growing-season averages (Nov–Apr) to match FAO EcoCrop methodology,
    # which evaluates precipitation suitability against growing season totals.
    avg_rainfall, avg_ndvi, avg_temp = get_growing_season_averages(forecasts)

    print(f"\n📅 Forecast Period: {forecasts.index[0].strftime('%Y-%m-%d')} to {forecasts.index[-1].strftime('%Y-%m-%d')}")
    print(f"\n🌧  Rainfall Forecast (growing season Nov–Apr):")
    print(f"   Average: {avg_rainfall:.1f} mm per 16-day period")
    print(f"   Full-period range: {forecasts['RAINFALL_MM'].min():.1f} - {forecasts['RAINFALL_MM'].max():.1f} mm")
    print(f"\n🌿 Vegetation Health / NDVI (growing season):")
    print(f"   Average: {avg_ndvi:.3f}")
    print(f"\n🌡  Temperature / LST (growing season):")
    print(f"   Average: {avg_temp:.1f}°C")

    suitability_scores = compute_crop_suitability(avg_temp, avg_rainfall, avg_ndvi)
    ranked = rank_crops(suitability_scores)

    print("\n" + "=" * 60)
    print(f"🌾 CROP SUITABILITY SCORES FOR {selection['name']}")
    print("=" * 60)

    for crop, data in ranked:
        score = data['score']
        label = get_suitability_label(score)
        bar = "█" * int(score / 5)
        print(f"  {crop:<12} {score:>5.1f}%  [{label}]  {bar}")

    if forecast_eval_metrics:
        print("\n" + "=" * 68)
        print("📊 FORECAST MODEL ACCURACY (Walk-Forward Validation)")
        print("=" * 68)
        for var, m in forecast_eval_metrics.items():
            label = var.replace('_VALUE', '').replace('_MM', ' (mm)')
            mape_str = "N/A*" if var == 'RAINFALL_MM' else (
                f"{m['mape']:.1f}%" if not np.isnan(m['mape']) else "N/A"
            )
            print(f"  {label:<20}  MAE={m['mae']:.3f}  RMSE={m['rmse']:.3f}  MAPE={mape_str}")
        print("  * MAPE excluded for Rainfall (50% zero readings in dry season)")

    print("=" * 60)


# FORECAST PIPELINE (used by Flask routes)

def run_forecast_pipeline(selection_input):
    """
    Run the full forecasting + suitability pipeline for a given region/country.
    Returns: (forecasts DataFrame, ci_dict, summary dict)
    """
    combined_df, _ = get_cached_data()
    if combined_df is None:
        return None, None, "Data loading failed."

    data = prepare_data_for_forecast(combined_df, selection_input)
    if data is None or data.empty:
        return None, None, "No data available for the selected region."

    forecasts, ci_dict = run_forecast(data, selection_input)
    if forecasts is None:
        return None, None, "Forecasting failed."

    # Use growing-season averages (Nov–Apr) to match FAO EcoCrop methodology.
    avg_rainfall, avg_ndvi, avg_temp = get_growing_season_averages(forecasts)

    suitability_scores = compute_crop_suitability(avg_temp, avg_rainfall, avg_ndvi)
    ranked = rank_crops(suitability_scores)

    try:
        forecast_accuracy = evaluate_forecast_accuracy(combined_df, n_splits=2, sample_regions=3)
    except Exception:
        forecast_accuracy = None

    summary = {
        'region': selection_input['name'],
        'avg_rainfall': avg_rainfall,
        'avg_ndvi': avg_ndvi,
        'avg_temp': avg_temp,
        'crop_suitability': ranked,
        'forecast_accuracy': forecast_accuracy,
        'crop_recommendations': [
            (crop, f"{d['score']:.1f}% suitability — {get_suitability_label(d['score'])}")
            for crop, d in ranked[:3]
        ],
        'least_recommendations': [
            (crop, f"{d['score']:.1f}% suitability — {get_suitability_label(d['score'])}")
            for crop, d in ranked[-3:][::-1]
        ],
    }

    return forecasts, ci_dict, summary


# PDF REPORT

def generate_pdf_report(summary, forecasts, selection):
    """Generate a PDF report for the forecast results."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=rl_colors.darkblue
    )

    story.append(Paragraph("Climate Forecast Report", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"<b>Region:</b> {summary['region']}", styles['Normal']))
    story.append(Spacer(1, 10))

    if len(forecasts) > 0:
        start_date = forecasts.index[0].strftime('%Y-%m-%d')
        end_date = forecasts.index[-1].strftime('%Y-%m-%d')
        story.append(Paragraph(f"<b>Forecast Period:</b> {start_date} to {end_date}", styles['Normal']))
        story.append(Spacer(1, 20))

    story.append(Paragraph("<b>Forecast Statistics</b>", styles['Heading2']))
    story.append(Spacer(1, 10))

    data_table = [
        ['Metric', 'Value'],
        ['Avg. Rainfall — growing season (Nov–Apr)', f"{summary['avg_rainfall']:.2f} mm per 16-day period"],
        ['Avg. NDVI — growing season', f"{summary['avg_ndvi']:.3f}"],
        ['Avg. Temperature (LST) — growing season', f"{summary['avg_temp']:.2f} °C"]
    ]

    table = Table(data_table)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), rl_colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, rl_colors.black)
    ]))
    story.append(table)
    story.append(Spacer(1, 30))

    story.append(Paragraph("<b>Crop Suitability Scores</b>", styles['Heading2']))
    story.append(Spacer(1, 10))

    suit_data = [['Crop', 'Score', 'Rating', 'Optimal LST (°C)', 'Optimal Rain (mm/16d)', 'Optimal NDVI']]
    for crop, d in summary.get('crop_suitability', []):
        suit_data.append([
            crop,
            f"{d['score']:.1f}%",
            get_suitability_label(d['score']),
            f"{d['optimal_lst'][0]}–{d['optimal_lst'][1]}°C",
            f"{d['optimal_rain'][0]}–{d['optimal_rain'][1]} mm",
            f"{d['optimal_ndvi'][0]}–{d['optimal_ndvi'][1]}",
        ])

    suit_table = Table(suit_data, colWidths=[1.1*inch, 0.7*inch, 1.1*inch, 1.4*inch, 1.5*inch, 1.2*inch])
    suit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.whitesmoke, rl_colors.beige]),
        ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.grey)
    ]))
    story.append(suit_table)
    story.append(Spacer(1, 8))

    note_style = ParagraphStyle('Note', parent=styles['Normal'],
                                fontSize=7, textColor=rl_colors.grey,
                                spaceAfter=20)
    story.append(Paragraph(
        "<i>How to read this table: Compare the forecasted averages (Rainfall: "
        f"{summary['avg_rainfall']:.1f} mm, Temperature: {summary['avg_temp']:.1f}°C, "
        f"NDVI: {summary['avg_ndvi']:.3f}) against each crop's optimal ranges above. "
        "The closer the forecast values are to the optimal range, the higher the suitability score.</i>",
        note_style
    ))
    story.append(Spacer(1, 20))

    chart_path = f"static/images/forecasts/forecast_{selection['name'].replace(' ', '_').lower()}.png"
    if os.path.exists(chart_path):
        try:
            story.append(Paragraph("<b>Forecast Visualization</b>", styles['Heading2']))
            story.append(Spacer(1, 10))
            img = Image(chart_path, width=6 * inch, height=4 * inch)
            story.append(img)
        except Exception:
            story.append(Paragraph("<i>Chart could not be included in PDF</i>", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer
