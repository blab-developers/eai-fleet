# fleet-mgr frontend — SvelteKit + adapter-node, served as its own container.
# The browser calls same-origin /api/*; hooks.server.ts proxies to EAI_FLEET_BACKEND_URL
# (the backend container), so no nginx/ingress is needed.
#
# The generated API client (src/lib/generated/fleet-backend-api) is committed, so the
# image build does NOT run `yarn gen:api` (no Python in this image) — it just builds.

# --- Stage 1: Build ---
FROM node:22-alpine AS builder
WORKDIR /usr/src/app

COPY package.json yarn.lock .yarnrc.yml ./
RUN corepack enable && yarn install --immutable

ARG GIT_SHA=""
ENV VITE_GIT_SHA=${GIT_SHA}
ENV NODE_OPTIONS="--max-old-space-size=4096"

COPY . .
RUN yarn build

# --- Stage 2: Production ---
FROM node:22-alpine
WORKDIR /usr/src/app
ENV NODE_ENV=production
ENV PORT=3000

# adapter-node leaves regular `dependencies` external (imported at request time), so
# the runtime image needs production node_modules.
COPY package.json yarn.lock .yarnrc.yml ./
RUN corepack enable && yarn workspaces focus --production && yarn cache clean

COPY --from=builder /usr/src/app/build ./build

USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["node", "build"]
