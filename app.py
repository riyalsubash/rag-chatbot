from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import shutil

# LangChain imports
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import Document

# Other imports
import pandas as pd

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max
app.config['VECTOR_DB_PATH'] = 'vectordb'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['VECTOR_DB_PATH'], exist_ok=True)

# Global variables
vectorstore = None
qa_chain = None
embeddings_instance = None

ALLOWED_EXTENSIONS = {'pdf', 'xlsx', 'xls', 'csv', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_embeddings():
    """Get or create embeddings instance using HuggingFace (free, local)"""
    global embeddings_instance
    if embeddings_instance is None:
        print("Loading embeddings model (first time may take a moment)...")
        embeddings_instance = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        print("Embeddings model loaded successfully")
    return embeddings_instance

def load_document(file_path):
    """Load document based on file type"""
    ext = file_path.rsplit('.', 1)[1].lower()
    
    try:
        if ext == 'pdf':
            loader = PyPDFLoader(file_path)
            return loader.load()
        elif ext in ['xlsx', 'xls']:
            df = pd.read_excel(file_path)
            text = df.to_string()
            return [Document(page_content=text, metadata={"source": file_path})]
        elif ext == 'csv':
            loader = CSVLoader(file_path)
            return loader.load()
        elif ext == 'txt':
            loader = TextLoader(file_path, encoding='utf-8')
            return loader.load()
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    except Exception as e:
        print(f"Error loading {file_path}: {str(e)}")
        raise

def process_documents(file_paths):
    """Process uploaded documents and create vector store"""
    global vectorstore, qa_chain
    
    # Load all documents
    all_documents = []
    for file_path in file_paths:
        try:
            docs = load_document(file_path)
            all_documents.extend(docs)
            print(f"Loaded {len(docs)} documents from {file_path}")
        except Exception as e:
            print(f"Error loading {file_path}: {str(e)}")
    
    if not all_documents:
        raise ValueError("No documents were successfully loaded")
    
    print(f"Total documents loaded: {len(all_documents)}")
    
    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_documents(all_documents)
    print(f"Created {len(chunks)} chunks")
    
    # Get embeddings instance
    embeddings = get_embeddings()
    
    # Clear existing vector store files
    vector_store_file = os.path.join(app.config['VECTOR_DB_PATH'], 'index.faiss')
    if os.path.exists(vector_store_file):
        try:
            os.remove(vector_store_file)
            pkl_file = os.path.join(app.config['VECTOR_DB_PATH'], 'index.pkl')
            if os.path.exists(pkl_file):
                os.remove(pkl_file)
        except Exception as e:
            print(f"Error clearing old vector store: {e}")
    
    # Create FAISS vector store
    print("Creating FAISS vector store...")
    vectorstore = FAISS.from_documents(
        documents=chunks,
        embedding=embeddings
    )
    
    # Save vector store
    vectorstore.save_local(app.config['VECTOR_DB_PATH'])
    print("Vector store saved")
    
    # Create conversational chain with Claude
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key='answer'
    )
    
    # Initialize Claude AI
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",  # Latest Claude model
        temperature=0,
        max_tokens=4096
    )
    
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
        memory=memory,
        return_source_documents=True,
        verbose=True
    )
    print("QA chain created with Claude AI")
    
    return len(chunks)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'})
        
        files = request.files.getlist('files')
        
        if not files:
            return jsonify({'success': False, 'error': 'No files selected'})
        
        # Clear upload folder
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            shutil.rmtree(app.config['UPLOAD_FOLDER'])
        os.makedirs(app.config['UPLOAD_FOLDER'])
        
        # Save files
        file_paths = []
        file_names = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                file_paths.append(file_path)
                file_names.append(filename)
        
        if not file_paths:
            return jsonify({'success': False, 'error': 'No valid files uploaded'})
        
        # Process documents
        num_chunks = process_documents(file_paths)
        
        return jsonify({
            'success': True,
            'message': f'Processed {len(file_paths)} files into {num_chunks} chunks',
            'files': file_names
        })
    
    except Exception as e:
        print(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/ask', methods=['POST'])
def ask_question():
    """Handle question answering"""
    try:
        if qa_chain is None:
            return jsonify({
                'success': False,
                'error': 'Please upload documents first'
            })
        
        data = request.json
        question = data.get('question', '')
        
        if not question:
            return jsonify({'success': False, 'error': 'No question provided'})
        
        # Get answer from Claude
        result = qa_chain({"question": question})
        answer = result['answer']
        
        # Include source documents if available
        if result.get('source_documents'):
            sources = [doc.metadata.get('source', 'Unknown') 
                      for doc in result['source_documents']]
            unique_sources = list(set([os.path.basename(s) for s in sources]))
            answer += f"\n\n📚 Sources: {', '.join(unique_sources)}"
        
        return jsonify({
            'success': True,
            'answer': answer
        })
    
    except Exception as e:
        print(f"Question error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Set your Anthropic API key here or via environment 
    from dotenv import load_dotenv
    load_dotenv()
    if 'ANTHROPIC_API_KEY' not in os.environ:
        print("⚠️  WARNING: ANTHROPIC_API_KEY not set!")
        print("Please set your API key:")
        print("  export ANTHROPIC_API_KEY='your-api-key-here'")
        print("Or uncomment and update the line below in the code\n")
        # Uncomment and add your key:
        os.environ['ANTHROPIC_API_KEY'] = os.getenv("CLAUDE_KEY")
        print("✓ Anthropic API key found")
    
    print("\n" + "="*50)
    print("🚀 Starting RAG Chatbot with Claude AI...")
    print("="*50)
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Vector DB path: {app.config['VECTOR_DB_PATH']}")
    print(f"Model: Claude 3.5 Sonnet")
    print(f"Embeddings: HuggingFace (free, local)")
    print("="*50 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')