-- Runs only on first init of the data volume. MLflow runs its own migrations, so it gets its own DB.
CREATE DATABASE mlflow OWNER decisionflow;
