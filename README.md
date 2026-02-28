## YouTube Q&A – RAG over YouTube Transcripts

This project lets you **ask natural-language questions about any YouTube video**, powered by a **Retrieval-Augmented Generation (RAG)** pipeline built with:

- **YouTube transcripts** via `youtube-transcript-api`
- **Chunking** via LangChain text splitters
- **Dense embeddings** via `HuggingFaceEmbeddings`
- **FAISS** vector search
- **Gemini** (via `ChatGoogleGenerativeAI`) as the LLM

A minimal Flask API exposes this pipeline, and a simple Chrome extension injects a sidebar on YouTube watch pages to call the API. The focus of this repository is the **RAG pipeline**, not the frontend.

---

## High‑Level Architecture

- **Chrome Extension**
  - Injects a sidebar iframe on `https://www.youtube.com/watch*` pages.
  - Sends `video_id` and `question` to the local Flask API (`POST /ask`).

- **Flask API (`app.py`)**
  - Single endpoint: `POST /ask`.
  - For each `video_id`, **lazy-builds** a full RAG pipeline and **caches** it in memory.
  - For every question, runs the query through the cached pipeline to generate an answer.

- **RAG Core (`main.py`)**
  - Contains the actual **YouTube → transcript → chunks → embeddings → FAISS → retriever → Gemini** logic.
  - Designed so the RAG pipeline is reusable outside of the Chrome/Flask context.

The frontend (HTML/CSS/JS) and Flask wiring are intentionally thin so that the RAG logic stays central and easy to understand.

---

## RAG Pipeline in Detail

All the core steps live in `main.py`. The configuration constants are:

- **`CHUNK_SIZE`**: `1000` characters  
- **`CHUNK_OVERLAP`**: `200` characters  
- **`TOP_K_RESULTS`**: `4` retrieved chunks per question  
- **`EMBED_MODEL`**: `"sentence-transformers/all-MiniLM-L6-v2"`  
- **`LLM_MODEL`**: `"gemini-3-flash-preview"`  
- **`LLM_TEMPERATURE`**: `0.7`

### 1. Fetch YouTube Transcript

Function: `fetch_transcript(video_id: str, language: str = "en") -> str`

- Uses `YouTubeTranscriptApi` to fetch the transcript for the given video.
- Handles common failure cases:
  - Transcripts disabled.
  - No transcript available in the requested language.
- Concatenates all transcript entries into **one long string**.

Conceptually:

```python
transcript_list = api.fetch(video_id, languages=[language])
transcript = " ".join(chunk.text for chunk in transcript_list)
```

If anything goes wrong, a `RuntimeError` is raised with a human-readable message, which the API layer can return to clients.

### 2. Split Transcript into Chunks

Function: `split_transcript(transcript: str, chunk_size: int, chunk_overlap: int)`

- Uses `RecursiveCharacterTextSplitter` from LangChain.
- Produces overlapping chunks so that **context flows across boundaries**.
- Returns a list of LangChain `Document` objects, each holding a chunk of the transcript.

Why overlap?  
Without overlap, an important sentence might be split across two chunks and never appear fully in any single one. The overlap keeps enough shared context to avoid brittle cuts.

### 3. Build FAISS Vector Store

Function: `build_vector_store(chunks, embed_model_name: str)`

- Creates a `HuggingFaceEmbeddings` instance using the configured model (`all-MiniLM-L6-v2`).
- Embeds all transcript chunks.
- Indexes them in a **FAISS** vector store.

This is the step where the transcript becomes **searchable by meaning** rather than by exact text. The result is a `FAISS` object that can be turned into a retriever.

### 4. Format Retrieved Documents

Function: `format_docs(retrieved_docs) -> str`

- Takes the list of retrieved `Document`s and concatenates `page_content` with double newlines.
- Produces a single **context string** fed into the LLM prompt.

This is intentionally simple: the goal is just to provide a compact but readable context block for Gemini.

### 5. Build the RAG Chain

Function: `build_rag_chain(retriever, llm)`

This function wires everything together into a **LangChain runnable**:

1. **Parallel branch** (`RunnableParallel`):
   - Branch 1: `retriever` → `format_docs` to build the `context`.
   - Branch 2: `RunnablePassthrough()` to forward the original `question`.
2. **Prompt** (`PromptTemplate`):
   - Enforces that Gemini must **only** answer using the transcript context.
   - If the context is insufficient, it instructs the model to say it doesn’t know.
3. **LLM call** (`ChatGoogleGenerativeAI`) + `StrOutputParser`:
   - Calls Gemini and parses the output into a simple string answer.

Pseudocode:

```python
parallel_chain = RunnableParallel({
    "context":  retriever | RunnableLambda(format_docs),
    "question": RunnablePassthrough(),
})

rag_chain = parallel_chain | prompt | llm | StrOutputParser()
```

Calling `rag_chain.invoke(question)` returns a **final answer string** grounded in the transcript.

---

## How the API Uses the Pipeline

The Flask API (`app.py`) is intentionally minimal and mostly delegates to `main.py`.

Key ideas:

- **Environment & API key**
  - Loads `C:\Studies\Langchain\Langchain_models\.env` with `load_dotenv`.
  - Expects `GOOGLE_API_KEY` or `GEMINI_API_KEY` to be set.
  - Fails fast at startup if no key is found, with a clear error message.

- **LLM initialization**
  - Creates a single `ChatGoogleGenerativeAI` instance at startup:
    - Model: `LLM_MODEL` from `main.py`.
    - Temperature: `LLM_TEMPERATURE`.
    - API key: taken from the environment.
  - This avoids reinitializing the LLM on every request.

- **In-memory cache**
  - `cache: Dict[video_id, rag_chain]`.
  - On the **first question** for a given `video_id`, the API:
    1. Fetches transcript.
    2. Splits into chunks.
    3. Builds FAISS vector store.
    4. Creates a retriever.
    5. Calls `build_rag_chain(retriever, llm)`.
    6. Stores the chain in `cache[video_id]`.
  - On subsequent questions for the same video, it **reuses** the pipeline and only runs the question through it.

This design ensures that the **expensive steps** (fetching transcripts, embeddings, FAISS indexing) happen only once per video in the lifetime of the server process.

---

## Minimal Setup & Usage

Although the focus is on the RAG logic, here is what you need to run the project end‑to‑end.

### 1. Environment & Dependencies

1. Create and activate a Python virtual environment (optional but recommended).
2. Install Python packages (adjust if you already have them elsewhere):

```bash
pip install \
  flask flask-cors python-dotenv \
  youtube_transcript_api \
  langchain langchain-community langchain-text-splitters \
  langchain-google-genai \
  faiss-cpu \
  sentence-transformers
```

3. Create or update the `.env` file used by the project:

- Path expected by the code:
  - `C:\Studies\Langchain\Langchain_models\.env`

- Inside that file, set your Gemini API key:

```text
GOOGLE_API_KEY=your_gemini_api_key_here
```

or

```text
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Run the RAG API Server

From the project root (`Youtube QA Extension` folder):

```bash
python app.py
```

If everything is configured correctly, you should see logs similar to:

- API key loaded.
- LLM initialized.
- When a question arrives, logs showing transcript fetch, chunking, FAISS build (for the first question per video), and answers.

The server listens on `http://localhost:5000` and exposes:

- `POST /ask` with JSON body:

```json
{
  "video_id": "YOUTUBE_VIDEO_ID",
  "question": "Your question about the video"
}
```

Response:

```json
{
  "answer": "Grounded answer based on the transcript"
}
```

If something goes wrong (no transcript, invalid ID, etc.), you get:

```json
{
  "error": "Human-readable error message"
}
```

---

## Chrome Extension (High Level Only)

The Chrome extension is intentionally lightweight and mainly a UI wrapper.

- **Content script**:
  - Injects an iframe sidebar into YouTube watch pages.
  - Constructs the iframe URL as `sidebar.html?video_id=<current_video_id>`.

- **Sidebar page**:
  - Simple chat-style UI (HTML/CSS/JS).
  - On submit, reads the current `video_id` from the URL.
  - Sends `fetch("http://localhost:5000/ask", { video_id, question })`.
  - Renders the answer returned by the API.

Because this part is mostly standard web/extension code, the main learning/extension point for this project is the **RAG core**.

---

## Extending the RAG Pipeline

Some ideas for further experiments:

- **Change embedding model**
  - Swap `EMBED_MODEL` for a different `sentence-transformers` model (e.g., `all-mpnet-base-v2`).
  - Compare retrieval quality and latency.

- **Tune chunking**
  - Adjust `CHUNK_SIZE` and `CHUNK_OVERLAP`.
  - Smaller chunks = more granular retrieval but potentially less context per chunk.

- **Add metadata**
  - When building documents, store timestamps or segment indices.
  - Use metadata to show *where* in the video an answer came from.

- **Add streaming answers**
  - Wrap the Gemini call in a streaming interface (where supported) to show partial responses in the UI.

The current structure (clean separation between `main.py` and `app.py`) is designed so that these changes can be made **entirely in the RAG layer** without touching the frontend.

---

## Summary

This repository demonstrates a complete but compact **RAG pipeline over YouTube transcripts**:

- Extract transcript → chunk → embed → index with FAISS → retrieve → answer with Gemini.
- Exposed via a single `/ask` endpoint.
- Driven by a simple Chrome extension UI.

If you want to learn or prototype with RAG on real-world content (YouTube videos) and Gemini, this project is a good starting point focused on the **core ML / retrieval logic**, not on frontend plumbing.

## Note

*I used Gemini model api for llm responses and local huggingface model for encodings, likewise we can use both local models too. Just need some imports and format changes, rest all remains same.*