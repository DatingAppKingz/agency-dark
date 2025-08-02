# TypeScript Error Fix Plan

## Current Status
- Started with: 215 TypeScript errors
- Currently at: 180 errors (35 fixed)
- Build still failing

## Error Categories & Solutions

### 1. ✅ Module/Import Errors (FIXED)
- Missing `api/index.ts` export file
- Missing `DateRange` type in reports
- Node.js types not included in tsconfig
- EventEmitter not available in browser
- Missing UI component imports

### 2. 🔄 Type Mismatches (IN PROGRESS)
Common patterns:
- Timeout types (NodeJS.Timeout vs number)
- Date constructor with wrong types
- API client usage (api vs apiClient)
- Component prop types

### 3. ❌ Remaining Issues
- Missing dependencies (notistack → react-hot-toast)
- Incorrect function arguments
- Type assertions needed
- Unused variables and imports
- Missing or incorrect return types

## Fix Strategy

### Phase 1: Critical Build Errors (Current)
1. Fix all import/module errors ✅
2. Fix type mismatches preventing compilation
3. Add missing dependencies
4. Create stub files for missing components

### Phase 2: Type Safety
1. Fix function argument types
2. Add proper type assertions
3. Fix union type issues
4. Handle nullable types correctly

### Phase 3: Code Quality
1. Remove unused imports and variables
2. Fix ESLint errors
3. Add missing return types
4. Improve type definitions

### Phase 4: Testing
1. Ensure build completes successfully
2. Test basic functionality
3. Run linting
4. Check for runtime errors

## Common Fixes Applied

### Import Fixes
```typescript
// Before
import { api } from '../services/api';
// After
import { apiClient } from '../services/api';
```

### Type Fixes
```typescript
// Before
private reconnectTimeout: NodeJS.Timeout | null = null;
// After
private reconnectTimeout: number | null = null;
```

### Conditional Type Guards
```typescript
// Before
value={value ? new Date(value) : null}
// After
value={value && typeof value !== 'boolean' ? new Date(value) : null}
```

## Next Steps
1. Continue fixing type mismatches
2. Address remaining 180 errors systematically
3. Focus on getting a successful build
4. Then improve code quality

## Tools & Commands
- Check errors: `npx tsc --noEmit`
- Count errors: `npx tsc --noEmit 2>&1 | grep "error TS" | wc -l`
- Run build: `npm run build`
- Check specific error types: `npx tsc --noEmit 2>&1 | grep "error TS2345"`