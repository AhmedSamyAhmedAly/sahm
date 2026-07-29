# Static hosting for the Vite/React app on Railway.
# Build with Node, then serve the compiled assets with nginx — nginx idles at ~10 MB
# RAM vs ~100 MB for a Node server, which directly lowers the Railway bill.

FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Vite inlines env vars at BUILD time, so the API URL must be present here.
# Railway passes service variables to the build as args.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Railway assigns the port at runtime; patch nginx to listen on it.
CMD ["sh", "-c", "sed -i \"s/listen 80;/listen ${PORT:-80};/\" /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
