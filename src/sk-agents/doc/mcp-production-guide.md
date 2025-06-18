# MCP Production Deployment Guide

This guide covers best practices for deploying MCP-enabled agents in production environments.

## Table of Contents

1. [Production Architecture](#production-architecture)
2. [Environment Configuration](#environment-configuration)
3. [Security Considerations](#security-considerations)
4. [Monitoring and Logging](#monitoring-and-logging)
5. [Performance Optimization](#performance-optimization)
6. [Disaster Recovery](#disaster-recovery)
7. [Troubleshooting](#troubleshooting)

## Production Architecture

### Recommended Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Teal Agents   │    │   MCP Servers   │
│                 │────│     Cluster     │────│     Cluster     │
│   (nginx/ALB)   │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Monitoring    │    │   Shared State  │    │   File Storage  │
│                 │    │                 │    │                 │
│ (Prometheus)    │    │    (Redis)      │    │     (NFS/S3)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Component Responsibilities

#### Load Balancer
- SSL termination
- Request routing
- Health checks
- Rate limiting

#### Teal Agents Cluster
- Agent runtime
- MCP client management
- Request processing
- State coordination

#### MCP Servers Cluster
- External tool services
- Data processing
- API integrations
- Resource management

#### Shared Services
- **Redis**: Session state, MCP client pooling
- **File Storage**: Shared agent configurations, logs
- **Monitoring**: Metrics, alerts, observability

## Environment Configuration

### Container Configuration

#### Dockerfile Best Practices

```dockerfile
FROM python:3.13-slim

# Security: Run as non-root user
RUN useradd --create-home --shell /bin/bash agent
USER agent
WORKDIR /home/agent

# Install Node.js for MCP servers
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
RUN sudo apt-get install -y nodejs

# Install MCP servers
RUN npm install -g @modelcontextprotocol/server-filesystem
RUN npm install -g @modelcontextprotocol/server-github

# Copy application
COPY --chown=agent:agent . .
RUN pip install --user -r requirements.txt

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.sk_agents.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose for Development

```yaml
version: '3.8'

services:
  agent:
    build: .
    environment:
      - TA_API_KEY=${TA_API_KEY}
      - TA_SERVICE_CONFIG=/config/agent.yaml
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./config:/config:ro
      - shared_storage:/shared
    depends_on:
      - redis
      - mcp-filesystem
    
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    
  mcp-filesystem:
    image: node:18-alpine
    command: npx @modelcontextprotocol/server-filesystem /shared
    volumes:
      - shared_storage:/shared
    
volumes:
  redis_data:
  shared_storage:
```

### Kubernetes Deployment

#### Agent Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: teal-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: teal-agent
  template:
    metadata:
      labels:
        app: teal-agent
    spec:
      containers:
      - name: agent
        image: teal-agents:latest
        ports:
        - containerPort: 8000
        env:
        - name: TA_API_KEY
          valueFrom:
            secretKeyRef:
              name: agent-secrets
              key: api-key
        - name: TA_SERVICE_CONFIG
          value: /config/agent.yaml
        - name: REDIS_URL
          value: redis://redis-service:6379
        volumeMounts:
        - name: config
          mountPath: /config
          readOnly: true
        - name: shared-storage
          mountPath: /shared
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
      volumes:
      - name: config
        configMap:
          name: agent-config
      - name: shared-storage
        persistentVolumeClaim:
          claimName: shared-storage
```

#### MCP Server Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-filesystem
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-filesystem
  template:
    metadata:
      labels:
        app: mcp-filesystem
    spec:
      containers:
      - name: filesystem-server
        image: node:18-alpine
        command: ["npx", "@modelcontextprotocol/server-filesystem", "/data"]
        ports:
        - containerPort: 8080
        volumeMounts:
        - name: data-storage
          mountPath: /data
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
      volumes:
      - name: data-storage
        persistentVolumeClaim:
          claimName: data-storage
```

## Security Considerations

### Authentication and Authorization

#### API Key Management
```yaml
# Use Kubernetes secrets for sensitive data
apiVersion: v1
kind: Secret
metadata:
  name: agent-secrets
type: Opaque
data:
  api-key: <base64-encoded-api-key>
  github-token: <base64-encoded-github-token>
```

#### Network Security
```yaml
# Network policies for pod-to-pod communication
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-network-policy
spec:
  podSelector:
    matchLabels:
      app: teal-agent
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: load-balancer
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: mcp-filesystem
    ports:
    - protocol: TCP
      port: 8080
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
```

### MCP Server Security

#### Filesystem Access Control
```yaml
mcp_servers:
  - name: FileSystem
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/app/data"]
    env:
      # Restrict filesystem access
      MCP_FILESYSTEM_ALLOWED_DIRS: "/app/data,/tmp"
      MCP_FILESYSTEM_READONLY: "false"
      MCP_FILESYSTEM_MAX_FILE_SIZE: "10MB"
```

#### GitHub Access Control
```yaml
mcp_servers:
  - name: GitHub
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      # Use fine-grained personal access tokens
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
      # Limit to specific repositories
      GITHUB_ALLOWED_REPOS: "org/repo1,org/repo2"
```

## Monitoring and Logging

### Metrics Collection

#### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'teal-agents'
    static_configs:
      - targets: ['agent:8000']
    metrics_path: /metrics
    scrape_interval: 30s
    
  - job_name: 'mcp-servers'
    static_configs:
      - targets: ['mcp-filesystem:8080']
    metrics_path: /metrics
    scrape_interval: 30s
```

#### Key Metrics to Monitor
- **Agent Performance**
  - Request rate and latency
  - Error rates by endpoint
  - Memory and CPU usage
  - Active connections

- **MCP Integration**
  - MCP server connection status
  - Tool execution success rates
  - Tool execution latency
  - Failed MCP connections

- **System Resources**
  - Pod resource utilization
  - Storage usage
  - Network throughput

### Logging Strategy

#### Structured Logging Configuration
```python
# logging_config.py
import logging
import json
from pythonjsonlogger import jsonlogger

def setup_logging():
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    logHandler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.addHandler(logHandler)
    logger.setLevel(logging.INFO)
    
    # MCP-specific logger
    mcp_logger = logging.getLogger('mcp')
    mcp_logger.setLevel(logging.DEBUG)
```

#### Log Aggregation with Fluentd
```yaml
# fluentd-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/teal-agent*.log
      pos_file /var/log/fluentd-agent.log.pos
      tag kubernetes.agent.*
      format json
      time_key timestamp
      time_format %Y-%m-%dT%H:%M:%S.%NZ
    </source>
    
    <filter kubernetes.agent.**>
      @type grep
      <regexp>
        key level
        pattern ^(ERROR|WARN|INFO)$
      </regexp>
    </filter>
    
    <match kubernetes.agent.**>
      @type elasticsearch
      host elasticsearch.logging.svc.cluster.local
      port 9200
      index_name agent-logs
    </match>
```

### Alerting Rules

#### Prometheus Alerting
```yaml
# alert-rules.yml
groups:
  - name: teal-agents
    rules:
      - alert: AgentHighErrorRate
        expr: rate(http_requests_total{job="teal-agents",status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in Teal Agents"
          description: "Error rate is {{ $value }} errors per second"
          
      - alert: MCPServerDown
        expr: up{job="mcp-servers"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "MCP server is down"
          description: "MCP server {{ $labels.instance }} is not responding"
          
      - alert: AgentMemoryUsage
        expr: container_memory_usage_bytes{pod=~"teal-agent.*"} / container_spec_memory_limit_bytes > 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage in agent pod"
          description: "Memory usage is {{ $value | humanizePercentage }}"
```

## Performance Optimization

### Connection Pooling

#### Redis Connection Pool
```python
# config.py
import redis
from redis.connection import ConnectionPool

# Configure Redis connection pool
redis_pool = ConnectionPool(
    host='redis-service',
    port=6379,
    max_connections=20,
    retry_on_timeout=True,
    socket_connect_timeout=5,
    socket_timeout=5
)

redis_client = redis.Redis(connection_pool=redis_pool)
```

#### MCP Client Pool
```python
# mcp_pool.py
import asyncio
from typing import Dict, List
from sk_agents.mcp_integration import SimplifiedMCPClient

class MCPClientPool:
    def __init__(self):
        self.pools: Dict[str, List[SimplifiedMCPClient]] = {}
        self.max_pool_size = 10
    
    async def get_client(self, server_name: str) -> SimplifiedMCPClient:
        if server_name not in self.pools:
            self.pools[server_name] = []
        
        pool = self.pools[server_name]
        if pool:
            return pool.pop()
        
        # Create new client if pool is empty
        return await self._create_client(server_name)
    
    async def return_client(self, server_name: str, client: SimplifiedMCPClient):
        pool = self.pools.get(server_name, [])
        if len(pool) < self.max_pool_size:
            pool.append(client)
        else:
            await client.cleanup()
```

### Caching Strategy

#### Agent Response Caching
```python
# cache.py
import json
import hashlib
from typing import Optional

class AgentCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 3600  # 1 hour
    
    def _make_key(self, agent_name: str, input_data: dict) -> str:
        content = f"{agent_name}:{json.dumps(input_data, sort_keys=True)}"
        return f"agent_cache:{hashlib.md5(content.encode()).hexdigest()}"
    
    async def get(self, agent_name: str, input_data: dict) -> Optional[dict]:
        key = self._make_key(agent_name, input_data)
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    async def set(self, agent_name: str, input_data: dict, response: dict):
        key = self._make_key(agent_name, input_data)
        await self.redis.setex(key, self.ttl, json.dumps(response))
```

### Horizontal Scaling

#### Auto-scaling Configuration
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: teal-agent-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: teal-agent
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
```

## Disaster Recovery

### Backup Strategy

#### Configuration Backup
```bash
#!/bin/bash
# backup-configs.sh

BACKUP_DIR="/backups/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# Backup Kubernetes configurations
kubectl get configmaps -o yaml > "$BACKUP_DIR/configmaps.yaml"
kubectl get secrets -o yaml > "$BACKUP_DIR/secrets.yaml"
kubectl get deployments -o yaml > "$BACKUP_DIR/deployments.yaml"

# Backup agent configurations
cp -r /config "$BACKUP_DIR/agent-configs"

# Upload to S3
aws s3 sync "$BACKUP_DIR" "s3://backup-bucket/teal-agents/$(date +%Y-%m-%d)"
```

#### Redis Data Backup
```bash
#!/bin/bash
# backup-redis.sh

REDIS_POD=$(kubectl get pods -l app=redis -o jsonpath='{.items[0].metadata.name}')
kubectl exec "$REDIS_POD" -- redis-cli BGSAVE

# Wait for backup to complete
kubectl exec "$REDIS_POD" -- redis-cli LASTSAVE > /tmp/last_save_time

# Copy backup file
kubectl cp "$REDIS_POD":/data/dump.rdb "./redis-backup-$(date +%Y-%m-%d).rdb"
```

### Recovery Procedures

#### Agent Recovery
```bash
#!/bin/bash
# recover-agents.sh

# Restore configurations
kubectl apply -f backups/latest/configmaps.yaml
kubectl apply -f backups/latest/secrets.yaml
kubectl apply -f backups/latest/deployments.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=teal-agent --timeout=300s

# Verify MCP connections
kubectl exec -l app=teal-agent -- python -c "
import asyncio
from src.sk_agents.health_check import check_mcp_servers
asyncio.run(check_mcp_servers())
"
```

## Troubleshooting

### Common Production Issues

#### High Memory Usage
```bash
# Check memory usage by pod
kubectl top pods -l app=teal-agent

# Get detailed memory breakdown
kubectl exec <pod-name> -- cat /proc/meminfo

# Check for memory leaks in MCP clients
kubectl logs <pod-name> | grep -i "mcp.*memory"
```

#### MCP Connection Failures
```bash
# Check MCP server status
kubectl get pods -l app=mcp-filesystem

# Check MCP server logs
kubectl logs -l app=mcp-filesystem

# Test MCP connection manually
kubectl exec <agent-pod> -- python -c "
import asyncio
from sk_agents.mcp_integration import SimplifiedMCPClient, MCPServerConfig

async def test():
    config = MCPServerConfig(
        name='test',
        command='npx',
        args=['@modelcontextprotocol/server-filesystem', '/tmp']
    )
    async with SimplifiedMCPClient(config) as client:
        tools = await client.list_tools()
        print(f'Available tools: {len(tools.tools)}')

asyncio.run(test())
"
```

#### Performance Degradation
```bash
# Check CPU and memory usage
kubectl top pods -l app=teal-agent

# Check agent response times
curl -w "@curl-format.txt" -s -o /dev/null http://agent-service/health

# Check MCP tool execution times
kubectl logs <pod-name> | grep "mcp.*duration"

# Check for blocked connections
kubectl exec <pod-name> -- netstat -an | grep ESTABLISHED
```

### Health Check Implementation

```python
# health_check.py
from fastapi import FastAPI
import asyncio
import logging
from sk_agents.mcp_integration import SimplifiedMCPIntegration

app = FastAPI()

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/ready")
async def readiness_check():
    """Readiness check including MCP server connectivity."""
    try:
        # Check MCP servers
        mcp_status = await check_mcp_servers()
        
        # Check Redis connection
        redis_status = await check_redis()
        
        if mcp_status and redis_status:
            return {"status": "ready", "mcp": "connected", "redis": "connected"}
        else:
            return {"status": "not_ready", "mcp": mcp_status, "redis": redis_status}
    
    except Exception as e:
        logging.error(f"Readiness check failed: {e}")
        return {"status": "not_ready", "error": str(e)}

async def check_mcp_servers():
    """Check connectivity to all configured MCP servers."""
    # Implementation depends on your specific MCP configuration
    return True

async def check_redis():
    """Check Redis connectivity."""
    # Implementation for Redis health check
    return True
```

This production guide provides comprehensive coverage of deploying MCP-enabled agents in production environments. Follow these practices to ensure reliable, scalable, and secure deployments.