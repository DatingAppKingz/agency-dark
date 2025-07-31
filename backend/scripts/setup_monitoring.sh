#!/bin/bash

# AgencyDark Monitoring Setup Script
# This script sets up the complete monitoring stack

set -euo pipefail

# Configuration
MONITORING_DIR="/opt/agencydark/monitoring"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$(openssl rand -base64 32)}"
PROMETHEUS_API_TOKEN="${PROMETHEUS_API_TOKEN:-$(openssl rand -hex 32)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
    fi
    
    # Check if user has Docker permissions
    if ! docker ps &> /dev/null; then
        error "Current user doesn't have Docker permissions. Add user to docker group."
    fi
    
    log "All prerequisites met"
}

# Create directories
create_directories() {
    log "Creating monitoring directories..."
    
    directories=(
        "$MONITORING_DIR"
        "$MONITORING_DIR/prometheus"
        "$MONITORING_DIR/prometheus/alerts"
        "$MONITORING_DIR/alertmanager"
        "$MONITORING_DIR/alertmanager/templates"
        "$MONITORING_DIR/grafana"
        "$MONITORING_DIR/grafana/dashboards"
        "$MONITORING_DIR/grafana/provisioning"
        "$MONITORING_DIR/grafana/provisioning/dashboards"
        "$MONITORING_DIR/grafana/provisioning/datasources"
        "$MONITORING_DIR/blackbox_exporter"
        "$MONITORING_DIR/postgres_exporter"
        "$MONITORING_DIR/loki"
        "$MONITORING_DIR/promtail"
        "$MONITORING_DIR/certs"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
    done
    
    # Set permissions
    chmod -R 755 "$MONITORING_DIR"
    
    log "Directories created"
}

# Generate certificates
generate_certificates() {
    log "Generating self-signed certificates for testing..."
    
    cd "$MONITORING_DIR/certs"
    
    # Generate CA
    openssl genrsa -out ca.key 4096
    openssl req -new -x509 -days 365 -key ca.key -out ca.crt \
        -subj "/C=US/ST=State/L=City/O=AgencyDark/CN=AgencyDark CA"
    
    # Generate server certificate
    openssl genrsa -out server.key 4096
    openssl req -new -key server.key -out server.csr \
        -subj "/C=US/ST=State/L=City/O=AgencyDark/CN=*.agencydark.com"
    openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key \
        -CAcreateserial -out server.crt
    
    # Clean up
    rm server.csr
    
    log "Certificates generated"
}

# Configure Prometheus
configure_prometheus() {
    log "Configuring Prometheus..."
    
    # Copy configuration files
    cp -r ./monitoring/prometheus/* "$MONITORING_DIR/prometheus/"
    
    # Create API token file
    echo "$PROMETHEUS_API_TOKEN" > "$MONITORING_DIR/prometheus/api_token"
    chmod 600 "$MONITORING_DIR/prometheus/api_token"
    
    # Update prometheus.yml with actual values
    sed -i "s|/etc/prometheus|$MONITORING_DIR/prometheus|g" \
        "$MONITORING_DIR/prometheus/prometheus.yml"
    
    log "Prometheus configured"
}

# Configure Alertmanager
configure_alertmanager() {
    log "Configuring Alertmanager..."
    
    # Copy configuration files
    cp -r ./monitoring/alertmanager/* "$MONITORING_DIR/alertmanager/"
    
    # Prompt for notification settings
    read -p "Enter SMTP password for alerts@agencydark.com: " smtp_password
    read -p "Enter Slack webhook URL (optional): " slack_webhook
    read -p "Enter PagerDuty service key (optional): " pagerduty_key
    
    # Update configuration
    sed -i "s|your_smtp_password|$smtp_password|g" \
        "$MONITORING_DIR/alertmanager/alertmanager.yml"
    
    if [ ! -z "$slack_webhook" ]; then
        sed -i "s|https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK|$slack_webhook|g" \
            "$MONITORING_DIR/alertmanager/alertmanager.yml"
    fi
    
    if [ ! -z "$pagerduty_key" ]; then
        sed -i "s|YOUR-PAGERDUTY-SERVICE-KEY|$pagerduty_key|g" \
            "$MONITORING_DIR/alertmanager/alertmanager.yml"
    fi
    
    log "Alertmanager configured"
}

# Configure Grafana
configure_grafana() {
    log "Configuring Grafana..."
    
    # Copy dashboards
    cp -r ./monitoring/grafana/dashboards/* "$MONITORING_DIR/grafana/dashboards/"
    
    # Create datasource provisioning
    cat > "$MONITORING_DIR/grafana/provisioning/datasources/prometheus.yml" <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: true

  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686
    editable: true
EOF

    # Create dashboard provisioning
    cat > "$MONITORING_DIR/grafana/provisioning/dashboards/dashboards.yml" <<EOF
apiVersion: 1

providers:
  - name: 'AgencyDark'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF

    # Create Grafana configuration
    cat > "$MONITORING_DIR/grafana/grafana.ini" <<EOF
[server]
root_url = https://grafana.agencydark.com

[security]
admin_user = admin
admin_password = $GRAFANA_ADMIN_PASSWORD

[users]
allow_sign_up = false
allow_org_create = false

[auth]
disable_login_form = false
disable_signout_menu = false

[auth.anonymous]
enabled = false

[dashboards]
default_home_dashboard_path = /var/lib/grafana/dashboards/agencydark-overview.json

[alerting]
enabled = true
execute_alerts = true

[unified_alerting]
enabled = true

[smtp]
enabled = true
host = smtp.gmail.com:587
user = alerts@agencydark.com
password = $smtp_password
from_address = alerts@agencydark.com
from_name = AgencyDark Monitoring
EOF

    log "Grafana configured"
}

# Configure exporters
configure_exporters() {
    log "Configuring exporters..."
    
    # PostgreSQL exporter queries
    cat > "$MONITORING_DIR/postgres_exporter/queries.yaml" <<EOF
pg_replication:
  query: "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) as lag"
  metrics:
    - lag:
        usage: "GAUGE"
        description: "Replication lag in seconds"

pg_database:
  query: "SELECT pg_database.datname, pg_database_size(pg_database.datname) as size FROM pg_database"
  metrics:
    - datname:
        usage: "LABEL"
        description: "Name of the database"
    - size:
        usage: "GAUGE"
        description: "Disk space used by the database"

pg_stat_user_tables:
  query: "SELECT schemaname, tablename, n_live_tup, n_dead_tup FROM pg_stat_user_tables"
  metrics:
    - schemaname:
        usage: "LABEL"
    - tablename:
        usage: "LABEL"
    - n_live_tup:
        usage: "GAUGE"
    - n_dead_tup:
        usage: "GAUGE"
EOF

    # Loki configuration
    cat > "$MONITORING_DIR/loki/loki-config.yaml" <<EOF
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s

schema_config:
  configs:
    - from: 2023-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: false
  retention_period: 0s
EOF

    # Promtail configuration
    cat > "$MONITORING_DIR/promtail/promtail-config.yaml" <<EOF
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    static_configs:
      - targets:
          - localhost
        labels:
          job: containerlogs
          __path__: /var/lib/docker/containers/*/*log
    
    pipeline_stages:
      - json:
          expressions:
            output: log
            stream: stream
            attrs:
      - json:
          expressions:
            tag:
          source: attrs
      - regex:
          expression: '(?P<container_name>(?:[^|]*))'
          source: tag
      - timestamp:
          format: RFC3339Nano
          source: time
      - labels:
          stream:
          container_name:
      - output:
          source: output

  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: varlogs
          __path__: /var/log/*log
EOF

    log "Exporters configured"
}

# Start monitoring stack
start_monitoring() {
    log "Starting monitoring stack..."
    
    cd /opt/agencydark/agency-dark/backend
    
    # Start monitoring services
    docker-compose -f docker-compose.monitoring.yml up -d
    
    # Wait for services to start
    log "Waiting for services to start..."
    sleep 30
    
    # Check service health
    services=("prometheus:9090" "alertmanager:9093" "grafana:3000")
    for service in "${services[@]}"; do
        IFS=':' read -r name port <<< "$service"
        if curl -f "http://localhost:$port" &> /dev/null; then
            log "✓ $name is running"
        else
            warning "✗ $name is not responding"
        fi
    done
    
    log "Monitoring stack started"
}

# Configure firewall
configure_firewall() {
    log "Configuring firewall rules..."
    
    if command -v ufw &> /dev/null; then
        # Allow monitoring ports (restrict to specific IPs in production)
        sudo ufw allow from 10.0.0.0/8 to any port 9090 comment "Prometheus"
        sudo ufw allow from 10.0.0.0/8 to any port 3000 comment "Grafana"
        sudo ufw allow from 10.0.0.0/8 to any port 9093 comment "Alertmanager"
        log "Firewall rules added"
    else
        warning "UFW not found, skipping firewall configuration"
    fi
}

# Print summary
print_summary() {
    echo
    echo "=========================================="
    echo "   AgencyDark Monitoring Setup Complete   "
    echo "=========================================="
    echo
    echo "Access URLs:"
    echo "  Prometheus:    http://localhost:9090"
    echo "  Grafana:       http://localhost:3000"
    echo "  Alertmanager:  http://localhost:9093"
    echo "  Jaeger:        http://localhost:16686"
    echo
    echo "Credentials:"
    echo "  Grafana Admin Password: $GRAFANA_ADMIN_PASSWORD"
    echo "  Prometheus API Token:   $PROMETHEUS_API_TOKEN"
    echo
    echo "Configuration files:"
    echo "  $MONITORING_DIR"
    echo
    echo "Next steps:"
    echo "1. Configure nginx reverse proxy for HTTPS access"
    echo "2. Update DNS records for monitoring subdomains"
    echo "3. Configure backup for monitoring data"
    echo "4. Test alerting rules and notifications"
    echo
    echo "Documentation:"
    echo "  https://docs.agencydark.com/monitoring"
    echo "=========================================="
}

# Main execution
main() {
    log "Starting AgencyDark monitoring setup..."
    
    check_prerequisites
    create_directories
    generate_certificates
    configure_prometheus
    configure_alertmanager
    configure_grafana
    configure_exporters
    start_monitoring
    configure_firewall
    print_summary
    
    log "Setup completed successfully!"
}

# Run main function
main

exit 0