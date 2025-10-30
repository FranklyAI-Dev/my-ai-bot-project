import os
import io
import google.generativeai as genai
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from flask_cors import CORS
import PyPDF2

# --- NEW: Import Firebase Admin SDK ---
import firebase_admin
from firebase_admin import credentials, firestore
# --- END NEW ---

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Step 1: Configure the Gemini API ---
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)
model = None 

# --- NEW: Initialize Firebase Admin ---
# This automatically uses the GOOGLE_APPLICATION_CREDENTIALS from .env
try:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
except ValueError:
    print("Firebase Admin already initialized.")

db = firestore.client() # This is our connection to the Firestore database
# --- END NEW ---


# --- Step 2: Set up the Flask Server ---
app = Flask(__name__, static_folder='static') 
CORS(app)

# --- DELETED: We no longer use this global variable ---
# document_context = "" 
# --- END DELETED ---


# --- Step 3: Endpoint for File Uploads (Updated for Firestore) ---
@app.route('/upload', methods=['POST'])
def upload_file():
    # --- NEW: Get the userID from the form data ---
    if 'userID' not in request.form:
        return jsonify({"error": "No User ID provided"}), 400
    userID = request.form.get('userID')
    # --- END NEW ---

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        file_content = ""
        
        if file.filename.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            for page in pdf_reader.pages:
                file_content += page.extract_text() or ""
        
        elif file.filename.endswith('.txt'):
            file_content = file.read().decode('utf-8')
        
        else:
            return jsonify({"error": "Unsupported file type"}), 400

        if not file_content:
             return jsonify({"error": "Could not read text from file"}), 500

        # --- NEW: Save the document text to Firestore ---
        # We create a collection called 'documents'
        # and create a document inside it named after the userID.
        doc_ref = db.collection('documents').document(userID)
        doc_ref.set({
            'text': file_content
        })
        # --- END NEW ---

        print(f"--- Document loaded for user {userID} ---")
        return jsonify({"message": "File processed successfully"}), 200

    except Exception as e:
        print(f"An error occurred during file processing: {e}")
        return jsonify({"error": f"Failed to process file: {e}"}), 500


# --- Step 4: Chat Endpoint for RAG (Updated for Firestore) ---
@app.route('/chat', methods=['POST'])
def chat():
    global model # We still need this
    
    try:
        request_data = request.json
        
        # --- NEW: Get the userID from the request ---
        if 'userID' not in request_data:
            return jsonify({"error": "No User ID provided"}), 400
        userID = request_data.get('userID')
        # --- END NEW ---

        # --- NEW: Load the document context from Firestore ---
        doc_ref = db.collection('documents').document(userID)
        doc = doc_ref.get()

        if not doc.exists:
            return jsonify({"error": "Document not found. Please upload a file."}), 404
        
        document_context = doc.to_dict().get('text')
        
        if not document_context:
            return jsonify({"error": "Document is empty. Please re-upload."}), 400
        # --- END NEW ---
        
        # This part is the same as before
        system_instruction = f"""
        You are a helpful assistant. You must answer questions based *only* on the
        following document context. Do not use any other knowledge.
        
        If the user's question cannot be answered using the document,
        you must say: 'I'm sorry, that information is not in the document.'

        --- DOCUMENT CONTEXT ---
        {document_context}
        --- END OF CONTEXT ---
        """
        
        model = genai.GenerativeModel(
            model_name='gemini-2.5-pro',
            system_instruction=system_instruction
        )
        
        chat_history_json = request_data.get('history')

        if not chat_history_json:
            return jsonify({"error": "History cannot be empty"}), 400
        
        user_message = chat_history_json.pop()
        
        formatted_history = []
        for msg in chat_history_json:
            formatted_history.append({
                "role": msg['role'],
                "parts": [{"text": msg['text']}]
            })

        chat_session = model.start_chat(history=formatted_history)
        response = chat_session.send_message(user_message['text'])

        return jsonify({"reply": response.text})

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "Failed to get response from AI"}), 500

# --- Step 5: Routes to Serve the Frontend Files (No change) ---

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# This makes the server run when you execute 'python app.py'
if __name__ == '__main__':
    app.run(port=5000, debug=True)

