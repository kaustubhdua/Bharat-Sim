# BharatSim ML and analytics pipeline — validated claim boundaries

## Overview

BharatSim contains two distinct failure-classification implementations and a deterministic anomaly heuristic. They have different training data and evaluation status; do not combine their metrics or describe them as a single independently validated model.

## 1. Backend portable classifier

**Implementation:** `backend/app/ml_classifier.py`  
**Model:** `backend/app/ml/failure_model.json`  
**Training script:** `scripts/train_classifier.py`

- TF-IDF-style tokenization with class-centroid vectors and a pure-Python inference path.
- The checked-in training corpus contains 58 curated examples.
- `backend/app/ml/model_metrics.json` records 1.0 accuracy on the training set. The training script explicitly computes this by classifying the same `TRAINING_DATA` used to build the centroids.
- This is resubstitution accuracy, not an independent test set, cross-validation, calibration study or field accuracy.
- The normalized softmax-like output is a relative score distribution. It is not probability calibration.

Use the backend model as a lightweight log-triage signal only. Do not quote 100% accuracy as a product performance guarantee.

## 2. Worker classifier

**Implementation:** `worker/ml.py`  
**Model:** `worker/models/failure_classifier.joblib`  
**Training script:** `scripts/train_worker_classifier.py`

The worker pipeline uses word and character TF-IDF features with a logistic-regression classifier. The documented training mix contains:
- Android LogHub lines weakly labelled by rules;
- templated failure lines generated from real exception classes, tags and message formats;
- optional local lines in `worker/.cache/labelled.tsv`.

The checked-in metrics file reports:
- 9,140 mixed samples;
- 5-fold GroupKFold evaluation;
- accuracy 0.7843 (reported standard deviation 0.0913);
- macro-F1 0.7707 (reported standard deviation 0.1024);
- per-class F1: ANR 0.5865, crash 0.8879, network 0.7143, OOM 0.8421, other 0.7930, storage 0.8889.

These scores describe performance on the documented mixed/weakly-labelled and partly templated dataset. They are not external field accuracy. Before quoting them as generalized model performance, independently audit weak-label quality, template/tag grouping and leakage, create a separately labelled external holdout, publish a confusion matrix and evaluate calibration.

## 3. Anomaly and regression detection

**Implementation:** `backend/app/anomaly_detector.py`

The current implementation is a transparent heuristic:
- fixed per-metric regression thresholds for startup latency, jank, memory and network latency;
- a fixed-reference z-score calculation over startup delta, constrained jank and memory delta;
- anomaly score = capped maximum absolute z-score × 25;
- no fitted covariance matrix, IsolationForest, neural model or production-trained multivariate model.

Missing metrics are currently represented as zero in the z-score feature row. This behavior should be treated as a limitation; it needs an explicit missing-data policy and tests before scores are used for high-stakes comparisons.

## 4. BharatScore

BharatScore is a heuristic score returned by the analysis API. It is not a probability, device certification, independent benchmark or proof of app health. Reports include the method and warning text. Keep the score tied to supplied evidence and explain that missing evidence limits interpretation.

## 5. Required validation before stronger claims

- Separate training and external test datasets by app, source and template.
- Independently label a representative Android logcat set.
- Publish confusion matrices and per-class precision/recall/F1.
- Evaluate calibration rather than treating softmax-like scores as confidence probabilities.
- Test adversarial, malformed, multilingual and unseen-version logs.
- Version the model and data provenance.
- Define missing-data behavior for anomaly metrics and repeatability for BharatScore.

Until then, describe classifier, anomaly and score outputs as triage heuristics.
