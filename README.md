# 🌾 Crop Prediction System with Time Series Analysis

### Forecasting Crop Suitability in Malawi Using SARIMA and FAO Thresholds

---

## Why This Project Exists

Agriculture is the backbone of Malawi's economy, employing the majority of the population and accounting for a significant share of GDP. Yet farmers, extension officers, and policymakers consistently face the same challenge: deciding what to grow, and when, without reliable forward-looking data.

Historically, crop planning in Malawi has leaned heavily on historical averages and institutional knowledge — approaches that are increasingly unreliable in the face of shifting rainfall patterns, rising temperatures, and erratic growing seasons. When a farmer plants the wrong crop for the conditions that actually materialise, the consequences are not merely economic. They are food security crises at the household and national level.

This project directly addresses that gap. Rather than describing what conditions _were_, it asks: **what are conditions likely to be — and which crops will thrive under them?**

---

## What This System Does

At its core, this project builds a **data-driven crop suitability prediction pipeline** for Malawi. It works in three stages:

**1. Forecasting Environmental Conditions**

Using SARIMA (Seasonal AutoRegressive Integrated Moving Average) models, the system analyses historical time series data for three critical agricultural indicators:

- **NDVI** (Normalised Difference Vegetation Index) — a satellite-derived measure of vegetation health and greenness
- **LST** (Land Surface Temperature) — surface thermal conditions that affect crop stress and growth
- **Rainfall** — precipitation levels that determine irrigation need and water availability

SARIMA is particularly well-suited here because these indicators follow strong seasonal cycles. The model learns those cycles from historical data and projects them forward in time.

**2. Synthesising a Composite Forecast**

Once each indicator is forecast independently, their predicted values are averaged into a composite environmental score — a single, interpretable signal representing the expected growing conditions for a given period and location.

**3. Measuring Against FAO Crop Thresholds**

The composite forecast is then evaluated against **FAO (Food and Agriculture Organization) crop suitability thresholds** — scientifically established ranges of temperature, moisture, and vegetation conditions under which specific crops are known to perform well. This comparison produces a suitability assessment: for each crop in the model, the system determines whether forecasted conditions are likely to support viable growth.

The result answers a practical question: _given what conditions are expected to look like, which crops are most suitable to plant?_

---

## Why It Matters

**For farmers and extension officers**, this system provides forward-looking, evidence-based guidance at the start of a planting season — moving beyond gut feel and generalised advice.

**For researchers and policymakers**, it demonstrates a reproducible, scalable methodology for integrating remote sensing data, time series forecasting, and international agronomic standards into a deployable decision-support tool.

**For Malawi specifically**, the approach is calibrated to local conditions. The thresholds, the datasets, and the environmental indicators selected all reflect the realities of Malawian agriculture — its dominant crops, its seasonal calendar, and its climate vulnerabilities.

---

## Navigating This Repository

The repository is organised into five top-level folders. Here is a guide to what lives where, what each component does, and the recommended order in which to approach them.

```
Crop_Prediction_System_With_Time_Series/
│
├── Datasets/
│   ├── Original_Datasets/
│   ├── Messy_Datasets/
│   └── Output_Datasets/
│
├── Notebooks/
│   ├── data_merging.ipynb
│   ├── data_cleaning.ipynb
│   ├── handle_missing_values.ipynb
│   └── eda.ipynb
│
├── Flask_Application_and_Notebook/
│   ├── app.py
│   ├── models.py
│   ├── services.py
│   ├── combined_with_plants.csv
│   ├── malawi_pipeline_walkthrough.ipynb
│   ├── templates/
│   ├── static/
│   └── models/
│
├── Report/
└── PowerPoint/
```

---

### 📁 `Datasets/` — The Raw Material

**Start here to understand the inputs.**

This folder is divided into three subfolders that reflect the data lifecycle:

| Subfolder            | Contents                                                                                                                                                                                                       |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Original_Datasets/` | Source data as obtained, before any processing. The raw NDVI, LST, and rainfall time series for Malawi. Start here if you want to understand the data origins or rerun the pipeline from scratch.              |
| `Messy_Datasets/`    | Intermediate datasets that have been partially combined or restructured but not yet fully cleaned. These represent the state of the data after initial merging and before the cleaning steps in the notebooks. |
| `Output_Datasets/`   | The final, clean, analysis-ready datasets produced by the preprocessing notebooks. These are the files consumed directly by the SARIMA modelling pipeline and the Flask application.                           |

---

### 📓 `Notebooks/` — The Data Preparation Pipeline

**Follow these notebooks in order.**

This folder contains four Jupyter notebooks that take the data from raw to ready. They are designed to be run sequentially:

| Step | Notebook                      | What It Does                                                                                                                                                                                                                    |
| ---- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `data_merging.ipynb`          | Combines the separate source files (NDVI, LST, rainfall) into unified datasets, aligning them by date and location.                                                                                                             |
| 2    | `data_cleaning.ipynb`         | Handles inconsistencies, formatting issues, and structural problems in the merged data — column standardisation, type corrections, and general tidying.                                                                         |
| 3    | `handle_missing_values.ipynb` | Addresses gaps in the time series data. Missing values in satellite and climate records are common due to cloud cover and sensor gaps. This notebook documents and resolves those gaps using appropriate imputation strategies. |
| 4    | `eda.ipynb`                   | Exploratory Data Analysis. Visualises the time series, examines seasonal patterns, and provides the analytical foundation that informs the SARIMA modelling choices made in the Flask pipeline.                                 |

> The cleaned, processed outputs from these notebooks are saved into `Datasets/Output_Datasets/` and consumed by the application.

---

### 🚀 `Flask_Application_and_Notebook/` — The Prediction Engine

**This is where the system comes to life.**

This folder contains both the deployed web application and the companion notebook that walks through the full modelling pipeline.

#### Application Files

| File                       | Role                                                                                                                                                                                           |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.py`                   | The main Flask application entry point. Run this file to launch the web interface locally.                                                                                                     |
| `models.py`                | The heart of the prediction logic. FAO crop suitability thresholds are defined here, and the averaged SARIMA forecasts are evaluated against those thresholds to produce crop recommendations. |
| `services.py`              | Supporting service functions that handle data retrieval, processing calls, and the orchestration between the SARIMA forecasting step and the threshold evaluation in `models.py`.              |
| `combined_with_plants.csv` | The combined dataset used directly by the application, linking environmental time series with crop plant data.                                                                                 |
| `templates/`               | HTML templates for the web interface front-end.                                                                                                                                                |
| `static/`                  | Static assets (CSS, JavaScript, images) for the front-end.                                                                                                                                     |
| `models/`                  | Stored and serialised model artefacts used by the application at runtime.                                                                                                                      |

#### Companion Notebook

`malawi_pipeline_walkthrough.ipynb` — Runs the full pipeline end-to-end in a step-by-step, annotated format: SARIMA modelling for NDVI, LST, and rainfall; composite forecast generation; and FAO threshold evaluation. If you want to understand the modelling methodology in detail, or adapt it for a different region or set of crops, this notebook is the authoritative reference.

#### Running the Application Locally

```bash
cd Flask_Application_and_Notebook
pip install -r requirements.txt
python app.py
```

The app will be accessible in your browser at `http://localhost:5000`.

---

### 📄 `Report/` — The Full Academic Write-Up

Contains the project report covering research background, methodology, results, and discussion — including literature review, model evaluation, and interpretation of findings. This is the authoritative reference for the academic and theoretical context of the system.

---

### 📊 `PowerPoint/` — High-Level Visual Summary

Contains the presentation slides for the project. A useful entry point if you want a concise overview before engaging with the technical materials.

---

## A Note on `models.py` and the FAO Thresholds

The `models.py` file is the decision layer of this system. It encodes FAO-defined environmental ranges for each supported crop — minimum and maximum acceptable values of temperature, vegetation health, and moisture. When a forecasted composite value falls within a crop's acceptable range, that crop is flagged as suitable for the projected conditions.

These thresholds are grounded in decades of agronomic research and are the same standards used by international development and food security bodies when assessing agricultural potential. Extending the system to additional crops requires only adding their threshold profiles to `models.py`.

---

## Suggested Starting Points

| Your goal                              | Where to start                                  |
| -------------------------------------- | ----------------------------------------------- |
| Understand the problem and methodology | `Report/` → `malawi_pipeline_walkthrough.ipynb` |
| Get a quick overview                   | `PowerPoint/`                                   |
| Run the app                            | `Flask_Application_and_Notebook/` → `app.py`    |
| Rerun the data pipeline                | `Notebooks/` in order (steps 1–4)               |
| Extend to new crops or regions         | `Flask_Application_and_Notebook/models.py`      |

---

_This project was developed as an applied research contribution to data-driven agricultural decision support in Malawi._
