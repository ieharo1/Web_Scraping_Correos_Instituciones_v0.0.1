.PHONY: run-local run-auto validate clean

run-local:
	python apps/run_pipeline.py --mode local

run-auto:
	python apps/run_pipeline.py --mode auto

validate:
	python apps/validate_pipeline.py

clean:
	powershell -Command "if (Test-Path data/raw) { Remove-Item data/raw/*.ndjson -Force -ErrorAction SilentlyContinue }; if (Test-Path data/outputs) { Remove-Item data/outputs/*.txt,data/outputs/*.json -Force -ErrorAction SilentlyContinue }; if (Test-Path data/lakehouse/contact_lakehouse.db) { Remove-Item data/lakehouse/contact_lakehouse.db -Force }"
