This is an excellent and very practical constraint. If you can only deploy an instance on GKE (Google Kubernetes Engine) or even a single GCE (Google Compute Engine) VM, the serverless, event-driven architecture is no longer an option.

In this scenario, the best approach is a classic, robust **batch processing model** using a scheduled script (CronJob). This is a well-understood, reliable, and straightforward pattern.

### The Architecture: Scheduled Batch Processing on GKE

1.  **Cloud Run Generates Logs:** Your FastAPI application still runs (let's assume on a GKE pod now) and writes its structured JSON logs to standard output.
2.  **Cloud Logging Captures:** Google Cloud Logging automatically collects all logs from your GKE cluster's standard output.
3.  **Scheduled Script (CronJob):** The core of this new architecture is a **Kubernetes CronJob**. This is a GKE-native resource that runs a containerized script on a schedule you define (e.g., every 5 minutes).
4.  **Log Querying:** The script inside the CronJob will use the Google Cloud Logging client library to query and export all the new `ai_interactions` logs that have been generated since its last run.
5.  **Data Transformation:** The script will parse the JSON logs and transform them into the correct format for a BigQuery insert.
6.  **BigQuery Batch Insert:** Finally, the script will use the BigQuery client library to perform a batch `insert_rows` operation, loading all the new log data into your `feedback.ai_interactions` table in one efficient call.



---

### Step-by-Step Implementation Guide

#### Prerequisite: BigQuery Table

The BigQuery table `feedback.ai_interactions` should be created exactly as described in the previous serverless plan. The destination remains the same.

---

### Step 1: Create the Python ETL Script

This script will be the heart of your CronJob. It will contain the logic to query logs and insert them into BigQuery.

1.  **Create a new folder** for your script, for example `gke-log-etl/`.
2.  Inside this folder, create three files: `main.py`, `requirements.txt`, and `Dockerfile`.

**File: `gke-log-etl/main.py`**
```python
import os
import json
from datetime import datetime, timedelta, timezone
from google.cloud import logging_v2, bigquery

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "aicontrol-8c59b")
BQ_DATASET = os.environ.get("BQ_DATASET", "feedback")
BQ_TABLE = os.environ.get("BQ_TABLE", "ai_interactions")
LOGGING_FILTER = (
    'resource.type="k8s_container" ' # Changed from cloud_run_revision to k8s_container
    'AND resource.labels.cluster_name="your-gke-cluster-name" ' # IMPORTANT: Add your cluster name
    'AND jsonPayload.interaction_id!=""'
)
# How far back to look for logs on each run
LOOKBACK_MINUTES = 10 

# --- Clients ---
LOGGING_CLIENT = logging_v2.LoggingServiceV2Client()
BQ_CLIENT = bigquery.Client(project=PROJECT_ID)
TABLE_ID = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

def main():
    """
    Main function to query logs and load them into BigQuery.
    """
    print(f"Starting ETL job at {datetime.now(timezone.utc).isoformat()}")
    
    # 1. Query Logs
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=LOOKBACK_MINUTES)
    
    # Format for Google Cloud Logging API filter
    filter_str = (
        f'{LOGGING_FILTER} AND '
        f'timestamp >= "{start_time.strftime("%Y-%m-%dT%H:%M:%SZ")}" AND '
        f'timestamp < "{end_time.strftime("%Y-%m-%dT%H:%M:%SZ")}"'
    )
    
    print(f"Querying logs with filter: {filter_str}")
    
    resource_names = [f"projects/{PROJECT_ID}"]
    
    log_entries = LOGGING_CLIENT.list_log_entries(
        resource_names=resource_names,
        filter_=filter_str,
        order_by="timestamp desc"
    )
    
    rows_to_insert = []
    processed_ids = set()
    
    # 2. Transform Logs
    for entry in log_entries:
        payload = entry.json_payload
        interaction_id = payload.get('interaction_id')
        
        # Avoid duplicates if lookback windows overlap
        if interaction_id in processed_ids:
            continue
        
        row = {
            "event_timestamp": entry.timestamp.isoformat(),
            "event_type": payload.get('event'),
            "interaction_id": interaction_id,
            "endpoint_name": payload.get('endpoint_name'),
            "username": payload.get('username'),
            "control_id": payload.get('control_id'),
            "section_name": payload.get('section_name'),
            "prompt_template_id": payload.get('prompt_template_id'),
            "ai_model_name": payload.get('ai_model_name'),
            "request_payload": json.dumps(payload.get('request_payload')),
            "response_payload": json.dumps(payload.get('response_payload')),
            "response_latency_ms": payload.get('response_latency_ms'),
            "error_message": payload.get('error_message')
        }
        rows_to_insert.append(row)
        processed_ids.add(interaction_id)
        
    if not rows_to_insert:
        print("No new log entries to process.")
        return

    print(f"Transformed {len(rows_to_insert)} log entries for BigQuery.")

    # 3. Batch Insert into BigQuery
    errors = BQ_CLIENT.insert_rows_json(TABLE_ID, rows_to_insert)
    if not errors:
        print(f"Successfully inserted {len(rows_to_insert)} rows into {TABLE_ID}.")
    else:
        print(f"BigQuery insert errors: {errors}")

if __name__ == "__main__":
    main()
```

**File: `gke-log-etl/requirements.txt`**
```
google-cloud-logging
google-cloud-bigquery
```

**File: `gke-log-etl/Dockerfile`**
```dockerfile
FROM python:3.11-slim
WORKDIR /etl
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["python", "main.py"]
```

---

### Step 2: Build and Push the ETL Container Image

Before you can run the script on GKE, you need to package it as a Docker image and push it to a container registry.

1.  **Build the image.** Run this from inside the `gke-log-etl/` directory.
    ```bash
    docker build -t gcr.io/aicontrol-8c59b/log-etl:latest .
    ```
2.  **Authenticate Docker with Google Container Registry.**
    ```bash
    gcloud auth configure-docker
    ```
3.  **Push the image.**
    ```bash
    docker push gcr.io/aicontrol-8c59b/log-etl:latest
    ```

---

### Step 3: Create and Deploy the Kubernetes CronJob

This is the final step. You will create a YAML file that defines the scheduled job.

**Create a file named `cronjob.yaml`:**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bq-log-etl-cronjob
spec:
  # Run every 5 minutes
  schedule: "*/5 * * * *"
  # Prevents jobs from running concurrently if one takes longer than 5 minutes
  concurrencyPolicy: Forbid
  # Keeps the last successful and failed jobs for debugging
  successfulJobsHistoryLimit: 1
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      template:
        spec:
          # IMPORTANT: You may need to specify a serviceAccountName that has permissions
          # to read logs (roles/logging.viewer) and write to BigQuery (roles/bigquery.dataEditor).
          # serviceAccountName: your-gke-service-account
          containers:
          - name: log-etl-container
            image: gcr.io/aicontrol-8c59b/log-etl:latest
            env:
            - name: GCP_PROJECT_ID
              value: "aicontrol-8c59b"
            - name: BQ_DATASET
              value: "feedback"
            - name: BQ_TABLE
              value: "ai_interactions"
            # --- CHANGE: Added resource requests and limits ---
            resources:
              requests:
                # Guaranteed minimum resources for the pod
                cpu: "100m"      # 1/10th of a CPU core
                memory: "256Mi"  # 256 Mebibytes of RAM
              limits:
                # Maximum resources the pod is allowed to use
                cpu: "500m"      # 1/2 of a CPU core
                memory: "512Mi"  # 512 Mebibytes of RAM
          restartPolicy: OnFailure
```

**Deploy the CronJob to your GKE cluster:**
```bash
kubectl apply -f cronjob.yaml
```

### Step 4: Create the bootstrap table in bq

```bash
bq mk --table \
  --description "Stores structured logs for GRC Co-pilot AI interactions" \
  aicontrol-8c59b:feedback.ai_interactions \
  ./bq_schema.json
```

For changes use:

```bash
bq update feedback.ai_interactions ./bq_schema.json
```

The  bq_schema.json file content is

```json
[
  {"name": "event_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "event_type", "type": "STRING", "mode": "NULLABLE"},
  {"name": "interaction_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "endpoint_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "username", "type": "STRING", "mode": "NULLABLE"},
  {"name": "control_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "section_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "prompt_template_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "ai_model_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "request_payload", "type": "JSON", "mode": "NULLABLE"},
  {"name": "response_payload", "type": "JSON", "mode": "NULLABLE"},
  {"name": "response_latency_ms", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "error_message", "type": "STRING", "mode": "NULLABLE"},
  {"name": "user_feedback_score", "type": "INTEGER", "mode": "NULLABLE"}
]
```

### What This Achieves

1.  **Scheduled Execution:** Your GKE cluster will now automatically launch a new pod running your ETL script every five minutes.
2.  **Efficient Data Extraction:** The script will query only the most recent logs from Cloud Logging, preventing reprocessing of old data.
3.  **Reliable Batch Loading:** The data is loaded into BigQuery in efficient batches.
4.  **Complete Decoupling:** This entire process runs independently of your main FastAPI application. If the ETL script fails for some reason, your main application is completely unaffected. The next run in 5 minutes will simply pick up the logs that were missed.

This batch processing architecture is a robust, reliable, and cost-effective way to achieve your analytics goals within the constraints of a GKE environment.