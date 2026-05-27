REGISTRY ?= ghcr.io/your-org
TAG      ?= latest

IMAGES = launcher agent nginx-egress

.PHONY: images push launcher agent nginx-egress helm-lint dev clean

images: $(IMAGES)

launcher:
	docker build -t $(REGISTRY)/agent-launcher:$(TAG) ./launcher

agent:
	docker build -t $(REGISTRY)/opencode:$(TAG)    ./agent
	docker tag    $(REGISTRY)/opencode:$(TAG) $(REGISTRY)/claude-code:$(TAG)
	docker tag    $(REGISTRY)/opencode:$(TAG) $(REGISTRY)/codex:$(TAG)

nginx-egress:
	docker build -t $(REGISTRY)/nginx-egress:$(TAG) ./nginx-egress

push:
	docker push $(REGISTRY)/agent-launcher:$(TAG)
	docker push $(REGISTRY)/opencode:$(TAG)
	docker push $(REGISTRY)/claude-code:$(TAG)
	docker push $(REGISTRY)/codex:$(TAG)
	docker push $(REGISTRY)/nginx-egress:$(TAG)

helm-lint:
	helm lint ./helm/launcher

# Run the launcher locally against your kubeconfig + a sqlite DB.
dev:
	cd launcher && \
	  DATABASE_URL=sqlite+aiosqlite:///./demo.db \
	  AGENT_NAMESPACE=agent-runs \
	  AGENT_IMAGE_REGISTRY=$(REGISTRY) \
	  LAUNCHER_INTERNAL_URL=http://host.docker.internal:8000 \
	  uvicorn app.main:app --reload

clean:
	rm -rf launcher/.venv launcher/demo.db
