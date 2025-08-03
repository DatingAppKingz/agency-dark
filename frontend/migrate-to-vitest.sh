#!/bin/bash

echo "Migrating tests from Jest to Vitest..."

# Find all test files and replace jest with vi
find tests -name "*.test.ts" -o -name "*.test.tsx" | while read file; do
  echo "Updating $file"
  
  # Add vitest import if not present
  if ! grep -q "import { vi" "$file"; then
    # Check if file already has imports from vitest
    if grep -q "from 'vitest'" "$file"; then
      # Update existing import
      sed -i '' "s/from 'vitest'/from 'vitest'/g" "$file"
    else
      # Add import at the beginning after React import
      sed -i '' "1a\\
import { vi } from 'vitest';" "$file"
    fi
  fi
  
  # Replace jest. with vi.
  sed -i '' 's/jest\./vi\./g' "$file"
  
  # Replace specific Jest matchers that might need adjustment
  sed -i '' 's/expect\.arrayContaining/expect\.arrayContaining/g' "$file"
  sed -i '' 's/expect\.objectContaining/expect\.objectContaining/g' "$file"
done

echo "Migration complete!"