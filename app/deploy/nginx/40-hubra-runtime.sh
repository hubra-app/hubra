#!/bin/sh
# Runtime configuration for the SPA images (frontend, admin-frontend,
# sso-frontend). Runs from the nginx image's /docker-entrypoint.d/ on every
# container start, so one image works for every host name:
#
#   1. Copies the pristine build from /opt/spa into the web root and replaces
#      the __RUNTIME_VITE_*__ placeholders the Dockerfile baked in with the
#      container's VITE_* environment variables (or the defaults below).
#   2. Writes the nginx server block. With API_UPSTREAM set (for example
#      http://backend:5000), /api/ is proxied to the backend so the SPA and the
#      API share one origin. REAL_IP_FROM (a CIDR, comma-separated list
#      allowed) trusts X-Forwarded-For from a proxy in front of this nginx.
#
# An image built with real VITE_* build args has no placeholders left, so
# step 1 changes nothing for it.
set -eu

src=/opt/spa
html=/usr/share/nginx/html

rm -rf "${html:?}"/*
cp -a "$src"/. "$html"/

# Escape a value for the replacement side of a sed s|...|...| expression.
sed_escape() {
  printf '%s' "$1" | sed -e 's/[\\|&]/\\&/g'
}

script=""
add() {
  eval "value=\${$1-$2}"
  script="${script}s|__RUNTIME_$1__|$(sed_escape "$value")|g;"
}
add VITE_API_BASE /api
add VITE_SSO_URL https://sso.hubra.club
add VITE_COS_URL https://app.hubra.club
add VITE_MANAGE_URL https://manage.hubra.club
add VITE_ADMIN_PORTAL_URL https://manage.hubra.club
add VITE_TENANT_APP_URL https://app.hubra.club

find "$html" -type f \( -name '*.js' -o -name '*.html' \) -exec sed -i "$script" {} +

real_ip=""
if [ -n "${REAL_IP_FROM:-}" ]; then
  for cidr in $(echo "$REAL_IP_FROM" | tr ',' ' '); do
    real_ip="${real_ip}    set_real_ip_from ${cidr};
"
  done
  real_ip="${real_ip}    real_ip_header X-Forwarded-For;
    real_ip_recursive on;
"
fi

api=""
if [ -n "${API_UPSTREAM:-}" ]; then
  api="    location /api/ {
        proxy_pass ${API_UPSTREAM};
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$hubra_forwarded_proto;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_read_timeout 120s;
    }
"
fi

cat > /etc/nginx/conf.d/default.conf <<CONF
map \$http_x_forwarded_proto \$hubra_forwarded_proto {
    default \$http_x_forwarded_proto;
    ""      \$scheme;
}

server {
    listen 80;
    server_name _;
    root ${html};
    index index.html;
    client_max_body_size 25m;
${real_ip}
${api}
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files \$uri =404;
    }

    location / {
        add_header Cache-Control "no-cache";
        try_files \$uri \$uri/ /index.html;
    }
}
CONF
