import os
import uuid  # For generating unique IDs
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import PyPDF2
import google.generativeai as genai

# Import Firebase Admin libraries
import firebase_admin
from firebase_admin import credentials, firestore

# --- Step 1: Initialize Firebase Admin ---
# This uses the GOOGLE_APPLICATION_CREDENTIALS env variable we set in Render
try:
    # This path is used by Render
    cred = firebase_admin.credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
    print("Firebase initialized with Application Default Credentials (for Render).")
except ValueError as e:
    # This value error happens on your local machine if the env var isn't set.
    # We fall back to using the key.json file directly.
    if not firebase_admin._apps: # Check if app is already initialized
        print("Falling back to local key.json for Firebase.")
        cred = credentials.Certificate('key.json')
        firebase_admin.initialize_app(cred)

# Get a reference to the Firestore database
db = firestore.client()


# --- Step 2: Configure the Gemini API ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Warning: GOOGLE_API_KEY not set in .env file.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-pro') # Using the model we found that works
print("Gemini API configured.")

# --- Step 3: Set up the Flask Server ---
# We point 'static_folder' to our 'static' directory
app = Flask(__name__, static_folder='static', static_url_path='')
print("Flask server initialized.")


# --- Helper Function to Extract Text ---
def extract_text_from_file(file):
    """Extracts text from a .txt or .pdf file."""
    text = ""
    filename = file.filename
    print(f"Extracting text from: {filename}")
    if filename.endswith('.pdf'):
        pdf_reader = PyPDF2.PdfReader(file.stream) # Use file.stream for compatibility
        for page in pdf_reader.pages:
            text += page.extract_text()
    elif filename.endswith('.txt'):
        text = file.read().decode('utf-8')
    print(f"Extracted {len(text)} characters.")
    return text

# --- Helper Function to Build RAG Prompt ---
def build_rag_prompt(context, chat_history, user_message):
    """Builds the prompt for the AI with context and history."""
    
    # Format chat history
    history_string = ""
    for entry in chat_history:
        role = "User" if entry['role'] == 'user' else "AI"
        history_string += f"{role}: {entry['text']}\n"

    # The system instruction
    system_instruction = f"""You are a helpful AI assistant. Your user has provided a document.
Your task is to answer the user's questions based *only* on the text from this document.
If the answer is not found in the document, you MUST say 'I'm sorry, that information is not in the document.'
Do not make up answers or use your general knowledge.

Here is the document text:
---
{context}
---

Now, please continue the conversation.
"""

    # Combine the system instruction, chat history, and new message
    final_prompt = system_instruction + "\n" + history_string + "\nUser: " + user_message
    return final_prompt

# --- API ENDPOINT 1: Upload a New Document ---
@app.route('/upload', methods=['POST'])
def upload_file():
    print("Received request for /upload")
    if 'file' not in request.files:
        print("Upload error: No file part")
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    userID = request.form.get('userID')

    if not userID:
        print("Upload error: No User ID provided")
        return jsonify({"error": "No User ID provided"}), 400
    if file.filename == '':
        print("Upload error: No selected file")
        return jsonify({"error": "No selected file"}), 400

    try:
        # Extract text from the file
        document_text = extract_text_from_file(file)
        if not document_text:
            print("Upload error: Could not extract text")
            return jsonify({"error": "Could not extract text from file"}), 400

        # Generate a new unique ID for this document
        documentID = str(uuid.uuid4())
        
        # Save the document to Firestore
        print(f"Saving document {documentID} for user {userID}")
        doc_ref = db.collection('users').document(userID).collection('documents').document(documentID)
        doc_ref.set({
            'filename': file.filename,
            'text': document_text,
            'createdAt': firestore.SERVER_TIMESTAMP
        })

        # Return the new document's info to the frontend
        print("Upload successful")
        return jsonify({
            "message": "File processed successfully",
            "documentID": documentID,
            "filename": file.filename
        }), 200

    except Exception as e:
        print(f"Error during upload: {e}")
        return jsonify({"error": "Server error processing file"}), 500

# --- API ENDPOINT 2: Chat with a Document ---
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    userID = data.get('userID')
    documentID = data.get('documentID')
    user_message = data.get('message')
    print(f"Received request for /chat for doc {documentID}")

    if not all([userID, documentID, user_message]):
        print(f"Chat error: Missing data. UserID: {userID}, DocID: {documentID}, Msg: {user_message}")
        return jsonify({"error": "Missing data"}), 400

    try:
        # 1. Fetch the Document Context from Firestore
        print("Fetching document context...")
        doc_ref = db.collection('users').document(userID).collection('documents').document(documentID)
        document = doc_ref.get()
        if not document.exists:
            print("Chat error: Document not found")
            return jsonify({"error": "Document not found"}), 404
        
        document_context = document.to_dict().get('text', '')

        # 2. Fetch the Chat History from Firestore
        print("Fetching chat history...")
        chat_history_ref = doc_ref.collection('chats').order_by('createdAt')
        chat_history_docs = chat_history_ref.stream()
        
        chat_history = []
        for doc in chat_history_docs:
            chat_history.append(doc.to_dict())

        # 3. Build the prompt
        print("Building RAG prompt...")
        full_prompt = build_rag_prompt(document_context, chat_history, user_message)
        
        # 4. Generate content with Gemini
        print("Sending prompt to Gemini...")
        response = model.generate_content(full_prompt)

        # 5. Save new messages to Firestore
        print("Saving new messages to Firestore...")
        # Save user message
        user_chat_ref = doc_ref.collection('chats').document()
        user_chat_ref.set({
            'role': 'user',
            'text': user_message,
            'createdAt': firestore.SERVER_TIMESTAMP
        })
        
        # Save AI response
        ai_chat_ref = doc_ref.collection('chats').document()
        ai_chat_ref.set({
            'role': 'model',
            'text': response.text,
            'createdAt': firestore.SERVER_TIMESTAMP
        })

        # 6. Send AI response back to the frontend
        print("Sending response to frontend.")
        return jsonify({"reply": response.text})

    except Exception as e:
        print(f"Error in /chat: {e}")
        return jsonify({"error": "Error generating AI response"}), 500

# --- API ENDPOINT 3: Get List of User's Documents ---
@app.route('/get_documents', methods=['POST'])
def get_documents():
    data = request.json
    userID = data.get('userID')
    print(f"Received request for /get_documents for user {userID}")
    if not userID:
        return jsonify({"error": "No User ID provided"}), 400

    try:
        docs_ref = db.collection('users').document(userID).collection('documents').order_by('createdAt', direction=firestore.Query.DESCENDING)
        docs = docs_ref.stream()
        
        document_list = []
        for doc in docs:
            document_list.append({
                "documentID": doc.id,
                "filename": doc.to_dict().get('filename', 'Untitled')
            })
        
        print(f"Found {len(document_list)} documents.")
        return jsonify({"documents": document_list}), 200
    except Exception as e:
        print(f"Error in /get_documents: {e}")
        return jsonify({"error": "Could not retrieve documents"}), 500

# --- API ENDPOINT 4: Get Chat History for a Document ---
@app.route('/get_chat_history', methods=['POST'])
def get_chat_history():
    data = request.json
    userID = data.get('userID')
    documentID = data.get('documentID')
    print(f"Received request for /get_chat_history for doc {documentID}")
    
    if not all([userID, documentID]):
        return jsonify({"error": "Missing data"}), 400

    try:
        chat_history_ref = db.collection('users').document(userID).collection('documents').document(documentID).collection('chats').order_by('createdAt')
        chat_history_docs = chat_history_ref.stream()
        
        chat_history = []
        for doc in chat_history_docs:
            chat_history.append(doc.to_dict())
        
        print(f"Found {len(chat_history)} chat messages.")
        return jsonify({"chatHistory": chat_history}), 200
    except Exception as e:
        print(f"Error in /get_chat_history: {e}")
        return jsonify({"error": "Could not retrieve chat history"}), 500

# --- API ENDPOINT 5: Delete a Document ---
@app.route('/delete_document', methods=['POST'])
def delete_document():
    data = request.json
    userID = data.get('userID')
    documentID = data.get('documentID')
    print(f"Received request for /delete_document for doc {documentID}")
    
    if not all([userID, documentID]):
        return jsonify({"error": "Missing data"}), 400

    try:
        doc_ref = db.collection('users').document(userID).collection('documents').document(documentID)

        # Delete all chat messages in the 'chats' subcollection
        # This is a bit advanced, but it's the "correct" way to delete
        chat_ref = doc_ref.collection('chats')
        for chat_doc in chat_ref.stream():
            chat_doc.reference.delete()
            
        # After deleting the subcollection, delete the main document
        doc_ref.delete()
        
        print("Document and chat history deleted.")
        return jsonify({"message": "Document deleted successfully"}), 200
    except Exception as e:
        print(f"Error in /delete_document: {e}")
        return jsonify({"error": "Could not delete document"}), 500

# --- Routes for Serving the Frontend ---

@app.route('/')
def index():
    """Serves the main index.html file."""
    print("Serving index.html")
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serves other static files (like style.css, script.js)."""
    # This will serve style.css and script.js
    print(f"Serving static file: {path}")
    return send_from_directory(app.static_folder, path)

# --- Run the App ---
if __name__ == '__main__':
    # Use 8080 as a default port for Render, but allow override
    port = int(os.environ.get('PORT', 8080))
    # Note: debug=True is great for local, but should be False in production
    # However, for Render's free tier, this is fine.
    print(f"Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)

