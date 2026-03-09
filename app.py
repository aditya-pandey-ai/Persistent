import streamlit as st
import tempfile
import os
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, CSVLoader, UnstructuredExcelLoader,
    UnstructuredWordDocumentLoader, JSONLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma

st.set_page_config(page_title="Credit Score RAG", page_icon="💳", layout="wide")

# Session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = False

st.title("💳 Credit Score RAG System")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")

    api_base_url = st.text_input(
        "API Gateway URL",
        placeholder="https://xxx.ap-south-1.awsapprunner.com"
    )

    api_key = st.text_input("API Key", type="password", placeholder="sk-...")

    st.markdown("---")

    embedding_model = st.selectbox(
        "Embedding Model",
        ["text-embedding-ada-002-AI_Team", "amazon.titan-embed-text-v2:0"]
    )

    llm_model = st.selectbox(
        "LLM Model",
        ["gpt4-o-AI_Team", "anthropic.claude-3-7-sonnet-AI_Team", "amazon.nova-pro-v1:0-AI_Team"]
    )

    st.markdown("---")
    persist_dir = st.text_input("ChromaDB Directory", value="./chroma_db")

    if api_base_url and api_key:
        st.success("✅ API Configured")

if not (api_base_url and api_key):
    st.info("👈 Configure API in sidebar")
    st.stop()

os.environ["OPENAI_API_KEY"] = api_key
os.environ["OPENAI_API_BASE"] = api_base_url

# File upload
st.header("📁 Upload Documents")
uploaded_files = st.file_uploader(
    "Choose files",
    type=['pdf', 'txt', 'docx', 'csv', 'xlsx', 'json'],
    accept_multiple_files=True
)

def load_document(file, ext):
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file.getvalue())
        tmp_path = tmp.name

    try:
        if ext == '.pdf':
            loader = PyPDFLoader(tmp_path)
        elif ext == '.txt':
            loader = TextLoader(tmp_path, encoding='utf-8')
        elif ext == '.csv':
            loader = CSVLoader(tmp_path)
        elif ext in ['.xlsx', '.xls']:
            loader = UnstructuredExcelLoader(tmp_path)
        elif ext == '.docx':
            loader = UnstructuredWordDocumentLoader(tmp_path)
        elif ext == '.json':
            loader = JSONLoader(tmp_path, jq_schema='.', text_content=False)
        else:
            return []

        docs = loader.load()
        for doc in docs:
            doc.metadata['source_file'] = file.name
        return docs
    except Exception as e:
        st.error(f"Error loading {file.name}: {e}")
        return []
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

if uploaded_files:
    st.write(f"**{len(uploaded_files)} file(s) uploaded**")

    if st.button("🚀 Process Documents", use_container_width=True):
        with st.spinner("Processing..."):
            all_docs = []
            progress = st.progress(0)

            for i, file in enumerate(uploaded_files):
                ext = Path(file.name).suffix.lower()
                docs = load_document(file, ext)
                all_docs.extend(docs)
                progress.progress((i + 1) / len(uploaded_files))

            progress.empty()

            if not all_docs:
                st.error("No documents processed")
                st.stop()

            st.success(f"✅ Loaded {len(all_docs)} documents")

            # Split
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            chunks = splitter.split_documents(all_docs)
            st.success(f"✅ Created {len(chunks)} chunks")

            # Embed
            try:
                embeddings = OpenAIEmbeddings(
                    model=embedding_model,
                    openai_api_key=api_key,
                    openai_api_base=api_base_url
                )

                st.session_state.vectorstore = Chroma.from_documents(
                    documents=chunks,
                    embedding=embeddings,
                    persist_directory=persist_dir
                )
                st.success("✅ Embedded in ChromaDB")
                st.session_state.documents_processed = True
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

# Chat
if st.session_state.documents_processed:
    st.markdown("---")
    st.header("💬 Ask Questions")

    # Initialize LLM
    if 'llm' not in st.session_state:
        st.session_state.llm = ChatOpenAI(
            model=llm_model,
            openai_api_key=api_key,
            openai_api_base=api_base_url,
            temperature=0
        )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "sources" in msg:
                with st.expander("📄 Sources"):
                    for src in msg["sources"]:
                        st.write(f"- {src}")

    if prompt := st.chat_input("Ask about credit scoring..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Retrieve docs
                    retriever = st.session_state.vectorstore.as_retriever(search_kwargs={"k": 5})
                    docs = retriever.get_relevant_documents(prompt)

                    # Build context
                    context = "\n\n".join([doc.page_content for doc in docs])

                    # Create prompt
                    full_prompt = f"""prompt 
You are a credit scoring system. Calculate the credit score using this EXACT formula:

Base Score: 300

Payment History (35% weight):
- All on-time payments: +245 points
- 1-2 late payments (30 days): +200 points
- 3-5 late payments: +150 points
- 6+ late payments: +50 points

Credit Utilization (30% weight):
- Under 10%: +210 points
- 10-30%: +180 points
- 30-50%: +120 points
- Over 50%: +60 points

[Continue with other factors...]

Documents: {context}

Step 1: Extract payment history
Step 2: Calculate payment points
Step 3: Extract utilization
Step 4: Calculate utilization points
... [detailed steps]

Final Score = Base + Payment Points + Utilization Points + ...

Provide ONLY the final numerical score.

Question: {prompt}

Answer:"""


                    # Call LLM
                    response = st.session_state.llm.invoke(full_prompt)
                    answer = response.content

                    # Get sources
                    sources = list(set([d.metadata.get('source_file', 'Unknown') for d in docs]))

                    st.markdown(answer)
                    if sources:
                        with st.expander("📄 Sources"):
                            for src in sources:
                                st.write(f"- {src}")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources
                    })
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()