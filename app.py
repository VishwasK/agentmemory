import os
import json
import time
import logging
import re

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
            # Extract key terms from question queries (e.g., "what is my name" -> "name")
            # This helps find factual content instead of the question itself
            search_query = message
            message_lower = message.lower().strip()
            original_message = message  # Keep original for filtering
            
            # If query looks like a question asking for information, extract key terms
            question_patterns = [
                r'what (is|are) (my|the|your) (\w+)',
                r'who (is|are) (my|the|your) (\w+)',
                r'where (is|are) (my|the|your) (\w+)',
                r'when (is|are|was|were) (my|the|your) (\w+)',
                r'how (is|are|was|were) (my|the|your) (\w+)',
            ]
            
            for pattern in question_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    # Extract the key term (the thing being asked about)
                    key_term = match.group(3) if len(match.groups()) >= 3 else match.group(2)
                    if key_term and len(key_term) > 2:  # Only use if meaningful
                        search_query = key_term
                        app.logger.info(f"Extracted key term from question: '{message}' -> '{search_query}' (but filtering against original)")
                        break
            
            try:
                # Get more results (k=5) so we can filter out the query itself
                # Prefer lexical search first (more reliable), then try hybrid if vector is available
                if has_lex_index:
                    search_results = mv.find(search_query, k=5, mode="lex")
                    search_mode = "lex"
                    app.logger.info(f"Used lexical search with query '{search_query}', found {len(search_results.get('hits', []))} results")
                elif has_vec_index:
                    # Only use vector if lexical isn't available
                    search_results = mv.find(search_query, k=5, mode="sem")
                    search_mode = "sem"
                    app.logger.info(f"Used semantic search with query '{search_query}', found {len(search_results.get('hits', []))} results")
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
            # Filter and process results
            # 1. Filter out results that are too similar to the query (to avoid returning the question itself)
            # 2. Prioritize factual content over questions
            # Use original message for filtering, not the search query (which might be extracted key term)
            message_lower = original_message.lower().strip()
            message_words = set(message_lower.split())
            
            app.logger.info(f"Processing {len(search_results['hits'])} search results for query: '{message}'")
            
            filtered_hits = []
            for i, hit in enumerate(search_results["hits"]):
                # Get content from snippet, text, or preview
                snippet = hit.get('snippet', '') or hit.get('text', '') or hit.get('preview', '')
                score = hit.get('score', 0)
                title = hit.get('title', 'Untitled')
                
                app.logger.info(f"Result {i+1}: snippet={snippet[:100] if snippet else 'EMPTY'}, score={score}")
                
                # Clean up snippet - remove metadata tags if present
                if snippet:
                    # Remove common metadata patterns
                    lines = snippet.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        # Skip metadata lines
                        if not any(line.lower().startswith(prefix) for prefix in ['title:', 'labels:', 'tags:', 'extractous_metadata:']):
                            cleaned_lines.append(line)
                    snippet = '\n'.join(cleaned_lines).strip()
                
                if not snippet:
                    app.logger.info(f"Result {i+1}: Skipped - empty snippet after cleaning")
                    continue
                
                snippet_lower = snippet.lower().strip()
                
                # Skip if snippet is too similar to the query (likely the question itself)
                # Check if snippet starts with or is exactly the query
                snippet_first_line = snippet_lower.split('\n')[0].strip()  # Get first line only
                
                # Skip if first line is exactly the query (allowing minor punctuation differences)
                if snippet_first_line == message_lower or snippet_first_line.replace('?', '').replace('!', '').strip() == message_lower:
                    app.logger.info(f"Result {i+1}: FILTERED - first line matches query exactly: '{snippet_first_line}'")
                    continue
                
                # Skip if snippet contains the full query as a substring and is roughly the same length
                if message_lower in snippet_lower and len(snippet_lower) < len(message_lower) * 1.5:
                    app.logger.info(f"Result {i+1}: FILTERED - too similar to query (substring match): '{snippet[:50]}...'")
                    continue
                
                # Skip if snippet words are a subset of query words (query is more specific)
                snippet_words = set(snippet_lower.split())
                if len(snippet_words) <= len(message_words) + 1 and snippet_words.issubset(message_words):
                    app.logger.info(f"Result {i+1}: FILTERED - words are subset of query: {snippet_words} subset of {message_words}")
                    continue
                
                # Prefer results that look like factual statements (contain "is", "was", "are", etc.)
                # or contain proper nouns (capitalized words)
                is_factual = any(word in snippet_lower for word in [' is ', ' was ', ' are ', ' were ', ' has ', ' have '])
                has_proper_noun = any(word[0].isupper() for word in snippet.split() if len(word) > 1)
                
                app.logger.info(f"Result {i+1}: KEPT - snippet='{snippet[:50]}...', is_factual={is_factual}, has_proper_noun={has_proper_noun}, score={score}")
                
                filtered_hits.append({
                    'snippet': snippet,
                    'score': score,
                    'title': title,
                    'is_factual': is_factual,
                    'has_proper_noun': has_proper_noun
                })
            
            app.logger.info(f"After filtering: {len(filtered_hits)} results kept out of {len(search_results['hits'])} total")
            
            # Sort by: factual content first, then score
            filtered_hits.sort(key=lambda x: (not x['is_factual'], -x['score']))
            
            # Take top 3 after filtering
            memories_used = min(len(filtered_hits), 3)
            app.logger.info(f"Using top {memories_used} results after sorting")
            
            for hit in filtered_hits[:memories_used]:
                memories_str += f"- {hit['snippet']}\n"
                search_details.append({
                    'title': hit['title'],
                    'snippet': hit['snippet'][:200],
                    'score': hit['score']
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
        
        # Store user message - disable embedding for now to avoid errors
        # We'll use lexical search which works without embeddings
        try:
            frame_id = mv.put(
                title=f"User Message - {timestamp}",
                label="user_message",
                text=message,
                metadata={"user_id": user_id, "type": "user_message", "timestamp": timestamp},
                enable_embedding=False  # Disable embedding to avoid errors
            )
            stored_count += 1
            logger.info(f"Stored user message (frame_id={frame_id}): {message[:50]}...")
        except Exception as e:
            logger.error(f"Failed to store user message: {e}", exc_info=True)
        
        # Store assistant response - disable embedding
        try:
            frame_id = mv.put(
                title=f"Assistant Response - {timestamp}",
                label="assistant_response",
                text=assistant_response,
                metadata={"user_id": user_id, "type": "assistant_response", "timestamp": timestamp},
                enable_embedding=False  # Disable embedding to avoid errors
            )
            stored_count += 1
            logger.info(f"Stored assistant response (frame_id={frame_id}): {assistant_response[:50]}...")
        except Exception as e:
            logger.error(f"Failed to store assistant response: {e}", exc_info=True)
        
        # Also store combined conversation (without embedding)
        conversation_text = f"User: {message}\nAssistant: {assistant_response}"
        try:
            frame_id = mv.put(
                title=f"Conversation - {timestamp}",
                label="conversation",
                text=conversation_text,
                metadata={"user_id": user_id, "type": "conversation", "timestamp": timestamp},
                enable_embedding=False
            )
            stored_count += 1
            logger.info(f"Stored combined conversation (frame_id={frame_id})")
        except Exception as e:
            logger.error(f"Failed to store combined conversation: {e}", exc_info=True)
        
        # Commit changes - this is critical for persistence
        try:
            mv.seal()
            logger.info(f"Successfully committed {stored_count} memory entries")
            
            # Verify storage by checking stats after commit
            stats_after = mv.stats()
            logger.info(f"After commit - frame_count: {stats_after.get('frame_count', 0)}")
            
            # Try a quick search to verify data is searchable
            if stored_count > 0:
                try:
                    test_search = mv.find(message[:10] if len(message) > 10 else message, k=1, mode="lex")
                    logger.info(f"Verification search found {len(test_search.get('hits', []))} results")
                except Exception as e:
                    logger.warning(f"Verification search failed: {e}")
        except Exception as e:
            logger.error(f"Failed to seal memory file: {e}", exc_info=True)
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
        # Note: timeline() returns preview field, not text/title/label directly
        memories = []
        for entry in timeline_entries:
            preview = entry.get('preview', '')
            # Extract title from preview if it contains "title: ..."
            title = entry.get('title', '')
            if not title and preview:
                # Preview format: "content\ntitle: X\n..." or "title: X\ncontent..."
                if 'title:' in preview.lower():
                    for line in preview.split('\n'):
                        if 'title:' in line.lower():
                            title = line.split('title:', 1)[1].strip()
                            break
            
            memories.append({
                'memory': preview or entry.get('text', ''),
                'title': title,
                'label': entry.get('label', ''),
                'preview': preview,
                'created_at': entry.get('timestamp', ''),
                'frame_id': entry.get('frame_id', ''),
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
        apply_filter = request.args.get('filter', 'true').lower() == 'true'  # Option to disable filtering
        
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
        raw_results = []
        filtered_results = []
        
        if search_results.get("hits"):
            message_lower = query.lower().strip()
            message_words = set(message_lower.split())
            
            for hit in search_results["hits"]:
                snippet = hit.get('snippet', '') or hit.get('text', '') or hit.get('preview', '')
                score = hit.get('score', 0)
                title = hit.get('title', 'Untitled')
                
                # Clean up snippet
                if snippet:
                    lines = snippet.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        if not any(line.lower().startswith(prefix) for prefix in ['title:', 'labels:', 'tags:', 'extractous_metadata:']):
                            cleaned_lines.append(line)
                    snippet = '\n'.join(cleaned_lines).strip()
                
                raw_result = {
                    'title': title,
                    'text': hit.get('text', ''),
                    'snippet': snippet,
                    'score': score,
                    'label': hit.get('label', ''),
                    'metadata': hit.get('metadata', {})
                }
                raw_results.append(raw_result)
                
                # Apply filtering if requested
                if apply_filter and snippet:
                    snippet_lower = snippet.lower().strip()
                    snippet_first_line = snippet_lower.split('\n')[0].strip()
                    
                    # Skip if matches query exactly
                    if snippet_first_line == message_lower or snippet_first_line.replace('?', '').replace('!', '').strip() == message_lower:
                        continue
                    
                    # Skip if too similar
                    if message_lower in snippet_lower and len(snippet_lower) < len(message_lower) * 1.5:
                        continue
                    
                    # Skip if words are subset
                    snippet_words = set(snippet_lower.split())
                    if len(snippet_words) <= len(message_words) + 1 and snippet_words.issubset(message_words):
                        continue
                
                filtered_results.append(raw_result)
        
        return jsonify({
            'query': query,
            'mode': mode,
            'filter_applied': apply_filter,
            'raw_results': raw_results,
            'filtered_results': filtered_results,
            'raw_count': len(raw_results),
            'filtered_count': len(filtered_results)
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
        
        # Try searching to see if content is actually searchable
        search_test_results = []
        if stats.get('frame_count', 0) > 0:
            try:
                # Try searching for common words
                test_queries = ["user", "message", "name", "vishwas"]
                for query in test_queries:
                    try:
                        results = mv.find(query, k=3, mode="lex")
                        if results.get('hits'):
                            search_test_results.append({
                                'query': query,
                                'found': len(results.get('hits', [])),
                                'first_hit': {
                                    'title': results['hits'][0].get('title', ''),
                                    'text': results['hits'][0].get('text', '')[:100] if results['hits'][0].get('text') else '',
                                    'snippet': results['hits'][0].get('snippet', '')[:100] if results['hits'][0].get('snippet') else ''
                                }
                            })
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Search test failed: {e}")
        
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
                    'text': e.get('text', ''),
                    'preview': e.get('preview', ''),  # Memvid returns preview in timeline
                    'text_preview': e.get('preview', '')[:200] if e.get('preview') else (e.get('text', '')[:200] if e.get('text') else ''),
                    'timestamp': e.get('timestamp', ''),
                    'frame_id': e.get('frame_id', ''),
                    'uri': e.get('uri', ''),
                    'metadata': e.get('metadata', {}),
                    'all_keys': list(e.keys()) if isinstance(e, dict) else []
                }
                for e in timeline
            ],
            'search_test': search_test_results,
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


