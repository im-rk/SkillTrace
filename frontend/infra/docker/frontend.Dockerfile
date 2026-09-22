# Multi-stage: the build stage has the full node_modules + devDependencies (TypeScript,
# ESLint types, etc.); the runtime stage copies out only Next's standalone server bundle,
# which already contains its own pruned node_modules.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# The frontend calls the API from the BROWSER, not from this build step, so the API's
# public URL must be baked in at build time (Next.js inlines NEXT_PUBLIC_* at build,
# not read at runtime) -- pass it with `docker build --build-arg`.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_OUTPUT_STANDALONE=true
RUN npm run build

FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
