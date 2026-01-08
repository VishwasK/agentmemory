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
            # Open existing file - use "auto" mode which handles both read and write
            # The file already has vector index enabled from creation
            mv = use("basic", file_path, mode="auto")
            logger.info(f"Opened existing memory file: {file_path}")
            return mv
        except Exception as e:
            logger.warning(f"Could not open existing file {file_path}, creating new: {e}")
    
    # Create new file with vector and lexical search enabled
    try:
        mv = create(file_path, enable_vec=True, enable_lex=True)
        logger.info(f"Created new memory file: {file_path}")
        return mv
    except Exception as e:
        logger.error(f"Failed to create memory file {file_path}: {e}")
        raise

@app.route('/')
def index():
    """Render the main chat interface"""
    import os
    
    # Read template file directly to verify content
    template_path = os.path.join(app.root_path, app.template_folder, 'index.html')
    template_exists = os.path.exists(template_path)
    
    # Log what we're actually serving
    if template_exists:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
            has_agentmemory = 'AgentMemory' in template_content
            has_view_memories = 'View Memories' in template_content
            has_mem0 = 'Mem0' in template_content
            logger.info(f"Template file: {template_path}")
            logger.info(f"File size: {len(template_content)} bytes")
            logger.info(f"Contains 'AgentMemory': {has_agentmemory}")
            logger.info(f"Contains 'View Memories': {has_view_memories}")
            logger.info(f"Contains 'Mem0': {has_mem0}")
            
            if has_mem0 and not has_agentmemory:
                logger.error("ERROR: Template still contains old Mem0 content!")
                return f"ERROR: Template file contains old content. Path: {template_path}", 500
    
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
    template_path = os.path.join(app.root_path, app.template_folder, 'index.html')
    template_exists = os.path.exists(template_path)
    
    info = {
        'template_folder': app.template_folder,
        'template_path': template_path,
        'template_exists': template_exists,
        'current_dir': os.getcwd(),
        'app_root': app.root_path,
        'root_path': app.root_path
    }
    
    if template_exists:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            info['file_size'] = len(content)
            info['has_agentmemory'] = 'AgentMemory' in content
            info['has_view_memories'] = 'View Memories' in content
            info['has_search_button'] = 'searchMemories' in content
            info['has_mem0'] = 'Mem0 Demo' in content or 'Mem0' in content
            info['title_content'] = content[content.find('<title>')+7:content.find('</title>')] if '<title>' in content else 'not found'
            info['h1_content'] = content[content.find('<h1>')+4:content.find('</h1>')] if '<h1>' in content else 'not found'
            # Show first 500 chars
            info['content_preview'] = content[:500]
    else:
        # Try alternative paths
        alt_paths = [
            os.path.join('templates', 'index.html'),
            os.path.join(app.root_path, 'templates', 'index.html'),
            'templates/index.html'
        ]
        info['alternative_paths_checked'] = []
        for alt_path in alt_paths:
            exists = os.path.exists(alt_path)
            info['alternative_paths_checked'].append({'path': alt_path, 'exists': exists})
    
    return jsonify(info)

@app.route('/raw-template', methods=['GET'])
def raw_template():
    """Return raw template content for debugging"""
    import os
    template_path = os.path.join(app.root_path, app.template_folder, 'index.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"Template not found at: {template_path}", 404

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
        frame_count = stats_before.get('frame_count', 0)
        has_vec_index = stats_before.get('has_vec_index', False)
        has_lex_index = stats_before.get('has_lex_index', False)
        
        app.logger.info(f"Frame count: {frame_count}, Has vector index: {has_vec_index}, Has lexical index: {has_lex_index}")
        
        # Only search if we have stored memories
        search_results = {"hits": []}
        search_mode = "none"
        
        if frame_count > 0:
            # We have memories, try to search
            try:
                # Prefer lexical search first (more reliable), then try hybrid if vector is available
                if has_lex_index:
                    search_results = mv.find(message, k=3, mode="lex")
                    search_mode = "lex"
                    app.logger.info(f"Used lexical search, found {len(search_results.get('hits', []))} results")
                elif has_vec_index:
                    # Only use vector if lexical isn't available
                    search_results = mv.find(message, k=3, mode="sem")
                    search_mode = "sem"
                    app.logger.info(f"Used semantic search, found {len(search_results.get('hits', []))} results")
                else:
                    app.logger.warning("No search indexes available")
            except Exception as e:
                error_msg = str(e)
                app.logger.error(f"Search failed: {error_msg}")
                # If it's a vector index error and we have lexical, try that
                if "MV011" in error_msg or "vector" in error_msg.lower():
                    if has_lex_index:
                        try:
                            app.logger.info("Retrying with lexical search after vector error")
                            search_results = mv.find(message, k=3, mode="lex")
                            search_mode = "lex"
                        except Exception as e2:
                            app.logger.error(f"Lexical search also failed: {e2}")
                            search_results = {"hits": []}
                    else:
                        app.logger.warning("Vector search failed and no lexical index available")
                        search_results = {"hits": []}
                else:
                    search_results = {"hits": []}
        else:
            app.logger.info("No memories stored yet, skipping search")
        
        app.logger.info(f"Search results (mode={search_mode}): {search_results}")
        
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
        stored_count = 0
        
        # Store user message - try with embedding first, fallback without if it fails
        try:
            mv.put(
                title=f"User Message - {timestamp}",
                label="user_message",
                text=message,
                metadata={"user_id": user_id, "type": "user_message", "timestamp": timestamp},
                enable_embedding=True,
                embedding_model="openai-small"  # Uses OPENAI_API_KEY
            )
            stored_count += 1
            logger.info(f"Stored user message: {message[:50]}...")
        except Exception as e:
            logger.error(f"Failed to store user message with embedding: {e}")
            # Try without embedding
            try:
                mv.put(
                    title=f"User Message - {timestamp}",
                    label="user_message",
                    text=message,
                    metadata={"user_id": user_id, "type": "user_message", "timestamp": timestamp},
                    enable_embedding=False
                )
                stored_count += 1
                logger.info("Stored user message without embedding")
            except Exception as e2:
                logger.error(f"Failed to store user message: {e2}")
        
        # Store assistant response
        try:
            mv.put(
                title=f"Assistant Response - {timestamp}",
                label="assistant_response",
                text=assistant_response,
                metadata={"user_id": user_id, "type": "assistant_response", "timestamp": timestamp},
                enable_embedding=True,
                embedding_model="openai-small"
            )
            stored_count += 1
            logger.info(f"Stored assistant response: {assistant_response[:50]}...")
        except Exception as e:
            logger.error(f"Failed to store assistant response with embedding: {e}")
            # Try without embedding
            try:
                mv.put(
                    title=f"Assistant Response - {timestamp}",
                    label="assistant_response",
                    text=assistant_response,
                    metadata={"user_id": user_id, "type": "assistant_response", "timestamp": timestamp},
                    enable_embedding=False
                )
                stored_count += 1
                logger.info("Stored assistant response without embedding")
            except Exception as e2:
                logger.error(f"Failed to store assistant response: {e2}")
        
        # Also store combined conversation (without embedding to avoid issues)
        conversation_text = f"User: {message}\nAssistant: {assistant_response}"
        try:
            mv.put(
                title=f"Conversation - {timestamp}",
                label="conversation",
                text=conversation_text,
                metadata={"user_id": user_id, "type": "conversation", "timestamp": timestamp},
                enable_embedding=False  # Don't enable embedding for combined to avoid errors
            )
            stored_count += 1
            logger.info("Stored combined conversation")
        except Exception as e:
            logger.error(f"Failed to store combined conversation: {e}")
        
        # Commit changes - this is critical for persistence
        try:
            mv.seal()
            logger.info(f"Successfully committed {stored_count} memory entries")
        except Exception as e:
            logger.error(f"Failed to seal memory file: {e}")
            # Try to continue anyway
        
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
        
        # Get stats to check available indexes
        stats = mv.stats()
        has_vec = stats.get('has_vec_index', False)
        has_lex = stats.get('has_lex_index', False)
        
        # Adjust mode based on available indexes
        if mode == "auto" and not has_vec:
            mode = "lex"
            logger.warning(f"Vector index not available, falling back to lexical search")
        elif mode == "sem" and not has_vec:
            return jsonify({'error': 'Vector index is not enabled. Use mode=lex or enable vector index.'}), 400
        
        # Search with error handling
        try:
            search_results = mv.find(query, k=k, mode=mode)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Search failed with mode {mode}: {error_msg}")
            
            # If vector search failed, try lexical
            if mode != "lex" and has_lex:
                logger.info("Retrying with lexical search")
                try:
                    search_results = mv.find(query, k=k, mode="lex")
                    mode = "lex"
                except Exception as e2:
                    return jsonify({'error': f'Search failed: {str(e2)}'}), 500
            else:
                return jsonify({'error': f'Search failed: {error_msg}'}), 500
        
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

@app.route('/test-storage/<user_id>', methods=['POST'])
def test_storage(user_id):
    """Test endpoint to verify storage is working"""
    try:
        data = request.json
        test_text = data.get('text', 'Test message')
        
        mv = get_memory_instance(user_id)
        
        # Try storing
        timestamp = int(time.time())
        mv.put(
            title=f"Test Entry - {timestamp}",
            label="test",
            text=test_text,
            metadata={"test": True, "timestamp": timestamp},
            enable_embedding=False  # Skip embedding for test
        )
        mv.seal()
        
        # Try retrieving
        stats = mv.stats()
        timeline = mv.timeline(limit=5)
        
        # Try searching
        search_results = mv.find(test_text[:10], k=3, mode="lex")
        
        return jsonify({
            'success': True,
            'stored_text': test_text,
            'stats': stats,
            'timeline_count': len(timeline),
            'timeline_preview': [
                {
                    'title': e.get('title', ''),
                    'text': e.get('text', '')[:100] if e.get('text') else '',
                    'label': e.get('label', '')
                }
                for e in timeline[:3]
            ],
            'search_results': len(search_results.get('hits', []))
        })
    except Exception as e:
        logger.error(f"Test storage failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

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


