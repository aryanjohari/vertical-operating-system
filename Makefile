# Test targets: unit (mocked), deployment (Railway/Vercel), or both.
# Unit tests: pytest backend/tests/ (no API_BASE_URL needed).
# Deployment: pytest tests/ (set API_BASE_URL and optionally FRONTEND_URL).

.PHONY: test test-unit test-deploy test-all

test: test-unit

test-unit:
	pytest backend/tests/ -v

test-deploy:
	@if [ -z "$$API_BASE_URL" ]; then \
		echo "Set API_BASE_URL to run deployment tests, e.g.: export API_BASE_URL=https://your-backend.railway.app"; \
		exit 1; \
	fi
	pytest tests/ -v

test-all: test-unit
	@if [ -n "$$API_BASE_URL" ]; then \
		pytest tests/ -v; \
	else \
		echo "Skipping deployment tests (API_BASE_URL not set). Set it to run against Railway/Vercel."; \
	fi
