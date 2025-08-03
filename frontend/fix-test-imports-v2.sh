#!/bin/bash

# Fix test imports to use relative paths
echo "Fixing test imports to use relative paths..."

# For unit tests - go up 3 levels
find tests/unit -name "*.ts*" -type f -exec sed -i '' \
  -e 's|@/tests/utils/enhanced-test-utils|../../../utils/enhanced-test-utils|g' \
  -e 's|@/tests/utils/test-server|../../../utils/test-server|g' \
  -e 's|@/tests/utils/test-utils|../../../utils/test-utils|g' \
  -e 's|@/tests/utils/mock-factories|../../../utils/mock-factories|g' \
  {} +

# For integration tests - go up 2 levels  
find tests/integration -name "*.ts*" -type f -exec sed -i '' \
  -e 's|@/tests/utils/enhanced-test-utils|../../utils/enhanced-test-utils|g' \
  -e 's|@/tests/utils/test-server|../../utils/test-server|g' \
  -e 's|@/tests/utils/test-utils|../../utils/test-utils|g' \
  -e 's|@/tests/utils/mock-factories|../../utils/mock-factories|g' \
  {} +

# For e2e tests - go up 2 levels
find tests/e2e -name "*.ts*" -type f -exec sed -i '' \
  -e 's|@/tests/utils/enhanced-test-utils|../../utils/enhanced-test-utils|g' \
  -e 's|@/tests/utils/test-server|../../utils/test-server|g' \
  -e 's|@/tests/utils/test-utils|../../utils/test-utils|g' \
  -e 's|@/tests/utils/mock-factories|../../utils/mock-factories|g' \
  {} +

echo "Import paths fixed!"