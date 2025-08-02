# AgencyDark Documentation

Welcome to the AgencyDark documentation. This directory contains all technical documentation, setup guides, and development resources for the AgencyDark platform.

## 📚 Documentation Structure

### Getting Started
- [**SETUP.md**](SETUP.md) - Complete setup guide for development and production
- [**API_REFERENCE.md**](API_REFERENCE.md) - Comprehensive API documentation
- [**WEBHOOKS.md**](WEBHOOKS.md) - Webhook integration guide
- [**TODO.md**](TODO.md) - Active development tasks and roadmap

### Technical Guides
Located in [`guides/`](guides/):
- [Database Setup Guide](guides/DATABASE_SETUP_GUIDE.md)
- [Deployment Guide](guides/DEPLOYMENT.md)
- [Elasticsearch Setup](guides/ELASTICSEARCH_SETUP.md)
- [Error Handling Guide](guides/ERROR_HANDLING_GUIDE.md)
- [Celery Setup](guides/CELERY_SETUP.md)
- [Notification System](guides/NOTIFICATION_SYSTEM.md)
- [Socket.IO Client Examples](guides/SOCKET_IO_CLIENT_EXAMPLE.md)

### Planning & Architecture
Located in [`planning/`](planning/):
- [Master Planning Document](planning/MASTER_PLANNING_DOCUMENT.md)
- [Implementation Notes](planning/IMPLEMENTATION_NOTES.md)
- [Next Phases Roadmap](planning/NEXT_PHASES_ROADMAP.md)
- [Full Setup Plan](planning/FULL_SETUP_PLAN.md)
- [Master Testing Document](planning/MASTER_TESTING_DOCUMENT.md)

### Production Documentation
Located in [`production/`](production/):
- Production setup and configuration
- SLA documentation
- Runbooks for incident response

### Platform-Specific Documentation
- [**Backend Documentation**](../backend/docs/) - Backend-specific technical docs
- [**Frontend Documentation**](../frontend/docs/) - Frontend-specific docs

### Archives
Located in [`archives/`](archives/) - Historical documentation:
- Development logs and session summaries
- Completed TODO items
- Historical planning documents

## 🚀 Quick Start

1. **New Developer?** Start with [SETUP.md](SETUP.md)
2. **API Integration?** Check [API_REFERENCE.md](API_REFERENCE.md)
3. **Contributing?** Review [documentation/BEST_PRACTICES_AND_RULES.md](documentation/BEST_PRACTICES_AND_RULES.md)

## 📋 Project Overview

AgencyDark is a white-label SaaS platform for OnlyFans marketing agencies, featuring:

- **Backend**: FastAPI + PostgreSQL + Redis + Celery
- **Frontend**: React + TypeScript + Material-UI
- **Infrastructure**: Docker + Kubernetes ready
- **Key Features**:
  - Multi-tenant architecture with RBAC
  - Real-time features with Socket.IO
  - Machine learning analytics
  - Comprehensive API with 434+ endpoints
  - Webhook support for external integrations

## 🔗 Important Links

- **API Documentation**: http://localhost:8000/docs (when running locally)
- **ReDoc**: http://localhost:8000/redoc
- **Frontend**: http://localhost:5173 (development)

## 📝 Contributing

Before contributing, please review:
1. [Best Practices and Rules](documentation/BEST_PRACTICES_AND_RULES.md)
2. Active tasks in [TODO.md](TODO.md)
3. Setup instructions in [SETUP.md](SETUP.md)

---

*Last Updated: August 2, 2025*