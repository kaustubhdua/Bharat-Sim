# BharatSim — ML and BharatScore validation status

**Status:** internal implementation review; not an independent model-validation certificate.

## 1. Failure classification

The repository has two separate classifier paths:

| Path | Implementation | Dataset / recorded metrics | Interpretation |
|---|---|---|---|
| Backend API | Pure-Python TF-IDF centroid model | 58 curated examples; 1.0 training/resubstitution accuracy | Not a holdout result; not field accuracy |
| Android worker | TF-IDF word/character features + logistic regression | 9,140 mixed samples; 5-fold GroupKFold accuracy 0.7843, macro-F1 0.7707 | Weak-rule LogHub labels and templated examples; not field accuracy |

The worker model's recorded per-class F1 is ANR 0.5865, crash 0.8879, network 0.7143, OOM 0.8421, other 0.7930 and storage 0.8889. These metrics are included for reproducibility, not as a guarantee of performance on arbitrary customer logs.

No independent external holdout, independently labelled confusion matrix, calibration report or representative field benchmark is currently accepted. The backend model's training-set accuracy must not be quoted as generalized accuracy.

## 2. Anomaly detection

The backend detector combines explicit thresholds with a fixed-reference z-score heuristic. It is not a trained multivariate model. Current implementation details and limitations are documented in [ML_PIPELINE.md](ML_PIPELINE.md), including the fixed reference values and the current treatment of missing metrics.

## 3. BharatScore

BharatScore is a heuristic summary score, not a probability of success and not a certification that an APK is ready for Indian devices. Its value depends on the signals present in the submitted log or worker report. Missing telemetry must not be interpreted as a pass.

Before using BharatScore for a release decision, publish the exact weights and thresholds from the implementation, validate them against repeated controlled runs and independent reviewer-labelled outcomes, and define a conservative missing-evidence policy.

## 4. Validation work remaining

- [ ] Independently label a representative external Android logcat dataset.
- [ ] Split by app, source and template to prevent leakage.
- [ ] Publish per-class precision/recall/F1 and a confusion matrix.
- [ ] Evaluate calibration and confidence reliability.
- [ ] Test unseen Android versions, app families, malformed logs and adversarial strings.
- [ ] Version datasets and models with reproducible provenance.
- [ ] Validate anomaly thresholds and BharatScore against repeated, controlled baseline/persona runs.
