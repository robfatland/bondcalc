#!/bin/bash
#
# launcher.sh — Start 25 bondcalc containers in parallel
#
# Usage: bash launcher.sh <API_BASE_URL>
# Example: bash launcher.sh https://myapp.azurewebsites.net/api
#

API_BASE="${1:?Usage: bash launcher.sh <API_BASE_URL>}"
IMAGE="robfatland/bondcalc:v1"
OUTPUT_DIR="${BONDCALC_OUTPUT:-$HOME/bondcalc_output}"

mkdir -p "$OUTPUT_DIR"

# Molecule assignments: ID MOLECULE
ASSIGNMENTS=(
    "01 H2O"
    "02 NaCl"
    "03 CO2"
    "04 NH3"
    "05 CaF2"
    "06 Fe2O3"
    "07 CH4"
    "08 MgSO4"
    "09 KMnO4"
    "10 TiO2"
    "11 SiO2"
    "12 Al2O3"
    "13 HCl"
    "14 HF"
    "15 LiF"
    "16 BeCl2"
    "17 BF3"
    "18 PCl3"
    "19 SO2"
    "20 NO2"
    "21 CsCl"
    "22 BaO"
    "23 ZnS"
    "24 CuO"
    "25 AgCl"
)

echo "=== bondcalc launcher ==="
echo "API:    $API_BASE"
echo "Image:  $IMAGE"
echo "Output: $OUTPUT_DIR"
echo "Starting 25 containers..."
echo ""

for entry in "${ASSIGNMENTS[@]}"; do
    ID=$(echo "$entry" | awk '{print $1}')
    MOL=$(echo "$entry" | awk '{print $2}')

    # Record launch time so the container can measure startup latency
    LAUNCH_EPOCH=$(date +%s.%N)

    docker run -d \
        --name "bondcalc_${ID}" \
        -e BONDCALC_ID="$ID" \
        -e MOLECULE="$MOL" \
        -e API_BASE="$API_BASE" \
        -e LAUNCH_EPOCH="$LAUNCH_EPOCH" \
        -v "$OUTPUT_DIR":/output \
        "$IMAGE"
done

echo ""
echo "All 25 containers launched. Monitoring..."
echo ""

# Give Docker a moment to register all containers
sleep 3

# Wait for all containers to finish
while true; do
    RUNNING=$(docker ps --filter "name=bondcalc_" --format "{{.Names}}" | wc -l)
    if [ "$RUNNING" -eq 0 ]; then
        break
    fi
    echo "  $RUNNING containers still running..."
    sleep 5
done

echo ""
echo "=== All containers finished ==="
echo "Results in $OUTPUT_DIR:"
ls -la "$OUTPUT_DIR"/*.json 2>/dev/null
echo ""
echo "Total result files: $(ls "$OUTPUT_DIR"/*.json 2>/dev/null | wc -l)"

# Aggregate results and clean up individual files
echo ""
echo "=== Aggregating results ==="
# Run aggregate.py from the same directory as this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/aggregate.py" "$OUTPUT_DIR"

echo ""
echo "=== Done ==="
echo "Final output: $OUTPUT_DIR/results.json"
