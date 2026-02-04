# Build stage
FROM node:18-alpine as build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Dev stage
FROM node:18-alpine as dev

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

EXPOSE 5173

CMD ["npm", "run", "dev"]

# Prod stage
FROM node:18-alpine as prod

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --only=production

COPY --from=build /app/dist ./dist

EXPOSE 5173

CMD ["npm", "run", "preview"]
