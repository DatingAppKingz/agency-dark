# Elasticsearch Search Setup

## Overview

AgencyDark uses Elasticsearch for advanced search functionality across all content types including models, messages, media, transactions, and users. The search system supports full-text search, faceted filtering, autocomplete suggestions, and saved searches.

## Architecture

### Indices Structure

1. **agencydark_models** - Model profiles and metadata
2. **agencydark_messages** - Chat messages
3. **agencydark_media** - Media files (images, videos)
4. **agencydark_transactions** - Financial transactions
5. **agencydark_users** - User accounts
6. **agencydark_content** - Unified content index for global search

### Features

- Full-text search with fuzzy matching
- Highlighted search results
- Faceted search with aggregations
- Autocomplete suggestions
- Multi-language support (when combined with i18n)
- Real-time indexing via Celery tasks
- Saved searches
- Popular search tracking

## Setup Instructions

### 1. Install Elasticsearch

#### Using Docker (Recommended)

```bash
# Create docker-compose.elasticsearch.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: agencydark-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data
    networks:
      - agencydark-network

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: agencydark-kibana
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
    networks:
      - agencydark-network

volumes:
  elasticsearch-data:

networks:
  agencydark-network:
    external: true
```

```bash
# Start Elasticsearch
docker-compose -f docker-compose.elasticsearch.yml up -d
```

#### Local Installation

```bash
# macOS
brew tap elastic/tap
brew install elastic/tap/elasticsearch-full

# Ubuntu/Debian
wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | sudo apt-key add -
echo "deb https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
sudo apt-get update && sudo apt-get install elasticsearch

# Start service
sudo systemctl start elasticsearch
sudo systemctl enable elasticsearch
```

### 2. Environment Configuration

Add to your `.env` file:

```bash
# Elasticsearch Configuration
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_USER=
ELASTICSEARCH_PASSWORD=
ELASTICSEARCH_VERIFY_CERTS=False  # Set to True in production with proper certs
```

### 3. Initialize Indices

The indices are automatically created when the application starts, but you can manually initialize them:

```python
# Python script to initialize indices
import asyncio
from backend.core.elasticsearch_client import es_client

async def init_indices():
    await es_client.initialize()
    print("Elasticsearch indices initialized successfully")

asyncio.run(init_indices())
```

### 4. Start Search Workers

Add search worker to your Celery configuration:

```bash
# Start search worker
celery -A celery_worker worker --queues=search --loglevel=info
```

Or update your supervisor configuration:

```ini
[program:celery-search]
command=celery -A celery_worker worker --queues=search --loglevel=info
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/search.log
```

## Usage

### 1. Search API Endpoints

#### Global Search
```bash
POST /api/v1/search/all
{
  "query": "john doe onlyfans",
  "filters": {
    "date_from": "2024-01-01"
  },
  "size": 20,
  "offset": 0
}
```

#### Type-Specific Search
```bash
# Search models
POST /api/v1/search/models
{
  "query": "fitness model",
  "platform": "onlyfans",
  "is_active": true,
  "min_revenue": 1000,
  "sort_by": "revenue"
}

# Search messages
POST /api/v1/search/messages
{
  "query": "hello",
  "model_id": "123",
  "has_media": true,
  "date_from": "2024-01-01T00:00:00Z"
}

# Search media
POST /api/v1/search/media
{
  "query": "beach photo",
  "media_type": "image",
  "tags": ["outdoor", "summer"],
  "is_nsfw": false
}
```

#### Search Suggestions
```bash
GET /api/v1/search/suggestions?query=joh&context=models
```

#### Save Search
```bash
POST /api/v1/search/saved
{
  "name": "High earning models",
  "query": "onlyfans",
  "filters": {
    "min_revenue": 5000,
    "is_active": true
  },
  "search_type": "models"
}
```

### 2. Frontend Integration

```typescript
import { searchApi } from '@/api/search';

// Perform global search
const results = await searchApi.searchAll({
  query: 'john doe',
  size: 20
});

// Get autocomplete suggestions
const suggestions = await searchApi.getSuggestions('joh');

// Save a search
await searchApi.saveSearch({
  name: 'Active Models',
  query: 'model',
  filters: { is_active: true },
  search_type: 'models'
});
```

### 3. Indexing Content

Content is automatically indexed when created/updated via Celery tasks:

```python
# Automatic indexing on model save
@receiver(post_save, sender=Model)
def index_model_on_save(sender, instance, **kwargs):
    from tasks.search_tasks import index_model
    index_model.delay(str(instance.id))

# Manual indexing
from tasks.search_tasks import index_model
index_model.delay(model_id)
```

### 4. Reindexing

To reindex all data for an agency:

```bash
# Via API
POST /api/v1/search/reindex

# Via Celery task
from tasks.search_tasks import reindex_agency
reindex_agency.delay(agency_id)
```

## Search Features

### 1. Full-Text Search
- Searches across multiple fields with boosting
- Fuzzy matching for typos
- Synonym support (configurable)

### 2. Faceted Search
- Filter by categories
- Date range filtering
- Numeric range filtering
- Multi-select filters

### 3. Highlighting
- Matching terms highlighted in results
- Configurable highlight tags
- Context snippets

### 4. Autocomplete
- Real-time suggestions as you type
- Based on popular searches
- Context-aware suggestions

### 5. Saved Searches
- Save complex searches
- Quick access to frequent searches
- Share searches within agency

## Performance Optimization

### 1. Index Settings
```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1,
    "index": {
      "refresh_interval": "5s"
    }
  }
}
```

### 2. Bulk Indexing
```python
# Bulk index messages
from tasks.search_tasks import bulk_index_messages
bulk_index_messages.delay(model_id, limit=1000)
```

### 3. Query Optimization
- Use filters instead of queries when possible
- Limit aggregation buckets
- Use source filtering to reduce payload
- Implement pagination properly

### 4. Monitoring

Access Kibana at http://localhost:5601 to:
- Monitor index health
- Analyze search performance
- Debug queries
- View index statistics

## Troubleshooting

### Common Issues

1. **Connection refused**
   - Check Elasticsearch is running: `curl http://localhost:9200`
   - Verify ELASTICSEARCH_URL in .env
   - Check firewall settings

2. **Slow searches**
   - Check index size: `GET /_cat/indices`
   - Review query complexity
   - Add more shards for large indices
   - Increase heap size

3. **Indexing failures**
   - Check Celery worker logs
   - Verify document structure
   - Check index mappings
   - Review field limits

### Useful Commands

```bash
# Check cluster health
curl -X GET "localhost:9200/_cluster/health?pretty"

# List all indices
curl -X GET "localhost:9200/_cat/indices?v"

# Get index mapping
curl -X GET "localhost:9200/agencydark_models/_mapping?pretty"

# Delete index (careful!)
curl -X DELETE "localhost:9200/agencydark_models"

# Check index stats
curl -X GET "localhost:9200/agencydark_*/_stats?pretty"
```

## Security Considerations

1. **Authentication** - Enable X-Pack security in production
2. **Network** - Use SSL/TLS for connections
3. **Access Control** - Implement IP whitelisting
4. **Data Privacy** - Ensure PII is properly handled
5. **Backup** - Regular snapshots of indices

## Scaling

### Horizontal Scaling
1. Add more nodes to cluster
2. Increase replica count
3. Use dedicated master nodes

### Vertical Scaling
1. Increase heap size (50% of RAM max)
2. Use SSDs for storage
3. Optimize shard allocation

### Index Lifecycle Management
1. Create time-based indices for messages
2. Implement index rotation
3. Archive old data
4. Use hot-warm architecture for large datasets