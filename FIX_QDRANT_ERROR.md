# Fix Qdrant Import Error

## Problem
The app is crashing with a Qdrant import error even though we're using Memvid, not Mem0/Qdrant.

## Solution

### 1. Clear Heroku Build Cache
The build cache might have old dependencies. Clear it:

```bash
heroku builds:cache:purge
```

### 2. Redeploy
```bash
git push heroku main
```

### 3. If Still Failing - Check Dependencies

The error suggests Qdrant is being imported as a transitive dependency. Check:

```bash
# SSH into Heroku dyno
heroku run bash

# Check what's installed
pip list | grep -i qdrant
pip list | grep -i memvid

# Check if memvid-sdk pulls in qdrant
pip show memvid-sdk
```

### 4. Alternative: Pin memvid-sdk Version

If there's a version issue, try pinning to a specific version:

```bash
# In requirements.txt, change:
memvid-sdk>=2.0.0
# To:
memvid-sdk==2.0.144
```

### 5. Check Startup

After deployment, check:
```bash
# View logs
heroku logs --tail

# Test startup check endpoint
curl https://your-app.herokuapp.com/startup-check
```

### 6. If Qdrant is Required Dependency

If memvid-sdk requires Qdrant (unlikely), we might need to:
- Install qdrant-client but not use it
- Or find an alternative approach

### 7. Nuclear Option: Fresh Deploy

If nothing works:
```bash
# Create new Heroku app
heroku create your-app-name-new

# Set config vars
heroku config:set OPENAI_API_KEY=your_key -a your-app-name-new

# Deploy
git push heroku main -a your-app-name-new
```

## Debugging Commands

```bash
# Check app status
heroku ps

# View recent logs
heroku logs --tail -n 200

# Check build logs
heroku builds

# Test health endpoint
curl https://your-app.herokuapp.com/health

# Test startup check
curl https://your-app.herokuapp.com/startup-check
```

