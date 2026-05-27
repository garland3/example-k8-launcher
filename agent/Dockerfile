# Base image for the agent Pod's main container.
#
# We bake every supported agent CLI into one image so AGENT_KIND just
# picks which one to run. In a real deployment you'd probably build a
# slimmer per-kind image; this is a teaching image.
FROM node:20-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PNPM_HOME=/usr/local/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq python3 python3-pip ripgrep tini \
    && rm -rf /var/lib/apt/lists/*

# Install the agent CLIs. Each line is independent so users can comment
# out anything they don't need.
RUN npm install -g \
      opencode-ai \
      @anthropic-ai/claude-code \
      @openai/codex \
    && npm cache clean --force
# cline is a VS Code extension, not a CLI; placeholder so AGENT_KIND=cline
# fails with a clear message.

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY hooks/ /usr/local/lib/agent-hooks/
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/lib/agent-hooks/*.sh

# OpenShift-friendly: arbitrary UID in group 0.
RUN mkdir -p /workspace && chgrp -R 0 /workspace && chmod -R g=u /workspace
WORKDIR /workspace
USER 1001

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
