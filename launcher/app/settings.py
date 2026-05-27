from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All knobs are env vars so the Helm chart can wire them through.

    Anything that controls *where* agents run, *what image* they pull, or
    *which hosts* they may reach lives here.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Storage -----------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./demo.db"

    # --- Where do agent Jobs land? ----------------------------------------
    agent_namespace: str = "agent-runs"
    agent_service_account: str = "agent-runner"

    # --- Where do agent container images come from? -----------------------
    # Image is built as f"{registry}/{kind}:{tag}" unless the user
    # overrides via the launch form.
    agent_image_registry: str = "ghcr.io/your-org"
    agent_image_tag: str = "latest"

    # --- Egress allowlist passed to the nginx sidecar ---------------------
    # Comma-separated list of hostnames the agent is allowed to reach.
    egress_allowlist: str = "api.anthropic.com,api.openai.com"

    # --- nginx sidecar image ----------------------------------------------
    nginx_image: str = "ghcr.io/your-org/nginx-egress:latest"

    # --- How the agent calls back to us -----------------------------------
    # The agent posts events to this URL. Resolved from inside the cluster,
    # so default is the in-cluster service DNS.
    launcher_internal_url: str = "http://launcher.agent-launcher.svc:8000"

    # --- Secret with provider API keys mounted into the agent -------------
    agent_api_keys_secret: str = "agent-api-keys"

    # --- Job lifecycle ----------------------------------------------------
    job_ttl_seconds: int = 3600
    job_active_deadline_seconds: int = 1800


settings = Settings()
