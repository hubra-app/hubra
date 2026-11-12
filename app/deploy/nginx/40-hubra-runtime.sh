#!/bin/sh
# Runtime configuration for the SPA images (frontend, admin-frontend,
# sso-frontend, support-frontend). Runs from the nginx image's /docker-entrypoint.d/ on every
# container start, so one image works for every host name:
#
#   1. Copies the pristine build from /opt/spa into the web root and replaces
#      the __RUNTIME_VITE_*__ placeholders the Dockerfile baked in with the
#      container's VITE_* environment variables (or the defaults below).
#   2. Writes the nginx server block. With API_UPSTREAM set (for example
#      http://backend:5000), /api/ is proxied to the backend so the SPA and the
#      API share one origin. PLATFORM_API_UPSTREAM (for example
#      http://platform-backend:5000) sends the platform API (/api/v1/platform
#      and the old /api/v1/manager and /api/v1/system paths) to a separate
#      platform backend (docs/platform-backend.md), GLOBAL_API_UPSTREAM (for
#      example http://global-backend:5000) the global API (/api/v1/global:
#      sign-in, account, public data, and its old paths) to a global backend.
#      REAL_IP_FROM (a CIDR, comma-separated list
#      allowed) trusts X-Forwarded-For from a proxy in front of this nginx.
#      MAX_UPLOAD_MB (default 100) is the largest request body, as for the
#      backend's file uploads; give both the same value.
#      nginx runs as a non-root user and listens on LISTEN_PORT (8080).
#
# An image built with real VITE_* build args has no placeholders left, so
# step 1 changes nothing for it.
set -eu

src=/opt/spa
html=/usr/share/nginx/html

max_upload_mb="${MAX_UPLOAD_MB:-100}"
case "$max_upload_mb" in
  ''|*[!0-9]*) max_upload_mb=100 ;;
esac

rm -rf "${html:?}"/*
cp -R "$src"/. "$html"/

# Escape a value for the replacement side of a sed s|...|...| expression.
sed_escape() {
  printf '%s' "$1" | sed -e 's/[\\|&]/\\&/g'
}

script=""
add() {
  value=""
  eval "value=\${$1-$2}"
  script="${script}s|__RUNTIME_$1__|$(sed_escape "$value")|g;"
}
add VITE_API_BASE /api
add VITE_SSO_URL https://sso.hubra.club
add VITE_COS_URL https://app.hubra.club
add VITE_MANAGE_URL https://manage.hubra.club
add VITE_ADMIN_PORTAL_URL https://manage.hubra.club
add VITE_TENANT_APP_URL https://app.hubra.club
add VITE_SUPPORT_URL https://support.hubra.club

find "$html" -type f \( -name '*.js' -o -name '*.html' \) -exec sed -i "$script" {} +

# Security headers for the SPA (the API sets its own). The page loads scripts
# and calls the API on its own origin or, when VITE_API_BASE is a full URL,
# on that origin (plugin frontends come from the API). Fonts are bundled
# (packages/ui/src/fonts), nothing loads from a third-party host. CSP
# replaces the policy; CSP=off sends none.
origin_of() {
  case "$1" in
    http://* | https://*) printf '%s' "$1" | sed -E 's#^(https?://[^/]+).*#\1#' ;;
  esac
}
api_origin="$(origin_of "${VITE_API_BASE-/api}")"
# Manage reads /version.json from the club app and SSO (Diagnose > Builds).
app_origins="$(origin_of "${VITE_COS_URL-https://app.hubra.club}") $(origin_of "${VITE_SSO_URL-https://sso.hubra.club}")"
default_csp="default-src 'self'; script-src 'self' ${api_origin}; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data: blob: https:; connect-src 'self' ${api_origin} ${app_origins}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
csp="${CSP:-$default_csp}"
# Strict-Transport-Security on HTTPS. No includeSubDomains by default: on an
# install served from a bare domain it would force HTTPS on every other host
# of that domain. HSTS replaces the value; HSTS=off sends none.
hsts="${HSTS:-max-age=31536000}"
if [ "$hsts" = "off" ]; then hsts=""; fi
{
  echo 'add_header X-Content-Type-Options "nosniff" always;'
  echo 'add_header X-Frame-Options "DENY" always;'
  echo 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;'
  # The camera stays allowed for the page itself: the Keys check-in scans
  # badges with it (BarcodeDetector). Nothing else, and no embedded frame.
  echo 'add_header Permissions-Policy "camera=(self), microphone=(), geolocation=(), payment=(), usb=(), serial=(), hid=(), bluetooth=()" always;'
  # HSTS only on HTTPS requests (directly or behind a TLS proxy). The value
  # comes from the map in default.conf and is empty, so not sent, over HTTP.
  echo "add_header Strict-Transport-Security \$hubra_hsts always;"
  if [ "$csp" != "off" ]; then
    echo "add_header Content-Security-Policy \"$csp\" always;"
  fi
} > /etc/nginx/conf.d/hubra-headers.inc

real_ip=""
trusted_proxies=""
if [ -n "${REAL_IP_FROM:-}" ]; then
  for cidr in $(echo "$REAL_IP_FROM" | tr ',' ' '); do
    real_ip="${real_ip}    set_real_ip_from ${cidr};
"
    trusted_proxies="${trusted_proxies}    ${cidr} 1;
"
  done
  real_ip="${real_ip}    real_ip_header X-Forwarded-For;
    real_ip_recursive on;
"
fi

proxy_block() {
  printf '%s\n' "    location $1 {
        proxy_pass $2;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$hubra_forwarded_proto;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_read_timeout 120s;
    }"
}

api=""
if [ -n "${API_UPSTREAM:-}" ]; then
  api="$(proxy_block /api/ "$API_UPSTREAM")
"
fi
# The platform paths of hubra.core.api_areas: /api/v1/platform and the old
# /manager and /system ones, except the person's own parts of /system (club
# directory, invites, requests), which stay on the club backend. A regex
# location wins over the /api/ prefix location. tests/test_api_areas.py
# checks this pattern against the backend's table.
platform_paths='^/api/v1/(platform|manager)(/|$)|^/api/v1/system(?!/(clubs|invites|join-requests|tenant-requests/mine|impersonation|permissions)(/|$))(/|$)'
if [ -n "${PLATFORM_API_UPSTREAM:-}" ]; then
  api="${api}$(proxy_block "~ $platform_paths" "$PLATFORM_API_UPSTREAM")
"
fi
# The global paths: /api/v1/global and the old paths that lead there.
global_paths='^/api/v1/(global|auth|account|i18n|health|version|instance|maintenance|status|public|roadmap|support|apps|plugins|system/(clubs|invites|join-requests|tenant-requests/mine|impersonation))(/|$)'
if [ -n "${GLOBAL_API_UPSTREAM:-}" ]; then
  api="${api}$(proxy_block "~ $global_paths" "$GLOBAL_API_UPSTREAM")
"
fi

cat > /etc/nginx/conf.d/default.conf <<CONF
# X-Forwarded-Proto counts only from a proxy: a private or loopback address
# (Traefik, Docker, a k8s ingress) or one of REAL_IP_FROM, and only as http
# or https. A client reaching this nginx directly can't claim HTTPS.
geo \$realip_remote_addr \$hubra_from_proxy {
    default        0;
    127.0.0.0/8    1;
    10.0.0.0/8     1;
    172.16.0.0/12  1;
    192.168.0.0/16 1;
    ::1            1;
    fc00::/7       1;
${trusted_proxies}}

map "\$hubra_from_proxy:\$http_x_forwarded_proto" \$hubra_forwarded_proto {
    "1:https" https;
    "1:http"  http;
    default   \$scheme;
}

map \$hubra_forwarded_proto \$hubra_hsts {
    https   "${hsts}";
    default "";
}

# No nginx version in the Server header or on error pages.
server_tokens off;

server {
    listen ${LISTEN_PORT:-8080};
    server_name _;
    root ${html};
    index index.html;
    client_max_body_size ${max_upload_mb}m;
${real_ip}
${api}
    # The commit this image was built from, for manage on another host.
    location = /version.json {
        include /etc/nginx/conf.d/hubra-headers.inc;
        add_header Cache-Control "no-cache";
        add_header Access-Control-Allow-Origin "*";
        try_files \$uri =404;
    }

    location /assets/ {
        expires 1y;
        include /etc/nginx/conf.d/hubra-headers.inc;
        add_header Cache-Control "public, immutable";
        try_files \$uri =404;
    }

    location / {
        include /etc/nginx/conf.d/hubra-headers.inc;
        add_header Cache-Control "no-cache";
        try_files \$uri \$uri/ /index.html;
    }
}
CONF
