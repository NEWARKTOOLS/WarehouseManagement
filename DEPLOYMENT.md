# WMS Deployment Guide

## Initial Setup: Push to GitHub

### 1. Create GitHub Repository

1. Go to https://github.com/new
2. Name it `wms` (or whatever you prefer)
3. Keep it **Private** (recommended for business data)
4. Don't initialize with README (we already have code)

### 2. Push Your Code (from your Windows PC)

```powershell
cd D:\WarehouseManagement

# Initialize git (if not already)
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial WMS commit"

# Add your GitHub repo as remote
git remote add origin https://github.com/YOUR_USERNAME/wms.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## Homelab Setup: Clone and Run

### 1. Clone on your homelab

```bash
# SSH to your homelab
ssh user@homelab

# Clone the repo
git clone https://github.com/YOUR_USERNAME/wms.git
cd wms

# Make scripts executable
chmod +x scripts/*.sh
```

### 2. Set up environment

```bash
# Create secret key
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env
```

### 3. Build and run with Docker

```bash
docker compose up -d --build
```

### 4. Access the app
- Via Tailscale: `http://your-homelab-tailscale-ip:5000`
- With MagicDNS: `http://homelab:5000`

### Default Login
- **Username:** `admin`
- **Password:** `admin123`
- ⚠️ **Change this immediately!**

---

## Auto-Updates: Choose Your Method

### Option A: Cron (Simplest) ⭐ Recommended

Automatically checks GitHub every 5 minutes and updates if there are changes.

```bash
# On your homelab, run:
cd ~/wms
./scripts/setup-cron-update.sh
```

That's it! Now whenever you push to GitHub, your homelab will update within 5 minutes.

**View update logs:**
```bash
tail -f /var/log/wms-updates.log
```

### Option B: GitHub Webhook (Instant)

Updates immediately when you push. Requires port 9000 to be accessible.

```bash
# Generate a secret
WEBHOOK_SECRET=$(openssl rand -hex 20)
echo "Your webhook secret: $WEBHOOK_SECRET"

# Run setup
./scripts/setup-webhook.sh $WEBHOOK_SECRET
```

Then configure GitHub:
1. Go to your repo → Settings → Webhooks → Add webhook
2. **Payload URL:** `http://your-tailscale-ip:9000/hooks/wms-deploy`
3. **Content type:** `application/json`
4. **Secret:** (the secret you generated)
5. **Events:** Just the push event

### Option C: Manual Update

```bash
cd ~/wms
./scripts/update.sh
```

---

## Daily Workflow

### On your Windows PC (development):

```powershell
cd D:\WarehouseManagement

# Make changes to your code...

# Commit and push
git add .
git commit -m "Description of changes"
git push
```

### On your homelab (automatic):
- **With cron:** Updates within 5 minutes automatically
- **With webhook:** Updates instantly
- **Manual:** Run `./scripts/update.sh`

---

## Useful Commands

```bash
# View app logs
docker-compose logs -f wms

# Restart the app
docker-compose restart

# Stop the app
docker-compose down

# Full rebuild (after Dockerfile changes)
docker-compose up -d --build

# Backup database
docker cp wms-app:/app/instance/warehouse.db ~/backup_$(date +%Y%m%d).db

# Check container status
docker ps

# View update logs (if using cron)
tail -f /var/log/wms-updates.log
```

---

## Backup Strategy

### Automatic Daily Database Backup

```bash
# Add to crontab (crontab -e)
0 2 * * * docker cp wms-app:/app/instance/warehouse.db /backups/wms_$(date +\%Y\%m\%d).db
```

### Using Built-in Backup
1. Go to Settings → Data Management
2. Click "Full Backup"
3. Downloads all data as CSV in a ZIP file

---

## Troubleshooting

### Container won't start
```bash
docker-compose logs wms
```

### Git permission issues
```bash
# If git pull fails with permission errors
sudo chown -R $USER:$USER ~/wms
```

### Port already in use
```bash
# Check what's using port 5000
sudo lsof -i :5000

# Or change port in docker-compose.yml:
# ports:
#   - "8080:5000"
```

### Reset everything
```bash
docker-compose down
docker volume rm wms_wms_data
docker-compose up -d --build
```
⚠️ This deletes all data!

---

## Security Notes

1. **Change default password** immediately after first login
2. **Keep repo private** on GitHub
3. **Use Tailscale** - don't expose port 5000 to the internet
4. **Backup regularly** - use the built-in backup feature
