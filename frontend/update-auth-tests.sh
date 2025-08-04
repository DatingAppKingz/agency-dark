#!/bin/bash

echo "Updating auth tests to work with cookie-based authentication..."

# Update auth service tests
echo "Updating authService tests..."
sed -i '' 's/expect(localStorage\.getItem.*auth_token.*)).toBe/\/\/ Tokens now in httpOnly cookies - not accessible via JS/g' tests/unit/services/authService.test.ts
sed -i '' 's/expect(localStorage\.getItem.*refresh_token.*)).toBe/\/\/ Tokens now in httpOnly cookies - not accessible via JS/g' tests/unit/services/authService.test.ts
sed -i '' 's/expect(localStorage\.getItem.*)).toBeNull/\/\/ Tokens now in httpOnly cookies - not accessible via JS/g' tests/unit/services/authService.test.ts
sed -i '' 's/localStorage\.setItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/services/authService.test.ts
sed -i '' 's/localStorage\.setItem.*refresh_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/services/authService.test.ts
sed -i '' 's/localStorage\.removeItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/services/authService.test.ts
sed -i '' 's/localStorage\.removeItem.*refresh_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/services/authService.test.ts

# Update auth store tests
echo "Updating authStore tests..."
sed -i '' 's/localStorage\.setItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/store/authStore.test.ts
sed -i '' 's/localStorage\.setItem.*refresh_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/store/authStore.test.ts

# Update auth integration tests
echo "Updating auth integration tests..."
sed -i '' 's/expect(localStorage\.getItem.*auth_token.*)).toBe/\/\/ Tokens now in httpOnly cookies/g' tests/integration/auth.integration.test.tsx
sed -i '' 's/expect(localStorage\.getItem.*refresh_token.*)).toBe/\/\/ Tokens now in httpOnly cookies/g' tests/integration/auth.integration.test.tsx
sed -i '' 's/expect(localStorage\.getItem.*)).toBeNull/\/\/ Tokens now in httpOnly cookies/g' tests/integration/auth.integration.test.tsx
sed -i '' 's/localStorage\.setItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/auth.integration.test.tsx
sed -i '' 's/localStorage\.setItem.*refresh_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/auth.integration.test.tsx

# Update auth flow tests
echo "Updating auth flow tests..."
sed -i '' 's/expect(localStorage\.getItem.*auth_token.*)).toBe/\/\/ Tokens now in httpOnly cookies/g' tests/integration/auth-flow.test.tsx
sed -i '' 's/expect(localStorage\.getItem.*refresh_token.*)).toBe/\/\/ Tokens now in httpOnly cookies/g' tests/integration/auth-flow.test.tsx
sed -i '' 's/expect(localStorage\.getItem.*)).toBeNull/\/\/ Tokens now in httpOnly cookies/g' tests/integration/auth-flow.test.tsx
sed -i '' 's/localStorage\.setItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/auth-flow.test.tsx
sed -i '' 's/localStorage\.setItem.*refresh_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/auth-flow.test.tsx

# Update simple auth tests
echo "Updating simple auth tests..."
sed -i '' 's/expect(localStorage\.getItem.*access_token.*)).toBe/\/\/ Tokens now in httpOnly cookies/g' tests/integration/simple-auth.test.tsx
sed -i '' 's/expect(localStorage\.getItem.*)).toBeNull/\/\/ Tokens now in httpOnly cookies/g' tests/integration/simple-auth.test.tsx
sed -i '' 's/localStorage\.setItem.*access_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/simple-auth.test.tsx
sed -i '' 's/localStorage\.setItem.*refresh_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/simple-auth.test.tsx
sed -i '' 's/localStorage\.removeItem.*access_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/simple-auth.test.tsx
sed -i '' 's/localStorage\.removeItem.*refresh_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/simple-auth.test.tsx

# Update useAuth hook tests
echo "Updating useAuth hook tests..."
sed -i '' 's/localStorage\.setItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/hooks/useAuth.test.ts
sed -i '' 's/localStorage\.removeItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/hooks/useAuth.test.ts
sed -i '' 's/localStorage\.removeItem.*refresh_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/unit/hooks/useAuth.test.ts

# Update test utils
echo "Updating test utils..."
sed -i '' 's/localStorage\.setItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/utils/enhanced-test-utils.tsx

# Update media upload test
echo "Updating media upload test..."
sed -i '' 's/localStorage\.setItem.*auth_token.*/\/\/ Tokens now managed via httpOnly cookies/g' tests/integration/media-upload.test.tsx

echo "Done! Auth tests have been updated to work with cookie-based authentication."
echo ""
echo "Note: Tests now focus on verifying auth state rather than checking localStorage"
echo "since tokens are stored in httpOnly cookies and not accessible via JavaScript."