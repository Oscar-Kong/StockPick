FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

ENV NEXT_PUBLIC_API_URL=http://127.0.0.1:18731
EXPOSE 3000
CMD ["npm", "run", "dev"]
