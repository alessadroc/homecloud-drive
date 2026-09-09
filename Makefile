PROD = docker compose -f docker-compose.yml -f docker-compose.prod.yml

.PHONY: deploy logs ps down restart status

deploy:
	@test -f docker-compose.prod.yml || (echo "Wrong directory - run from the project root" && exit 1)
	git pull
	$(PROD) up -d --build
	@echo "--- restart policy check ---"
	@docker inspect --format '{{.Name}} {{.HostConfig.RestartPolicy.Name}}' \
		$$($(PROD) ps -q)

logs:
	$(PROD) logs -f

ps:
	$(PROD) ps

status: ps

down:
	$(PROD) down

restart:
	$(PROD) up -d --force-recreate