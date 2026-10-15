FROM instrumentisto/haraka:3.1.5


RUN apk add --no-cache gettext openssl && \
    npm install --prefix /usr/local/lib/node_modules/Haraka @zone-eu/haraka-plugin-wildduck && \
    ln -s \
      /usr/local/lib/node_modules/Haraka/node_modules/@zone-eu/haraka-plugin-wildduck \
      /usr/local/lib/node_modules/Haraka/node_modules/haraka-plugin-wildduck

COPY config.template/ /app/config.template/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
