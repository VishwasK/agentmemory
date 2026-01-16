# AgentMemory - Heroku App

A demo application showcasing AI agent memory capabilities. This is a simple chat interface that demonstrates how agents remember user preferences and context across conversations using a single-file, portable memory system powered by MemvidAI v2.

## Features

- 🧠 **Long-term Memory**: Memvid remembers user preferences and past conversations in a single portable .mv2 file
- 💬 **Interactive Chat**: Clean, modern chat interface
- 🔍 **Memory Visualization**: See when memories are being used in responses
- 👤 **Multi-user Support**: Test with different user IDs
- 📦 **Single-File Architecture**: Everything stored in portable .mv2 files - no databases required
- 🔄 **Hybrid Search**: Combines BM25 lexical matching with semantic vector search
- ⏱️ **Time-Travel**: Built-in timeline index for temporal queries
- 📄 **PDF Knowledge Base**: Upload PDF files as reference documents - automatically chunked and indexed for search

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

### Important: Heroku's Ephemeral Filesystem

**⚠️ Critical**: Heroku dynos have an **ephemeral filesystem**. Any files written to disk are **automatically deleted** when:
- The dyno restarts (happens at least once every 24 hours)
- You deploy new code
- The dyno crashes or is manually restarted

**Why this matters for Memvid**: Memvid stores memories in `.mv2` files. By default, these are stored in `/tmp/memvid` which **will be lost** on Heroku dyno restarts!

**Solutions for Persistent Storage**:

1. **Use a mounted volume** (if available on your Heroku plan)
2. **Use cloud storage** (S3, Google Cloud Storage, etc.) - download on startup, upload on changes
3. **Use Heroku Postgres** with a file storage extension (advanced)

For this demo, we use local storage which works for testing but won't persist across restarts. For production, implement one of the solutions above.

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
   heroku config:set MEMVID_STORAGE_PATH=/tmp/memvid  # Optional, defaults to /tmp/memvid
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

- `OPENAI_API_KEY` (Required): Your OpenAI API key (used for embeddings and LLM)
- `OPENAI_MODEL` (Optional): Model to use (default: `gpt-4o-mini`)
- `MEMVID_STORAGE_PATH` (Optional): Path to store .mv2 files (default: `/tmp/memvid`)
- `PORT` (Set automatically by Heroku): Port for the web server

### Storage Configuration

The app stores one `.mv2` file per user in the configured storage path. Each file contains all memories, embeddings, and indices for that user in a single portable file. For production deployments, consider implementing cloud storage integration to persist files across dyno restarts.

## Usage

1. Enter a User ID (or use the default "demo_user")
2. Start chatting with the AI
3. Tell the AI about yourself, your preferences, or ask questions
4. In later messages, reference previous information to see Memvid's memory in action
5. Notice the memory badge showing how many memories were used in each response
6. Each user gets their own portable `.mv2` file containing all their memories

## Example Conversation

**User**: "My name is John and I love Python programming"

**AI**: "Nice to meet you, John! Python is a fantastic language..."

**User** (later): "What programming language do I like?"

**AI**: "You mentioned you love Python programming!"

## PDF Knowledge Base

You can upload PDF files as reference documents that will be automatically indexed and searchable:

1. Click the **"📄 Upload PDF"** button in the header
2. Select a PDF file from your computer
3. **Choose embedding option**: 
   - ✅ **Use embeddings** (checked by default): Enables semantic/vector search - requires OpenAI API key and uses LLM calls for embedding generation
   - ❌ **Don't use embeddings**: Uses lexical (BM25) search only - faster, no LLM costs, but less semantic understanding
4. The PDF will be automatically:
   - Extracted page by page
   - Chunked (each page stored as a separate memory frame)
   - Indexed for lexical search (always) and semantic search (if embeddings enabled)
   - Stored in your user's `.mv2` memory file

5. Once uploaded, you can ask questions about the PDF content in your conversations, and the AI will search through the PDF content along with your conversation history.

**Note**: 
- Memvid doesn't automatically chunk PDFs - we extract text from each page and store them as separate frames. This allows for precise page-level retrieval and search.
- **Embeddings vs Lexical**: Embeddings enable semantic search (finds conceptually similar content), while lexical search finds exact keyword matches. You can disable embeddings to save on LLM API costs if lexical search is sufficient for your use case.

## API Endpoints

- `GET /` - Main chat interface
- `POST /chat` - Send a chat message
  ```json
  {
    "message": "Hello!",
    "user_id": "demo_user"
  }
  ```
- `POST /upload` - Upload PDF files as knowledge references
  - Form data: 
    - `file` (PDF file, required)
    - `user_id` (optional, defaults to "default_user")
    - `enable_embeddings` (optional, "true" or "false", defaults to global ENABLE_EMBEDDINGS setting)
  - Returns: Upload status, pages processed, chunks stored, embeddings_used flag
- `GET /memories/<user_id>` - Get all memories for a user
- `GET /health` - Health check endpoint

## Technologies

- **Flask**: Web framework
- **MemvidAI v2**: Single-file memory layer for AI agents (replaces complex RAG pipelines)
- **OpenAI**: LLM provider (for embeddings and chat completion)
- **PyPDF2**: PDF text extraction library
- **Gunicorn**: WSGI HTTP Server for Heroku

## Why MemvidAI v2?

Unlike traditional vector databases or memory wrappers, MemvidAI v2 offers:

- **Single-file architecture**: Everything (data, embeddings, indices, WAL) in one portable `.mv2` file
- **No database required**: No PostgreSQL, Qdrant, or other vector databases needed
- **Hybrid search**: Combines BM25 lexical matching with semantic vector search
- **Time-travel debugging**: Built-in timeline index for temporal queries
- **Crash-safe**: Embedded WAL ensures data integrity
- **Offline-first**: Works completely offline, no cloud dependencies
- **Sub-5ms search**: Lightning-fast local memory access

## License

Apache 2.0

## References

- [Memvid Documentation](https://docs.memvid.com)
- [Memvid GitHub](https://github.com/memvid/memvid)
- [Memvid Python SDK](https://pypi.org/project/memvid-sdk/)


