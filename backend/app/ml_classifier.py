"""Machine Learning Failure Classifier for BharatSim.

Uses portable TF-IDF feature weights trained on Android failure signatures.
Pure-Python implementation with zero C/C++ or OpenMP DLL dependencies, ensuring
100% reliable execution across Windows, Linux, macOS, and Vercel serverless.
"""
from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODEL_JSON_PATH = Path(__file__).resolve().parent / "ml" / "failure_model.json"
_MODEL_DATA: dict[str, Any] | None = None


def _load_model() -> dict[str, Any] | None:
    global _MODEL_DATA
    if _MODEL_DATA is None:
        if MODEL_JSON_PATH.is_file():
            try:
                with open(MODEL_JSON_PATH, "r", encoding="utf-8") as f:
                    _MODEL_DATA = json.load(f)
                logger.info("Loaded BharatSim failure model from %s", MODEL_JSON_PATH)
            except Exception as exc:
                logger.warning("Failed to load %s: %s", MODEL_JSON_PATH, exc)
                _MODEL_DATA = {}
        else:
            logger.info("Failure model JSON not found at %s", MODEL_JSON_PATH)
            _MODEL_DATA = {}
    return _MODEL_DATA if _MODEL_DATA else None


def tokenize(text: str) -> list[str]:
    """Extract lowercase alpha tokens from text, filtering stopwords and units."""
    stopwords = {"in", "at", "to", "for", "from", "on", "with", "after", "is", "ms", "kb", "mb", "pid", "tid", "uid", "code", "act", "cat"}
    tokens = [m.lower() for m in re.findall(r"(?i)[a-z_][a-z0-9_]*", text) if len(m) >= 3]
    return [t for t in tokens if t not in stopwords]


def classify_log_snippet(line: str) -> dict[str, Any]:
    """Classify a logcat line using the trained TF-IDF centroid model.

    Returns:
        dict with:
            - 'category': 'crash' | 'anr' | 'oom' | 'network' | 'storage' | 'normal'
            - 'confidence': float (0.0 to 1.0)
            - 'is_failure': bool
            - 'scores': normalized relative class scores (not calibrated probabilities)
    """
    cleaned = line.strip()
    if not cleaned:
        return {"category": "normal", "confidence": 1.0, "is_failure": False}

    model = _load_model()
    if not model:
        # Fallback keyword classifier if model JSON is unreadable
        lower = cleaned.lower()
        if any(t in lower for t in ("fatal exception", "sigsegv", "sigabrt", "process.*has died")):
            return {"category": "crash", "confidence": 0.90, "is_failure": True}
        if any(t in lower for t in ("anr in", "input dispatching timed out", "application not responding")):
            return {"category": "anr", "confidence": 0.88, "is_failure": True}
        if any(t in lower for t in ("outofmemoryerror", "low memory killer", "lmkd.*kill")):
            return {"category": "oom", "confidence": 0.92, "is_failure": True}
        if any(t in lower for t in ("sockettimeoutexception", "unknownhostexception", "connectexception", "504 gateway")):
            return {"category": "network", "confidence": 0.89, "is_failure": True}
        if any(t in lower for t in ("enospc", "sqlitefullexception", "no space left on device")):
            return {"category": "storage", "confidence": 0.91, "is_failure": True}
        return {"category": "normal", "confidence": 0.80, "is_failure": False}

    tokens = tokenize(cleaned)
    classes: list[str] = model["classes"]
    idf: dict[str, float] = model["idf"]
    class_vectors: dict[str, dict[str, float]] = model["class_vectors"]

    # Compute raw dot-product similarity scores
    raw_scores: dict[str, float] = {}
    for c in classes:
        vec = class_vectors.get(c, {})
        score = sum(vec.get(t, 0.0) * idf.get(t, 1.0) for t in tokens)
        raw_scores[c] = score

    # Normalize relative class scores for ranking; this is not probability calibration.
    max_score = max(raw_scores.values()) if raw_scores else 0.0
    if max_score > 0.0:
        exp_scores = {c: math.exp(min(50.0, s / 2.0)) for c, s in raw_scores.items()}
        total_exp = sum(exp_scores.values()) or 1.0
        probabilities = {c: round(exp_scores[c] / total_exp, 4) for c in classes}
        pred_label = max(probabilities, key=probabilities.get)
        top_conf = probabilities[pred_label]
    else:
        probabilities = {c: 1.0 / len(classes) for c in classes}
        pred_label = "normal"
        top_conf = probabilities["normal"]

    return {
        "category": pred_label,
        "confidence": top_conf,
        "is_failure": pred_label != "normal",
        "probabilities": probabilities,
    }


def classify_logcat_stream(text: str) -> list[dict[str, Any]]:
    """Scan logcat text and return ML-classified failure markers with line numbers."""
    lines = text.splitlines()
    findings: list[dict[str, Any]] = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if len(stripped) < 8:
            continue
        res = classify_log_snippet(stripped)
        if res.get("is_failure") and res.get("confidence", 0) >= 0.40:
            findings.append({
                "line_number": idx,
                "text": stripped[:300],
                "category": res["category"],
                "confidence": res["confidence"],
                "probabilities": res.get("probabilities", {}),
            })

    return findings
