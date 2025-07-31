const fs = require('fs');
const path = require('path');
const glob = require('glob');

// Find all TypeScript/JavaScript files
const files = glob.sync('src/**/*.{ts,tsx,js,jsx}');

let totalFixed = 0;

files.forEach(file => {
  const fullPath = path.join(process.cwd(), file);
  let content = fs.readFileSync(fullPath, 'utf8');
  let originalContent = content;
  
  // Fix broken event handlers where parameter name is missing
  content = content.replace(/\(:\s*React\./g, '(event: React.');
  content = content.replace(/\(\s*:\s*(\w)/g, '(event: $1');
  
  // Fix object properties with missing names
  content = content.replace(/(\s+):\s*\[\]/g, '$1documents: []');
  content = content.replace(/(\s+):\s*string\[\]/g, '$1documents: string[]');
  
  // Fix onChange handlers with missing event parameter
  content = content.replace(/onChange=\{(\(e?\)) => (.*?)\.currentTarget/g, 'onChange={(event) => $2event.currentTarget');
  content = content.replace(/onClick=\{(\(e?\)) => (.*?)\.currentTarget/g, 'onClick={(event) => $2event.currentTarget');
  
  // Fix setters with missing event reference
  content = content.replace(/set(\w+)\(\.currentTarget/g, 'set$1(event.currentTarget');
  content = content.replace(/set(\w+)\(\.target/g, 'set$1(event.target');
  
  // Fix "No newline at end of file" issues
  if (content.includes('No newline at end of file')) {
    content = content.replace(/No newline at end of file/g, '');
  }
  
  // Ensure file ends with newline
  if (content.length > 0 && !content.endsWith('\n')) {
    content += '\n';
  }
  
  if (content !== originalContent) {
    fs.writeFileSync(fullPath, content);
    console.log(`Fixed syntax in ${file}`);
    totalFixed++;
  }
});

console.log(`\nTotal files fixed: ${totalFixed}`);