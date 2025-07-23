# AgencyDark

A white-label SaaS platform for OnlyFans marketing agencies, providing comprehensive tools for model management, fan engagement, analytics, and financial operations.

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)
![Redis](https://img.shields.io/badge/Redis-7-red.svg)
![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)
![License](https://img.shields.io/badge/license-Proprietary-red.svg)

## Features

- **Multi-tenant Architecture**: Complete agency isolation with PostgreSQL schemas
- **Role-based Access Control**: Super Admin, Agency Owner, Agency Admin, Model, and Chatter roles
- **JWT Authentication**: Secure token-based authentication with refresh tokens
- **Real-time Features**: Socket.IO integration for live chat and notifications
- **Fan Claiming System**: Exclusive communication management between chatters and fans
- **Analytics Dashboard**: Comprehensive metrics and KPIs for content creators
- **Commission Management**: Tiered commission structure based on subscriber count
- **API Wrappers**: Full integration with Inflow and OnlyFansAPI

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with AsyncPG
- **ORM**: SQLAlchemy 2.0 with Alembic migrations
- **Cache**: Redis 7
- **Authentication**: JWT with python-jose
- **Real-time**: Socket.IO
- **Task Queue**: Celery (planned)

### Frontend
- **Framework**: Next.js 15 with React 19
- **UI Library**: Material-UI (MUI) v7
- **State Management**: Zustand
- **Data Fetching**: TanStack React Query
- **Charts**: Recharts
- **TypeScript**: Full type safety

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Reverse Proxy**: Caddy with automatic HTTPS
- **Monitoring**: Prometheus + OpenTelemetry

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)
- PostgreSQL 16 (if not using Docker)
- Redis 7 (if not using Docker)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/DatingAppKingz/agency-dark.git
   cd agency-dark
   ```

2. **Start the development environment**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs

## Development Setup

### Backend Development

1. **Create a virtual environment**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start the development server**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Development

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Set up environment variables**
   ```bash
   cp .env.local.example .env.local
   # Edit .env.local with your configuration
   ```

3. **Start the development server**
   ```bash
   npm run dev
   ```

## API Documentation

### Authentication Endpoints

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login with email/password
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout current user
- `GET /api/v1/auth/me` - Get current user info
- `POST /api/v1/auth/verify-email/{token}` - Verify email address
- `POST /api/v1/auth/password-reset/request` - Request password reset
- `POST /api/v1/auth/password-reset/confirm` - Confirm password reset

### Role Permissions

1. **Super Admin**: Full system access, read-only chat access
2. **Agency Owner**: Full agency management, read-only chat access
3. **Agency Admin**: Model management, read-only chat access
4. **Model**: Own account management, full chat access, fan claiming
5. **Chatter**: Chat management, fan claiming

## Database Schema

The application uses a multi-tenant architecture with the following main entities:

- **Agencies**: Organizations managing multiple models
- **Users**: All system users with role-based permissions
- **ModelProfiles**: OnlyFans creator accounts
- **Fans**: OnlyFans subscribers
- **FanClaims**: Exclusive communication assignments
- **Sessions**: JWT refresh token management
- **AuditLogs**: Activity tracking

## Commission Structure

- 0-5,000 paying subscribers: 70% commission
- 5,001-10,000 paying subscribers: 65% commission
- 10,000+ paying subscribers: 60% commission

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key
ENVIRONMENT=development
DEBUG=true
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

## Deployment

### Production with Docker Compose
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Manual Deployment
See deployment documentation in `/docs/deployment.md`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary software. All rights reserved.

## Support

For support, email support@agencydark.com or join our Slack channel.