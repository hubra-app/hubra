FROM node:22-alpine AS base
WORKDIR /app
COPY packages/api-client /packages/api-client
COPY app/sso-frontend/package.json app/sso-frontend/package-lock.json* ./
RUN npm ci
COPY app/sso-frontend/ ./

FROM base AS dev
EXPOSE 5175
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
ENV VITE_API_BASE=${VITE_API_BASE} \
    VITE_SSO_URL=${VITE_SSO_URL} \
    VITE_COS_URL=${VITE_COS_URL} \
    VITE_MANAGE_URL=${VITE_MANAGE_URL} \
    VITE_ADMIN_PORTAL_URL=${VITE_ADMIN_PORTAL_URL} \
    VITE_TENANT_APP_URL=${VITE_TENANT_APP_URL}
RUN npm run build

FROM nginx:alpine AS production
COPY --from=builder /app/dist /opt/spa
COPY app/deploy/nginx/40-hubra-runtime.sh /docker-entrypoint.d/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
