const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Get all TypeScript errors
let errors = '';
try {
  errors = execSync('npx tsc --noEmit 2>&1', { encoding: 'utf8' }).toString();
} catch (e) {
  errors = e.stdout ? e.stdout.toString() : e.toString();
}

// Parse unused import errors
const unusedImports = {};
errors.split('\n').forEach(line => {
  const match = line.match(/(.+\.tsx?)\((\d+),(\d+)\): error TS6133: '(.+)' is declared but its value is never read\./);
  if (match) {
    const [, file, lineNum, , importName] = match;
    if (!unusedImports[file]) {
      unusedImports[file] = new Set();
    }
    unusedImports[file].add(importName);
  }
});

// Process each file
Object.entries(unusedImports).forEach(([filePath, imports]) => {
  const fullPath = path.join(process.cwd(), filePath);
  let content = fs.readFileSync(fullPath, 'utf8');
  
  imports.forEach(importName => {
    // Remove from import statements
    content = content.replace(
      new RegExp(`\\b${importName}\\b,?\\s*`, 'g'),
      ''
    );
  });
  
  // Clean up empty imports and trailing commas
  content = content.replace(/import\s*{\s*}\s*from\s*['"][^'"]+['"]\s*;?\n/g, '');
  content = content.replace(/,\s*}/g, ' }');
  content = content.replace(/{\s*,/g, '{ ');
  content = content.replace(/,\s*,/g, ',');
  
  fs.writeFileSync(fullPath, content);
  console.log(`Fixed ${imports.size} unused imports in ${filePath}`);
});