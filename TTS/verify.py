#!/usr/bin/env python3
"""Verify the C runtime matches sklearn's predict_proba exactly."""
import subprocess, re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from train import analyze  # reuse the exact same tokenizer

df = pd.read_csv("emergency_data.csv")
vec = TfidfVectorizer(analyzer=analyze)
X = vec.fit_transform(df["text"].astype(str))
clf = LogisticRegression(max_iter=2000, C=10.0).fit(X, df["label"].astype(str))

tests = [
    "I'm lost",
    "I've completely lost my bearings out here",
    "help my leg is broken and bleeding",
    "the kitchen is on fire",
    "i can't get out the door is jammed",
    "what time is it",
    "i am stuck under a fallen tree",
]

print(f"{'phrase':42} {'py_class':9} {'py_p':6} {'c_class':9} {'c_p':6} match")
worst = 0.0
for t in tests:
    proba = clf.predict_proba(vec.transform([t]))[0]
    py_i = proba.argmax()
    py_class, py_p = clf.classes_[py_i], proba[py_i]

    out = subprocess.run(["./classifier", "--raw", t], capture_output=True, text=True).stdout
    m = re.match(r"(?:uncertain \(top=)?(\w+)\)? \(?([\d.]+)", out)
    c_class, c_p = m.group(1), float(m.group(2))

    diff = abs(py_p - c_p)
    worst = max(worst, diff)
    ok = "OK" if (c_class == py_class and diff < 1e-3) else "XX"
    print(f"{t[:42]:42} {py_class:9} {py_p:.3f}  {c_class:9} {c_p:.3f}  {ok}")

print(f"\nworst probability difference: {worst:.2e}")
