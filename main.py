# ============================================================
# YouTube Video Q&A Pipeline — Core Functions
# ============================================================
# Imported by app.py (Flask server).
# Contains all pipeline logic: transcript → chunks → FAISS → RAG chain.
# ============================================================

import os
from dotenv import load_dotenv

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser


# ── Configuration ─────────────────────────────────────────────

CHUNK_SIZE      = 1000
CHUNK_OVERLAP   = 200
TOP_K_RESULTS   = 4
EMBED_MODEL     = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL       = "gemini-3-flash-preview"
LLM_TEMPERATURE = 0.7


# ── Step 1: Fetch Transcript ──────────────────────────────────

def fetch_transcript(video_id: str, language: str = "en") -> str:
    """Fetch and concatenate the transcript text for a YouTube video."""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id, languages=[language])
        transcript = " ".join(chunk.text for chunk in transcript_list)
        print(f"[✓] Transcript fetched ({len(transcript)} characters)")
        return transcript

    except TranscriptsDisabled:
        raise RuntimeError("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        raise RuntimeError(f"No '{language}' transcript found for video: {video_id}")


# ── Step 2: Split Transcript into Chunks ─────────────────────

def split_transcript(transcript: str, chunk_size: int, chunk_overlap: int):
    """
    Split the transcript into overlapping chunks.
    Overlap preserves context across chunk boundaries.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = splitter.create_documents([transcript])
    print(f"[✓] Transcript split into {len(chunks)} chunks")
    return chunks


# ── Step 3: Build FAISS Vector Store ─────────────────────────

def build_vector_store(chunks, embed_model_name: str):
    """Embed chunks and index them in a FAISS vector store."""
    embeddings = HuggingFaceEmbeddings(model_name=embed_model_name)
    vector_store = FAISS.from_documents(chunks, embeddings)
    print(f"[✓] Vector store built with {len(chunks)} documents")
    return vector_store


# ── Step 4: Format Retrieved Docs ────────────────────────────

def format_docs(retrieved_docs) -> str:
    """Concatenate retrieved document chunks into a single context string."""
    return "\n\n".join(doc.page_content for doc in retrieved_docs)


# ── Step 5: Build RAG Chain ───────────────────────────────────

def build_rag_chain(retriever, llm):
    """
    Construct a Retrieval-Augmented Generation (RAG) chain:
      - Parallel branch 1: retrieve → format context
      - Parallel branch 2: pass the question through unchanged
      - Then: fill prompt → call LLM → parse output
    """
    prompt = PromptTemplate(
        template="""
You are a helpful assistant.
Answer ONLY from the provided transcript context.
If the context is insufficient, say you don't know.

Context:
{context}

Question: {question}
""",
        input_variables=["context", "question"]
    )

    parallel_chain = RunnableParallel({
        "context":  retriever | RunnableLambda(format_docs),
        "question": RunnablePassthrough()
    })

    rag_chain = parallel_chain | prompt | llm | StrOutputParser()
    return rag_chain