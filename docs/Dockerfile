FROM nginx:alpine

# Copy built documentation to nginx html directory
COPY . /usr/share/nginx/html

# Expose nginx port
EXPOSE 8080

# Use nginx default startup command
CMD ["nginx", "-g", "daemon off;"]
