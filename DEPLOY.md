# Deployment Guide

## Current Status

✅ **5 commits pushed to main** (as of 2026-11-26 21:30)
✅ **Image building in GitHub Actions** (monitor at https://github.com/miklyx/berlin_stats/actions)

New fixes deployed:
1. Parser None-safety checks (critical)
2. Scraper health monitoring endpoint
3. Improved CronJob for redundancy
4. Better error tracking

---

## Deployment Steps on Raspberry Pi (192.168.178.29)

### Option A: Automatic (imagePullPolicy: Always)
```bash
# Already configured in deployment
# Image will auto-pull when it's available on ghcr.io
# Wait ~10 minutes for GitHub Actions to complete

# Monitor image build:
watch -n 10 'curl -s https://ghcr.io/v2/miklyx/berlin_stats/manifests/latest | jq .'
```

### Option B: Manual Restart (Faster)
```bash
# SSH to Raspberry
ssh kuliki@192.168.178.29

# Kill all running containers to force new pull
sudo pkill -f 'python.*main:app'

# Wait ~30 seconds for K3s to auto-restart them
# New image will be pulled

# Verify they're running
ps aux | grep 'python.*main:app' | grep -v grep
```

### Option C: Using kubectl (Requires sudoers NOPASSWD)

**Step 1: Configure sudoers for kuliki (run from Raspberry as root or with sudo)**
```bash
# SSH as root or with sudo access
ssh kuliki@192.168.178.29
sudo -i  # or su -

# Create sudoers file for kubectl and K3s commands
cat > /etc/sudoers.d/kuliki-k3s << 'EOF'
# Allow kuliki to run kubectl without password
kuliki ALL=(ALL) NOPASSWD: /usr/local/bin/kubectl

# Allow kuliki to kill/restart processes without password
kuliki ALL=(ALL) NOPASSWD: /bin/kill, /bin/pkill
EOF

# Verify syntax
visudo -c -f /etc/sudoers.d/kuliki-k3s

# Set correct permissions
chmod 440 /etc/sudoers.d/kuliki-k3s
```

**Step 2: Restart deployment**
```bash
# Now kuliki can run kubectl without password
sudo kubectl -n berlin-stats rollout restart deployment/berlin-stats

# Or for faster pull:
sudo kubectl set image deployment/berlin-stats -n berlin-stats \
  berlin-stats=ghcr.io/miklyx/berlin_stats:latest \
  --record=true

# Monitor rollout
kubectl -n berlin-stats rollout status deployment/berlin-stats

# Check new pods are running
kubectl -n berlin-stats get pods -o wide
```

---

## Verify Health After Deployment

### Check API Response
```bash
# From Raspberry or any host with network access
curl -H 'X-Password: acabdata' http://192.168.178.29/berlin-stats/health/scraper | jq .

# Expected response (after ~30 sec):
{
  "status": "healthy",
  "last_poll": "2026-11-26T21:30:00Z",
  "hours_since_poll": 0.1,
  "last_result": [50, 1289]
}
```

### Check Database Updates
```bash
# Connect to PostgreSQL from Raspberry
psql -U berlin_stats -d berlin_stats -c \
  "SELECT MAX(time) as last_polizei_update FROM polizei; 
   SELECT MAX(von) as last_meeting_update FROM meeting;"

# Should show today's date/time
```

### View Logs
```bash
# If you have kubectl access:
kubectl -n berlin-stats logs deployment/berlin-stats --tail=100 -f

# Without kubectl, check container logs via containerd:
# (requires root)
sudo crictl logs $(sudo crictl ps | grep berlin-stats | head -1 | awk '{print $1}')
```

---

## GitHub Actions Status

Track the image build at:
https://github.com/miklyx/berlin_stats/actions

The workflow will:
1. ✅ Run tests
2. ✅ Build Docker image (linux/arm64 for Raspberry)
3. ✅ Push to ghcr.io/miklyx/berlin_stats:latest
4. ✅ Push tagged image: ghcr.io/miklyx/berlin_stats:<commit-sha>

Expected build time: **5-10 minutes**

---

## CronJob Deployment (Optional)

For additional redundancy, deploy the CronJob:

```bash
# If you have kubectl access:
kubectl apply -f k8s/cronjob.yaml

# Check CronJob created:
kubectl -n berlin-stats get cronjob

# Monitor job runs:
kubectl -n berlin-stats get jobs -l job-type=scraper -w
```

The CronJob will:
- Run scraping every 12 hours (alternative to background poll_loop)
- Provide independent data updates if main pods fail
- Keep last 10 failed jobs for debugging

---

## Troubleshooting

### Pods not restarting after push

**Problem:** Image not being pulled
```bash
# Check current image hash
ps aux | grep python | grep -v grep | head -1

# Check if new image is available
crictl images | grep berlin_stats
```

**Solution:** Force image pull
```bash
# Kill container to force K3s restart
sudo pkill -f 'berlin-stats-.*python'

# K3s will auto-restart with imagePullPolicy: Always
```

### Health endpoint returns "unhealthy"

**Likely causes:**
1. Pod just started (hasn't run first poll yet)
2. Scraper failing silently (check logs)
3. Database connection lost

**Check pod logs:**
```bash
# Get pod name
ps aux | grep -o 'berlin-stats-.*python' | head -1

# View full container logs
sudo crictl logs <container_id> | tail -50
```

### Database not updating

**Verify table structure:**
```bash
# From Raspberry
psql -U berlin_stats -d berlin_stats -c "
  SELECT table_name FROM information_schema.tables 
  WHERE table_schema='public';
"
```

**Check for errors in parsing:**
Look for "textile div not found" or "Could not find" in logs - indicates website structure changed again.

---

## Monitoring Going Forward

### Add Health Probe to K8s Deployment
```yaml
# In manifest.yaml, add to pod spec:
livenessProbe:
  httpGet:
    path: /health/scraper
    port: 8000
  periodSeconds: 300  # Check every 5 min
  timeoutSeconds: 10
  failureThreshold: 2  # Restart after 10 min of failures
```

### Expected Update Schedule
- **Polizei**: ~50 new reports per day (run every 24h, actual varies)
- **Meetings**: ~10-20 new meetings per day (run every 24h)
- **CronJob backup**: Every 12h regardless of main poll

---

## Rollback (if needed)

If new version causes issues, rollback to previous:

```bash
# Get previous image SHA
git log --oneline | head -5
# Find pre-ac934e3 commit

# Force pull old image
docker pull ghcr.io/miklyx/berlin_stats:<old-sha>

# Or rebuild from tag
git checkout <previous-tag>
docker build -t berlin_stats:previous .
```

---

## Files Changed This Release

- `scrap.py`: Critical parser fixes
- `main.py`: Health tracking + /health/scraper
- `db.py`: Init error logging
- `k8s/cronjob.yaml`: Redundant scraping job
- `TROUBLESHOOTING.md`: Complete guide
- `DEPLOY.md`: This deployment guide
