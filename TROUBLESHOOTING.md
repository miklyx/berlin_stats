# Troubleshooting Guide: Scraper Issues

## Symptom: Data hasn't been updated for weeks

The scraper is configured to run every 24 hours via `poll_loop()` in the K8s pod, but data hasn't been updated.

### Root Cause (IDENTIFIED ✅)

**Parser silently failed** when website HTML structure changed around Oct 20-30, 2026.

The code had critical bugs:
```python
# BUG: If soup.find() returns None, .find_all() throws AttributeError
soup.find('ul', class_='list--tablelist').find_all('li')  # Could be None!
soup.find('thead').find_all('th')  # Could be None!
```

This caused:
- **Silent failure**: Exception swallowed, scraper exits
- **Data stops updating**: Both polizei and meetings stopped ~same time
- **Pod keeps running**: No crash, just stuck in poll_loop

### Why It Took Until Now to Notice

- Podia running 34 days without restart ✓
- Scraper runs every 24 hours in background
- Errors logged but overlooked
- Site probably updated HTML around Oct 20

---

## ✅ Fixed in This Release

### 1. Parser Defensive Checks (Critical)
```python
# OLD - crashes silently
soup.find('ul', class_='list--tablelist').find_all('li')

# NEW - safe with logging
list_ul = soup.find('ul', class_='list--tablelist')
if list_ul is None:
    logger.error("Could not find polizei list element")
    return []
```

### 2. Scraper Health Endpoint
```bash
# Check if scraper is healthy
curl http://berlin-stats/health/scraper

# Returns:
{
  "status": "healthy|unhealthy",
  "last_poll": "2026-11-26T08:59:49Z",
  "hours_since_poll": 0.5,
  "last_result": [50, 1289]  # polizei count, meetings count
}
```

### 3. Improved CronJob (Redundancy)
- Runs every **12 hours** (not 24) for redundancy
- **Timeout**: 10 minutes (prevents hanging)
- **Timestamped logs** for debugging
- **Exit codes**: Fail fast on errors
- **Job history**: Keep last 10 failed jobs for investigation

### 4. Better Error Tracking
- Consecutive error counter (alerts after 5 failures)
- Database init error logging
- Per-item exception handling in parsers

---

## Diagnostics

### Quick Status Check

```bash
# From K8s cluster:
curl -H "X-Password: $SECRET_PASSWORD" \
  http://berlin-stats:8000/health/scraper | jq .
```

### View Scraper Logs

```bash
# Last 100 lines
kubectl -n berlin-stats logs deployment/berlin-stats --tail=100

# Follow live
kubectl -n berlin-stats logs deployment/berlin-stats -f

# From specific pod
kubectl -n berlin-stats logs <pod-name> -f
```

### Check CronJob Execution

```bash
# List CronJob
kubectl -n berlin-stats get cronjob

# View job history
kubectl -n berlin-stats get jobs -l job-type=scraper

# View job logs
kubectl -n berlin-stats logs job/<job-name>

# View job status
kubectl -n berlin-stats describe job/<job-name>
```

### Manual Test from Local

```bash
# Test polizei parser
python3 << 'EOF'
from scrap import get_html, parse_polizei_html
html = get_html("https://www.berlin.de/polizei/polizeimeldungen")
reports = parse_polizei_html(html, skip_urls=frozenset(), delay=0.05)
print(f"Found {len(reports)} polizei reports")
EOF

# Test meetings parser
python3 << 'EOF'
from scrap import get_html, parse_meeting_html
html = get_html("https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege")
meetings = parse_meeting_html(html)
print(f"Found {len(meetings)} meetings")
EOF
```

---

## Recovery Steps

### Step 1: Deploy Fixed Code
```bash
# Push new commits with parser fixes
git push origin main

# Wait for image build (GitHub Actions)
# Image will be pushed to ghcr.io/miklyx/berlin_stats:latest
```

### Step 2: Trigger Deployment Rollout
```bash
kubectl -n berlin-stats rollout restart deployment/berlin-stats
# or let K8s auto-restart with imagePullPolicy: Always
```

### Step 3: Verify Health
```bash
# Wait ~30s for pod startup
# Check /health/scraper endpoint
curl -H "X-Password: xxx" http://berlin-stats:8000/health/scraper | jq .

# Should show:
# {
#   "status": "healthy",
#   "last_poll": "2026-11-26T09:00:00Z",
#   "last_result": [50, 1289]
# }
```

### Step 4: (Optional) Apply CronJob for Redundancy
```bash
# Apply independent scheduled scraping (runs every 12h)
kubectl apply -f k8s/cronjob.yaml

# Verify
kubectl -n berlin-stats get cronjob
```

---

## Database Location

**Production**: PostgreSQL in K8s cluster
- Namespace: `berlin-stats` or `postgres`
- Secret: `berlin-stats-db` → DATABASE_URL

**Local SQLite** (`polizei.db`): **OBSOLETE** - not used by code

---

## Monitoring Going Forward

### Add Pod Probe for Scraper Health
```yaml
# Add to Deployment spec.containers[0]
livenessProbe:
  httpGet:
    path: /health/scraper
    port: 8000
  periodSeconds: 300  # Check every 5 minutes
  timeoutSeconds: 10
  failureThreshold: 2  # Restart after 2 failures (10+ min)
```

### Add AlertManager Rule (Optional)
```bash
# Alert if scraper unhealthy for more than 36 hours
alert: ScraperNotRunning
expr: |
  increase(berlin_stats_scraper_hours_since_poll[1h]) > 36
```

---

## Expected Behavior After Fix

✅ Both `polizei` and `meetings` tables update regularly
✅ `/health/scraper` endpoint shows recent poll time
✅ CronJob runs every 12 hours as backup
✅ Error logs show parsing issues (if any) with context
✅ No silent failures

---

## Files Changed

- `scrap.py`: Fixed parser None-handling
- `main.py`: Added scraper health tracking and /health/scraper endpoint
- `db.py`: Better init_db error logging
- `k8s/cronjob.yaml`: Improved reliability and logging
- `TROUBLESHOOTING.md`: This guide (enhanced)
