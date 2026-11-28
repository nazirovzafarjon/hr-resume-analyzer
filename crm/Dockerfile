# Stage 1: Build the React + TypeScript frontend
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

# Vite inlines VITE_* values at build time, and .env files are not part of the
# build context, so they arrive as build args (see docker-compose.public.yml).
# Args left unset keep the app's built-in defaults.
ARG VITE_API_BASE_URL
ARG VITE_GOOGLE_CLIENT_ID
ARG VITE_GOOGLE_REDIRECT_URI
ARG VITE_LANDING_URL

COPY . .
RUN npm run build

# Stage 2: Serve with minimal hardened Nginx
FROM nginx:1.27-alpine AS runner

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
