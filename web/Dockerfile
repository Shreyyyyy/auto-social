# The Next.js studio UI. It proxies /api and /media to the API container (API_URL is fixed at build time).
FROM node:22-bookworm-slim AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG API_URL=http://api:8787
ENV API_URL=$API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3737
COPY --from=build /web/package.json /web/next.config.mjs ./
COPY --from=build /web/node_modules ./node_modules
COPY --from=build /web/.next ./.next
USER node
EXPOSE 3737
CMD ["npx", "next", "start", "-p", "3737", "-H", "0.0.0.0"]
