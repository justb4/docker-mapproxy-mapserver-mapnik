#!/bin/bash
set -x
TARGET_FILE=$(find /usr -type f -name mapnik.py)
# echo "DO: patch ${TARGET_FILE} mapnik.patch"
# patch  ${TARGET_FILE} mapnik.patch

# echo "DO: cp mapnik.py ${TARGET_FILE}"
cp mapnik.py ${TARGET_FILE}
