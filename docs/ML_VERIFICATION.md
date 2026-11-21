# BharatSim — ML Verification

**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
**Date:** 2026-11-21

## Classifier

The implemented classifier is a TF-IDF class-centroid classifier using a small curated Android logcat dataset. A 100% resubstitution result on the training rows is not independent generalization accuracy. It must not be described as 100% holdout accuracy or a reliable production diagnosis.

## Anomaly detection

Current logic uses deterministic thresholds/statistical heuristics (including z-score-style checks). This is not an IsolationForest model or a validated multivariate anomaly detector.

## Evaluation status

No independently labelled held-out dataset, model version registry, calibration report, or credible per-class precision/recall/F1/confusion matrix was verified in this audit. Therefore no such metrics are reported.

## Required evaluation

- Freeze/version the dataset and document label definitions/adjudication.
- Split by app/device/source to reduce leakage.
- Report per-class precision, recall, F1, macro/weighted scores and confusion matrix.
- Check calibration/abstention and confidence behavior on unknown, malformed and out-of-domain logcat.
- Version dataset, vectorizer, preprocessing, model artifact and inference response.
- Test deterministic scoring with missing metrics, boundary values and repeated same inputs.
