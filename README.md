# CAFE (Composite AI Flow Engine)

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![GitHub Actions](https://github.com/yourusername/cafe/workflows/CI/badge.svg)](https://github.com/yourusername/cafe/actions)
[![codecov](https://codecov.io/gh/yourusername/cafe/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/cafe)
[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://yourusername.github.io/cafe)
[![Version](https://img.shields.io/github/v/release/yourusername/cafe)](https://github.com/yourusername/cafe/releases)
[![Dependencies](https://status.david-dm.org/gh/yourusername/cafe.svg)](https://david-dm.org/yourusername/cafe)

CAFE is a self-learning, autonomous AI agent capable of automating multi-scale and multi-modal AI models. It dynamically spins up containerized environments as needed, leveraging self-learning capabilities to optimize workflow automation.

## Features

- Chat-based workflow creation
- Multi-service integration (Gmail, Slack, etc.)
- Containerized service execution
- Database-driven execution history management

### Supported Use Cases

1. Email Automation Support
   - ChatGPT + Gmail integration
   - Template-based auto-generation

2. Chat Task Extraction (Slack, Teams)
   - Automatic chat history summarization
   - Automated ToDo list generation

3. Meeting-Related Tasks
   - Schedule coordination automation
   - Minutes generation
   - Follow-up email creation

4. Additional Features
   - Proposal & presentation draft creation
   - Telemarketing list generation
   - Automated customer inquiry handling

## Architecture

- Frontend: React + Vite
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL
- Container Management: Docker

## Setup

### Prerequisites

- Python 3.11 or higher
- Docker & Docker Compose
- PostgreSQL
- [Rye](https://rye-up.com/guide/installation/) (Python package manager)

### Environment Setup

1. Clone repository and install dependencies

```bash
git clone [repository-url]
cd cafe
rye sync
```

2. Configure environment variables

```bash
cp .env.example .env
```

Required environment variables in .env:
- DATABASE_URL
- OPENAI_API_KEY
- Other necessary API keys

3. Launch Docker containers

```bash
docker-compose up -d
```

4. Run database migrations

```bash
cd server
alembic upgrade head
```

5. Start development servers

Backend:
```bash
rye run python -m server.main
```

Frontend:
```bash
npm run dev
```

## Development Guide

### Adding New Workflows

1. Service Integration
   - Add Docker image generation logic in server/docker_manager.py
   - Update .env.example with required variables

2. Adding New Task Types
   - Add new tools to WorkflowManager class's available_tools
   - Create Docker images as needed

### Database Migrations

1. Model Changes
   - Update SQLAlchemy models in server/models.py

2. Generate Migration
```bash
cd server
alembic revision --autogenerate -m "description of changes"
```

3. Apply Migration
```bash
alembic upgrade head
```

## Troubleshooting

### Common Issues and Solutions

1. Docker Issues
   - Verify Docker daemon status
   ```bash
   docker ps
   ```
   - Check for port conflicts
   ```bash
   docker-compose ps
   ```

2. Database Connection Errors
   - Check PostgreSQL container status
   ```bash
   docker-compose logs db
   ```
   - Verify environment variables
   ```bash
   echo $DATABASE_URL
   ```

3. API Authentication Errors
   - Check environment variables
   ```bash
   echo $OPENAI_API_KEY
   ```
   - Verify API key validity
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 CAFE Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
