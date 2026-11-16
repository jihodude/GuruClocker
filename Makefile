# guruclocker developer commands. Friends don't need these: they double-click mac.command or windows.bat.
# Type `make` (or `make help`) to list them.

IMAGE  := guruclocker
VOLUME := guruclocker-models
# Pass extra arguments through, e.g.  make run LINKS="https://..., https://..."  or  make run FILE=links.txt
RUN_ARGS = $(if $(LINKS),--links "$(LINKS)") $(if $(FILE),--file "$(FILE)") $(ARGS)

.DEFAULT_GOAL := help
.PHONY: help setup run check test clean docker-build docker-run docker-check docker-clean

help: ## List the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

setup: ## Install everything natively (Mac/Linux): uv, Python, packages, .env
	@command -v uv >/dev/null 2>&1 || { echo "Installing uv (Python installer)..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }
	uv sync --frozen
	@test -f .env || { cp .env.example .env; echo "Created .env (the program will ask for your API key)"; }

run: ## Run natively. Asks for links, or: make run LINKS="url, url" / FILE=links.txt
	uv run --frozen python -m guruclocker $(RUN_ARGS)

check: ## Print a system check (GPU, model, key, folders)
	uv run --frozen python -m guruclocker --check

test: ## Run the unit tests
	uv run --frozen pytest -q

clean: ## Delete the local virtualenv and caches (keeps output/ and .env)
	rm -rf .venv .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

docker-build: ## Build the optional Docker image
	docker build -f dev/Dockerfile -t $(IMAGE) .

# Uses the NVIDIA GPU when Docker can see one, otherwise CPU. Same steps as windows.bat.
docker-run: docker-build ## Run inside Docker (GPU if available). Same LINKS=/FILE= options
	@mkdir -p output; test -f .env || cp .env.example .env
	@GPUS=$$(docker run --rm --gpus all --entrypoint python $(IMAGE) -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())" 2>/dev/null || echo 0); \
	if [ "$${GPUS:-0}" -gt 0 ] 2>/dev/null; then FLAG="--gpus all"; echo "NVIDIA GPU found: fast mode"; \
	else FLAG=""; echo "No NVIDIA GPU visible to Docker: CPU mode (slower)"; fi; \
	TTY=$$([ -t 0 ] && echo "-t"); \
	docker run --rm -i $$TTY $$FLAG -v "$(CURDIR)/output:/app/output" -v "$(CURDIR)/.env:/app/.env" \
		-v $(VOLUME):/cache $(IMAGE) $(RUN_ARGS)

docker-check: docker-build ## System check inside Docker
	@test -f .env || cp .env.example .env
	docker run --rm -v "$(CURDIR)/.env:/app/.env" $(IMAGE) --check

docker-clean: ## Remove the Docker image and the downloaded speech model
	-docker rmi $(IMAGE)
	-docker volume rm $(VOLUME)
