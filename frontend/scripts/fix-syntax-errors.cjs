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

// Find files with syntax errors
const syntaxErrors = {};
errors.split('\n').forEach(line => {
  const match = line.match(/(.+\.tsx?)\((\d+),(\d+)\): error TS1109: Expression expected\./);
  if (match) {
    const [, file, lineNum] = match;
    if (!syntaxErrors[file]) {
      syntaxErrors[file] = new Set();
    }
    syntaxErrors[file].add(parseInt(lineNum));
  }
});

// Fix onChange handlers that are missing the event parameter
Object.entries(syntaxErrors).forEach(([filePath, lineNumbers]) => {
  const fullPath = path.join(process.cwd(), filePath);
  if (!fs.existsSync(fullPath)) return;
  
  let content = fs.readFileSync(fullPath, 'utf8');
  const lines = content.split('\n');
  
  // Convert Set to Array and sort in reverse order
  const sortedLines = Array.from(lineNumbers).sort((a, b) => b - a);
  
  sortedLines.forEach(lineNum => {
    const lineIndex = lineNum - 1;
    if (lineIndex >= 0 && lineIndex < lines.length) {
      // Fix patterns like "onChange={() => updateCustomModule(module.id, { enabled: .target.checked })}"
      lines[lineIndex] = lines[lineIndex].replace(
        /onChange=\{(\(\)) => (.+?)\{ (.+?): (\.target\..+?) \}/g,
        'onChange={(e) => $2{ $3: e$4 }'
      );
      
      // Fix patterns where just the parameter is missing
      lines[lineIndex] = lines[lineIndex].replace(
        /onChange=\{(\(\)) => (.+?)(\.target\..+?)\}/g,
        'onChange={(e) => $2e$3}'
      );
      
      // Fix patterns in the middle of expressions
      lines[lineIndex] = lines[lineIndex].replace(
        /(\w+): (\.target\..+?)([,}])/g,
        '$1: e$2$3'
      );
    }
  });
  
  fs.writeFileSync(fullPath, lines.join('\n'));
  console.log(`Fixed ${lineNumbers.size} syntax errors in ${filePath}`);
});

// Also fix the import alias issues
const aliasErrors = errors.split('\n').filter(line => line.includes('error TS1005'));
if (aliasErrors.length > 0) {
  aliasErrors.forEach(error => {
    const match = error.match(/(.+\.tsx?)\((\d+),(\d+)\): error TS1005:/);
    if (match) {
      const [, file] = match;
      const fullPath = path.join(process.cwd(), file);
      if (fs.existsSync(fullPath)) {
        let content = fs.readFileSync(fullPath, 'utf8');
        
        // Fix import alias issues
        content = content.replace(/Tooltip\s+as\s+RechartsTooltip/g, 'Tooltip as RechartsTooltip');
        content = content.replace(/\{\s*([^,}]+)\s+as\s+([^,}]+)\s*\}/g, '{ $1 as $2 }');
        
        fs.writeFileSync(fullPath, content);
      }
    }
  });
}

console.log('Syntax error fixes complete!');