FROM node:lts-alpine

WORKDIR /app

# Pin to a specific release tag for reproducible, supply-chain-safe builds.
# Update the tag after verifying compatibility with @zone-eu/zonemta-wildduck.
ARG ZONEMTA_TEMPLATE_REF=v1.11.2
RUN apk add --no-cache git gettext && \
    git clone --branch ${ZONEMTA_TEMPLATE_REF} --depth 1 https://github.com/zone-eu/zone-mta-template . && \
    npm install && \
    npm install @zone-eu/zonemta-wildduck

COPY config.template/ /app/config.template/
COPY plugins/ /app/plugins/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 587 465 2525 12080

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--config=config/zonemta.toml"]
