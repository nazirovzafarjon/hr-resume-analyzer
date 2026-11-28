# Stage 1: Build the Landing static application
FROM node:24-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

# Vite inlines VITE_* values at build time, and .env files are not part of the
# build context, so they arrive as build args (see docker-compose.prod.yml).
# VITE_SITE_URL is required: the build prerenders canonical/hreflang links,
# Open Graph tags and sitemap.xml from it, and fails without it.
ARG VITE_SITE_URL
ARG VITE_APP_URL
ARG VITE_API_BASE_URL
ARG VITE_CONTACT_EMAIL

COPY . .
RUN npm run build

# Stage 2: Serve with minimal hardened Nginx
FROM nginx:1.27-alpine AS runner

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/security-headers.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
