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
  
  // Fix broken import aliases like "Download as Delete as DeleteIcon"
  content = content.replace(/(\w+)\s+as\s+(\w+)\s+as\s+(\w+)\s+as\s+(\w+)/g, '$1 as $4');
  content = content.replace(/(\w+)\s+as\s+(\w+)\s+as\s+(\w+)/g, '$1 as $3');
  
  // Fix imports like "Download as Delete as DeleteIcon,"
  content = content.replace(/(\w+)\s+as\s+(\w+)\s+as\s+(\w+),/g, '$1 as $3,');
  
  // Fix imports like "Schedule as AttachMoney as Lock as LockIcon"
  content = content.replace(/(\w+)\s+as\s+(\w+)\s+as\s+(\w+)\s+as\s+(\w+),/g, '$1 as $4,');
  
  // Fix trailing "as }" or "as ,"
  content = content.replace(/(\w+)\s+as\s+}/g, '$1 }');
  content = content.replace(/(\w+)\s+as\s+,/g, '$1,');
  content = content.replace(/as\s+}/g, '}');
  content = content.replace(/as\s+,/g, ',');
  
  // Fix "CheckCircle as Error as }"
  content = content.replace(/(\w+)\s+as\s+(\w+)\s+as\s+}/g, '$1 as $2 }');
  
  // Fix empty as statements
  content = content.replace(/,\s*as\s+}/g, ' }');
  content = content.replace(/{\s*as\s+/g, '{ ');
  
  // Fix "No newline at end of file" issues
  if (content.length > 0 && !content.endsWith('\n')) {
    content += '\n';
  }
  
  if (content !== originalContent) {
    fs.writeFileSync(fullPath, content);
    console.log(`Fixed imports in ${file}`);
    totalFixed++;
  }
});

console.log(`\nTotal files fixed: ${totalFixed}`);