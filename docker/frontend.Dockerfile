FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY app app
COPY tsconfig.json next.config.ts ./
ARG BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL
RUN npm run build
CMD ["npm", "start"]
