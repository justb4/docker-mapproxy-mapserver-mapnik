#!/bin/bash
set -x

PATCH_FILE="geopackage.py"
TARGET_FILE=$(find /usr -type f -name ${PATCH_FILE} | grep mapproxy/cache)

# echo "DO: cp ${PATCH_FILE} ${TARGET_FILE}"
cp ${PATCH_FILE} ${TARGET_FILE}

# For later
# echo "DO: patch ${TARGET_FILE} mapnik.patch"
# patch  ${TARGET_FILE} mapnik.patch
