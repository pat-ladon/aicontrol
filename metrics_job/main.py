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
        SELECT 
        TIMESTAMP_TRUNC(timestamp, DAY) AS d, 
        COUNT(DISTINCT jsonPayload.username) AS u, 
        COUNT(DISTINCT jsonPayload.interaction_id) AS i 
        FROM `{BQ_TABLE_ID}` 
        WHERE timestamp >= '{thirty_days_ago}' 
        GROUP BY 1 ORDER BY 1;
    """
    endpoint_query = f"""
        SELECT jsonPayload.endpoint_name as e, COUNT(DISTINCT jsonPayload.interaction_id) as i 
        FROM `{BQ_TABLE_ID}` 
        WHERE jsonPayload.endpoint_name IS NOT NULL AND jsonPayload.interaction_id IS NOT NULL 
        GROUP BY 1 ORDER BY 2 DESC;
    """
    total_interactions_query = f"""
        SELECT COUNT(DISTINCT jsonPayload.interaction_id) as total 
        FROM `{BQ_TABLE_ID}` WHERE jsonPayload.interaction_id IS NOT NULL;
    """
        
    try:
        # Execute queries and format results
        trend_results = list(bq_client.query(trend_query).result())
        endpoint_results = list(bq_client.query(endpoint_query).result())
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