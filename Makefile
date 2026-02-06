DOCKER_COMPOSE=docker compose
RUN_CONTAINER=$(DOCKER_COMPOSE) run --rm -u `id -u`:`id -u` cost_care_service_commands
RUN_CONTAINER_DEV_TOOLS=$(DOCKER_COMPOSE) run --rm cost_care_service_commands


build:
	docker build --no-cache -f Dockerfile .
	$(DOCKER_COMPOSE) build --no-cache

bash:
	$(RUN_CONTAINER) bash


poetry_lock:
	$(RUN_CONTAINER_DEV_TOOLS) poetry lock

poetry_add: # -i args=name
	$(RUN_CONTAINER_DEV_TOOLS) poetry add $(args)

poetry_add_dev: # -i args=name
	$(RUN_CONTAINER_DEV_TOOLS) poetry add --dev $(args)

run_conversation:
	$(RUN_CONTAINER) python main.py

black:
	$(RUN_CONTAINER) black .

isort:
	$(RUN_CONTAINER) isort .

lint:
	$(RUN_CONTAINER) flake8

bandit:
	$(RUN_CONTAINER) bandit -r .

format: isort black lint bandit


unittests:
	$(RUN_CONTAINER_DEV_TOOLS) pytest -vv -s -p no:cacheprovider tests/unittests/
