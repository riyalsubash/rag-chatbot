#!/usr/bin/env python3
"""Test OpenAI and LangChain integration"""

import os
import sys

# Set API key (replace with your key)
os.environ['OPENAI_API_KEY'] = 'your-key-here'

print("Testing OpenAI integration...\n")

try:
    print("1. Testing direct OpenAI client...")
    from openai import OpenAI
    client = OpenAI()
    print("   ✓ OpenAI client created successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n2. Testing LangChain OpenAI embeddings...")
    from langchain_openai import OpenAIEmbeddings
    embeddings = OpenAIEmbeddings()
    print("   ✓ OpenAIEmbeddings created successfully")
    
    print("\n3. Testing embedding generation...")
    test_text = "This is a test"
    result = embeddings.embed_query(test_text)
    print(f"   ✓ Generated embedding of length {len(result)}")
    
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n4. Testing ChatOpenAI...")
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
    print("   ✓ ChatOpenAI created successfully")
    
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n5. Testing FAISS with embeddings...")
    from langchain_community.vectorstores import FAISS
    from langchain.docstore.document import Document
    
    docs = [
        Document(page_content="Test document 1"),
        Document(page_content="Test document 2")
    ]
    
    vectorstore = FAISS.from_documents(docs, embeddings)
    print("   ✓ FAISS vectorstore created successfully")
    
    results = vectorstore.similarity_search("test", k=1)
    print(f"   ✓ Similarity search returned {len(results)} results")
    
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*50)
print("All tests passed! The setup is working correctly.")
print("="*50)