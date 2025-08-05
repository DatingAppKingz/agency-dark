import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
// import TestApp from './TestApp'
import './index.css'
import './i18n/config' // Initialize i18n

console.log('main.tsx loading...')

const rootElement = document.getElementById('root')
console.log('Root element:', rootElement)

if (rootElement) {
  console.log('Creating React root...')
  const root = ReactDOM.createRoot(rootElement)
  console.log('Rendering App...')
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
  console.log('Render called')
} else {
  console.error('Root element not found!')
}
