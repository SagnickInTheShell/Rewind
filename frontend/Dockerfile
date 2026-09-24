FROM node:22-alpine
WORKDIR /app/frontend
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ENV REWIND_BACKEND_URL=http://backend:8000
EXPOSE 5173
CMD ["npm", "run", "dev"]
