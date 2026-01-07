import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from mem0 import Memory

app = Flask(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize Mem0 memory
memory = Memory()

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

