FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS base
ARG VITE_API_BASE
ARG VITE_SSO_URL
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_SSO_URL=${VITE_SSO_URL}
WORKDIR /app
COPY packages/api-client /packages/api-client
COPY app/frontend/package.json app/frontend/package-lock.json* ./
RUN npm ci
COPY app/frontend/ ./

FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM base AS builder
RUN npm run build

FROM nginx:alpine@sha256:54f2a904c251d5a34adf545a72d32515a15e08418dae0266e23be2e18c66fefa AS production
RUN apk add --no-cache wget
COPY --from=builder /app/dist /usr/share/nginx/html
COPY app/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
