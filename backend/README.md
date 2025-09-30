# Backend README for RAG Chatbot

# RAG Chatbot Backend

This is the backend component of the RAG Chatbot project. It is built using FastAPI and serves as the API for the chatbot functionality.

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd rag-chatbot-production/backend
   ```

2. **Create a virtual environment (optional but recommended):**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the required dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

The backend will be running on `http://localhost:8000` by default. The interactive API documentation is available at `http://localhost:8000/docs` when the server is running.

## Usage

The backend provides endpoints for interacting with the chatbot. You can send requests to the API to get responses from the chatbot.

## Contributing

Feel free to submit issues or pull requests if you have suggestions or improvements for the backend.
