import os
import urllib.parse
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from mem0 import Memory

app = Flask(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Configure Mem0 to use PostgreSQL with pgvector for persistent storage
# This is required for Heroku's ephemeral filesystem
def get_memory_instance():
    """Initialize Mem0 with PostgreSQL backend for Heroku compatibility"""
    # Check if DATABASE_URL is set (Heroku Postgres)
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Parse DATABASE_URL (format: postgres://user:password@host:port/dbname)
        # Heroku Postgres uses postgres:// but psycopg2 needs postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Enable pgvector extension if not already enabled
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cursor.close()
            conn.close()
        except Exception as e:
            app.logger.warning(f"Could not enable pgvector extension: {e}")
        
        config = {
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "connection_string": database_url,
                    "collection_name": "mem0_memories",
                    "embedding_model_dims": 1536  # OpenAI text-embedding-3-small dimensions
                }
            }
        }
        return Memory.from_config(config)
    else:
        # Fallback to default (for local development)
        # Note: This will use local Qdrant/SQLite which won't persist on Heroku
        app.logger.warning("DATABASE_URL not set. Using default storage (not persistent on Heroku)")
        return Memory()
    
# Initialize Mem0 memory
memory = get_memory_instance()

@app.route('/')
def index():
    """Render the main chat interface"""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages with memory integration"""
    try:
        data = request.json
        message = data.get('message', '').strip()
        user_id = data.get('user_id', 'default_user')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Retrieve relevant memories
        relevant_memories = memory.search(query=message, user_id=user_id, limit=3)
        memories_str = ""
        if relevant_memories.get("results"):
            memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories["results"])
        
        # Generate Assistant response
        system_prompt = """You are a helpful AI assistant with memory capabilities. 
Answer the user's question based on the query and any relevant memories.
Be conversational and helpful."""
        
        if memories_str:
            system_prompt += f"\n\nRelevant User Memories:\n{memories_str}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        response = openai_client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=messages
        )
        assistant_response = response.choices[0].message.content
        
        # Create new memories from the conversation
        messages.append({"role": "assistant", "content": assistant_response})
        memory.add(messages, user_id=user_id)
        
        return jsonify({
            'response': assistant_response,
            'memories_used': len(relevant_memories.get("results", []))
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/memories/<user_id>', methods=['GET'])
def get_memories(user_id):
    """Get all memories for a user"""
    try:
        # Search with empty query to get recent memories
        all_memories = memory.search(query="", user_id=user_id, limit=10)
        return jsonify({
            'memories': all_memories.get("results", []),
            'count': len(all_memories.get("results", []))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


