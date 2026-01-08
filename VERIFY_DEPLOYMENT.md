# Verify Deployment - Debug Steps

## The template file is correct locally. Follow these steps to verify deployment:

### 1. Check if commits are pushed to Heroku
```bash
# Check local commits
git log --oneline -5

# Check Heroku remote
git remote -v

# Push if needed
git push heroku main
```

### 2. Verify template is deployed
After pushing, check the debug endpoint:
```
https://your-app.herokuapp.com/debug-template
```

This will show:
- Template file path
- If file exists
- Content checks (has "AgentMemory", "View Memories", etc.)
- Actual title and h1 content

### 3. Check version endpoint
```
https://your-app.herokuapp.com/version
```

Should show version 2.0.0

### 4. View source of the page
1. Open your app in browser
2. Right-click → "View Page Source"
3. Search for "AgentMemory" - should find it in title and h1
4. Search for "View Memories" - should find the button

### 5. Check Heroku logs
```bash
heroku logs --tail
```

Look for:
- "Rendering index.html from: ..."
- "Has 'AgentMemory': True"
- "Has 'View Memories': True"

### 6. If template shows old content in source

**Check if old commit is deployed:**
```bash
heroku releases
```

**Force rebuild:**
```bash
heroku builds:cache:purge
git push heroku main --force
```

### 7. Verify file on Heroku
```bash
heroku run bash
ls -la templates/
cat templates/index.html | grep -i "AgentMemory\|View Memories"
exit
```

### 8. Check response headers
In browser DevTools → Network tab:
- Look for `X-App-Version: 2.0.0` header
- Check `Cache-Control` headers

## Expected Results

**Template debug endpoint should show:**
```json
{
  "has_agentmemory": true,
  "has_view_memories": true,
  "has_search_button": true,
  "title_content": "AgentMemory - AI Chat with Persistent Memory",
  "h1_content": "🧠 AgentMemory"
}
```

**Page source should contain:**
- `<title>AgentMemory - AI Chat with Persistent Memory</title>`
- `<h1>🧠 AgentMemory</h1>`
- Button with text "🔍 View Memories"
- Button with text "🔎 Search"

