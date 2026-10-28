# The official plugin marketplace (plugins.hubra.club): the signed index.json
# and plugin archives that .github/workflows/plugins.yml builds into public/,
# served as static files. Built and pushed by that workflow, not by hand.
FROM nginx:alpine@sha256:54f2a904c251d5a34adf545a72d32515a15e08418dae0266e23be2e18c66fefa
COPY app/deploy/plugins/nginx.conf /etc/nginx/conf.d/default.conf
COPY public/ /usr/share/nginx/html/
# The workflow signs under umask 077, so the files arrive as 0600 and the
# nginx worker (user nginx) answered 403. Make them world-readable.
RUN chmod -R a+rX /usr/share/nginx/html
