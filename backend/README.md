# AgencyDark Backend

A high-performance, scalable backend API for the AgencyDark platform - an advanced OnlyFans agency management system.

## 🚀 Features

### Core Features
- **Multi-tenant Architecture**: Complete isolation between agencies
- **Real-time Communication**: WebSocket support for instant messaging
- **Advanced Authentication**: JWT-based auth with refresh tokens
- **Role-based Access Control**: Granular permissions system
- **API Key Management**: Secure API key generation and validation

### Advanced Features
- **Video Transcoding**: FFmpeg integration for multiple quality presets
- **Push Notifications**: Support for FCM, APNS, and Web Push
- **External API Integration**: OnlyFans, Stripe, and Inflow API validation
- **Report Generation**: Charts and PDF export capabilities
- **Task Scheduling**: Cron-based task scheduling with visual builder
- **Multi-language Support**: i18n with dynamic translations
- **Advanced Caching**: Multi-tier caching with Redis
- **Performance Monitoring**: Prometheus metrics and OpenTelemetry tracing

## 🛠️ Technology Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with AsyncPG
- **ORM**: SQLAlchemy 2.0 with async support
- **Cache**: Redis
- **Task Queue**: Celery with Redis broker
- **File Storage**: S3-compatible storage
- **Container**: Docker with multi-stage builds
- **Monitoring**: Prometheus + Grafana

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Docker & Docker Compose (optional)
- FFmpeg (for video processing)

## 🔧 Installation

### 1. Clone the repository
```bash
git clone https://github.com/DatingAppKingz/agency-dark.git
cd agency-dark/backend
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Install dependencies

#### Using Poetry (recommended)
```bash
poetry install
poetry shell
```

#### Using pip
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run database migrations
```bash
alembic upgrade head
```

### 5. Seed initial data (development only)
```bash
python seed_data.py
```

### 6. Start the server
```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 🐳 Docker Deployment

### Development
```bash
docker-compose up --build
```

### Production
```bash
# Build optimized image
docker build -f Dockerfile.optimized -t agencydark-backend:latest .

# Run container
docker run -d \
  --name agencydark-backend \
  -p 8000:8000 \
  --env-file .env \
  agencydark-backend:latest
```

## 📚 API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔒 Security Features

- **Security Headers**: Automatic security headers on all responses
- **Rate Limiting**: Advanced rate limiting with different tiers
- **Input Validation**: Comprehensive request validation
- **SQL Injection Protection**: Parameterized queries
- **XSS Protection**: Content Security Policy headers
- **CORS Configuration**: Configurable CORS settings
- **API Key Security**: Hashed API keys with scoping

## 📊 Monitoring & Logging

### Structured Logging
The application uses structured JSON logging with context tracking:
- Request IDs for tracing
- User and agency context
- Performance metrics
- Error tracking with Sentry

### Health Checks
- `/health` - Full health check
- `/health/live` - Kubernetes liveness probe
- `/health/ready` - Kubernetes readiness probe

### Metrics
Prometheus metrics available at `/metrics`:
- Request duration
- Database query performance
- Cache hit rates
- API usage statistics

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

## 📦 Project Structure

```
backend/
├── alembic/              # Database migrations
├── api/                  # API endpoints
│   └── v1/              # API version 1
├── core/                # Core functionality
│   ├── auth.py         # Authentication
│   ├── database.py     # Database setup
│   └── config.py       # Configuration
├── middleware/          # Custom middleware
├── models/             # SQLAlchemy models
├── modules/            # Feature modules
├── schemas/            # Pydantic schemas
├── services/           # Business logic
├── tasks/              # Celery tasks
├── tests/              # Test suite
└── utils/              # Utilities
```

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key

# External APIs
STRIPE_SECRET_KEY=sk_test_...
INFLOW_API_KEY=your-inflow-key

# AWS S3 (for file storage)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=your-bucket-name

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Push Notifications
FCM_CREDENTIALS_FILE=path/to/firebase-credentials.json
APNS_KEY_FILE=path/to/apns-key.p8
```

## 🚀 Performance Optimization

- **Database Indexes**: Optimized queries with proper indexing
- **Connection Pooling**: Async connection pooling
- **Response Caching**: Multi-tier caching strategy
- **Lazy Loading**: Efficient ORM relationship loading
- **Pagination**: Default pagination on list endpoints
- **Compression**: Gzip compression for responses

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is proprietary and confidential.

## 🆘 Support

For support, email support@agencydark.com or create an issue in the repository.