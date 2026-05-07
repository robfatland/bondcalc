"""
aggregate.py — Merge per-molecule bondcalc results and timing files
into a single results.json, then clean up the individual files.
Also validates computed bond properties against literature reference values.

Usage: python aggregate.py [output_dir]
       Defaults to /output (the container mount point).

Reference sources:
  - Pauling electronegativity values (Pauling scale, CRC Handbook)
  - Experimental bond lengths from NIST CCCBDB, CRC Handbook, and
    standard general chemistry references (Pearson, Saylor/LibreTexts)
  Content was rephrased for compliance with licensing restrictions.
"""

import json
import glob
import math
import os
import sys

output_dir = sys.argv[1] if len(sys.argv) > 1 else "/output"

# ── Reference data for validation ────────────────────────────────────────────
# Pauling electronegativities (standard textbook values)
REFERENCE_EN = {
    "H": 2.20, "Li": 0.98, "Be": 1.57, "B": 2.04, "C": 2.55,
    "N": 3.04, "O": 3.44, "F": 3.98, "Na": 0.93, "Mg": 1.31,
    "Al": 1.61, "Si": 1.90, "P": 2.19, "S": 2.58, "Cl": 3.16,
    "K": 0.82, "Ca": 1.00, "Ti": 1.54, "Mn": 1.55, "Fe": 1.83,
    "Cu": 1.90, "Zn": 1.65, "Ag": 1.93, "Ba": 0.89, "Cs": 0.79,
}

# Experimental bond lengths in pm (from NIST, CRC Handbook, Pearson refs)
# For ionic compounds, this is the cation-anion distance in the crystal.
# For covalent molecules, this is the gas-phase bond length.
REFERENCE_BOND_LENGTH = {
    "O-H":   95.8,    # water O-H
    "Na-Cl": 236.1,   # NaCl crystal
    "C-O":   116.0,   # CO2 C=O (double bond)
    "N-H":   101.2,   # ammonia N-H
    "Ca-F":  219.0,   # CaF2 crystal
    "Fe-O":  194.5,   # Fe2O3 avg Fe-O
    "C-H":   108.7,   # methane C-H
    "Mg-O":  210.0,   # MgSO4 Mg-O (crystal)
    "S-O":   143.1,   # SO2 S=O
    "K-O":   228.0,   # KMnO4 K-O (crystal)
    "Mn-O":  163.0,   # KMnO4 Mn=O
    "Ti-O":  195.0,   # TiO2 rutile Ti-O
    "Si-O":  161.0,   # SiO2 Si-O
    "Al-O":  191.0,   # Al2O3 corundum Al-O
    "H-Cl":  127.5,   # HCl gas phase
    "H-F":    91.7,   # HF gas phase
    "Li-F":  156.4,   # LiF crystal
    "Be-Cl": 179.7,   # BeCl2 gas phase
    "B-F":   130.7,   # BF3 gas phase
    "P-Cl":  204.3,   # PCl3 gas phase
    "N-O":   119.7,   # NO2 N-O (avg single/double)
    "Cs-Cl": 290.6,   # CsCl crystal
    "Ba-O":  194.0,   # BaO crystal
    "Zn-S":  234.0,   # ZnS sphalerite
    "Cu-O":  195.0,   # CuO crystal
    "Ag-Cl": 277.4,   # AgCl crystal
}

# Expected bond classification based on standard Δχ thresholds
# (same thresholds as bondcalc.py: <0.5 nonpolar, 0.5-1.7 polar, ≥1.7 ionic)
REFERENCE_CLASSIFICATION = {}
for bond_key, _ in REFERENCE_BOND_LENGTH.items():
    a, b = bond_key.split("-")
    en_a = REFERENCE_EN.get(a)
    en_b = REFERENCE_EN.get(b)
    if en_a is not None and en_b is not None:
        delta = abs(en_a - en_b)
        if delta < 0.5:
            REFERENCE_CLASSIFICATION[bond_key] = "nonpolar covalent"
        elif delta < 1.7:
            REFERENCE_CLASSIFICATION[bond_key] = "polar covalent"
        else:
            REFERENCE_CLASSIFICATION[bond_key] = "ionic"


def validate_bonds(molecules_data):
    """Compare computed bond results against reference values.
    Returns a list of per-bond validation records and an overall summary."""

    validations = []
    total_bonds = 0
    classification_matches = 0
    en_errors = []

    for mol in molecules_data:
        molecule_name = mol.get("molecule", "?")
        for bond in mol.get("bonds", []):
            bond_key = bond.get("bond", "")
            total_bonds += 1
            v = {"molecule": molecule_name, "bond": bond_key, "checks": []}

            # ── Check electronegativity values ────────────────────────────
            a, b = bond.get("element_a", ""), bond.get("element_b", "")
            for elem, field in [(a, "electronegativity_a"), (b, "electronegativity_b")]:
                calc_en = bond.get(field)
                ref_en = REFERENCE_EN.get(elem)
                if calc_en is not None and ref_en is not None:
                    err = abs(calc_en - ref_en)
                    en_errors.append(err)
                    v["checks"].append({
                        "property": f"EN({elem})",
                        "calculated": calc_en,
                        "reference": ref_en,
                        "error": round(err, 4),
                        "pass": err < 0.05,
                    })

            # ── Check Δχ ──────────────────────────────────────────────────
            calc_delta = bond.get("delta_electronegativity")
            ref_en_a = REFERENCE_EN.get(a)
            ref_en_b = REFERENCE_EN.get(b)
            if calc_delta is not None and ref_en_a is not None and ref_en_b is not None:
                ref_delta = round(abs(ref_en_a - ref_en_b), 4)
                err = abs(calc_delta - ref_delta)
                v["checks"].append({
                    "property": "delta_EN",
                    "calculated": calc_delta,
                    "reference": ref_delta,
                    "error": round(err, 4),
                    "pass": err < 0.05,
                })

            # ── Check % ionic character ───────────────────────────────────
            calc_ionic = bond.get("percent_ionic_character")
            if calc_ionic is not None and ref_en_a is not None and ref_en_b is not None:
                ref_delta = abs(ref_en_a - ref_en_b)
                ref_ionic = round((1 - math.exp(-0.25 * ref_delta ** 2)) * 100, 2)
                err = abs(calc_ionic - ref_ionic)
                v["checks"].append({
                    "property": "percent_ionic",
                    "calculated": calc_ionic,
                    "reference": ref_ionic,
                    "error": round(err, 2),
                    "pass": err < 1.0,
                })

            # ── Check classification ──────────────────────────────────────
            calc_class = bond.get("classification", "")
            ref_class = REFERENCE_CLASSIFICATION.get(bond_key)
            if ref_class is not None:
                match = calc_class == ref_class
                if match:
                    classification_matches += 1
                v["checks"].append({
                    "property": "classification",
                    "calculated": calc_class,
                    "reference": ref_class,
                    "pass": match,
                })

            # ── Check bond length (note: expected to diverge) ─────────────
            calc_length = bond.get("estimated_bond_length_pm")
            ref_length = REFERENCE_BOND_LENGTH.get(bond_key)
            if calc_length is not None and ref_length is not None:
                err = abs(calc_length - ref_length)
                pct_err = (err / ref_length) * 100
                v["checks"].append({
                    "property": "bond_length_pm",
                    "calculated": calc_length,
                    "reference": ref_length,
                    "error_pm": round(err, 1),
                    "error_pct": round(pct_err, 1),
                    "note": "uses atomic/vdW radii sum, not covalent radii",
                })

            validations.append(v)

    # ── Overall precision summary ─────────────────────────────────────────
    bonds_with_ref_class = sum(
        1 for v in validations
        for c in v["checks"]
        if c["property"] == "classification"
    )

    precision_summary = {
        "total_bonds_checked": total_bonds,
        "classification_accuracy": (
            f"{classification_matches}/{bonds_with_ref_class}"
            if bonds_with_ref_class > 0 else "N/A"
        ),
        "classification_pct": (
            round(classification_matches / bonds_with_ref_class * 100, 1)
            if bonds_with_ref_class > 0 else None
        ),
        "mean_EN_error": (
            round(sum(en_errors) / len(en_errors), 4)
            if en_errors else None
        ),
        "max_EN_error": (
            round(max(en_errors), 4)
            if en_errors else None
        ),
        "note": (
            "Bond length estimates use atomic/van der Waals radii sums "
            "and will significantly overestimate actual covalent or ionic "
            "bond lengths. This is a known model limitation."
        ),
    }

    return validations, precision_summary


# ── Collect molecule result files ─────────────────────────────────────────────
all_json = sorted(glob.glob(os.path.join(output_dir, "*.json")))

molecule_files = []
timing_files = []

for path in all_json:
    basename = os.path.basename(path)
    if basename.startswith("timing_"):
        timing_files.append(path)
    elif basename == "results.json":
        pass
    else:
        molecule_files.append(path)

if not molecule_files:
    print("aggregate: no molecule result files found in", output_dir)
    sys.exit(1)

print(f"aggregate: found {len(molecule_files)} molecule files, "
      f"{len(timing_files)} timing files", flush=True)

# ── Load and merge ────────────────────────────────────────────────────────────
molecules = []
for path in molecule_files:
    with open(path) as f:
        molecules.append(json.load(f))

timing = []
for path in timing_files:
    with open(path) as f:
        timing.append(json.load(f))

molecules.sort(key=lambda m: m.get("bondcalc_id", "00"))
timing.sort(key=lambda t: t.get("id", "00"))

# ── Compute timing summary ───────────────────────────────────────────────────
timing_summary = {}
if timing:
    starts = [t["start_epoch"] for t in timing]
    ends = [t["end_epoch"] for t in timing]
    latencies = [t.get("startup_latency_seconds") for t in timing]
    latencies = [l for l in latencies if l is not None]

    timing_summary = {
        "total_containers": len(timing),
        "wall_clock_seconds": round(max(ends) - min(starts), 2),
    }

    if latencies:
        fastest_startup = min(timing, key=lambda t: t.get("startup_latency_seconds") or 999)
        slowest_startup = max(timing, key=lambda t: t.get("startup_latency_seconds") or 0)
        timing_summary["startup_latency"] = {
            "min_seconds": round(min(latencies), 3),
            "max_seconds": round(max(latencies), 3),
            "mean_seconds": round(sum(latencies) / len(latencies), 3),
            "fastest": {
                "id": fastest_startup["id"],
                "molecule": fastest_startup["molecule"],
                "latency": fastest_startup.get("startup_latency_seconds"),
            },
            "slowest": {
                "id": slowest_startup["id"],
                "molecule": slowest_startup["molecule"],
                "latency": slowest_startup.get("startup_latency_seconds"),
            },
        }

# ── Validate bond calculations ───────────────────────────────────────────────
validations, precision_summary = validate_bonds(molecules)

# ── Print precision report to console ─────────────────────────────────────────
print("", flush=True)
print("=" * 70, flush=True)
print("  STARTUP LATENCY", flush=True)
print("=" * 70, flush=True)
if timing_summary.get("startup_latency"):
    sl = timing_summary["startup_latency"]
    print(f"  Containers:  {timing_summary['total_containers']}", flush=True)
    print(f"  Min latency: {sl['min_seconds']}s "
          f"(bondcalc {sl['fastest']['id']}, {sl['fastest']['molecule']})", flush=True)
    print(f"  Max latency: {sl['max_seconds']}s "
          f"(bondcalc {sl['slowest']['id']}, {sl['slowest']['molecule']})", flush=True)
    print(f"  Mean latency: {sl['mean_seconds']}s", flush=True)
    print(f"  Wall clock:  {timing_summary['wall_clock_seconds']}s", flush=True)
    print("", flush=True)
    print("  Per-container startup:", flush=True)
    for t in timing:
        lat = t.get("startup_latency_seconds")
        lat_str = f"{lat:.3f}s" if lat is not None else "N/A"
        print(f"    bondcalc {t['id']}  {t['molecule']:>8}  startup {lat_str}", flush=True)
else:
    print("  No startup latency data (LAUNCH_EPOCH not set).", flush=True)
print("", flush=True)

print("=" * 70, flush=True)
print("  PRECISION REPORT", flush=True)
print("=" * 70, flush=True)
print(f"  Bonds checked:            {precision_summary['total_bonds_checked']}", flush=True)
print(f"  Classification accuracy:  {precision_summary['classification_accuracy']}"
      f" ({precision_summary['classification_pct']}%)", flush=True)
print(f"  Mean EN error:            {precision_summary['mean_EN_error']}", flush=True)
print(f"  Max EN error:             {precision_summary['max_EN_error']}", flush=True)
print("", flush=True)

# Print per-bond details
for v in validations:
    bond_label = f"{v['molecule']} {v['bond']}"
    fails = [c for c in v["checks"] if not c.get("pass", True)]
    if fails:
        print(f"  {bond_label}:", flush=True)
        for f in fails:
            if f["property"] == "bond_length_pm":
                print(f"    {f['property']}: calc={f['calculated']} ref={f['reference']} "
                      f"err={f['error_pct']}%", flush=True)
            else:
                print(f"    {f['property']}: calc={f['calculated']} ref={f['reference']}", flush=True)

    # Always show bond length comparison (it's informational, not pass/fail)
    for c in v["checks"]:
        if c["property"] == "bond_length_pm":
            print(f"  {bond_label} length: calc={c['calculated']} pm, "
                  f"actual={c['reference']} pm, "
                  f"overestimate={c['error_pct']}%", flush=True)

print("", flush=True)
print(f"  NOTE: {precision_summary['note']}", flush=True)
print("=" * 70, flush=True)
print("", flush=True)

# ── Write aggregated results ─────────────────────────────────────────────────
results = {
    "summary": timing_summary,
    "precision": precision_summary,
    "validation": validations,
    "timing": timing,
    "molecules": molecules,
}

results_path = os.path.join(output_dir, "results.json")
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"aggregate: wrote {results_path}", flush=True)

# ── Clean up individual files ─────────────────────────────────────────────────
removed = 0
for path in molecule_files + timing_files:
    try:
        os.remove(path)
        removed += 1
    except OSError as e:
        print(f"aggregate: WARNING: could not remove {path}: {e}", flush=True)

print(f"aggregate: cleaned up {removed} individual files", flush=True)
print("aggregate: done", flush=True)
