FROM node:22-alpine AS base
ARG VITE_API_BASE
ARG VITE_SSO_URL
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_SSO_URL=${VITE_SSO_URL}
WORKDIR /app
COPY packages/api-client /packages/api-client
COPY app/admin-frontend/package.json app/admin-frontend/package-lock.json* ./
RUN npm ci
COPY app/admin-frontend/ ./

FROM base AS dev
EXPOSE 5174
CMD ["npm", "run", "dev"]

FROM base AS builder
RUN npm run build

FROM nginx:alpine AS production
RUN apk add --no-cache wget
COPY --from=builder /app/dist /usr/share/nginx/html
COPY app/admin-frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
