FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS base
WORKDIR /app
COPY packages/api-client /packages/api-client
COPY packages/ui /packages/ui
COPY app/frontend/package.json app/frontend/package-lock.json* ./
# No install scripts: nothing in the tree needs one, and a compromised
# dependency must not run code while installing.
RUN npm ci --ignore-scripts
COPY app/frontend/ ./

FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM base AS builder
# Frontend URLs. By default the bundle gets __RUNTIME_*__ placeholders that
# app/deploy/nginx/40-hubra-runtime.sh fills in from the container's
# environment at start, so one image serves any host name. Pass real values
# as build args to bake them in instead.
ARG VITE_API_BASE=__RUNTIME_VITE_API_BASE__
ARG VITE_SSO_URL=__RUNTIME_VITE_SSO_URL__
ARG VITE_COS_URL=__RUNTIME_VITE_COS_URL__
ARG VITE_MANAGE_URL=__RUNTIME_VITE_MANAGE_URL__
ARG VITE_ADMIN_PORTAL_URL=__RUNTIME_VITE_ADMIN_PORTAL_URL__
ARG VITE_TENANT_APP_URL=__RUNTIME_VITE_TENANT_APP_URL__
ARG VITE_SUPPORT_URL=__RUNTIME_VITE_SUPPORT_URL__
ENV VITE_API_BASE=${VITE_API_BASE} \
    VITE_SSO_URL=${VITE_SSO_URL} \
    VITE_COS_URL=${VITE_COS_URL} \
    VITE_MANAGE_URL=${VITE_MANAGE_URL} \
    VITE_ADMIN_PORTAL_URL=${VITE_ADMIN_PORTAL_URL} \
    VITE_TENANT_APP_URL=${VITE_TENANT_APP_URL} \
    VITE_SUPPORT_URL=${VITE_SUPPORT_URL}
RUN npm run build
# The commit this image was built from (images.yml passes it), served as
# /version.json for manage's Diagnose page. Empty means a local build ("dev").
ARG GIT_SHA=""
RUN printf '{"commit":"%s"}\n' "${GIT_SHA}" > dist/version.json

FROM nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11 AS production
# nginx runs as the image's unprivileged nginx user (uid 101), never root:
# no user directive, the pid file in /tmp, and the start script may write
# only the web root, /etc/nginx/conf.d and nginx's temp directory (so a
# read-only root filesystem works with those three and /tmp as volumes).
# It listens on 8080 (LISTEN_PORT), since a non-root process can't bind 80.
# apk upgrade: fixes published since the base image was built (Trivy fails
# the SPA images on fixable HIGH/CRITICAL CVEs, see images.yml).
RUN apk upgrade --no-cache \
 && sed -i -e '/^user /d' -e 's#^pid .*#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
 && chown -R nginx:nginx /usr/share/nginx/html /etc/nginx/conf.d /var/cache/nginx
COPY --from=builder /app/dist /opt/spa
COPY app/deploy/nginx/40-hubra-runtime.sh /docker-entrypoint.d/
USER nginx
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
