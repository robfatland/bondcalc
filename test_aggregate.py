"""
test_aggregate.py — Run bondcalc for a few molecules (no sleep),
then run aggregate.py to test the full pipeline including precision report.
"""

import json
import math
import os
import urllib.request
import shutil

API_BASE = "https://student-atomic-portal-identifierstring.westus2-01.azurewebsites.net/api"
TEST_DIR = "test_output"

# Clean and create test output dir
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)
os.makedirs(TEST_DIR)

# Load molecules
with open("molecules.json") as f:
    all_molecules = json.load(f)

symbol_to_name = all_molecules.get("_symbol_to_name", {})

def fetch_element(symbol):
    name = symbol_to_name.get(symbol, symbol)
    url = f"{API_BASE}/lookup?name={name}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = json.loads(resp.read().decode())
        return raw[0] if isinstance(raw, list) and raw else raw

def get_float(d, key, default=None):
    v = d.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

# Test with a subset: H2O, NaCl, CO2, CH4, CaF2
test_molecules = ["H2O", "NaCl", "CO2", "CH4", "CaF2"]

for idx, mol_name in enumerate(test_molecules, 1):
    mol_id = f"{idx:02d}"
    bonds = all_molecules[mol_name]["bonds"]

    elements_needed = set()
    for a, b in bonds:
        elements_needed.add(a)
        elements_needed.add(b)

    element_data = {}
    for elem in elements_needed:
        element_data[elem] = fetch_element(elem)

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

        result = {"bond": f"{atom_a}-{atom_b}", "element_a": atom_a, "element_b": atom_b}

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

        if mass_a is not None and mass_b is not None:
            result["reduced_mass_amu"] = round((mass_a * mass_b) / (mass_a + mass_b), 4)
            result["mass_a_amu"] = round(mass_a, 4)
            result["mass_b_amu"] = round(mass_b, 4)

        if radius_a is not None and radius_b is not None:
            result["estimated_bond_length_pm"] = round(radius_a + radius_b, 1)
            result["radius_a_pm"] = radius_a
            result["radius_b_pm"] = radius_b

        bond_results.append(result)

    output = {
        "bondcalc_id": mol_id,
        "molecule": mol_name,
        "elements_queried": list(elements_needed),
        "bonds": bond_results,
        "total_time_seconds": 1.0,
    }

    with open(os.path.join(TEST_DIR, f"{mol_name}.json"), "w") as f:
        json.dump(output, f, indent=2)

    # Fake timing file
    import time
    now = time.time()
    with open(os.path.join(TEST_DIR, f"timing_{mol_id}.json"), "w") as f:
        json.dump({"id": mol_id, "molecule": mol_name,
                    "start_epoch": now - 1, "end_epoch": now, "duration": 1.0}, f)

    print(f"  Generated {mol_name} ({mol_id})")

print(f"\nGenerated {len(test_molecules)} molecule files in {TEST_DIR}/")
print("\nRunning aggregate.py...\n")

# Run aggregate
os.system(f'python aggregate.py {TEST_DIR}')
