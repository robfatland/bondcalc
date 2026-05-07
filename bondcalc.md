# bondcalc: Dockerized Molecular Bond Analysis

## Purpose

A classroom demonstration that ties together three Azure labs: a Linux VM,
a Cosmos DB periodic table database, and a Function App API. Twenty-five
Docker containers run in parallel on the VM, each analyzing a different
molecule by querying element properties from the API and computing bond
characteristics. After all containers finish, results are aggregated into
a single JSON file with a precision report comparing calculations against
literature values.


## Architecture

```
Azure VM (or local Docker host)
  └── launcher.sh
        ├── bondcalc container 01  ──→  Function App API  ──→  Cosmos DB
        ├── bondcalc container 02  ──→  Function App API  ──→  Cosmos DB
        ├── ...
        └── bondcalc container 25  ──→  Function App API  ──→  Cosmos DB
                                              ↓
                                     /output/<MOLECULE>.json  (per container)
                                     /output/timing_<ID>.json (per container)
                                              ↓
                                     aggregate.py
                                              ↓
                                     /output/results.json     (final)
```


## File Reference

### bondcalc.py (container entrypoint)

The main analysis script. Runs inside each Docker container. Uses only
Python standard library (no pip dependencies).

Behavior:
1. Reads `BONDCALC_ID`, `MOLECULE`, and `API_BASE` from environment variables.
2. Loads `molecules.json` to get the bond pairs for its assigned molecule.
3. Resolves element symbols to full names using the `_symbol_to_name` map
   in `molecules.json` (e.g. `"Fe"` → `"Iron"`).
4. Queries the Function App API at `GET /api/lookup?name=<ElementName>` for
   each unique element. The API returns a JSON array; the script takes the
   first entry.
5. For each unique bond pair, computes:
   - Electronegativity difference (Δχ)
   - Percent ionic character via the Pauling formula: `1 - exp(-0.25 × Δχ²)`
   - Bond polarity classification (nonpolar covalent / polar covalent / ionic)
   - Reduced mass of the atom pair (amu)
   - Estimated bond length from atomic radii (sum of radii from the DB)
6. Sleeps to reach a target duration of 30 ± 10 seconds (uniform random jitter)
   so the demo has visible container lifecycle spread.
7. Writes two files to `/output`:
   - `<MOLECULE>.json` — element data, computed bond properties, timing
   - `timing_<ID>.json` — start/end epoch and duration for aggregation

### aggregate.py (post-run aggregation and validation)

Runs after all 25 containers finish. Called by `launcher.sh` with the output
directory as an argument.

Behavior:
1. Reads all `<MOLECULE>.json` and `timing_<ID>.json` files from the output
   directory.
2. Computes a timing summary: wall clock time, start spread, mean duration,
   fastest and slowest containers.
3. Validates every computed bond against built-in reference data:
   - Pauling electronegativity values for all 26 elements used
   - Δχ and percent ionic character recalculated from reference EN values
   - Bond classification checked against reference thresholds
   - Estimated bond length compared to experimental bond lengths (from NIST
     CCCBDB, CRC Handbook, and standard general chemistry references)
4. Prints a precision report to the console showing classification accuracy,
   EN error statistics, and per-bond length comparisons.
5. Writes `results.json` containing: timing summary, precision summary,
   per-bond validation details, raw timing data, and all molecule results.
6. Deletes the individual per-molecule and timing JSON files.

### molecules.json (molecule definitions and element name map)

Contains two sections:
- `_symbol_to_name`: Maps element symbols to full names for the API query
  (26 elements covering all molecules in the set).
- One entry per molecule (25 total), each listing unique bond pairs as
  `[element_a_symbol, element_b_symbol]`. Degenerate bonds (same element
  pair appearing multiple times in a molecule) are listed once.

### launcher.sh (orchestrator)

Bash script that runs on the VM (or local Docker host).

Behavior:
1. Takes the API base URL as a required argument.
2. Launches 25 Docker containers in parallel, each with a unique
   `BONDCALC_ID` (01–25) and `MOLECULE` assignment.
3. Mounts `~/bondcalc_output` as `/output` in each container.
4. Polls `docker ps` every 5 seconds until all containers exit.
5. Lists the output files, then calls `python3 aggregate.py` to merge
   results and produce the precision report.

### Dockerfile

Minimal image based on `python:3.11-slim`. Copies `bondcalc.py`,
`molecules.json`, and `aggregate.py` into `/app`. Entrypoint is
`python bondcalc.py`.

### test_h2o.py (single-molecule validation)

Standalone test that fetches Oxygen and Hydrogen from the live API, runs
the same math as `bondcalc.py`, and compares every computed property against
known literature values for the O-H bond. Prints a side-by-side table with
pass/fail indicators.

### test_aggregate.py (multi-molecule pipeline test)

Generates bondcalc output for 5 molecules (H2O, NaCl, CO2, CH4, CaF2) by
calling the live API directly (no Docker, no sleep), writes the result and
timing files to a `test_output/` directory, then runs `aggregate.py` against
them to verify the full aggregation and precision reporting pipeline.


## API

The Function App API is deployed at:
```
https://student-atomic-portal-identifierstring.westus2-01.azurewebsites.net/api
```

Query: `GET /api/lookup?name=<ElementName>` (e.g. `?name=Carbon`)

Returns a JSON array with one object containing element properties:
```json
[{
  "AtomicNumber": 6,
  "Element": "Carbon",
  "Symbol": "C",
  "AtomicMass": 12.011,
  "Electronegativity": 2.55,
  "AtomicRadius": 170,
  "Type": "Non-Metal",
  ...
}]
```

Key fields used by bondcalc: `AtomicMass`, `Electronegativity`, `AtomicRadius`.


## Molecules (25 total)

| #  | Molecule | Unique bonds     |
|----|----------|------------------|
| 01 | H₂O     | O-H              |
| 02 | NaCl    | Na-Cl            |
| 03 | CO₂     | C-O              |
| 04 | NH₃     | N-H              |
| 05 | CaF₂    | Ca-F             |
| 06 | Fe₂O₃   | Fe-O             |
| 07 | CH₄     | C-H              |
| 08 | MgSO₄   | Mg-O, S-O        |
| 09 | KMnO₄   | K-O, Mn-O        |
| 10 | TiO₂    | Ti-O             |
| 11 | SiO₂    | Si-O             |
| 12 | Al₂O₃   | Al-O             |
| 13 | HCl     | H-Cl             |
| 14 | HF      | H-F              |
| 15 | LiF     | Li-F             |
| 16 | BeCl₂   | Be-Cl            |
| 17 | BF₃     | B-F              |
| 18 | PCl₃    | P-Cl             |
| 19 | SO₂     | S-O              |
| 20 | NO₂     | N-O              |
| 21 | CsCl    | Cs-Cl            |
| 22 | BaO     | Ba-O             |
| 23 | ZnS     | Zn-S             |
| 24 | CuO     | Cu-O             |
| 25 | AgCl    | Ag-Cl            |


## Testing Performed

### 1. API integration (test_h2o.py)

Verified that the live Function App API returns correct element data by
fetching Oxygen and Hydrogen and comparing every field against CRC Handbook
reference values. All properties matched exactly: electronegativity (O=3.44,
H=2.20), atomic mass (O=15.999, H=1.008), and atomic radius (O=152 pm,
H=120 pm).

### 2. Calculation accuracy (test_h2o.py)

Ran the full bondcalc math for the O-H bond and compared against known values:
- Δχ = 1.24 (exact match)
- Percent ionic character = 31.91% (literature ~32%, within rounding)
- Classification = polar covalent (correct)
- Reduced mass = 0.9483 amu (reference 0.9472, within 0.001)

### 3. End-to-end script test (bondcalc.py, no Docker)

Ran `bondcalc.py` directly with environment variables set for H2O, pointing
at the live API. Confirmed the script:
- Resolved "H" → "Hydrogen" and "O" → "Oxygen" via the symbol-to-name map
- Successfully queried the API and parsed the array response
- Computed correct bond properties
- Wrote output JSON to the expected path
- Completed the sleep/timing cycle

### 4. Aggregation and precision pipeline (test_aggregate.py)

Generated bondcalc output for 5 molecules (H2O, NaCl, CO2, CH4, CaF2) using
the live API, then ran `aggregate.py` against the output. Verified:
- All 5 molecule files and 5 timing files were found and processed
- Classification accuracy: 5/5 (100%)
- Mean electronegativity error: 0.0 (API values match Pauling reference exactly)
- Bond length overestimates reported correctly (67–184%, expected due to
  van der Waals vs covalent radius difference)
- Individual files cleaned up, single `results.json` produced

### 5. Known limitation: bond length estimation

The estimated bond length (sum of atomic radii from the database) uses
van der Waals or general atomic radii, not covalent radii. This produces
significant overestimates compared to experimental bond lengths:
- H₂O O-H: 272 pm estimated vs 95.8 pm actual (184% over)
- NaCl: 402 pm estimated vs 236 pm actual (70% over)
- CH₄ C-H: 290 pm estimated vs 109 pm actual (167% over)

This is documented in the precision report and noted in the aggregate output.
It is a deliberate simplification for the classroom context, not a bug.


## Timing

Each container targets a 30-second execution time with ±10 seconds of
uniform random jitter:
- Fastest container: ~20 seconds
- Slowest container: ~40 seconds
- All 25 run concurrently


## Local 25-Container Test (pulling from DockerHub)

These steps run the full 25-container demo on a local machine with Docker
installed. Replace `<dockerhub_user>` with the actual DockerHub username
and `<API_BASE>` with the Function App URL.

### Prerequisites

- Docker installed and running
- Network access to the Function App API
- Python 3 installed on the host (for `aggregate.py`)
- The image pushed to DockerHub (see "Push to DockerHub" below)

### Push to DockerHub (one-time setup)

```bash
# Build the image
cd bondcalc
docker build -t bondcalc:v1 .

# Tag for DockerHub
docker tag bondcalc:v1 <dockerhub_user>/bondcalc:v1

# Log in and push
docker login
docker push <dockerhub_user>/bondcalc:v1
```

### Run the full test

```bash
# 1. Update launcher.sh to use the DockerHub image
#    Edit the IMAGE variable at the top of launcher.sh:
#      IMAGE="<dockerhub_user>/bondcalc:v1"

# 2. Create the output directory
mkdir -p ~/bondcalc_output

# 3. Launch all 25 containers
bash launcher.sh <API_BASE>

#    Example:
#    bash launcher.sh https://student-atomic-portal-identifierstring.westus2-01.azurewebsites.net/api

# 4. Wait for completion
#    The script polls every 5 seconds and prints progress.
#    Expected wall clock time: ~40 seconds (limited by the slowest container).

# 5. Review results
#    The script automatically runs aggregate.py when all containers finish.
#    Final output: ~/bondcalc_output/results.json
#
#    The precision report prints to the console. To review it again:
cat ~/bondcalc_output/results.json | python3 -m json.tool
```

### Verify

After the run completes, check:

1. **Console output** — The precision report should show 100% classification
   accuracy and 0.0 mean EN error (assuming the Cosmos DB has standard
   Pauling electronegativity values).

2. **results.json** — Should contain:
   - `summary`: timing stats for all 25 containers
   - `precision`: classification accuracy, EN error stats, bond length note
   - `validation`: per-bond checks with calculated vs reference values
   - `molecules`: full bond analysis results for all 25 molecules

3. **Cleanup** — The individual per-molecule and timing JSON files should
   be deleted. Only `results.json` should remain in the output directory.

### Troubleshooting

- **"unknown molecule" error**: The `MOLECULE` env var doesn't match a key
  in `molecules.json`. Check spelling and case.
- **API timeout/failure**: Verify the Function App is running and accessible
  from the Docker host. Test with:
  `curl "<API_BASE>/lookup?name=Carbon"`
- **Missing results**: If fewer than 25 molecule files appear, check
  `docker logs bondcalc_<ID>` for the failing container.
- **aggregate.py not found**: Make sure `aggregate.py` is in the current
  directory when `launcher.sh` runs, or copy it to the output directory.


### Inspecting Stopped Containers

Containers persist after exiting (no `--rm` flag) so their logs remain
available for inspection. A stopped container (Docker status: `Exited`)
retains its filesystem, metadata, and stdout/stderr history on disk until
explicitly removed.

View the execution log for any container:
```bash
docker logs bondcalc_01
docker logs bondcalc_17
```

Copy a file out of a stopped container's filesystem:
```bash
docker cp bondcalc_01:/app/molecules.json ./molecules_copy.json
```

Clean up all bondcalc containers when done:
```bash
docker rm $(docker ps -a --filter "name=bondcalc_" -q)
```

Note: Using `docker logs` and `docker cp` is standard practice for
debugging and post-run inspection. For retrieving computation results at
scale, the preferred pattern is what bondcalc already does: write output
to a mounted volume so results are available on the host filesystem
independent of container lifecycle.
