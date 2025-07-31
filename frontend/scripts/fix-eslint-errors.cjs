#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Get all TypeScript files with ESLint errors
const eslintOutput = execSync('npm run lint 2>&1 || true', { encoding: 'utf8' });
const lines = eslintOutput.split('\n');

const fileErrors = new Map();

// Parse ESLint output
lines.forEach(line => {
  const match = line.match(/^(\/[^:]+\.tsx?)$/);
  if (match) {
    currentFile = match[1];
    if (!fileErrors.has(currentFile)) {
      fileErrors.set(currentFile, []);
    }
  } else if (currentFile) {
    const errorMatch = line.match(/^\s*(\d+):(\d+)\s+error\s+(.+)\s+(@typescript-eslint\/.+)$/);
    if (errorMatch) {
      fileErrors.get(currentFile).push({
        line: parseInt(errorMatch[1]),
        column: parseInt(errorMatch[2]),
        message: errorMatch[3],
        rule: errorMatch[4]
      });
    }
  }
});

console.log(`Found ${fileErrors.size} files with ESLint errors`);

// Fix common patterns
fileErrors.forEach((errors, filePath) => {
  console.log(`\nProcessing ${filePath}...`);
  let content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n');
  let modified = false;

  // Sort errors by line number in reverse to avoid offset issues
  errors.sort((a, b) => b.line - a.line);

  errors.forEach(error => {
    const lineIndex = error.line - 1;
    const line = lines[lineIndex];

    // Fix unused imports
    if (error.rule === '@typescript-eslint/no-unused-vars' && error.message.includes('is defined but never used')) {
      if (line.includes('import')) {
        console.log(`  - Commenting out unused import on line ${error.line}`);
        lines[lineIndex] = '// ' + line;
        modified = true;
      } else if (line.includes('const') || line.includes('let')) {
        // Check if it's a destructuring assignment that's never used
        const varMatch = line.match(/^\s*(const|let)\s+(\w+)\s*=/);
        if (varMatch) {
          console.log(`  - Prefixing unused variable with underscore on line ${error.line}`);
          lines[lineIndex] = line.replace(varMatch[2], '_' + varMatch[2]);
          modified = true;
        }
      }
    }

    // Fix assigned but never used
    if (error.rule === '@typescript-eslint/no-unused-vars' && error.message.includes('is assigned a value but never used')) {
      const varMatch = line.match(/^\s*(const|let)\s+(\w+)\s*=/);
      if (varMatch && !varMatch[2].startsWith('_')) {
        console.log(`  - Prefixing unused assigned variable with underscore on line ${error.line}`);
        lines[lineIndex] = line.replace(varMatch[2], '_' + varMatch[2]);
        modified = true;
      }
    }

    // Fix function parameters that are unused
    if (error.rule === '@typescript-eslint/no-unused-vars' && line.includes('(') && line.includes(')')) {
      const paramMatch = error.message.match(/'(\w+)' is defined but never used/);
      if (paramMatch) {
        const param = paramMatch[1];
        if (!param.startsWith('_')) {
          console.log(`  - Prefixing unused parameter '${param}' with underscore on line ${error.line}`);
          // More careful replacement to avoid breaking other parts
          const regex = new RegExp(`\\b${param}\\b`, 'g');
          lines[lineIndex] = lines[lineIndex].replace(regex, '_' + param);
          modified = true;
        }
      }
    }
  });

  if (modified) {
    content = lines.join('\n');
    fs.writeFileSync(filePath, content);
    console.log(`  ✓ Fixed ${filePath}`);
  }
});

console.log('\nRunning ESLint again to check remaining errors...');
execSync('npm run lint', { stdio: 'inherit' });