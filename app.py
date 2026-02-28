# ============================================================
# YouTube Q&A — Flask API Server
# ============================================================
# Serves one endpoint: POST /ask
# Receives { video_id, question } from the Chrome extension,
# returns { answer } as JSON.
#
# Run with: python app.py
# ============================================================

import os
from dotenv import load_dotenv

# ── Load .env FIRST, before any other imports ─────────────────
load_dotenv(dotenv_path=r"C:\Studies\Langchain\Langchain_models\.env")

# ── Verify API key loaded correctly ───────────────────────────
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not api_key:
    raise EnvironmentError(
        "❌ API key not found.\n"
        "Make sure your .env file contains: GOOGLE_API_KEY=your_key_here\n"
        f"Looked in: C:\\Studies\\Langchain\\Langchain_models\\.env"
    )
print(f"[✓] API key loaded (...{api_key[-4:]})")

from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_google_genai import ChatGoogleGenerativeAI

from main import (
    fetch_transcript,
    split_transcript,
    build_vector_store,
    build_rag_chain,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBED_MODEL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    TOP_K_RESULTS,
)

# ── Init LLM once at startup (not per request) ────────────────
llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL,
    temperature=LLM_TEMPERATURE,
    google_api_key=api_key
)
print("[✓] LLM initialized")

# ── Flask app ─────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # allows requests from the Chrome extension

# Cache: video_id → rag_chain
# Avoids re-embedding the same video on every question
cache = {}


@app.route("/ask", methods=["POST"])
def ask():
    """
    Expects JSON body: { "video_id": "...", "question": "..." }
    Returns JSON:      { "answer": "..." } or { "error": "..." }
    """
    data = request.json
    video_id = data.get("video_id")
    question = data.get("question")

    if not video_id or not question:
        return jsonify({"error": "Missing video_id or question"}), 400

    # Build RAG chain for this video if not already cached
    if video_id not in cache:
        print(f"[→] New video: {video_id} — building pipeline...")
        try:
            transcript  = fetch_transcript(video_id)
            chunks      = split_transcript(transcript, CHUNK_SIZE, CHUNK_OVERLAP)
            vector_store = build_vector_store(chunks, EMBED_MODEL)
            retriever   = vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": TOP_K_RESULTS}
            )
            cache[video_id] = build_rag_chain(retriever, llm)
            print(f"[✓] Pipeline ready for video: {video_id}")
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 400

    # Run the question through the cached chain
    print(f"[→] Question: {question}")
    answer = cache[video_id].invoke(question)
    print(f"[✓] Answer: {answer[:80]}...")
    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(port=5000, debug=True)