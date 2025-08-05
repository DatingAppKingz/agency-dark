import React from 'react';

export default function TestApp() {
  console.log('TestApp rendering');
  return (
    <div style={{ padding: '20px' }}>
      <h1>Test App</h1>
      <p>If you see this, React is working!</p>
    </div>
  );
}