.PHONY: flutter-test help backend-install backend-run backend-test backend-lint backend-format admin-install admin-dev admin-build flutter-bootstrap flutter-analyze db-up db-down backend-migrate

help:
	@echo "ZURUV developer commands"
	@echo "  make backend-install    create backend/.venv and install dependencies"
	@echo "  make backend-run        run FastAPI on http://localhost:8008"
	@echo "  make backend-test       run backend tests"
	@echo "  make backend-lint       ruff check + format check"
	@echo "  make backend-format     ruff format"
	@echo "  make admin-install      npm install for the admin site"
	@echo "  make admin-dev          run the admin site on http://localhost:3000"
	@echo "  make admin-build        production build of the admin site"
	@echo "  make flutter-bootstrap  generate Android/iOS platform folders and fetch packages (mobile app)"
	@echo "  make flutter-analyze    flutter analyze for the shared package and the mobile app"
	@echo "  make flutter-test       flutter test for the shared package and the mobile app"
	@echo "  make db-up / db-down    local PostgreSQL container"

backend-install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip && pip install -r requirements-dev.txt

backend-run:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8008

backend-test:
	cd backend && . .venv/bin/activate && pytest

backend-lint:
	cd backend && . .venv/bin/activate && ruff check . && ruff format --check .

backend-format:
	cd backend && . .venv/bin/activate && ruff format . && ruff check --fix .

admin-install:
	cd apps/admin_web && npm install

admin-dev:
	cd apps/admin_web && npm run dev

admin-build:
	cd apps/admin_web && npm run build

flutter-bootstrap:
	./scripts/bootstrap_flutter.sh

flutter-analyze:
	cd packages/flutter_shared && flutter analyze
	cd apps/mobile_app && flutter analyze

flutter-test:
	cd packages/flutter_shared && flutter test
	cd apps/mobile_app && flutter test

db-up:
	docker compose up -d db

db-down:
	docker compose down

backend-migrate:
	cd backend && . .venv/bin/activate && alembic upgrade head
