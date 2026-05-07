"""
bondcalc: Molecular bond analysis using periodic table data from an API.
Runs inside a Docker container. Receives BONDCALC_ID and MOLECULE as
environment variables, queries a Function App API for element properties,
computes bond characteristics, and writes results to /output.
"""

import os
import sys
import json
import time
import math
import random
import urllib.request
import urllib.error

# ── Config from environment ───────────────────────────────────────────────────
BONDCALC_ID = os.environ.get("BONDCALC_ID", "00")
MOLECULE = os.environ.get("MOLECULE", "H2O")
API_BASE = os.environ.get("API_BASE", 
    "https://student-atomic-portal-identifierstring.westus2-01.azurewebsites.net/api")
LAUNCH_EPOCH = os.environ.get("LAUNCH_EPOCH")  # set by launcher.sh
OUTPUT_DIR = "/output"
TARGET_DURATION = 30  # seconds
JITTER = 10           # +/- seconds

print(f"bondcalc {BONDCALC_ID} starting on {MOLECULE}", flush=True)
start_time = time.time()

# Compute startup latency (time from docker run to Python execution)
startup_latency = None
if LAUNCH_EPOCH:
    try:
        startup_latency = round(start_time - float(LAUNCH_EPOCH), 3)
        print(f"bondcalc {BONDCALC_ID}   startup latency: {startup_latency}s", flush=True)
    except ValueError:
        pass

# ── Load molecule definition ──────────────────────────────────────────────────
with open("molecules.json") as f:
    all_molecules = json.load(f)

if MOLECULE not in all_molecules:
    print(f"bondcalc {BONDCALC_ID} ERROR: unknown molecule {MOLECULE}", flush=True)
    sys.exit(1)

bonds = all_molecules[MOLECULE]["bonds"]

# Collect unique elements needed
elements_needed = set()
for a, b in bonds:
    elements_needed.add(a)
    elements_needed.add(b)

# ── Query API for element properties ──────────────────────────────────────────
element_data = {}

for element in elements_needed:
    # Resolve full element name for the API query
    elem_name = all_molecules.get("_symbol_to_name", {}).get(element, element)
    url = f"{API_BASE}/lookup?name={elem_name}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode())
            # API returns an array; take the first entry
            data = raw[0] if isinstance(raw, list) and raw else raw
            element_data[element] = data
            print(f"bondcalc {BONDCALC_ID}   fetched {element} ({elem_name}): "
                  f"mass={data.get('AtomicMass', '?')}, "
                  f"EN={data.get('Electronegativity', '?')}", flush=True)
    except urllib.error.URLError as e:
        print(f"bondcalc {BONDCALC_ID}   WARNING: API call failed for {element}: {e}", flush=True)
        element_data[element] = {}
    except Exception as e:
        print(f"bondcalc {BONDCALC_ID}   WARNING: unexpected error for {element}: {e}", flush=True)
        element_data[element] = {}

# ── Compute bond properties ───────────────────────────────────────────────────
def get_float(d, key, default=None):
    v = d.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

bond_results = []

for atom_a, atom_b in bonds:
    da = element_data.get(atom_a, {})
    db = element_data.get(atom_b, {})

    en_a = get_float(da, "Electronegativity")
    en_b = get_float(db, "Electronegativity")
    mass_a = get_float(da, "AtomicMass")
    mass_b = get_float(db, "AtomicMass")
    radius_a = get_float(da, "AtomicRadius")
    radius_b = get_float(db, "AtomicRadius")

    result = {
        "bond": f"{atom_a}-{atom_b}",
        "element_a": atom_a,
        "element_b": atom_b,
    }

    # Electronegativity difference and ionic character
    if en_a is not None and en_b is not None:
        delta_en = abs(en_a - en_b)
        ionic_pct = (1 - math.exp(-0.25 * delta_en ** 2)) * 100

        if delta_en < 0.5:
            classification = "nonpolar covalent"
        elif delta_en < 1.7:
            classification = "polar covalent"
        else:
            classification = "ionic"

        result["electronegativity_a"] = en_a
        result["electronegativity_b"] = en_b
        result["delta_electronegativity"] = round(delta_en, 4)
        result["percent_ionic_character"] = round(ionic_pct, 2)
        result["classification"] = classification
    else:
        result["delta_electronegativity"] = None
        result["percent_ionic_character"] = None
        result["classification"] = "unknown (missing electronegativity data)"

    # Reduced mass (in atomic mass units)
    if mass_a is not None and mass_b is not None:
        reduced_mass = (mass_a * mass_b) / (mass_a + mass_b)
        result["mass_a_amu"] = round(mass_a, 4)
        result["mass_b_amu"] = round(mass_b, 4)
        result["reduced_mass_amu"] = round(reduced_mass, 4)
    else:
        result["reduced_mass_amu"] = None

    # Estimated bond length from atomic radii (sum of covalent radii)
    if radius_a is not None and radius_b is not None:
        est_bond_length = radius_a + radius_b
        result["radius_a_pm"] = radius_a
        result["radius_b_pm"] = radius_b
        result["estimated_bond_length_pm"] = round(est_bond_length, 1)
    else:
        result["estimated_bond_length_pm"] = None

    bond_results.append(result)
    print(f"bondcalc {BONDCALC_ID}   bond {atom_a}-{atom_b}: "
          f"Δχ={result.get('delta_electronegativity', '?')}, "
          f"ionic={result.get('percent_ionic_character', '?')}%, "
          f"{result.get('classification', '?')}", flush=True)

# ── Sleep to reach target duration ────────────────────────────────────────────
elapsed = time.time() - start_time
target = TARGET_DURATION + random.uniform(-JITTER, JITTER)
remaining = max(0, target - elapsed)
if remaining > 0:
    print(f"bondcalc {BONDCALC_ID}   sleeping {remaining:.1f}s to reach target {target:.1f}s", flush=True)
    time.sleep(remaining)

# ── Write output ──────────────────────────────────────────────────────────────
output = {
    "bondcalc_id": BONDCALC_ID,
    "molecule": MOLECULE,
    "elements_queried": list(elements_needed),
    "bonds": bond_results,
    "total_time_seconds": round(time.time() - start_time, 2),
}

os.makedirs(OUTPUT_DIR, exist_ok=True)
output_path = os.path.join(OUTPUT_DIR, f"{MOLECULE}.json")
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)

# Write timing file for the launcher to collect
timing_path = os.path.join(OUTPUT_DIR, f"timing_{BONDCALC_ID}.json")
with open(timing_path, "w") as f:
    json.dump({
        "id": BONDCALC_ID,
        "molecule": MOLECULE,
        "launch_epoch": float(LAUNCH_EPOCH) if LAUNCH_EPOCH else None,
        "start_epoch": start_time,
        "end_epoch": time.time(),
        "startup_latency_seconds": startup_latency,
        "duration": round(time.time() - start_time, 2),
    }, f)

print(f"bondcalc {BONDCALC_ID} task completed", flush=True)
