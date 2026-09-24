# REWIND task runner. On native Windows without make, use: pwsh scripts/dev.ps1 <target>
SHELL := bash
ifeq ($(OS),Windows_NT)
  PY := backend/.venv/Scripts/python
else
  PY := backend/.venv/bin/python
endif

.PHONY: setup setup-backend setup-frontend dev backend frontend test test-backend test-frontend lint demo train contracts clean

setup: setup-backend setup-frontend

setup-backend:
	python -m venv backend/.venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e "backend[dev,perf]"

setup-frontend:
	cd frontend && npm install

dev:
	$(MAKE) -j2 backend frontend

backend:
	cd backend && ../$(PY) -m uvicorn rewind.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && ../$(PY) -m pytest -q

test-frontend:
	cd frontend && npm test

lint:
	cd backend && ../$(PY) -m ruff check rewind tests ../scripts && ../$(PY) -m mypy rewind
	cd frontend && npm run lint && npm run typecheck

contracts:
	$(PY) scripts/gen_data_contracts.py

demo:
	$(PY) scripts/make_demo.py

train:
	$(PY) -m rewind.training.synth_dataset
	$(PY) -m rewind.training.train_temporal
	$(PY) -m rewind.training.train_xgb
	$(PY) -m rewind.training.evaluate

clean:
	rm -rf data/runs/* data/synthetic/* frontend/dist
