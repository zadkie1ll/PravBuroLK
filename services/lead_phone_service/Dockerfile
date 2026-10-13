FROM node:22-alpine
WORKDIR /app
COPY package.json ./
COPY src ./src
RUN mkdir /data && chown node:node /data
USER node
CMD ["node", "src/main.js"]
