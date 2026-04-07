import io

from flask import Flask, flash, redirect, render_template, request, send_file

from models import get_suitability_label, rank_crops
from services import (
    generate_pdf_report,
    get_available_options,
    get_cached_data,
    get_growing_season_averages,
    plot_results,
    prepare_data_for_forecast,
    run_forecast,
    run_forecast_pipeline,
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'SECRET-KEY-FROM-GEORGE'

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/forecast')
def forecast():
    return render_template('forecast.html')


@app.route('/selection', methods=['GET', 'POST'])
def selection():
    combined_df, region_mapping = get_cached_data()

    if combined_df is None:
        flash("Failed to load data", "error")
        return redirect('/selection')

    if request.method == 'POST':
        region_code = request.form.get("region")

        if not region_code:
            flash("Please select a region", "error")
            return redirect('/selection')

        country_mapping = {'MWI': 'Malawi'}

        if region_code in country_mapping:
            selection_input = {
                'type': 'country',
                'value': region_code,
                'name': country_mapping[region_code]
            }
        elif region_code in region_mapping:
            selection_input = {
                'type': 'region',
                'value': region_code,
                'name': region_mapping[region_code]
            }
        else:
            flash("Invalid region selected", "error")
            return redirect('/selection')

        forecasts, ci_dict, summary = run_forecast_pipeline(selection_input)

        if forecasts is None:
            flash(f"Forecast failed: {summary}", "error")
            return redirect('/selection')

        try:
            data = prepare_data_for_forecast(combined_df, selection_input)
            plot_results(data, forecasts, ci_dict, selection_input)
        except Exception as e:
            flash(f"Could not generate plot: {str(e)}", "error")
            return redirect('/selection')

        return render_template('results.html', summary=summary)

    available_countries, region_mapping = get_available_options(combined_df)
    return render_template('selection.html',
                           countries=available_countries,
                           regions=region_mapping)


@app.route('/forecastselection')
def forecastselection():
    return render_template('forecastselection.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/help')
def help_page():
    return render_template('help.html')


@app.route('/download_pdf/<region_name>')
def download_pdf(region_name):
    combined_df, region_mapping = get_cached_data()
    if combined_df is None:
        flash("Data not available", "error")
        return redirect('/selection')

    selection_input = None
    for gid, name in region_mapping.items():
        if name.replace(' ', '_').lower() == region_name:
            selection_input = {'type': 'region', 'value': gid, 'name': name}
            break

    if selection_input is None:
        flash("Region not found", "error")
        return redirect('/selection')

    data = prepare_data_for_forecast(combined_df, selection_input)
    if data is None or data.empty:
        flash("No data available", "error")
        return redirect('/selection')

    forecasts, ci_dict = run_forecast(data, selection_input)
    if forecasts is None:
        flash("Could not generate forecast", "error")
        return redirect('/selection')

    from models import compute_crop_suitability
    avg_rainfall, avg_ndvi, avg_temp = get_growing_season_averages(forecasts)
    suitability_scores = compute_crop_suitability(avg_temp, avg_rainfall, avg_ndvi)
    ranked = rank_crops(suitability_scores)

    summary = {
        'region': selection_input['name'],
        'avg_rainfall': avg_rainfall,
        'avg_ndvi': avg_ndvi,
        'avg_temp': avg_temp,
        'crop_suitability': ranked,
        'crop_recommendations': [
            (crop, f"{d['score']:.1f}% — {get_suitability_label(d['score'])}")
            for crop, d in ranked[:3]
        ],
        'least_recommendations': [
            (crop, f"{d['score']:.1f}% — {get_suitability_label(d['score'])}")
            for crop, d in ranked[-3:][::-1]
        ],
    }

    pdf_buffer = generate_pdf_report(summary, forecasts, selection_input)
    region_safe = selection_input['name'].replace(' ', '_').lower()
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f'forecast_report_{region_safe}.pdf',
        mimetype='application/pdf'
    )


@app.route('/download_csv/<region_name>')
def download_csv(region_name):
    combined_df, region_mapping = get_cached_data()
    if combined_df is None:
        flash("Data not available", "error")
        return redirect('/selection')

    selection_input = None
    for gid, name in region_mapping.items():
        if name.replace(' ', '_').lower() == region_name:
            selection_input = {'type': 'region', 'value': gid, 'name': name}
            break

    if selection_input is None:
        flash("Region not found", "error")
        return redirect('/selection')

    data = prepare_data_for_forecast(combined_df, selection_input)
    if data is None or data.empty:
        flash("No data available", "error")
        return redirect('/selection')

    forecasts, _ = run_forecast(data, selection_input)
    if forecasts is None:
        flash("Could not generate forecast", "error")
        return redirect('/selection')

    region_safe = selection_input['name'].replace(' ', '_').lower()
    return send_file(
        io.BytesIO(forecasts.to_csv().encode()),
        as_attachment=True,
        download_name=f'forecast_data_{region_safe}.csv',
        mimetype='text/csv'
    )

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
