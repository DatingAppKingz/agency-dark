# AgencyDark Frontend SPA Implementation Plan

## Overview
Comprehensive plan to build a Single Page Application (SPA) frontend for AgencyDark platform using React with Vite, TypeScript, Material-UI, and Socket.IO.

## Architecture Overview

### Tech Stack (SPA Approach)
- **Build Tool**: Vite (instead of Next.js)
- **Framework**: React 18+ 
- **Language**: TypeScript
- **Routing**: React Router v6
- **UI Library**: Material-UI v7
- **State Management**: Zustand + React Query
- **Real-time**: Socket.IO Client
- **Charts**: Recharts
- **Forms**: React Hook Form + Zod
- **Authentication**: JWT with interceptors

### SPA Architecture Benefits
- True single page experience
- Faster navigation between views
- Better state persistence
- Offline capabilities
- Smaller hosting requirements
- Better real-time integration

## Project Setup & Migration

### Migration from Next.js to Vite SPA
```bash
# New project structure
frontend/
├── src/
│   ├── main.tsx          # Entry point
│   ├── App.tsx           # Root component
│   ├── router/           # Route definitions
│   ├── layouts/          # Layout components
│   ├── pages/            # Page components
│   ├── components/       # Reusable components
│   ├── services/         # API services
│   ├── hooks/            # Custom hooks
│   ├── store/            # Zustand stores
│   ├── utils/            # Utilities
│   └── types/            # TypeScript types
├── public/               # Static assets
├── index.html            # SPA entry
├── vite.config.ts        # Vite configuration
└── package.json          # Dependencies
```

## Implementation Phases

### Phase 1: SPA Foundation & Core Setup (Days 1-3)

#### 1.1 Vite Project Setup
- [ ] Initialize Vite with React + TypeScript
- [ ] Configure path aliases
- [ ] Set up environment variables (.env)
- [ ] Configure proxy for API calls
- [ ] Set up hot module replacement
- [ ] Configure build optimization

#### 1.2 Routing Architecture
```typescript
// React Router v6 setup
const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    errorElement: <ErrorBoundary />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" />
      },
      {
        path: "auth",
        element: <AuthLayout />,
        children: [
          { path: "login", element: <LoginPage /> },
          { path: "register", element: <RegisterPage /> },
          { path: "forgot-password", element: <ForgotPasswordPage /> }
        ]
      },
      {
        path: "dashboard",
        element: <ProtectedRoute><DashboardLayout /></ProtectedRoute>,
        children: [
          { index: true, element: <DashboardHome /> },
          { path: "users", element: <UsersPage /> },
          { path: "models", element: <ModelsPage /> },
          { path: "chat", element: <ChatPage /> },
          { path: "analytics", element: <AnalyticsPage /> },
          { path: "financial", element: <FinancialPage /> },
          { path: "settings", element: <SettingsPage /> }
        ]
      }
    ]
  }
]);
```

#### 1.3 Authentication System (SPA-Specific)
- [ ] Token storage in memory + secure refresh
- [ ] Axios interceptors for auth headers
- [ ] Auto-refresh token mechanism
- [ ] Protected route component
- [ ] Persistent login state
- [ ] Logout cleanup

```typescript
// Auth Service for SPA
class AuthService {
  private accessToken: string | null = null;
  
  setToken(token: string) {
    this.accessToken = token;
    // Don't store in localStorage for security
  }
  
  getToken() {
    return this.accessToken;
  }
  
  async refreshToken() {
    // Refresh logic with httpOnly cookie
  }
}
```

### Phase 2: State Management & Data Flow (Days 4-5)

#### 2.1 Zustand Store Structure
```typescript
// Global stores for SPA
const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false,
  permissions: [],
  login: async (credentials) => { /* ... */ },
  logout: () => { /* ... */ },
  checkAuth: async () => { /* ... */ }
}));

const useUIStore = create((set) => ({
  sidebarOpen: true,
  theme: 'light',
  notifications: [],
  toggleSidebar: () => { /* ... */ },
  addNotification: (notification) => { /* ... */ }
}));

const useChatStore = create((set) => ({
  conversations: [],
  activeConversation: null,
  messages: {},
  typingUsers: {},
  sendMessage: async (message) => { /* ... */ }
}));
```

#### 2.2 React Query Configuration
```typescript
// Query client for server state
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 3,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

// Custom hooks for data fetching
export const useUsers = () => {
  return useQuery({
    queryKey: ['users'],
    queryFn: userService.getUsers,
  });
};
```

### Phase 3: Core SPA Components (Days 6-8)

#### 3.1 Layout System
- [ ] App shell with persistent header/sidebar
- [ ] Lazy-loaded route components
- [ ] Breadcrumb navigation
- [ ] Loading progress bar
- [ ] Error boundaries
- [ ] Offline indicator

```typescript
// Main App Layout for SPA
const AppLayout = () => {
  const { isAuthenticated } = useAuthStore();
  
  return (
    <Box sx={{ display: 'flex' }}>
      {isAuthenticated && <Sidebar />}
      <Box component="main" sx={{ flexGrow: 1 }}>
        {isAuthenticated && <Header />}
        <Suspense fallback={<PageLoader />}>
          <Outlet />
        </Suspense>
      </Box>
      <NotificationContainer />
      <SocketIOProvider />
    </Box>
  );
};
```

#### 3.2 Progressive Enhancement
- [ ] Service worker for offline support
- [ ] PWA manifest
- [ ] Cache strategies
- [ ] Background sync
- [ ] Push notifications

### Phase 4: Real-time Integration (Days 9-11)

#### 4.1 Socket.IO Manager
```typescript
// Singleton Socket.IO connection for SPA
class SocketManager {
  private socket: Socket | null = null;
  
  connect(token: string) {
    this.socket = io(import.meta.env.VITE_WS_URL, {
      auth: { token },
      transports: ['websocket', 'polling'],
    });
    
    this.setupEventListeners();
  }
  
  private setupEventListeners() {
    this.socket?.on('notification', (data) => {
      useUIStore.getState().addNotification(data);
    });
    
    this.socket?.on('chat:message', (data) => {
      useChatStore.getState().addMessage(data);
    });
  }
}
```

#### 4.2 Optimistic Updates
- [ ] Immediate UI updates
- [ ] Background sync
- [ ] Conflict resolution
- [ ] Retry mechanisms
- [ ] Offline queue

### Phase 5: SPA-Specific Features (Days 12-14)

#### 5.1 Client-Side Routing
- [ ] Route guards with permissions
- [ ] Navigation progress indicator
- [ ] Route transitions
- [ ] Deep linking support
- [ ] Browser history management
- [ ] Query string handling

#### 5.2 Performance Optimization
- [ ] Code splitting by route
- [ ] Dynamic imports
- [ ] Tree shaking
- [ ] Bundle analysis
- [ ] Compression
- [ ] CDN integration

```typescript
// Lazy loading routes
const DashboardPage = lazy(() => import('./pages/Dashboard'));
const UsersPage = lazy(() => import('./pages/Users'));
const ModelsPage = lazy(() => import('./pages/Models'));
```

### Phase 6: Advanced SPA Features (Days 15-17)

#### 6.1 Offline Capabilities
- [ ] IndexedDB for local storage
- [ ] Sync when online
- [ ] Offline mode indicators
- [ ] Queue actions
- [ ] Conflict resolution

#### 6.2 Virtual Scrolling
- [ ] Large list optimization
- [ ] Infinite scroll
- [ ] Virtualized tables
- [ ] Image lazy loading
- [ ] Intersection observer

### Phase 7: Testing & Optimization (Days 18-20)

#### 7.1 SPA Testing Strategy
- [ ] Component testing
- [ ] Integration tests
- [ ] E2E with Playwright
- [ ] Performance testing
- [ ] Bundle size monitoring

#### 7.2 Build Optimization
```typescript
// Vite config for production
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'mui-vendor': ['@mui/material', '@emotion/react'],
          'utils': ['lodash', 'date-fns', 'axios'],
        },
      },
    },
    target: 'esnext',
    minify: 'terser',
  },
});
```

## SPA Deployment Strategy

### Static Hosting Options
1. **Vercel/Netlify**
   - Automatic deployments
   - Edge functions for API
   - Global CDN

2. **AWS S3 + CloudFront**
   - Cost-effective
   - High performance
   - Custom domain

3. **Docker + Nginx**
   - Self-hosted option
   - Full control
   - Kubernetes ready

### Nginx Configuration for SPA
```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  
  # SPA routing - serve index.html for all routes
  location / {
    try_files $uri $uri/ /index.html;
  }
  
  # API proxy
  location /api {
    proxy_pass http://backend:8000;
  }
  
  # WebSocket proxy
  location /socket.io {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}
```

## Key SPA Implementation Patterns

### 1. Authentication Flow
```typescript
// SPA Auth Flow
1. User enters credentials
2. API returns access token + sets httpOnly refresh cookie
3. Store access token in memory only
4. Add token to all API requests
5. Auto-refresh before expiry
6. Handle 401s globally
```

### 2. Data Caching Strategy
```typescript
// Intelligent caching for SPA
- User data: Cache for session
- Analytics: Cache for 5 minutes
- Chat messages: Cache indefinitely
- Financial data: No cache
- Settings: Cache until change
```

### 3. State Persistence
```typescript
// Selective state persistence
const persist = {
  theme: localStorage,
  language: localStorage,
  filters: sessionStorage,
  auth: memory only,
  sensitive: never persist
};
```

## Development Workflow

### Local Development
```bash
# Start development server
npm run dev

# API proxy configured in vite.config.ts
# Hot reload enabled
# Source maps enabled
```

### Build Process
```bash
# Production build
npm run build

# Preview production build
npm run preview

# Bundle analysis
npm run analyze
```

## Performance Metrics

### SPA-Specific Targets
- **Initial Load**: < 2s (with code splitting)
- **Route Change**: < 100ms
- **API Response**: < 200ms
- **Real-time Latency**: < 50ms
- **Bundle Size**: < 200KB initial chunk

## Security Considerations for SPA

1. **Token Management**
   - Never store sensitive tokens in localStorage
   - Use httpOnly cookies for refresh tokens
   - Implement token rotation
   - Short-lived access tokens

2. **API Security**
   - CORS properly configured
   - Rate limiting per user
   - Request signing
   - Input validation

3. **Content Security**
   - CSP headers
   - XSS protection
   - Sanitize user input
   - Secure CDN usage

## Monitoring & Analytics

### SPA Monitoring
- Route navigation tracking
- API call performance
- Error tracking (Sentry)
- User behavior analytics
- Real-time connection status

## Conclusion

The SPA approach offers several advantages for AgencyDark:
- Better user experience with instant navigation
- Superior real-time capabilities
- Easier state management
- Lower hosting costs
- Better offline support

The migration from Next.js to Vite-based SPA can be completed within the same timeline while providing a more responsive and modern application architecture.