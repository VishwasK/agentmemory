import os
import json
import time
import logging

# Configure logging FIRST before any other imports that might log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from flask import Flask, render_template, request, jsonify
from openai import OpenAI

# Import memvid_sdk with error handling
try:
    from memvid_sdk import create, use
    MEMVID_AVAILABLE = True
    logger.info("memvid_sdk imported successfully")
except ImportError as e:
    logger.error(f"Failed to import memvid_sdk: {e}")
    MEMVID_AVAILABLE = False
    # Create dummy functions to prevent crashes
    def create(*args, **kwargs):
        raise RuntimeError("memvid_sdk not available - check installation")
    def use(*args, **kwargs):
        raise RuntimeError("memvid_sdk not available - check installation")

app = Flask(__name__, template_folder='templates', static_folder='static')

# Initialize OpenAI client with error handling
try:
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not set - embeddings and LLM will fail")
    openai_client = OpenAI(api_key=openai_api_key)
    logger.info("OpenAI client initialized")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    openai_client = None

# Memvid uses single-file .mv2 format - store files in a persistent location
# For Heroku, we'll use a configurable storage path (can be mounted volume or S3-backed)
MEMVID_STORAGE_PATH = os.getenv('MEMVID_STORAGE_PATH', '/tmp/memvid')

# Ensure storage directory exists
os.makedirs(MEMVID_STORAGE_PATH, exist_ok=True)

def get_memory_instance(user_id):
    """Initialize Memvid memory file for a specific user"""
    # Create a .mv2 file per user for isolation
    file_path = os.path.join(MEMVID_STORAGE_PATH, f"{user_id}.mv2")
    
    # Check if file exists
    if os.path.exists(file_path):
        try:
            # Try to open existing file
            mv = use("basic", file_path, mode="open")
            return mv
        except Exception as e:
            app.logger.warning(f"Could not open existing file {file_path}, creating new: {e}")
    
    # Create new file
    try:
        mv = create(file_path, enable_vec=True, enable_lex=True)
        app.logger.info(f"Created new memory file: {file_path}")
        return mv
    except Exception as e:
        app.logger.error(f"Failed to create memory file {file_path}: {e}")
        raise

@app.route('/')
def index():
    """Render the main chat interface"""
    import os
    template_path = os.path.join(app.template_folder, 'index.html')
    template_exists = os.path.exists(template_path)
    
    logger.info(f"Rendering index.html from: {template_path}")
    logger.info(f"Template exists: {template_exists}")
    if template_exists:
        with open(template_path, 'r') as f:
            content_preview = f.read()[:200]
            logger.info(f"Template content preview: {content_preview}")
            has_agentmemory = 'AgentMemory' in content_preview
            has_view_memories = 'View Memories' in content_preview
            logger.info(f"Has 'AgentMemory': {has_agentmemory}, Has 'View Memories': {has_view_memories}")
    
    if not MEMVID_AVAILABLE:
        response = app.make_response(render_template('index.html'))
        response.status_code = 503
    else:
        response = app.make_response(render_template('index.html'))
    
    # Add cache-busting headers
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Add version header
    response.headers['X-App-Version'] = '2.0.0'
    return response

@app.route('/debug-template', methods=['GET'])
def debug_template():
    """Debug endpoint to check template file"""
    import os
    template_path = os.path.join(app.template_folder, 'index.html')
    template_exists = os.path.exists(template_path)
    
    info = {
        'template_folder': app.template_folder,
        'template_path': template_path,
        'template_exists': template_exists,
        'current_dir': os.getcwd(),
        'app_root': app.root_path
    }
    
    if template_exists:
        with open(template_path, 'r') as f:
            content = f.read()
            info['file_size'] = len(content)
            info['has_agentmemory'] = 'AgentMemory' in content
            info['has_view_memories'] = 'View Memories' in content
            info['has_search_button'] = 'searchMemories' in content
            info['title_content'] = content[content.find('<title>')+7:content.find('</title>')] if '<title>' in content else 'not found'
            info['h1_content'] = content[content.find('<h1>')+4:content.find('</h1>')] if '<h1>' in content else 'not found'
    
    return jsonify(info)

@app.route('/startup-check', methods=['GET'])
def startup_check():
    """Check if all dependencies are available"""
    checks = {
        'memvid_sdk': MEMVID_AVAILABLE,
        'openai': openai_client is not None,
        'storage_path': MEMVID_STORAGE_PATH,
        'storage_writable': os.access(MEMVID_STORAGE_PATH, os.W_OK) if os.path.exists(MEMVID_STORAGE_PATH) else False
    }
    
    if MEMVID_AVAILABLE:
        try:
            # Try a simple operation
            test_file = os.path.join(MEMVID_STORAGE_PATH, '.startup_test.mv2')
            if os.path.exists(test_file):
                os.remove(test_file)
            mv = create(test_file, enable_vec=False, enable_lex=False)
            mv.put(title="Test", label="test", text="test", enable_embedding=False)
            mv.seal()
            os.remove(test_file)
            checks['memvid_test'] = True
        except Exception as e:
            checks['memvid_test'] = False
            checks['memvid_error'] = str(e)
    
    status = 200 if all([checks['memvid_sdk'], checks['openai']]) else 503
    return jsonify(checks), status

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages with memory integration"""
    try:
        data = request.json
        message = data.get('message', '').strip()
        user_id = data.get('user_id', 'default_user')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get user's memory instance
        mv = get_memory_instance(user_id)
        
        # Get stats before search
        stats_before = mv.stats()
        app.logger.info(f"Memory stats before search: {stats_before}")
        
        # Search for relevant memories using hybrid search (BM25 + vector)
        search_results = mv.find(message, k=3, mode="auto")
        app.logger.info(f"Search results: {search_results}")
        
        memories_str = ""
        memories_used = 0
        search_details = []
        
        if search_results.get("hits"):
            memories_used = len(search_results["hits"])
            for hit in search_results["hits"]:
                snippet = hit.get('snippet', hit.get('text', ''))
                score = hit.get('score', 0)
                title = hit.get('title', 'Untitled')
                memories_str += f"- {snippet}\n"
                search_details.append({
                    'title': title,
                    'snippet': snippet[:200],
                    'score': score
                })
        
        app.logger.info(f"Found {memories_used} memories for query: {message}")
        if memories_used > 0:
            app.logger.info(f"Memory snippets: {memories_str[:500]}")
        
        # Generate Assistant response
        system_prompt = """You are a helpful AI assistant with memory capabilities. 
Answer the user's question based on the query and any relevant memories.
Be conversational and helpful."""
        
        if memories_str:
            system_prompt += f"\n\nRelevant User Memories:\n{memories_str}"
            app.logger.info(f"System prompt includes {memories_used} memories")
        else:
            app.logger.warning("No memories found for query - system prompt has no memory context")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        response = openai_client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=messages
        )
        assistant_response = response.choices[0].message.content
        
        # Store conversation as memory in Memvid
        # Store both user message and assistant response separately for better search
        timestamp = int(time.time())
        
        # Store user message
        mv.put(
            title=f"User Message - {timestamp}",
            label="user_message",
            text=message,
            metadata={"user_id": user_id, "type": "user_message", "timestamp": timestamp},
            enable_embedding=True,
            embedding_model="openai-small"  # Uses OPENAI_API_KEY
        )
        
        # Store assistant response
        mv.put(
            title=f"Assistant Response - {timestamp}",
            label="assistant_response",
            text=assistant_response,
            metadata={"user_id": user_id, "type": "assistant_response", "timestamp": timestamp},
            enable_embedding=True,
            embedding_model="openai-small"
        )
        
        # Also store combined conversation
        conversation_text = f"User: {message}\nAssistant: {assistant_response}"
        mv.put(
            title=f"Conversation - {timestamp}",
            label="conversation",
            text=conversation_text,
            metadata={"user_id": user_id, "type": "conversation", "timestamp": timestamp},
            enable_embedding=True,
            embedding_model="openai-small"
        )
        
        mv.seal()  # Commit changes
        
        stats_after = mv.stats()
        app.logger.info(f"Memory stats after storage: {stats_after}")
        
        return jsonify({
            'response': assistant_response,
            'memories_used': memories_used,
            'search_details': search_details,
            'debug': {
                'stats_before': stats_before,
                'stats_after': stats_after
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/memories/<user_id>', methods=['GET'])
def get_memories(user_id):
    """Get all memories for a user"""
    try:
        # Get user's memory instance
        mv = get_memory_instance(user_id)
        
        # Get stats
        stats = mv.stats()
        
        # Get recent entries from timeline
        limit = request.args.get('limit', 50, type=int)
        timeline_entries = mv.timeline(limit=limit)
        
        # Format memories for response
        memories = []
        for entry in timeline_entries:
            memories.append({
                'memory': entry.get('text', ''),
                'title': entry.get('title', ''),
                'label': entry.get('label', ''),
                'created_at': entry.get('timestamp', ''),
                'metadata': entry.get('metadata', {}),
                'uri': entry.get('uri', '')
            })
        
        return jsonify({
            'memories': memories,
            'count': len(memories),
            'stats': stats,
            'file_path': os.path.join(MEMVID_STORAGE_PATH, f"{user_id}.mv2")
        })
    except Exception as e:
        app.logger.error(f"Error getting memories: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/search/<user_id>', methods=['GET'])
def search_memories(user_id):
    """Search memories for a user"""
    try:
        query = request.args.get('q', '')
        k = request.args.get('k', 5, type=int)
        mode = request.args.get('mode', 'auto')  # 'auto', 'lex', or 'sem'
        
        if not query:
            return jsonify({'error': 'Query parameter "q" is required'}), 400
        
        # Get user's memory instance
        mv = get_memory_instance(user_id)
        
        # Search
        search_results = mv.find(query, k=k, mode=mode)
        
        # Format results
        results = []
        if search_results.get("hits"):
            for hit in search_results["hits"]:
                results.append({
                    'title': hit.get('title', 'Untitled'),
                    'text': hit.get('text', ''),
                    'snippet': hit.get('snippet', ''),
                    'score': hit.get('score', 0),
                    'label': hit.get('label', ''),
                    'metadata': hit.get('metadata', {})
                })
        
        return jsonify({
            'query': query,
            'mode': mode,
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        app.logger.error(f"Error searching memories: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/debug/<user_id>', methods=['GET'])
def debug_memory(user_id):
    """Debug endpoint to inspect memory file"""
    try:
        file_path = os.path.join(MEMVID_STORAGE_PATH, f"{user_id}.mv2")
        file_exists = os.path.exists(file_path)
        file_size = os.path.getsize(file_path) if file_exists else 0
        
        mv = get_memory_instance(user_id)
        stats = mv.stats()
        timeline = mv.timeline(limit=20)
        
        return jsonify({
            'user_id': user_id,
            'file_path': file_path,
            'file_exists': file_exists,
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'stats': stats,
            'recent_entries': [
                {
                    'title': e.get('title', ''),
                    'label': e.get('label', ''),
                    'text_preview': e.get('text', '')[:200],
                    'timestamp': e.get('timestamp', ''),
                    'metadata': e.get('metadata', {})
                }
                for e in timeline
            ],
            'storage_path': MEMVID_STORAGE_PATH,
            'all_files': [f for f in os.listdir(MEMVID_STORAGE_PATH) if f.endswith('.mv2')] if os.path.exists(MEMVID_STORAGE_PATH) else []
        })
    except Exception as e:
        app.logger.error(f"Error in debug endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/version', methods=['GET'])
def version():
    """Get deployment version info"""
    import subprocess
    try:
        git_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()
    except:
        git_hash = "unknown"
    
    return jsonify({
        'version': '2.0.0',
        'git_hash': git_hash,
        'memvid_available': MEMVID_AVAILABLE,
        'ui_title': 'AgentMemory',
        'has_debug_buttons': True
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        # Test if memvid_sdk can be imported and basic operations work
        test_file = os.path.join(MEMVID_STORAGE_PATH, '.health_check.mv2')
        if os.path.exists(test_file):
            os.remove(test_file)
        
        mv = create(test_file, enable_vec=True, enable_lex=True)
        mv.put(title="Health Check", label="test", text="test", enable_embedding=False)
        mv.seal()
        stats = mv.stats()
        os.remove(test_file)
        
        return jsonify({
            'status': 'healthy',
            'memvid_sdk': 'working',
            'storage_path': MEMVID_STORAGE_PATH,
            'storage_writable': os.access(MEMVID_STORAGE_PATH, os.W_OK),
            'test_stats': stats
        }), 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'storage_path': MEMVID_STORAGE_PATH
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


