# Monitoring Guide

## Overview

The monitoring stack includes:
1. **Berlin-Stats Exporter** - Application-level metrics (poll duration, errors, etc.)
2. **PostgreSQL Exporter** - Database metrics (record counts, DB size, latest timestamps, etc.)
3. **Prometheus** - Metrics collection and storage
4. **Grafana** - Visualization dashboards

This provides **independent monitoring** of both the service and the database.

---

## Accessing Grafana & Prometheus

### From Raspberry Pi (192.168.178.29)

**Grafana Dashboard:**
```
http://192.168.178.29/grafana
```
- Default credentials: `admin` / `prom-operator` (may need to check Helm values)
- Shows berlin-stats and PostgreSQL metrics in real-time graphs

**Prometheus UI:**
```
http://192.168.178.29/prometheus
```
- Raw metrics explorer
- Query builder for custom queries

---

## Deployment

### Step 1: Create PostgreSQL Exporter Secret
First, you need to set the PostgreSQL password in the secret:

```bash
ssh kuliki@192.168.178.29

# Edit the secret with the actual PostgreSQL password
sudo kubectl -n postgres create secret generic postgres-exporter \
  --from-literal=DATABASE_URL='postgres://postgres:YOUR_PASSWORD@postgres.postgres.svc.cluster.local:5432/berlin_stats?sslmode=disable' \
  --dry-run=client -o yaml | sudo kubectl apply -f -
```

### Step 2: Apply postgres-exporter deployment
```bash
sudo kubectl apply -f k8s/postgres-exporter.yaml
sudo kubectl apply -f k8s/postgres-servicemonitor.yaml
```

### Step 3: Apply berlin-stats ServiceMonitor & Grafana Ingress
```bash
sudo kubectl apply -f k8s/prometheus-servicemonitor.yaml
sudo kubectl apply -f k8s/grafana-ingress.yaml
```

### Step 4: Verify metrics are flowing
```bash
# Check if postgres-exporter is running
kubectl -n postgres get pods | grep postgres-exporter

# Check if Prometheus sees both targets
curl http://192.168.178.29/prometheus/api/v1/targets

# Query a PostgreSQL metric directly
curl 'http://192.168.178.29/prometheus/api/v1/query?query=pg_berlin_stats_polizei_total'
```

---

## Available Metrics

### Berlin-Stats Service Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `berlin_stats_polizei_records_total` | Gauge | Total polizei records in database |
| `berlin_stats_meetings_records_total` | Gauge | Total meetings records in database |
| `berlin_stats_polizei_added_total` | Counter | Cumulative polizei records added |
| `berlin_stats_meetings_added_total` | Counter | Cumulative meetings records added |
| `berlin_stats_poll_duration_seconds` | Gauge | Last poll execution time |
| `berlin_stats_poll_errors_total` | Counter | Total poll failures |

### PostgreSQL Database Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `pg_berlin_stats_polizei_total` | Gauge | Total polizei records (direct from DB) |
| `pg_berlin_stats_meetings_total` | Gauge | Total meetings records (direct from DB) |
| `pg_berlin_stats_latest_polizei_timestamp` | Gauge | Latest polizei record timestamp (Unix epoch) |
| `pg_berlin_stats_latest_meeting_timestamp` | Gauge | Latest meeting record timestamp (Unix epoch) |
| `pg_database_size_bytes` | Gauge | Size of berlin_stats database in bytes |
| `pg_stat_activity` | Gauge | Active database connections |
| `pg_database_age` | Gauge | Database age in transactions |

---

## Why Monitor PostgreSQL Directly?

**Independence:**
- If berlin-stats service crashes, we still see DB metrics
- If /metrics endpoint fails, we still see real data
- Database is source of truth

**Detailed Insights:**
- Record timestamps (is data actually new?)
- Database size growth
- Query performance
- Connection pooling

**Verification:**
- Compare `berlin_stats_polizei_records_total` (from app) vs `pg_berlin_stats_polizei_total` (from DB)
- If they differ, something's wrong with the app

---

## Creating Grafana Dashboards

### Dashboard: Database Health

**Panel 1: Polizei Records (from DB)**
```promql
pg_berlin_stats_polizei_total
```

**Panel 2: Meetings Records (from DB)**
```promql
pg_berlin_stats_meetings_total
```

**Panel 3: Last Polizei Update**
```promql
time() - pg_berlin_stats_latest_polizei_timestamp
# This shows "seconds since last polizei record"
```

**Panel 4: Last Meeting Update**
```promql
time() - pg_berlin_stats_latest_meeting_timestamp
# This shows "seconds since last meeting record"
```

**Panel 5: Database Size**
```promql
pg_database_size_bytes / 1024 / 1024
# Size in MB
```

### Dashboard: Service Health

**Panel 1: Poll Duration**
```promql
berlin_stats_poll_duration_seconds
```

**Panel 2: Records Added (Rate)**
```promql
rate(berlin_stats_polizei_added_total[1h])
# Polizei records per hour
```

**Panel 3: Poll Errors**
```promql
increase(berlin_stats_poll_errors_total[24h])
# Errors in last 24 hours
```

**Panel 4: Comparison (App vs DB)**
```promql
berlin_stats_polizei_records_total - pg_berlin_stats_polizei_total
# If not 0, something's wrong!
```

---

## Custom PostgreSQL Queries

To add more custom metrics, edit `k8s/postgres-exporter.yaml` → `ConfigMap` section.

Example: Track updates by date
```yaml
pg_berlin_stats_polizei_by_date:
  query: "SELECT date, COUNT(*) as count FROM (SELECT DATE(CAST(time AS TIMESTAMP)) as date FROM berlin_stats.polizei) grouped GROUP BY date ORDER BY date DESC LIMIT 30"
  metrics:
    - name: pg_berlin_stats_polizei_by_date
      type: gauge
      valueLabel: count
      labels:
        - date
```

Then restart postgres-exporter:
```bash
kubectl -n postgres rollout restart deployment/postgres-exporter
```

---

## Troubleshooting

### postgres-exporter not running
```bash
kubectl -n postgres logs deployment/postgres-exporter
# Check if secret DATABASE_URL is correct
kubectl -n postgres get secret postgres-exporter -o yaml
```

### "No data" in PostgreSQL dashboard
```bash
# Check if ServiceMonitor is created
kubectl get servicemonitor -n postgres

# Wait 2 minutes for first scrape, then:
curl 'http://192.168.178.29/prometheus/api/v1/query?query=pg_berlin_stats_polizei_total'
```

### PostgreSQL metrics not updating
```bash
# Test connection directly
kubectl -n postgres exec -it postgres-0 -- psql -U postgres -d berlin_stats \
  -c "SELECT COUNT(*) FROM polizei;"
```

### Verify app is writing to DB
```bash
# Check if DB counts match app metrics
curl http://192.168.178.29/berlin-stats/health/scraper | jq .last_result
# Compare with:
curl 'http://192.168.178.29/prometheus/api/v1/query?query=pg_berlin_stats_polizei_total'
```

---

## Maintenance

**Update scrape interval:**
Edit `k8s/postgres-servicemonitor.yaml` → `interval` field (default: 60s)

**Update custom queries:**
Edit `k8s/postgres-exporter.yaml` → `ConfigMap` queries.yaml section

**Update PostgreSQL password:**
```bash
kubectl -n postgres patch secret postgres-exporter \
  --patch '{"data":{"DATABASE_URL":"'$(echo -n 'postgres://postgres:NEWPASSWORD@postgres.postgres.svc.cluster.local:5432/berlin_stats?sslmode=disable' | base64)'"}}'

kubectl -n postgres rollout restart deployment/postgres-exporter
```

