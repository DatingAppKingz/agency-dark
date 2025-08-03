#!/bin/bash

# Fix test imports in integration tests
echo "Fixing test import paths..."

# Replace old import paths with new ones
find tests -name "*.ts*" -type f -exec sed -i '' \
  -e 's|@/__tests__/utils/test-utils|@/tests/utils/test-utils|g' \
  -e 's|@/__tests__/mocks/api-mocks|@/tests/utils/test-server|g' \
  -e 's|../../__mocks__/services|@/tests/utils/mock-factories|g' \
  -e 's|../../__mocks__/pages|@/pages|g' \
  {} +

echo "Import paths fixed!"