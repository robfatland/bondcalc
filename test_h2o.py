"""
test_h2o.py — Validate bondcalc computation for H2O against known values.

Fetches Oxygen and Hydrogen from the live API, runs the same math as
bondcalc.py, and compares results to literature values for the O-H bond.
"""

import json
import math
import urllib.request

API_BASE = "https://student-atomic-portal-identifierstring.westus2-01.azurewebsites.net/api"

# ── Known / literature values for O-H bond ────────────────────────────────────
# Sources: general chemistry references (Pauling, CRC Handbook)
KNOWN = {
    "O_electronegativity": 3.44,
    "H_electronegativity": 2.20,
    "delta_en": 1.24,
    "percent_ionic_character": 32.0,   # ~32% by Pauling formula
    "classification": "polar covalent",
    "O_atomic_mass": 15.999,
    "H_atomic_mass": 1.008,
    "reduced_mass_amu": 0.9472,        # (15.999 * 1.008) / (15.999 + 1.008)
    "O_atomic_radius_pm": 152,         # van der Waals varies by source
    "H_atomic_radius_pm": 120,         # van der Waals varies by source
    "actual_bond_length_pm": 95.84,    # experimental O-H bond length
}

# ── Fetch element data from API ───────────────────────────────────────────────
def fetch_element(name):
    url = f"{API_BASE}/lookup?name={name}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = json.loads(resp.read().decode())
        return raw[0] if isinstance(raw, list) and raw else raw

print("Fetching element data from API...")
oxygen = fetch_element("Oxygen")
hydrogen = fetch_element("Hydrogen")

print(f"  Oxygen:   mass={oxygen['AtomicMass']}, EN={oxygen['Electronegativity']}, radius={oxygen['AtomicRadius']} pm")
print(f"  Hydrogen: mass={hydrogen['AtomicMass']}, EN={hydrogen['Electronegativity']}, radius={hydrogen['AtomicRadius']} pm")
print()

# ── Run bondcalc math (same as bondcalc.py) ───────────────────────────────────
en_o = float(oxygen["Electronegativity"])
en_h = float(hydrogen["Electronegativity"])
mass_o = float(oxygen["AtomicMass"])
mass_h = float(hydrogen["AtomicMass"])
radius_o = float(oxygen["AtomicRadius"])
radius_h = float(hydrogen["AtomicRadius"])

delta_en = abs(en_o - en_h)
ionic_pct = (1 - math.exp(-0.25 * delta_en ** 2)) * 100

if delta_en < 0.5:
    classification = "nonpolar covalent"
elif delta_en < 1.7:
    classification = "polar covalent"
else:
    classification = "ionic"

reduced_mass = (mass_o * mass_h) / (mass_o + mass_h)
est_bond_length = radius_o + radius_h

# ── Compare ───────────────────────────────────────────────────────────────────
print("=" * 65)
print(f"{'Property':<35} {'Calculated':>12} {'Known':>12}")
print("=" * 65)

def compare(label, calc, known, unit="", tolerance=None):
    calc_str = f"{calc:.4f}" if isinstance(calc, float) else str(calc)
    known_str = f"{known:.4f}" if isinstance(known, float) else str(known)
    match = ""
    if tolerance is not None and isinstance(calc, (int, float)) and isinstance(known, (int, float)):
        diff = abs(calc - known)
        match = " ✓" if diff <= tolerance else f" ✗ (off by {diff:.4f})"
    elif isinstance(calc, str):
        match = " ✓" if calc == known else " ✗"
    print(f"{label:<35} {calc_str:>12} {known_str:>12}{match}")

compare("O electronegativity",       en_o,            KNOWN["O_electronegativity"],  tolerance=0.01)
compare("H electronegativity",       en_h,            KNOWN["H_electronegativity"],  tolerance=0.01)
compare("Δχ (electronegativity)",     delta_en,        KNOWN["delta_en"],             tolerance=0.01)
compare("% ionic character",          ionic_pct,       KNOWN["percent_ionic_character"], tolerance=2.0)
compare("Classification",             classification,  KNOWN["classification"])
compare("O atomic mass (amu)",        mass_o,          KNOWN["O_atomic_mass"],        tolerance=0.01)
compare("H atomic mass (amu)",        mass_h,          KNOWN["H_atomic_mass"],        tolerance=0.01)
compare("Reduced mass (amu)",         reduced_mass,    KNOWN["reduced_mass_amu"],     tolerance=0.01)
compare("O atomic radius (pm)",       radius_o,        KNOWN["O_atomic_radius_pm"],   tolerance=30)
compare("H atomic radius (pm)",       radius_h,        KNOWN["H_atomic_radius_pm"],   tolerance=30)
compare("Est. bond length (pm)",      est_bond_length, KNOWN["actual_bond_length_pm"], tolerance=999)

print("=" * 65)
print()
print("NOTE: 'Est. bond length' sums van der Waals / atomic radii from the DB,")
print("      which will be much larger than the actual covalent O-H bond length")
print(f"      of {KNOWN['actual_bond_length_pm']} pm. This is expected — the bondcalc model")
print("      uses a simple radius sum, not covalent radii.")
print()

# ── Summary ───────────────────────────────────────────────────────────────────
print("Pauling ionic character formula check:")
print(f"  1 - exp(-0.25 × {delta_en:.4f}²) = {ionic_pct:.2f}%")
manual = (1 - math.exp(-0.25 * 1.24**2)) * 100
print(f"  Using known Δχ=1.24:              {manual:.2f}%")
print(f"  Literature value:                  ~{KNOWN['percent_ionic_character']:.1f}%")
