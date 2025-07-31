const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Get all TypeScript errors
let errors = '';
try {
  execSync('cd .. && npx tsc --noEmit', { encoding: 'utf8', stdio: 'pipe' });
} catch (e) {
  errors = e.stdout || '';
}

// Categorize errors
const errorCategories = {
  unusedImports: [],
  implicitAny: [],
  missingProperties: [],
  typeErrors: [],
  other: []
};

errors.split('\n').forEach(line => {
  if (line.includes('error TS6133')) {
    errorCategories.unusedImports.push(line);
  } else if (line.includes('error TS7006')) {
    errorCategories.implicitAny.push(line);
  } else if (line.includes('error TS2339')) {
    errorCategories.missingProperties.push(line);
  } else if (line.includes('error TS')) {
    errorCategories.typeErrors.push(line);
  }
});

// Summary
console.log('TypeScript Error Summary:');
console.log('========================');
console.log(`Total errors: ${errors.split('error TS').length - 1}`);
console.log(`Unused imports: ${errorCategories.unusedImports.length}`);
console.log(`Implicit any: ${errorCategories.implicitAny.length}`);
console.log(`Missing properties: ${errorCategories.missingProperties.length}`);
console.log(`Other type errors: ${errorCategories.typeErrors.length}`);

// Write detailed report
const report = {
  summary: {
    total: errors.split('error TS').length - 1,
    unusedImports: errorCategories.unusedImports.length,
    implicitAny: errorCategories.implicitAny.length,
    missingProperties: errorCategories.missingProperties.length,
    otherTypeErrors: errorCategories.typeErrors.length
  },
  errors: errorCategories
};

fs.writeFileSync(
  path.join(__dirname, 'ts-error-report.json'),
  JSON.stringify(report, null, 2)
);

console.log('\nDetailed report written to scripts/ts-error-report.json');