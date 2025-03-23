# ZVision Production Deployment Guide

This guide provides instructions for deploying the ZVision application to production.

## Prerequisites

- Python 3.9+
- Node.js 14+ (for building the React frontend)
- A webserver like Nginx for HTTPS termination (recommended)
- A domain name (for HTTPS)

## Preparing the Frontend

1. Build the React frontend:

```bash
cd frontend
npm install
npm run build
```

This will create a `build` directory with the static files for the React app.

## Deploying the Backend

1. Clone the repository:

```bash
git clone https://github.com/your-username/zvision.git
cd zvision
```

2. Set up a Python virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Use the deployment script to set up the production environment:

```bash
# Create all necessary files for production
python deploy.py --react-build path/to/frontend/build --env production --service --requirements

# Or for development
python deploy.py --env development --requirements
```

5. Edit the `.env` file with your production settings, including:
   - Generate a strong JWT secret key
   - Set your production domain
   - Other environment-specific settings

## Running in Production

### Option 1: Using Systemd (Recommended for Linux servers)

If you used the `--service` flag with the deployment script, a systemd service file has been created.

1. Copy the service file to the systemd directory:

```bash
sudo cp zvision.service /etc/systemd/system/
sudo systemctl daemon-reload
```

2. Enable and start the service:

```bash
sudo systemctl enable zvision
sudo systemctl start zvision
```

3. Check the service status:

```bash
sudo systemctl status zvision
```

### Option 2: Using a Process Manager

You can use a process manager like PM2 or Supervisor:

```bash
# Using PM2
npm install -g pm2
pm2 start "uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2" --name zvision

# Save the PM2 configuration
pm2 save
```

## HTTPS with Nginx (Recommended)

For production, it's recommended to use Nginx as a reverse proxy with HTTPS:

1. Install Nginx:

```bash
sudo apt-get install nginx
```

2. Create a Nginx configuration file:

```bash
sudo nano /etc/nginx/sites-available/zvision
```

3. Add the following configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect HTTP to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name yourdomain.com;
    
    # SSL configuration
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Proxy headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # API requests
    location /api/ {
        proxy_pass http://localhost:8000;
    }
    
    # Frontend static files
    location / {
        proxy_pass http://localhost:8000;
    }
}
```

4. Enable the site and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/zvision /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## SSL Certificate with Let's Encrypt

You can obtain a free SSL certificate using Let's Encrypt:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

Follow the prompts to complete the certificate setup.

## Monitoring and Logs

- Systemd logs can be viewed with:
  ```bash
  sudo journalctl -u zvision -f
  ```

- Application logs are stored in the `logs` directory.

## Updating the Application

1. Pull the latest changes:
   ```bash
   git pull
   ```

2. Rebuild the frontend if needed:
   ```bash
   cd frontend
   npm run build
   ```

3. Copy the new build to the backend:
   ```bash
   python deploy.py --react-build path/to/frontend/build
   ```

4. Restart the service:
   ```bash
   sudo systemctl restart zvision
   ```

## Backup

Regularly back up the database file:

```bash
cp database/zvision.db /backup/zvision-$(date +%Y%m%d).db
```

## Troubleshooting

- If the application doesn't start, check the logs:
  ```bash
  sudo journalctl -u zvision -n 100
  ```

- If Nginx returns a 502 Bad Gateway error, check if the application is running:
  ```bash
  curl http://localhost:8000/api/ping
  ```

- For CORS issues, check that your production domain is correctly set in the `.env` file.

---

For more information, please refer to the [FastAPI documentation](https://fastapi.tiangolo.com/) and [React deployment guide](https://create-react-app.dev/docs/deployment/). 