# Import necessary libraries
import streamlit as st
import os
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings, ChatNVIDIA
from langchain_community.document_loaders import WebBaseLoader
from langchain.embeddings import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
import time
import tempfile

# Import dotenv for loading environment variables
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set the NVIDIA API key from environment variable
os.environ['NVIDIA_API_KEY'] = os.getenv("NVIDIA_API_KEY")

# Initialize session state variables
if "reference_websites" not in st.session_state:
    st.session_state.reference_websites = [
        "https://www.nyc.gov/site/buildings/codes/2022-construction-codes.page"
    ]

# Function to perform vector embedding and document ingestion
def vector_embedding(uploaded_files):
    # Initialize the necessary components for document processing and embeddings
    st.session_state.embeddings = NVIDIAEmbeddings()  # Set the embeddings model (NVIDIA)
    
    # Create a list to store all documents
    all_docs = []
    
    # Process each uploaded file
    for uploaded_file in uploaded_files:
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        # Load the PDF file
        loader = PyPDFLoader(tmp_file_path)
        docs = loader.load()
        all_docs.extend(docs)
        
        # Clean up the temporary file
        os.unlink(tmp_file_path)

    # Initialize the text splitter for chunking documents into smaller pieces
    st.session_state.text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=50)
    
    # Split documents into chunks for processing
    st.session_state.final_documents = st.session_state.text_splitter.split_documents(all_docs)

    # Print a debug message (can be removed in production)
    print("Document processing and chunking completed.")

    # Perform vectorization of the documents using FAISS and the NVIDIA embeddings
    st.session_state.vectors = FAISS.from_documents(st.session_state.final_documents, st.session_state.embeddings)

# Streamlit app setup
st.set_page_config(layout="wide", page_title="Building Code Compliance App")
st.title("🏗️ Building Code Compliance Copilot")

# Initialize the NVIDIA LLM for chat-based functionality
llm = ChatNVIDIA(model="meta/llama3-70b-instruct", streaming=True)

# Define chat prompt templates
def get_system_prompt():
    websites = "\n".join([f"* {website}" for website in st.session_state.reference_websites])
    return f"""
    You are an expert Building Code Officer working for the New York City Department of Buildings (NYC DOB). Your expertise is specifically in the NYC Construction Codes, with primary reference to the 2022 Construction Codes and additional reference materials from:

    {websites}

    Your primary responsibilities are:

    1. Provide accurate interpretations of NYC Building Codes and regulations
    2. Review and analyze building applications for compliance with NYC Construction Codes
    3. Cite specific sections from the NYC Construction Codes in your responses
    4. Ensure all recommendations align with current NYC DOB standards and practices
    5. Highlight any potential compliance issues specific to NYC requirements

    Guidelines for responses:
    - Always reference specific sections of the NYC Construction Codes when possible
    - If citing code sections, include the specific code (Building Code, Plumbing Code, etc.) and section number
    - When referencing specific chapters or sections, include a clickable link to that chapter using Markdown format: [Chapter Name](URL)
    - For NYC Construction Codes, use the format: [Chapter X - Title](https://www.nyc.gov/site/buildings/codes/2022-construction-codes.page#chapter-X)
    - For other reference websites, include the direct link to the specific chapter or section
    - Clearly distinguish between requirements for different building types (residential, commercial, mixed-use)
    - Include relevant NYC-specific considerations (zoning, local laws, etc.)
    - If you don't have enough information, state this limitation and suggest consulting the official NYC DOB website
    - For compliance questions, specify which NYC code sections are applicable
    - Include information about required permits and inspections specific to NYC
    - Mention any recent updates or amendments to the NYC Construction Codes that might be relevant
    - When referencing information from additional websites, clearly cite the source with a clickable link

    Please structure your response in the following format:
    <think>
    Your detailed thinking process and analysis steps here
    </think>
    <answer>
    Your final answer here, including clickable links to specific chapters when referencing them
    </answer>
    """

general_prompt = ChatPromptTemplate.from_template(
    get_system_prompt() + """
    Question:{input}
    """
)

document_prompt = ChatPromptTemplate.from_template(
    get_system_prompt() + """
    <context>
    {context}
    </context>
    Question:{input}
    """
)

# Create chains
general_chain = general_prompt | llm | StrOutputParser()

# Add sidebar for PDF upload and example questions
with st.sidebar:
    st.subheader("Example Questions")
    st.markdown("Click any question to ask:")
    
    example_questions = [
        "Outline the steps for obtaining a building permit",
        "What are the requirements for rooftop access for firefighting operations?",
        "What are the minimum ceiling height requirements for commercial spaces?",
        "What are the requirements for bicycle parking in a new commercial building?",
        "Review the uploaded building application for the compliance check with NYC building codes"
    ]
    
    # Create a session state variable to store the selected question
    if "selected_question" not in st.session_state:
        st.session_state.selected_question = None
    
    for question in example_questions:
        if st.button(question, key=question):
            st.session_state.selected_question = question
            st.rerun()
    
    st.markdown("---")
    st.header("Upload Permit Applications")
    uploaded_files = st.file_uploader("Upload PDF files", type=['pdf'], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("Process Documents"):
            with st.spinner("Processing documents..."):
                vector_embedding(uploaded_files)
                st.success("Documents processed successfully!")
    
    st.markdown("---")
    st.subheader("Additional Reference Websites")
    st.markdown("Add building code websites for reference:")
    
    # Add new website
    new_website = st.text_input("Enter website URL", key="new_website")
    if st.button("Add Website") and new_website:
        if new_website not in st.session_state.reference_websites:
            st.session_state.reference_websites.append(new_website)
            st.success("Website added!")
            st.rerun()
    
    # Display current websites with delete option
    st.markdown("**Current References:**")
    for i, website in enumerate(st.session_state.reference_websites):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"* {website}")
        with col2:
            if st.button("🗑️", key=f"delete_{i}"):
                st.session_state.reference_websites.pop(i)
                st.rerun()

# Initialize chat history with welcome message
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """I am a NYC Department of Buildings (DOB) Code Compliance Officer, specializing in the 2022 NYC Construction Codes. I can help you with:

* Building Code interpretations and compliance checks
* Permit application reviews
* Code section citations and requirements
* NYC-specific construction regulations
* Zoning and local law considerations

I have direct access to the [2022 NYC Construction Codes](https://www.nyc.gov/site/buildings/codes/2022-construction-codes.page). You may also add additional link to other building codes websites.

To get started:
1. Ask specific questions about code requirements
2. (optional) Upload your permit application or relevant documents
3. I'll provide detailed analysis & cite the building code section that is relevant to your question

How can I assist you with your project today?"""
        }
    ]

# Function to format response text
def format_response(text):
    if "<think>" in text and "</think>" in text:
        think_section = text.split("<think>")[1].split("</think>")[0].strip()
        answer_section = text.split("</think>")[1].strip()
        
        # Remove answer tags if they exist
        if "<answer>" in answer_section and "</answer>" in answer_section:
            answer_section = answer_section.split("<answer>")[1].split("</answer>")[0].strip()
        
        return {
            "think": think_section,
            "answer": answer_section
        }
    return {
        "think": None,
        "answer": text
    }

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            formatted_response = format_response(message["content"])
            if formatted_response["think"]:
                with st.expander("🤔 Analysis Process", expanded=False):
                    st.markdown(formatted_response["think"])
            st.markdown(formatted_response["answer"])
        else:
            st.markdown(message["content"])

# Handle both chat input and example question selection
if prompt := st.chat_input("Ask a question about NYC Building Codes") or st.session_state.selected_question:
    # Use either the chat input or the selected question
    current_prompt = st.session_state.selected_question if st.session_state.selected_question else prompt
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": current_prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(current_prompt)
    
    # Display assistant response
    with st.chat_message("assistant"):
        # Create placeholders for analysis and answer
        analysis_placeholder = st.empty()
        answer_placeholder = st.empty()
        full_response = ""
        
        if "vectors" in st.session_state:
            # Use document-based response with streaming
            retriever = st.session_state.vectors.as_retriever()
            docs = retriever.invoke(current_prompt)
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Create document chain with streaming
            document_chain = document_prompt | llm | StrOutputParser()
            
            # Stream the response
            for response in document_chain.stream({"context": context, "input": current_prompt}):
                full_response += response
                # Format the response as it streams
                formatted_response = format_response(full_response)
                
                # Update the display
                if formatted_response["think"]:
                    with analysis_placeholder.expander("🤔 Analysis Process", expanded=True):
                        st.markdown(formatted_response["think"])
                answer_placeholder.markdown(formatted_response["answer"] + "▌")
            
            # Final update without the cursor
            formatted_response = format_response(full_response)
            if formatted_response["think"]:
                with analysis_placeholder.expander("🤔 Analysis Process", expanded=False):
                    st.markdown(formatted_response["think"])
            answer_placeholder.markdown(formatted_response["answer"])
            
            # Show document context in expander
            with st.expander("📄 Relevant Document Context"):
                for i, doc in enumerate(docs):
                    st.write(doc.page_content)
                    st.write("--------------------------------")
        else:
            # Use general response with streaming
            for response in general_chain.stream({"input": current_prompt}):
                full_response += response
                # Format the response as it streams
                formatted_response = format_response(full_response)
                
                # Update the display
                if formatted_response["think"]:
                    with analysis_placeholder.expander("🤔 Analysis Process", expanded=True):
                        st.markdown(formatted_response["think"])
                answer_placeholder.markdown(formatted_response["answer"] + "▌")
            
            # Final update without the cursor
            formatted_response = format_response(full_response)
            if formatted_response["think"]:
                with analysis_placeholder.expander("🤔 Analysis Process", expanded=False):
                    st.markdown(formatted_response["think"])
            answer_placeholder.markdown(formatted_response["answer"])
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        
        # Clear the selected question after processing
        st.session_state.selected_question = None
