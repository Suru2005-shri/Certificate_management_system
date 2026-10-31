FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ARG VITE_KEYCLOAK_URL=http://localhost:8080
ENV VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL
RUN npm run build

FROM nginx:alpine
# nginx fills ${...} from the environment at start (official image feature), so one image works anywhere
ENV KEYCLOAK_PUBLIC_URL=http://localhost:8080 FILES_PUBLIC_URL=http://localhost:9000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
