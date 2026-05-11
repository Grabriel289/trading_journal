.PHONY: dev install reset backend frontend build

# One command: install (if needed) + start backend + frontend
dev:
	@./dev.sh

install:
	@./dev.sh --install-only

reset:
	@./dev.sh --reset

# Run components separately (assumes deps installed)
backend:
	.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build
