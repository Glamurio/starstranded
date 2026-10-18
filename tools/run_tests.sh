#!/bin/sh
# usage: tools/run_tests.sh GROUP GROUPS  -- run every GROUPS-th test file starting at GROUP (to split a long run)
cd "$(dirname "$0")/../src" || exit 1
files=$(ls ../tests/test_*.py | awk -v g="$1" -v n="$2" 'NR % n == g')
python -m pytest $files -q -p no:cacheprovider 2>&1 | tail -${3:-15}
