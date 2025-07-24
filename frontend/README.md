# AgencyDark Frontend

Single Page Application (SPA) built with React, TypeScript, and Material-UI.

## Tech Stack

- **Build Tool**: Vite
- **Framework**: React 18
- **Language**: TypeScript
- **UI Library**: Material-UI v5
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)
- **Routing**: React Router v6
- **Forms**: React Hook Form + Zod
- **Real-time**: Socket.IO Client
- **Charts**: Recharts

## Getting Started

### Prerequisites

- Node.js 18+
- Backend API running on http://localhost:8000

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

The app will be available at http://localhost:3000

### Build

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
src/
├── components/     # Reusable components
├── hooks/         # Custom React hooks
├── layouts/       # Layout components
├── pages/         # Page components
├── router/        # Route definitions
├── services/      # API services
├── store/         # Zustand stores
├── theme/         # Material-UI theme
├── types/         # TypeScript types
└── utils/         # Utility functions
```

## Features Implemented

- ✅ Authentication (Login/Register/Forgot Password)
- ✅ JWT token management with refresh
- ✅ Protected routes with role-based access
- ✅ Responsive layout with sidebar navigation
- ✅ Dark/Light theme support (ready)
- ✅ Error handling and toast notifications
- ✅ Code splitting with lazy loading

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=http://localhost:8000
VITE_APP_NAME=AgencyDark
```

## Default Test Credentials

- Email: `owner@testagencypremium.com`
- Password: `Test123!`

Other test users:
- `admin@testagencypremium.com` - Agency Admin
- `model1@testagencypremium.com` - Model
- `chatter1@testagencypremium.com` - Chatter
- `super@agencydark.com` - Super Admin

All use password: `Test123!`