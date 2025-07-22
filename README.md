# AgencyDark

White-label SaaS portal for OnlyFans marketing agencies.

## Tech Stack

- **Backend**: FastAPI (Python) with modular monolith architecture
- **Frontend**: React + Next.js with Material-UI components
- **Database**: PostgreSQL with Row-Level Security + Redis caching
- **Real-time**: Socket.IO with Redis adapter
- **Infrastructure**: Docker Compose/Swarm on Hetzner Cloud
- **Queue**: Redis Queue initially, RabbitMQ later
- **Reverse Proxy**: Caddy for automatic HTTPS

## Quick Start

1. Clone the repository
2. Copy `.env.example` to `.env` and configure
3. Run `docker-compose up -d` for development
4. Backend API: http://localhost:8000
5. Frontend: http://localhost:3000

## Project Structure

```
AgencyDark/
├── backend/          # FastAPI application
├── frontend/         # Next.js application
├── docker/           # Docker configurations
└── docs/            # Documentation
```

## Development

See [docs/development.md](docs/development.md) for detailed development instructions.

## Deployment

See [docs/deployment.md](docs/deployment.md) for production deployment guide.