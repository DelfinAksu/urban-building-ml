# Urban Building Pattern Discovery and Property Value Prediction using NYC PLUTO Dataset

## Project Overview

This project explores urban building patterns and predicts property values in Brooklyn, New York using a hybrid machine learning pipeline. Instead of directly applying machine learning to a ready-made dataset, a custom data integration and feature engineering workflow was developed by combining multiple urban data sources.

The project has two main objectives:

1. Discover hidden urban building typologies using unsupervised learning (K-Means clustering)
2. Predict building property values using engineered spatial and urban features

The project combines data engineering, geospatial analysis, clustering, and regression modeling.

---

## Problem Definition

Property values are influenced not only by physical building characteristics but also by spatial and environmental context.

Traditional datasets often ignore:

* proximity to public transportation
* neighborhood amenities
* urban density
* hidden spatial patterns

This project integrates these factors into a unified building-level dataset and investigates whether discovered urban patterns can improve prediction performance.

---

## Data Sources

### NYC PLUTO Dataset

Source: NYC Department of City Planning

Contains:

* building characteristics
* land use information
* geographic attributes
* tax assessment data

Original dataset:

* 858,644 building records
* 92 attributes

Brooklyn subset used.

### MTA Subway Stations

Source: MTA Open Data

Used to generate:

* nearest_subway_dist
* subway_count_500m
* subway_count_1000m

### OpenStreetMap POIs

Source: Overpass API

Collected categories:

* cafes
* restaurants
* schools
* parks
* supermarkets
* convenience stores

POI density features were generated within a 500m radius.

---

## Data Cleaning

Main cleaning steps:

* Removed missing coordinates
* Removed invalid building area values
* Removed invalid lot area values
* Removed undefined target values
* Converted yearbuilt = 0 into NaN
* Applied coordinate sanity checks

Dataset size:

276,324 rows → 265,507 rows retained

Retention rate:
96.1%

---

## Feature Engineering

Three groups of features were created.

### Subway Accessibility

* nearest_subway_dist
* subway_count_500m
* subway_count_1000m

### POI Density Features

Generated counts for:

* cafes
* restaurants
* schools
* parks
* supermarkets
* convenience stores

### PLUTO-derived Features

* building_age
* FAR
* unit_density
* commercial_unit_ratio
* commercial_area_ratio

Final integrated feature set combines physical, environmental and spatial information.

---

## Urban Pattern Discovery

K-Means clustering was used to discover hidden urban building patterns.

Selected:

K = 6

Examples of discovered cluster profiles:

* Mid-density residential
* Luxury high-rise
* Commercial mixed-use
* Working-class residential
* Rare extreme structures

These clusters were later used as predictive features.

---

## Spatial Validation Strategy

Traditional random train-test splitting may cause spatial information leakage because nearby buildings often share similar characteristics.

To avoid this:

* Brooklyn was divided into 1km × 1km spatial cells
* Spatial GroupKFold (k=5) was used

This ensures more realistic evaluation.

---

## Regression Models

Models evaluated:

* Ridge Regression
* Random Forest
* XGBoost

Evaluation metrics:

* RMSE
* MAE
* R²

---

## Results

Best model:

XGBoost + Cluster-enhanced feature set

Performance:

* R² = 0.942
* RMSE = 0.267
* MAE = 0.192

Urban pattern information improved prediction performance and provided additional predictive signals.

---

## Future Work

Potential improvements:

* Integrate Google Street View imagery
* Add visual building appearance features
* Combine image-based deep learning with tabular data
* Extend to all NYC boroughs

---

## Repository Structure

project/
│
├── data/
├── notebooks/
├── results/
├── figures/
├── README.md
└── requirements.txt

---

## Author

Delfin Aksu
Computer Engineering
Eskişehir Technical University
