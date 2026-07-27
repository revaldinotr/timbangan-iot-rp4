# Self-Hosting n8n on a Raspberry Pi

This guide will walk you through the process of self-hosting n8n on a Raspberry Pi and making it securely available on the internet using Cloudflare Tunnels.

## Prerequisites
- A Raspberry Pi (e.g., Raspberry Pi 4) with an OS installed (like Raspberry Pi OS) and SSH access enabled.
- A Cloudflare account with a configured domain.
- Docker and Docker Compose installed on your Raspberry Pi.

## Part 1: Exposing Your Raspberry Pi to the Internet with Cloudflare Tunnels

### 1. Configure Cloudflare Zero Trust
1. Log in to your Cloudflare dashboard and navigate to **Zero Trust**.
2. Go to **Networks** -> **Tunnels**.
3. Click on **Add a tunnel** and select **Cloudflared**.
4. Give your tunnel a name (e.g., `raspberry-pi-tunnel`) and save it.
5. You will see a command to install and run the connector, but don't run it just yet! You need to install Cloudflare on your Raspberry Pi first.
6. Note the token inside the command, you will need it later. Keep it secret!

### 2. Install Cloudflare on Raspberry Pi
SSH into your Raspberry Pi and run the following commands to add Cloudflare's GPG keys and repository:

```bash
# Create directory for GPG keys
sudo mkdir -p --mode=0755 /usr/share/keyrings

# Download Cloudflare GPG key
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

# Add Cloudflare repository
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bullseye main' | sudo tee /etc/apt/sources.list.d/cloudflared.list

# Update package list and install Cloudflared
sudo apt update
sudo apt install cloudflared
```

### 3. Connect the Tunnel
Run the command provided in your Cloudflare dashboard to connect the tunnel. It will look something like this:
```bash
sudo cloudflared service install <YOUR_SECRET_TOKEN>
```
Once successfully run, you should see the Raspberry Pi connected in your Cloudflare dashboard.

### 4. Route a Subdomain
1. In the Cloudflare tunnel setup, click **Next** and set up a subdomain (e.g., `n8n.yourdomain.com`).
2. Under **Service**, select `HTTP` and set the URL to `localhost:5678` (where n8n will run locally).
3. Save the configuration.

---

## Part 2: Installing and Running n8n with Docker

### 1. Set Up the Project Directory
Navigate to your preferred workspace on your Raspberry Pi and create a directory for n8n:
```bash
mkdir n8n
cd n8n
```

### 2. Configure Environment Variables
Create an `.env` file to store your configuration:
```bash
nano .env
```
Add the following details (adjust accordingly):
```env
N8N_HOST=n8n.yourdomain.com
N8N_PROTOCOL=https
N8N_PERSONALIZATION_ENABLED=false
GENERIC_TIMEZONE=Asia/Jakarta
```

### 3. Create Docker Compose File
Create a `docker-compose.yml` file:
```bash
nano docker-compose.yml
```
Define the n8n service and volume:
```yaml
version: "3"

services:
  n8n:
    image: docker.n8n.io/n8nio/n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=${N8N_HOST}
      - N8N_PROTOCOL=${N8N_PROTOCOL}
      - N8N_PERSONALIZATION_ENABLED=${N8N_PERSONALIZATION_ENABLED}
      - GENERIC_TIMEZONE=${GENERIC_TIMEZONE}
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  n8n_data:
```

### 4. Start n8n
Start the container to download the image and boot up n8n:
```bash
docker compose up -d
```
Check the logs to see if it started properly:
```bash
docker compose logs
```

### 5. Fix Permission Issues (If Applicable)
If you check the logs and see a permission error preventing n8n from starting, follow these steps to fix the volume permissions:

1. Stop the instance:
   ```bash
   docker compose stop
   ```
2. Change the ownership of the volume so the node user inside the container can access it:
   ```bash
   docker run --rm -v n8n_data:/home/node/.n8n alpine chown -R 1000:1000 /home/node/.n8n
   ```
3. Restart the n8n instance:
   ```bash
   docker compose start
   ```

Check the logs again:
```bash
docker compose logs -f
```
You should see that migrations are running and the startup tasks have completed successfully.

### 6. Access Your n8n Instance
Open your browser and navigate to the subdomain you set up (e.g., `https://n8n.yourdomain.com`). 
Go through the initial setup process, enter your details, and you're ready to start building automations!

---
