# Troubleshooting Guide: Scraper Issues

## Symptom: Data hasn't been updated for weeks

The scraper is configured to run every 24 hours via `poll_loop()` in the K8s pod, but data hasn't been updated.

### Root Causes

1. **Pod is not running or crashed**
   - Check pod status: `kubectl -n berlin-stats get pods -o wide`
   - View logs: `kubectl -n berlin-stats logs deployment/berlin-stats --tail=100`

2. **Cannot connect to PostgreSQL**
   - Verify DATABASE_URL secret exists: `kubectl -n berlin-stats get secret berlin-stats-db`
   - Check PostgreSQL pod: `kubectl -n postgres get pods`
   - Verify network connectivity between namespaces

3. **Website structure changed** (parsing fails silently)
   - Now improved with better error logging and None-checks
   - Check logs for: `"textile div not found"` warnings

4. **Deployment scaled to 0 replicas**
   - Check: `kubectl -n berlin-stats get deployment berlin-stats -o wide`

---

## Quick Diagnostics

### 1. Check pod status
```bash
kubectl -n berlin-stats get pods -o wide
kubectl -n berlin-stats describe pod <pod-name>
```

### 2. View application logs
```bash
# Last 100 lines
kubectl -n berlin-stats logs deployment/berlin-stats --tail=100

# Follow live logs
kubectl -n berlin-stats logs deployment/berlin-stats -f

# Logs from previous pod (if crashed)
kubectl -n berlin-stats logs deployment/berlin-stats --previous
```

### 3. Test scraper manually
```bash
# Get password from secret
PASSWORD=$(kubectl -n berlin-stats get secret berlin-stats -o jsonpath='{.data.SECRET_PASSWORD}' | base64 -d)

# Trigger polizei scrape
kubectl -n berlin-stats exec -it deployment/berlin-stats -- \
  curl -s http://localhost:8000/update_polizei -H "X-Password: $PASSWORD" | jq .

# Trigger meetings scrape  
kubectl -n berlin-stats exec -it deployment/berlin-stats -- \
  curl -s http://localhost:8000/update_meetings -H "X-Password: $PASSWORD" | jq .
```

### 4. Check database connectivity
```bash
# From pod shell
kubectl -n berlin-stats exec -it deployment/berlin-stats -- /bin/sh

# Inside pod:
echo $DATABASE_URL
psql $DATABASE_URL -c "SELECT COUNT(*) FROM polizei; SELECT MAX(time) FROM polizei;"
```

---

## Solutions

### Option A: Restart the deployment
```bash
kubectl -n berlin-stats rollout restart deployment/berlin-stats
```

### Option B: Use CronJob for guaranteed updates (recommended)
```bash
# Apply the CronJob manifest
kubectl apply -f k8s/cronjob.yaml

# Check CronJob status
kubectl -n berlin-stats get cronjob
kubectl -n berlin-stats get jobs -l job-type=scraper
```

### Option C: Manual update script
```bash
# Set password environment variable
export SECRET_PASSWORD=$(kubectl -n berlin-stats get secret berlin-stats -o jsonpath='{.data.SECRET_PASSWORD}' | base64 -d)

# Run update
./k8s/update-data.sh
```

---

## Improvements Made

### Error Handling
- `parse_polizei_record_html()` now safely handles missing HTML elements
- Defensive checks with proper logging
- Won't crash if website structure changes

### Monitoring  
- `poll_loop()` tracks consecutive errors
- Logs critical alert after 5 consecutive failures
- Helps identify permanent vs temporary issues

### Reliability Options
- **CronJob**: Independent scheduled scraping (alternative to background poll)
- **HTTP endpoints**: Manual triggering via `/update_polizei` and `/update_meetings`
- **Script**: Easy wrapper for K8s-based updates

---

## Database Location

**Production**: PostgreSQL in K8s cluster (from `DATABASE_URL` secret)
- Namespace: `berlin-stats` or `postgres` 
- Secret: `berlin-stats-db`

**Local development**: Not used (legacy SQLite `polizei.db` is obsolete)
- Code only uses PostgreSQL via `db.py`

---

## Expected Behavior

- Scraper runs automatically every 24 hours
- Retrieves ~50 new police reports per cycle
- Updates are written to PostgreSQL
- Errors are logged with consecutive count
