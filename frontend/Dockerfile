FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 3000

ENV PORT=3000 \
    HOST=0.0.0.0

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
