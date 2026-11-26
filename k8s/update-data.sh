#!/bin/bash
# Update polizei and meeting data in K8s cluster
set -e

NAMESPACE="berlin-stats"
SERVICE="berlin-stats"
PASSWORD="${SECRET_PASSWORD}"

if [ -z "$PASSWORD" ]; then
    echo "Error: SECRET_PASSWORD not set"
    exit 1
fi

echo "🔄 Triggering polizei scrape..."
kubectl -n "$NAMESPACE" exec -it deployment/berlin-stats -- curl -s -X GET "http://localhost:8000/update_polizei" -H "X-Password: $PASSWORD" | jq . || echo "Polizei update completed"

echo "🔄 Triggering meetings scrape..."
kubectl -n "$NAMESPACE" exec -it deployment/berlin-stats -- curl -s -X GET "http://localhost:8000/update_meetings" -H "X-Password: $PASSWORD" | jq . || echo "Meetings update completed"

echo "✓ Done!"
