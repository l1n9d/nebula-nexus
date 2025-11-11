"""
Airflow DAG for PubMed Medical Paper Ingestion Pipeline

This DAG:
1. Verifies services (PostgreSQL, PubMed API)
2. Fetches papers from PubMed based on search query
3. Stores metadata in PostgreSQL
4. Indexes papers to OpenSearch for hybrid search
5. Generates ingestion report

Schedule: Daily at 2 AM UTC
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Import task functions
from pubmed_ingestion.fetching import fetch_daily_papers
from pubmed_ingestion.indexing import index_recent_papers
from pubmed_ingestion.reporting import generate_ingestion_report
from pubmed_ingestion.setup import verify_services

# Default arguments
default_args = {
    "owner": "rag-team",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Create DAG
dag = DAG(
    "pubmed_paper_ingestion",
    default_args=default_args,
    description="Fetch and index medical papers from PubMed",
    schedule_interval="0 2 * * *",  # Daily at 2 AM UTC
    catchup=False,
    tags=["pubmed", "medical", "rag", "ingestion"],
)

# Task 1: Verify services
verify_task = PythonOperator(
    task_id="verify_services",
    python_callable=verify_services,
    dag=dag,
)

# Task 2: Fetch papers from PubMed
fetch_task = PythonOperator(
    task_id="fetch_papers",
    python_callable=fetch_daily_papers,
    dag=dag,
)

# Task 3: Index to OpenSearch
index_task = PythonOperator(
    task_id="index_papers",
    python_callable=index_recent_papers,
    dag=dag,
)

# Task 4: Generate report
report_task = PythonOperator(
    task_id="generate_report",
    python_callable=generate_ingestion_report,
    dag=dag,
)

# Define task dependencies
verify_task >> fetch_task >> index_task >> report_task




