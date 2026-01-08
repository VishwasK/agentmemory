# Deployment Troubleshooting Checklist

## If you don't see changes after deployment:

### 1. **Check Browser Cache**
   - Hard refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
   - Or open in incognito/private window
   - Or clear browser cache

### 2. **Verify Deployment Actually Happened**
   ```bash
   # Check Heroku logs
   heroku logs --tail
   
   # Check if latest commit is deployed
   heroku releases
   ```

### 3. **Check if App is Running**
   ```bash
   # Check app status
   heroku ps
   
   # Check recent logs for errors
   heroku logs --tail -n 100
   ```

### 4. **Test Health Endpoint**
   Visit: `https://your-app.herokuapp.com/health`
   
   Should return JSON with status "healthy" and memvid_sdk working

### 5. **Check for Build Errors**
   ```bash
   # View build logs
   heroku logs --source app
   ```

### 6. **Verify Dependencies Installed**
   Check logs for:
   - `memvid-sdk` installation success
   - Any import errors
   - Missing dependencies

### 7. **Test Locally First**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Run locally
   python app.py
   
   # Visit http://localhost:5000
   ```

### 8. **Common Issues**

   **Issue: App crashes on startup**
   - Check: `heroku logs --tail`
   - Look for: Import errors, missing modules
   - Fix: Ensure `memvid-sdk>=2.0.0` is in requirements.txt

   **Issue: Old UI still showing**
   - Hard refresh browser (Ctrl+Shift+R)
   - Check: `heroku releases` to see if latest commit deployed
   - Redeploy: `git push heroku main`

   **Issue: Memory not working**
   - Check: `/health` endpoint
   - Check: `/debug/<user_id>` endpoint
   - Verify: `OPENAI_API_KEY` is set (needed for embeddings)

### 9. **Force Redeploy**
   ```bash
   # Push latest changes
   git push heroku main
   
   # Or restart dyno
   heroku restart
   ```

### 10. **Check Environment Variables**
   ```bash
   # List all config vars
   heroku config
   
   # Verify OPENAI_API_KEY is set
   heroku config:get OPENAI_API_KEY
   ```

