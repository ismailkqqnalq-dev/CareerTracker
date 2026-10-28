"""Synthetic OCR evaluation: python -m scripts.evaluate_ocr --font /path/to/font.ttf.

Images stay in memory; JSON goes to stdout. Only this script imports application
code, never the reverse. Factory plugins are trusted local developer code.
"""

import argparse
from collections import Counter
import ctypes
import hashlib
import importlib
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import random
import statistics
import string
import sys
import time
import unicodedata

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.skill_catalog import SKILL_CATALOG
from app.services.ocr_engine import OcrError, RapidOCREngine
from app.services.ocr_service import extract_text

TURKISH_SPECIAL = "ğüşıİöçĞÜŞÖÇ"
SEED = 4172026


def _normalize_layout(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def _alignment(reference, output):
    """Levenshtein alignment; prefer exact diagonals, then substitutions/deletions."""
    n, m = len(reference), len(output)
    matrix = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        matrix[i][0] = i
    for j in range(m + 1):
        matrix[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1,
                               matrix[i - 1][j - 1] + (reference[i - 1] != output[j - 1]))
    pairs = []
    i, j = n, m
    while i or j:
        if i and j and matrix[i][j] == matrix[i - 1][j - 1] + (reference[i - 1] != output[j - 1]):
            pairs.append((reference[i - 1], output[j - 1]))
            i, j = i - 1, j - 1
        elif i and matrix[i][j] == matrix[i - 1][j] + 1:
            pairs.append((reference[i - 1], "<deleted>"))
            i -= 1
        else:
            pairs.append(("<inserted>", output[j - 1]))
            j -= 1
    return matrix[n][m], list(reversed(pairs))


def character_metrics(reference, output):
    # Use the application's exact folding behavior, without duplicating its rules.
    from app.services.skill_normalizer import normalize_text

    reference, output = _normalize_layout(reference), _normalize_layout(output)
    distance, pairs = _alignment(reference, output)
    confusions = {char: Counter() for char in sorted(set(string.ascii_letters + TURKISH_SPECIAL + reference))}
    insertions = Counter()
    for expected, observed in pairs:
        if expected == "<inserted>":
            insertions[observed] += 1
        else:
            confusions[expected][observed] += 1
    total = sum(char in TURKISH_SPECIAL for char in reference)
    correct = sum(expected in TURKISH_SPECIAL and expected == observed for expected, observed in pairs)
    folded_reference, folded_output = normalize_text(reference), normalize_text(output)
    folded_distance, _ = _alignment(folded_reference, folded_output)
    return {
        "edit_distance": distance, "reference_chars": len(reference),
        "cer": distance / max(1, len(reference)),
        "folded_edit_distance": folded_distance, "folded_reference_chars": len(folded_reference),
        "folded_cer": folded_distance / max(1, len(folded_reference)),
        "turkish_correct": correct, "turkish_total": total,
        "turkish_accuracy": correct / total if total else None,
        "confusions": {char: dict(counts) for char, counts in confusions.items()},
        "insertions": dict(insertions),
    }


def term_recall(output, terms):
    """Count canonical catalog names present after the application's normalization."""
    from app.services.skill_normalizer import normalize_text

    normalized_output = normalize_text(output)
    matched = [term for term in terms if normalize_text(term) in normalized_output]
    expected = len(terms)
    return {
        "expected": expected,
        "found": len(matched),
        "recall": len(matched) / expected if expected else None,
        "matched": matched,
        "missing": [term for term in terms if term not in matched],
    }


def synthetic_cases(font_path=None):
    """Default Pillow font is for unit tests; the evaluation CLI requires a real font."""
    specifications = [
        ("tr-clean", "İşe alım ekibimiz güçlü yazılı iletişim ve çözüm odaklı yaklaşım arıyor.", 32, False, False),
        ("tr-letters", "Ğ Ü Ş I İ Ö Ç ğ ü ş ı i ö ç", 32, False, False),
        ("tr-job", "Python, FastAPI ve PostgreSQL bilgisi tercih sebebidir.", 30, False, False),
        ("en-clean", "We are looking for a software engineer with API design experience.", 30, False, False),
        ("en-benefits", "Benefits include paid leave, health insurance, and flexible hours.", 28, False, False),
        ("tr-lines", "Aranan nitelikler: Python ve SQL deneyimi.\nİngilizce bilen adaylar tercih edilir.", 28, False, False),
        ("tr-small", "İş süreçlerini ölçer, geliştirir ve sonuçları raporlarsınız.", 16, False, False),
        ("en-small", "Applicants should communicate clearly and work with data.", 16, False, False),
        ("tr-contrast", "İş ilanı: çözüm odaklı, ölçülü ve güçlü iletişim.", 28, True, False),
        ("tr-noise", "Görüşme için özgeçmişinizi ve öğrenim bilgilerinizi paylaşın.", 27, False, True),
        ("mixed", "İstanbul ekibi: C#, .NET, müşteri ilişkileri ve çözüm üretme.", 28, False, False),
        ("tr-degraded", "Ücret: rekabetçi. Çalışma: uzaktan; başvuru için İK ile görüşün.", 17, True, True),
    ]
    rng = random.Random(SEED)
    cases = []
    for name, text, size, low_contrast, noise in specifications:
        font = ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default(size=size)
        lines = text.splitlines()
        width = max(700, int(max(font.getlength(line) for line in lines)) + 80)
        height = max(120, 60 + len(lines) * (size + 20))
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.multiline_text((28, 28), text, font=font, spacing=20,
                            fill=(170, 170, 170) if low_contrast else (20, 20, 20))
        if noise:
            for _ in range(1500):
                x, y = rng.randrange(width), rng.randrange(height)
                value = rng.choice([0, 50, 210, 255])
                image.putpixel((x, y), (value, value, value))
        if noise and low_contrast:
            blurred = image.filter(ImageFilter.GaussianBlur(0.35))
            image.close()
            image = blurred
        stream = BytesIO()
        image.save(stream, format="PNG")
        image.close()
        cases.append({"id": name, "reference": text, "image": stream.getvalue(),
                      "width": width, "height": height, "font_px": size})

    catalog_terms = tuple(entry["name"] for entry in SKILL_CATALOG)
    term_lines = [", ".join(catalog_terms[index:index + 3])
                  for index in range(0, len(catalog_terms), 3)]
    lines = ["Aranan beceriler:", *term_lines]
    text = "\n".join(lines)
    font = ImageFont.truetype(str(font_path), 28) if font_path else ImageFont.load_default(size=28)
    width = max(700, int(max(font.getlength(line) for line in lines)) + 80)
    height = max(120, 60 + len(lines) * 48)
    image = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(image).multiline_text((28, 28), text, font=font, spacing=20, fill=(20, 20, 20))
    stream = BytesIO()
    image.save(stream, format="PNG")
    image.close()
    cases.append({"id": "tr-catalog-terms", "reference": text, "image": stream.getvalue(),
                  "width": width, "height": height, "font_px": 28, "skill_terms": catalog_terms})
    return cases


def rss_bytes():
    """Sample current process RSS, not just Python allocations or model memory."""
    if sys.platform == "win32":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in
                ("peak_rss", "rss", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
        if query(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return counters.rss
    elif sys.platform.startswith("linux"):
        try:
            pages = int(Path("/proc/self/statm").read_text().split()[1])
            return pages * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, IndexError):
            pass
    return None


def evaluate_cases(engine, cases, repeats=1):
    samples = [rss_bytes()]
    rows = []
    for case in cases:
        measurements = []
        first_text, first_error = "", None
        for repetition in range(repeats + 1):
            wall, cpu = time.perf_counter(), time.process_time()
            try:
                text = extract_text(case["image"], engine=engine).text
                error = None
            except OcrError as exc:
                if exc.error_code in {"ocr_engine_unavailable", "ocr_engine_initialization_failed"}:
                    raise
                text, error = "", exc.error_code
            measurements.append({"wall_s": time.perf_counter() - wall,
                                 "cpu_s": time.process_time() - cpu, "error_code": error})
            samples.append(rss_bytes())
            if repetition == 0:
                first_text, first_error = text, error
        rows.append({key: value for key, value in case.items() if key != "image"} | {
            "output": first_text, "error_code": first_error,
            "metrics": character_metrics(case["reference"], first_text),
            "term_metrics": term_recall(first_text, case["skill_terms"]) if case.get("skill_terms") else None,
            "first_pass": measurements[0], "warm_runs": measurements[1:],
        })
    valid_memory = [sample for sample in samples if sample is not None]
    aggregate = {}
    insertions = Counter()
    for row in rows:
        for expected, counts in row["metrics"]["confusions"].items():
            aggregate.setdefault(expected, Counter()).update(counts)
        insertions.update(row["metrics"]["insertions"])
    total = sum(row["metrics"]["reference_chars"] for row in rows)
    folded_total = sum(row["metrics"]["folded_reference_chars"] for row in rows)
    special_total = sum(row["metrics"]["turkish_total"] for row in rows)
    warm = [run for row in rows for run in row["warm_runs"]]
    term_rows = [row["term_metrics"] for row in rows if row["term_metrics"] is not None]
    expected_terms = sum(row["expected"] for row in term_rows)
    found_terms = sum(row["found"] for row in term_rows)
    top_confusions = [
        {"expected": expected, "observed": observed, "count": count}
        for expected, counts in aggregate.items()
        for observed, count in counts.items()
        if expected != observed
    ]
    top_confusions.sort(key=lambda item: (-item["count"], item["expected"], item["observed"]))
    return {
        "images": rows,
        "summary": {
            "cer": sum(row["metrics"]["edit_distance"] for row in rows) / max(1, total),
            "folded_cer": sum(row["metrics"]["folded_edit_distance"] for row in rows) / max(1, folded_total),
            "turkish_accuracy": sum(row["metrics"]["turkish_correct"] for row in rows) / special_total if special_total else None,
            "confusions": {char: dict(counts) for char, counts in aggregate.items()},
            "top_confusions": top_confusions[:10],
            "insertions": dict(insertions),
            "term_recall": {
                "expected": expected_terms,
                "found": found_terms,
                "recall": found_terms / expected_terms if expected_terms else None,
            },
            "cold_first_call": rows[0]["first_pass"],
            "warm_wall_mean_s": statistics.mean(run["wall_s"] for run in warm),
            "warm_cpu_mean_s": statistics.mean(run["cpu_s"] for run in warm),
            "rss_before_bytes": samples[0], "rss_after_bytes": samples[-1],
            "rss_sampled_peak_bytes": max(valid_memory) if valid_memory else None,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="rapidocr", help="rapidocr or trusted module:factory returning OcrEngine")
    parser.add_argument("--lang", default="tr", choices=["tr", "ch"])
    parser.add_argument("--font", type=Path, required=True, help="Local TrueType/OpenType font supporting Turkish")
    parser.add_argument("--repeats", type=int, default=1, help="Warm repetitions per image (at least one)")
    args = parser.parse_args(argv)
    if args.repeats < 1 or not args.font.is_file():
        parser.error("--repeats must be >=1 and --font must point to an existing font")
    # normalize_text imports application model definitions; don't read the real .env.
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    if args.engine == "rapidocr":
        engine = RapidOCREngine(lang=args.lang)
    else:
        module, separator, factory = args.engine.partition(":")
        if not separator:
            parser.error("custom engine must have module:factory syntax")
        engine = getattr(importlib.import_module(module), factory)()
    try:
        report = evaluate_cases(engine, synthetic_cases(args.font), args.repeats)
    except OcrError as exc:
        print(json.dumps(exc.to_payload()), file=sys.stderr)
        return 2
    packages = {}
    for name in ("rapidocr", "onnxruntime", "Pillow"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    report["environment"] = {
        "python": platform.python_version(), "platform": platform.platform(),
        "logical_cpus": os.cpu_count(), "engine": args.engine, "lang": args.lang,
        "packages": packages, "seed": SEED,
        "font_sha256": hashlib.sha256(args.font.read_bytes()).hexdigest(),
        "memory": "sampled process RSS; null if unavailable; not an isolated model allocation",
        "timing": "first call includes lazy model loading; OS caches are not flushed; CPU sums threads",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
