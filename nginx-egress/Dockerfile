# Forward-proxy sidecar.
#
# The folder is called "nginx-egress" historically; we actually use
# `tinyproxy` because it natively supports a destination allowlist for
# both plain HTTP and HTTPS (CONNECT) without extra modules.
FROM alpine:3.20

RUN apk add --no-cache tinyproxy bash

COPY tinyproxy.conf.template /etc/tinyproxy/tinyproxy.conf.template
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# OpenShift random-UID friendliness.
RUN mkdir -p /run/tinyproxy /var/log/tinyproxy /etc/tinyproxy \
 && chgrp -R 0 /run/tinyproxy /var/log/tinyproxy /etc/tinyproxy \
 && chmod -R g=u /run/tinyproxy /var/log/tinyproxy /etc/tinyproxy

EXPOSE 3128
USER 1001
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
