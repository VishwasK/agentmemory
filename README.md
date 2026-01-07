# Mem0 Demo - Heroku App

A quick demo application showcasing Mem0's memory capabilities for AI agents. This is a simple chat interface that demonstrates how Mem0 remembers user preferences and context across conversations.

## Features

- 🧠 **Long-term Memory**: Mem0 remembers user preferences and past conversations
- 💬 **Interactive Chat**: Clean, modern chat interface
- 🔍 **Memory Visualization**: See when memories are being used in responses
- 👤 **Multi-user Support**: Test with different user IDs

## Local Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd AgentMemory
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**
   ```bash
   export OPENAI_API_KEY=your_openai_api_key_here
   export OPENAI_MODEL=gpt-4o-mini  # Optional, defaults to gpt-4o-mini
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Open your browser**
   Navigate to `http://localhost:5000`

## Heroku Deployment

### Prerequisites
- Heroku account
- Heroku CLI installed
- Git repository initialized

### Deployment Steps

1. **Login to Heroku**
   ```bash
   heroku login
   ```

2. **Create a new Heroku app**
   ```bash
   heroku create your-app-name
   ```

3. **Set environment variables**
   ```bash
   heroku config:set OPENAI_API_KEY=your_openai_api_key_here
   heroku config:set OPENAI_MODEL=gpt-4o-mini  # Optional
   ```

4. **Deploy to Heroku**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push heroku main
   ```

5. **Open your app**
   ```bash
   heroku open
   ```

### Environment Variables

- `OPENAI_API_KEY` (Required): Your OpenAI API key
- `OPENAI_MODEL` (Optional): Model to use (default: `gpt-4o-mini`)
- `PORT` (Set automatically by Heroku): Port for the web server

## Usage

1. Enter a User ID (or use the default "demo_user")
2. Start chatting with the AI
3. Tell the AI about yourself, your preferences, or ask questions
4. In later messages, reference previous information to see Mem0's memory in action
5. Notice the memory badge showing how many memories were used in each response

## Example Conversation

**User**: "My name is John and I love Python programming"

**AI**: "Nice to meet you, John! Python is a fantastic language..."

**User** (later): "What programming language do I like?"

**AI**: "You mentioned you love Python programming!"

## API Endpoints

- `GET /` - Main chat interface
- `POST /chat` - Send a chat message
  ```json
  {
    "message": "Hello!",
    "user_id": "demo_user"
  }
  ```
- `GET /memories/<user_id>` - Get all memories for a user
- `GET /health` - Health check endpoint

## Technologies

- **Flask**: Web framework
- **Mem0**: Memory layer for AI agents
- **OpenAI**: LLM provider
- **Gunicorn**: WSGI HTTP Server for Heroku

## License

Apache 2.0

## References

- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)

