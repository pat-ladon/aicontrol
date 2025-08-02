Excellent. This is a much more secure and robust architecture. Using a scheduled Cloud Run Job with a mounted private bucket is a professional, production-grade pattern.

Here is a complete guide to implement this, using only `gcloud` commands and manual steps, without Terraform.

---

### High-Level Architecture (Secure & Automated)

1.  **Cloud Run Job (The Worker):** A containerized Python script.
2.  **Cloud Scheduler (The Trigger):** An integrated trigger that executes the Cloud Run Job on a schedule (e.g., daily).
3.  **BigQuery (Data Source):** The job queries the `aicontrol-8c59b.app_logging.python` table.
4.  **Cloud Storage Bucket (Private Data Store):** The job writes a `metrics.json` file to a private bucket named `aicontrol-8c59b`.
5.  **Cloud Run Service (The "aicontrol" App):** Your main web application will have the private GCS bucket **mounted as a local directory** (e.g., `/mnt/gcs`).
6.  **New API Endpoint:** The web app will have a new endpoint (e.g., `/api/metrics`) that reads the `metrics.json` file from the mounted directory and serves it to the frontend.
7.  **Chart.js (The Consumer):** The frontend JavaScript now fetches data from `/api/metrics` instead of a public URL.

---

### Step 1: Prepare the Job Code

This is the Python script that will run on a schedule.

1.  Create a new folder in your project root named `metrics_job`.
2.  Inside `metrics_job`, create these three files:

**File: `metrics_job/main.py`**
```python
import os
import json
from datetime import datetime, timedelta
from google.cloud import bigquery, storage

def run_metrics_job():
    # --- Configuration (from environment variables) ---
    PROJECT_ID = os.environ.get("GCP_PROJECT")
    BQ_TABLE_ID = os.environ.get("BQ_TABLE_ID")
    GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

    if not all([PROJECT_ID, BQ_TABLE_ID, GCS_BUCKET_NAME]):
        print("Error: Missing one or more required environment variables.")
        return

    print(f"Starting metrics generation job for table {BQ_TABLE_ID}...")

    bq_client = bigquery.Client()
    storage_client = storage.Client()
    
    # --- Define and Run Queries ---
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
    # Note the change to query the 'python' table
    trend_query = f"""
        SELECT TIMESTAMP_TRUNC(timestamp, DAY) AS d, COUNT(DISTINCT JSON_VALUE(payload, '$.username')) AS u, COUNT(*) AS i 
        FROM `{BQ_TABLE_ID}` 
        WHERE timestamp >= '{thirty_days_ago}' GROUP BY 1 ORDER BY 1;
    """
    endpoint_query = f"""
        SELECT JSON_VALUE(payload, '$.endpoint_name') as e, COUNT(*) as i 
        FROM `{BQ_TABLE_ID}` 
        GROUP BY 1 ORDER BY 2 DESC;
    """
    total_interactions_query = f"SELECT COUNT(*) as total FROM `{BQ_TABLE_ID}`;"
    
    try:
        # Execute queries and format results
        trend_results = bq_client.query(trend_query).result()
        endpoint_results = bq_client.query(endpoint_query).result()
        total_interactions_result = list(bq_client.query(total_interactions_query).result())

        final_metrics = {
            "generated_at_utc": datetime.utcnow().isoformat(),
            "trend_data": {
                "labels": [row.d.strftime('%Y-%m-%d') for row in trend_results],
                "active_users": [row.u for row in trend_results],
                "interactions": [row.i for row in trend_results]
            },
            "endpoint_data": {
                "labels": [row.e for row in endpoint_results if row.e],
                "interactions": [row.i for row in endpoint_results if row.e]
            },
            "total_interactions": total_interactions_result[0].total if total_interactions_result else 0
        }

        # --- Upload to Cloud Storage (NO LONGER PUBLIC) ---
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob("metrics.json")
        blob.upload_from_string(json.dumps(final_metrics, indent=2), content_type="application/json")
        
        print(f"Successfully generated and uploaded metrics.json to gs://{GCS_BUCKET_NAME}")
    except Exception as e:
        print(f"FATAL: Error generating metrics: {e}")
        raise e

if __name__ == "__main__":
    run_metrics_job()
```

**File: `metrics_job/requirements.txt`**
```
google-cloud-bigquery
google-cloud-storage
```

**File: `metrics_job/Dockerfile`**
```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
WORKDIR /job
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["python", "main.py"]
```

---

### Step 2: Create the Private Cloud Storage Bucket

Run this command in your terminal to create the bucket.

```bash
gcloud storage buckets create gs://aicontrol-8c59b --project=aicontrol-8c59b --location=us-central1 --uniform-bucket-level-access
```
This creates a private bucket named `aicontrol-8c59b`.

---

### Step 3: Deploy the Scheduled Cloud Run Job

This single command builds your job's container, deploys it as a Cloud Run Job, and sets up the daily trigger.

```bash
gcloud run jobs deploy metrics-generator \
  --source ./metrics_job \
  --region us-central1 \
  --schedule "0 0 * * *" \
  --set-env-vars "GCP_PROJECT=aicontrol-8c59b,BQ_TABLE_ID=aicontrol-8c59b.app_logging.python,GCS_BUCKET_NAME=aicontrol-8c59b"
```
During the deployment, `gcloud` may ask you to create and assign a service account for the job. Say yes. Note down the service account email it uses (e.g., `...-compute@developer.gserviceaccount.com`).

---

### Step 4: Grant Permissions to the Job's Service Account

The job needs permission to read from BigQuery and write to your new bucket.

Replace `JOB_SERVICE_ACCOUNT_EMAIL` with the email from the previous step.

```bash
# Grant permission to read BigQuery data
gcloud projects add-iam-policy-binding aicontrol-8c59b \
  --member="serviceAccount:JOB_SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataViewer"

# Grant permission to write to the Cloud Storage bucket
gcloud storage buckets add-iam-policy-binding gs://aicontrol-8c59b \
  --member="serviceAccount:JOB_SERVICE_ACCOUNT_EMAIL" \
  --role="roles/storage.objectAdmin"
```

---

### Step 5: Modify and Redeploy the Main Web App

Now we'll update the main `aicontrol` service to read from the mounted bucket.

**1. Add a New API Endpoint in `main.py`:**
This endpoint will read the JSON file from the mounted directory and serve it.
```python
# In main.py, add this new endpoint

@app.get("/api/metrics")
async def get_metrics():
    """
    Reads the metrics.json file from the mounted GCS volume and returns it.
    """
    # The mount path for the bucket inside the Cloud Run container
    metrics_path = Path("/mnt/gcs/metrics.json")
    
    if not metrics_path.exists():
        return {"error": "Metrics file not found. The job may not have run yet."}
    
    try:
        with open(metrics_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        log.error("metrics_read_failed", error=str(e))
        return {"error": f"Failed to read or parse metrics file: {e}"}
```

**2. Update the Frontend JavaScript in `templates/index.html`:**
Change the `fetch` URL to point to your new local API endpoint.
```javascript
// In the <script> block at the bottom of index.html
// ...
// CHANGE THIS LINE:
const METRICS_URL = `/api/metrics`;

fetch(METRICS_URL)
    .then(response => response.json())
    // ... rest of the script is the same
```

**3. Redeploy the `aicontrol` Service with the Bucket Mounted:**
This is the final deployment command. It's your normal deploy command plus the crucial `--mount-gcs-volume` flag.

```bash
gcloud run deploy aicontrol \
  --source . \
  --region us-central1 \
  --memory 1Gi \
  --mount-gcs-volume bucket=aicontrol-8c59b,mount-path=/mnt/gcs \
  --set-env-vars "PY_ENV=prod,..." # Add your other env vars here
```
Cloud Run will use a service account for this service. It also needs permission to read from the bucket. Replace `SERVICE_ACCOUNT_EMAIL` with your `aicontrol` service's identity.

```bash
# Grant permission for the main app to read from the bucket
gcloud storage buckets add-iam-policy-binding gs://aicontrol-8c59b \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/storage.objectViewer"
```

---

### Step 6: Test the Pipeline

1.  **Manually Run the Job:** Go to the Cloud Run console, find the "Jobs" tab, select `metrics-generator`, and click **EXECUTE**. Check its logs to confirm it ran successfully.
2.  **Verify the File:** Go to the Cloud Storage console and check your `aicontrol-8c59b` bucket. You should see `metrics.json` inside.
3.  **Load Your App:** Open your `aicontrol` web application. The dashboard on the front page should now load the data by calling your new `/api/metrics` endpoint.