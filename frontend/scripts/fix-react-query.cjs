const fs = require('fs');
const path = require('path');
const glob = require('glob');

// Find all TypeScript files
const files = glob.sync('src/**/*.{ts,tsx}', { 
  cwd: path.join(__dirname, '..'),
  absolute: true 
});

let totalFixed = 0;

files.forEach(file => {
  let content = fs.readFileSync(file, 'utf8');
  let modified = false;
  
  // Replace isLoading with isPending for mutations
  if (content.includes('.isLoading')) {
    const newContent = content.replace(/\.isLoading/g, '.isPending');
    if (newContent !== content) {
      content = newContent;
      modified = true;
      console.log(`Fixed isLoading in ${path.relative(process.cwd(), file)}`);
    }
  }
  
  // Replace isLoading with isPending in destructuring
  if (content.includes('isLoading')) {
    const newContent = content.replace(/\bisLoading\b/g, 'isPending');
    if (newContent !== content) {
      content = newContent;
      modified = true;
      console.log(`Fixed isLoading destructuring in ${path.relative(process.cwd(), file)}`);
    }
  }
  
  if (modified) {
    fs.writeFileSync(file, content);
    totalFixed++;
  }
});

console.log(`\nTotal files fixed: ${totalFixed}`);