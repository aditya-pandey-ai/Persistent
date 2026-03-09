import streamlit as st
import tempfile
import os
from pathlib import Path
import re

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

# Credit Score Calculation Function
def calculate_credit_score(llm, context, applicant_info=""):
    """
    Use LLM to calculate credit score with structured prompt
    """

    scoring_prompt = f"""You are a CREDIT SCORING CALCULATOR. Your job is to calculate an exact numerical credit score (300-900) based on the FICO methodology.

CREDIT DOCUMENTS:
{context}

APPLICANT INFO:
{applicant_info if applicant_info else "See documents above"}

========================================
SCORING FORMULA (MANDATORY TO FOLLOW):
========================================

Base Score: 300 points

1. PAYMENT HISTORY (35% = 245 points maximum)
   Analyze payment records and assign points:
   - All payments on-time, no late payments: +245 points
   - 1-2 late payments (30 days) in last 2 years: +200 points
   - 3-5 late payments or 1 late payment (60 days): +150 points
   - 6+ late payments or multiple 60+ day lates: +100 points
   - Any 90+ day late payments or collections: +50 points
   - Defaults, charge-offs, bankruptcy: +0 points

2. CREDIT UTILIZATION (30% = 210 points maximum)
   Calculate: (Total Credit Used / Total Credit Available) × 100
   - Under 10% utilization: +210 points
   - 10-30% utilization: +180 points
   - 30-50% utilization: +120 points
   - 50-75% utilization: +60 points
   - Over 75% utilization: +30 points

3. LENGTH OF CREDIT HISTORY (15% = 105 points maximum)
   - 15+ years of credit history: +105 points
   - 10-15 years: +90 points
   - 7-10 years: +75 points
   - 4-7 years: +60 points
   - 2-4 years: +40 points
   - Under 2 years: +20 points

4. NEW CREDIT INQUIRIES (10% = 70 points maximum)
   Count hard inquiries in last 12 months:
   - 0 inquiries: +70 points
   - 1-2 inquiries: +60 points
   - 3-4 inquiries: +45 points
   - 5-6 inquiries: +30 points
   - 7+ inquiries: +10 points

5. CREDIT MIX (10% = 70 points maximum)
   Diversity of credit types (credit cards, loans, mortgage, etc.):
   - Excellent mix (4+ different types, well managed): +70 points
   - Good mix (3 types): +55 points
   - Fair mix (2 types): +40 points
   - Limited (1 type only): +20 points
   - No credit accounts: +0 points

========================================
CALCULATION STEPS (MUST FOLLOW):
========================================

Step 1: Extract payment history data from documents
   - Count total accounts
   - Count late payments (30, 60, 90+ days)
   - Note any collections, defaults, or bankruptcies
   - Assign points based on formula above

Step 2: Extract and calculate credit utilization
   - Find total credit limits across all accounts
   - Find total current balances
   - Calculate utilization percentage
   - Assign points based on formula above

Step 3: Determine length of credit history
   - Find oldest account open date
   - Calculate years of credit history
   - Assign points based on formula above

Step 4: Count new credit inquiries
   - Count hard inquiries in last 12 months
   - Assign points based on formula above

Step 5: Assess credit mix
   - List all credit account types
   - Count variety
   - Assign points based on formula above

Step 6: Calculate final score
   Final Score = 300 + Payment Points + Utilization Points + History Points + Inquiry Points + Mix Points

========================================
REQUIRED OUTPUT FORMAT:
========================================

CREDIT SCORE CALCULATION REPORT

STEP 1 - PAYMENT HISTORY:
[Your analysis]
Points Awarded: [X] / 245

STEP 2 - CREDIT UTILIZATION:
[Your analysis with calculation]
Points Awarded: [X] / 210

STEP 3 - LENGTH OF CREDIT HISTORY:
[Your analysis]
Points Awarded: [X] / 105

STEP 4 - NEW CREDIT INQUIRIES:
[Your analysis]
Points Awarded: [X] / 70

STEP 5 - CREDIT MIX:
[Your analysis]
Points Awarded: [X] / 70

========================================
FINAL CALCULATION:
Base Score: 300
Payment History: +[X]
Credit Utilization: +[X]
Credit History Length: +[X]
New Credit: +[X]
Credit Mix: +[X]
========================================
TOTAL CREDIT SCORE: [XXX]
========================================

CREDIT RATING: [Excellent/Good/Fair/Poor/Very Poor]
RISK LEVEL: [Low/Moderate/High]

KEY FACTORS:
- [Factor 1]
- [Factor 2]
- [Factor 3]

RECOMMENDATIONS:
- [Recommendation 1]
- [Recommendation 2]

Now calculate the credit score following this exact format."""

    response = llm.invoke(scoring_prompt)
    return response.content


def extract_score_from_response(response_text):
    """Extract numerical score from LLM response"""
    # Try to find "TOTAL CREDIT SCORE: XXX"
    match = re.search(r'TOTAL CREDIT SCORE:\s*(\d{3})', response_text)
    if match:
        return int(match.group(1))

    # Fallback: find any 3-digit number between 300-900
    matches = re.findall(r'([3-9]\d{2})', response_text)
    for match in matches:
        score = int(match)
        if 300 <= score <= 900:
            return score

    return None


# Chat interface
if st.session_state.documents_processed:
    st.markdown("---")

    # Two tabs: Regular Chat and Credit Score Calculator
    tab1, tab2 = st.tabs(["💬 Q&A Chat", "🧮 Calculate Credit Score"])

    # Initialize LLM
    if 'llm' not in st.session_state:
        st.session_state.llm = ChatOpenAI(
            model=llm_model,
            openai_api_key=api_key,
            openai_api_base=api_base_url,
            temperature=0
        )

    # TAB 1: Regular Q&A Chat
    with tab1:
        st.header("Ask Questions About Credit")

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
                        full_prompt = f"""You are a credit risk analyst. Answer based on the context.

Context:
{context}

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

        if st.button("🗑️ Clear Chat", key="clear_chat"):
            st.session_state.messages = []
            st.rerun()

    # TAB 2: Credit Score Calculator
    with tab2:
        st.header("🧮 Credit Score Calculator")
        st.info("⚠️ This uses LLM calculations - results may not be 100% accurate. For production use, combine with traditional ML models.")

        applicant_id = st.text_input("Applicant ID (optional)", placeholder="e.g., 10001")

        if st.button("📊 Calculate Credit Score", use_container_width=True, type="primary"):
            with st.spinner("Analyzing documents and calculating credit score..."):
                try:
                    # Get all relevant documents for this applicant
                    if applicant_id:
                        search_query = f"applicant {applicant_id} credit report payment history"
                    else:
                        search_query = "credit report payment history utilization"

                    retriever = st.session_state.vectorstore.as_retriever(search_kwargs={"k": 10})
                    docs = retriever.get_relevant_documents(search_query)

                    if not docs:
                        st.error("No relevant credit documents found. Please upload credit reports.")
                        st.stop()

                    # Build context from all relevant documents
                    context = "\n\n=== DOCUMENT ===\n\n".join([doc.page_content for doc in docs])

                    # Calculate score
                    result = calculate_credit_score(st.session_state.llm, context, applicant_id)

                    # Extract numerical score
                    score = extract_score_from_response(result)

                    # Display results
                    if score:
                        st.markdown("---")
                        col1, col2, col3 = st.columns([2, 3, 2])

                        with col2:
                            st.metric(
                                label="Credit Score",
                                value=score,
                                delta=f"{score - 650} from Fair" if score != 650 else None
                            )

                            # Score gauge
                            if score >= 750:
                                st.success("🟢 Excellent Credit")
                            elif score >= 700:
                                st.success("🟡 Good Credit")
                            elif score >= 650:
                                st.warning("🟠 Fair Credit")
                            elif score >= 600:
                                st.warning("🟠 Poor Credit")
                            else:
                                st.error("🔴 Very Poor Credit")

                        st.markdown("---")

                    # Show detailed report
                    st.markdown("### Detailed Credit Score Report")
                    st.markdown(result)

                    # Show sources
                    with st.expander("📄 Documents Used"):
                        sources = list(set([d.metadata.get('source_file', 'Unknown') for d in docs]))
                        for src in sources:
                            st.write(f"- {src}")

                except Exception as e:
                    st.error(f"Error calculating credit score: {e}")