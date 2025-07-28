gcloud run deploy gcr-copilot \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="DEMO_PASSCODE=YOUR_DEMO_PASSCODE,SECRET_KEY=YOUR_SECRET_KEY"