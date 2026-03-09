# Credit Score RAG (Retrieval-Augmented Generation)

A **Streamlit-based RAG application** that ingests credit-related documents (PDF, CSV, XLSX, DOCX, JSON, TXT), embeds them into a vector store (ChromaDB), and uses an LLM to answer credit scoring queries with a structured FICO-like scoring formula.

## 🚀 What It Does

- Uploads credit documents and converts them into a unified vector store (ChromaDB)
- Uses embeddings (OpenAI/Amazon Titan, etc.) to build a searchable knowledge base
- Lets you chat with the system and get credit score estimates based on real financial documents
- Includes a document generator (`generate_credit_docs.py`) to create realistic credit report test files in multiple formats (PDF, CSV, XLSX, JSON)

## 📁 Project Structure

- `app.py` - Streamlit web app (main entrypoint)
- `alpha.py` - Alternate Streamlit UI (similar to `app.py`, includes more detailed scoring prompt)
- `src/database/chroma_client.py` - Simple ChromaDB client wrapper
- `src/database/generate_credit_docs.py` - Generates synthetic credit documents (PDF/CSV/XLSX/JSON)
- `Requirements.txt` - Python dependencies
- `chroma_db/` - Default vector store directory (persisted embeddings)

## ✅ Prerequisites

- Python 3.10+ recommended
- A working OpenAI-compatible API (or Anthropic/AWS models depending on config)
- macOS (based on your environment)

## 🔧 Setup

1. Create a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r Requirements.txt
```

3. (Optional) If you're using a different vector store path, update the default in the app UI.

## ▶️ Running the App

Start the Streamlit app:

```bash
streamlit run app.py
```

Then open the URL printed by Streamlit in your browser.

## 🧠 How to Use

1. Configure your **API Gateway URL** and **API Key** in the sidebar.
2. Choose your preferred embedding and LLM model (from the provided options).
3. Upload one or more documents (PDF/CSV/XLSX/DOCX/JSON/TXT).
4. Click **Process Documents** to build the ChromaDB vector store.
5. Once processing is complete, ask questions in the chat box and get credit score estimates based on the uploaded documents.

## 🧪 Generating Sample Credit Documents (Optional)

Use `src/database/generate_credit_docs.py` to generate sample documents in multiple formats.

Example:

```bash
python src/database/generate_credit_docs.py
```

This will create a `credit_documents/` folder with sample PDFs, CSVs, XLSXs, and JSON files.

## 🗂️ ChromaDB Persistence

By default, the app persists embeddings to `./chroma_db`. You can change the directory from the Streamlit sidebar.

## ✅ Notes

- The credit scoring logic is implemented as a prompt to the LLM (in `app.py` / `alpha.py`).
- The score is based on a fixed formula (300-900) and is influenced by the retrieved document context.

---

If you want help extending this project (e.g., adding more document formats, splitting the UI, or supporting custom scoring rules), just ask!
