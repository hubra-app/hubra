FROM node:22-alpine AS base
ARG VITE_API_BASE
ENV VITE_API_BASE=${VITE_API_BASE}
WORKDIR /app
COPY packages/api-client /packages/api-client
COPY app/sso-frontend/package.json app/sso-frontend/package-lock.json* ./
RUN npm ci
COPY app/sso-frontend/ ./

FROM base AS dev
EXPOSE 5175
CMD ["npm", "run", "dev"]

FROM base AS builder
RUN npm run build

FROM nginx:alpine AS production
RUN apk add --no-cache wget
COPY --from=builder /app/dist /usr/share/nginx/html
COPY app/sso-frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
