# Monitoring Guide

## Overview

The berlin-stats service includes comprehensive Prometheus metrics for monitoring:
- Total records in database (polizei and meetings)
- Records added per poll cycle
- Poll duration and errors
- Scraper health status

Grafana dashboards are pre-configured to visualize this data.

---

## Accessing Grafana & Prometheus

### From Raspberry Pi (192.168.178.29)

**Grafana Dashboard:**
```
http://192.168.178.29/grafana
```
- Default credentials: `admin` / `prom-operator` (may need to check Helm values)
- Shows berlin-stats metrics in real-time graphs

**Prometheus UI:**
```
http://192.168.178.29/prometheus
```
- Raw metrics explorer
- Query builder for custom queries

---

## Deployment

### 1. Apply ServiceMonitor (enables Prometheus scraping)
```bash
kubectl apply -f k8s/prometheus-servicemonitor.yaml
```

### 2. Apply Ingress rules (enables web access)
```bash
kubectl apply -f k8s/grafana-ingress.yaml
```

### 3. Verify metrics are flowing
```bash
# Check if Prometheus sees berlin-stats target
curl http://192.168.178.29/prometheus/api/v1/targets

# Query a metric directly
curl 'http://192.168.178.29/prometheus/api/v1/query?query=berlin_stats_polizei_records_total'
```

---

## Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `berlin_stats_polizei_records_total` | Gauge | Total polizei records in database |
| `berlin_stats_meetings_records_total` | Gauge | Total meetings records in database |
| `berlin_stats_polizei_added_total` | Counter | Cumulative polizei records added |
| `berlin_stats_meetings_added_total` | Counter | Cumulative meetings records added |
| `berlin_stats_poll_duration_seconds` | Gauge | Last poll execution time |
| `berlin_stats_poll_errors_total` | Counter | Total poll failures |

---

## Creating Grafana Dashboards

### Quick Start: Import Dashboard
1. Go to **Grafana → Dashboards → New → Import**
2. Use this PromQL to create panels:

**Panel: Polizei Records Growth**
```
rate(berlin_stats_polizei_added_total[1h])
```

**Panel: Meetings Records Growth**
```
rate(berlin_stats_meetings_added_total[1h])
```

**Panel: Last Poll Duration**
```
berlin_stats_poll_duration_seconds
```

**Panel: Poll Errors (last 24h)**
```
increase(berlin_stats_poll_errors_total[24h])
```

**Panel: Total Records**
```
berlin_stats_polizei_records_total + berlin_stats_meetings_records_total
```

### Create Manual Dashboard
1. In Grafana, click **+ → Dashboard**
2. Click **Add a new panel**
3. Under "Query", select "Prometheus" data source
4. Paste PromQL queries above
5. Configure visualization (graph, gauge, stat)
6. Save dashboard

---

## Troubleshooting

### Metrics not showing in Prometheus
```bash
# Check if ServiceMonitor is created
kubectl get servicemonitor -n berlin-stats

# Check prometheus scrape config
kubectl -n default exec -it $(kubectl -n default get pod -l app.kubernetes.io/name=prometheus -o jsonpath='{.items[0].metadata.name}') -- cat /etc/prometheus/prometheus.yml | grep berlin-stats

# Check berlin-stats metrics endpoint directly
curl http://192.168.178.29/berlin-stats/metrics
```

### Grafana not accessible
```bash
# Check ingress
kubectl get ingress -A | grep grafana

# Check pod logs
kubectl -n default logs deployment/monitoring-grafana
```

### "No data" in dashboard
- Ensure `/metrics` endpoint is responding: `curl http://localhost/berlin-stats/metrics`
- Wait ~2 minutes for Prometheus to scrape the first time
- Verify poll_loop is running: check `/health/scraper` endpoint

---

## Maintenance

**Update poll interval alerting:**
Edit `k8s/prometheus-servicemonitor.yaml` → `interval` field

**Change scrape timeout:**
Edit `k8s/prometheus-servicemonitor.yaml` → `scrapeTimeout` field

**Update Grafana credentials:**
```bash
kubectl -n default patch secret monitoring-grafana \
  --patch '{"data":{"admin-password":"'$(echo -n 'newpassword' | base64)'"}}'
```

Restart Grafana to apply changes:
```bash
kubectl -n default rollout restart deployment/monitoring-grafana
```
