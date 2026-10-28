FROM instrumentisto/haraka:3.1.5@sha256:55484431233c190e09b15e71cfc53f96a10ea4a490c35308b45315b7ec335a1f


RUN apk add --no-cache gettext openssl && \
    npm install --prefix /usr/local/lib/node_modules/Haraka @zone-eu/haraka-plugin-wildduck && \
    ln -s \
      /usr/local/lib/node_modules/Haraka/node_modules/@zone-eu/haraka-plugin-wildduck \
      /usr/local/lib/node_modules/Haraka/node_modules/haraka-plugin-wildduck

COPY config.template/ /app/config.template/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
