FROM alpine:3.19
RUN apk add --no-cache inotify-tools docker-cli
COPY watch.sh /watch.sh
RUN chmod +x /watch.sh
ENTRYPOINT ["/watch.sh"]
