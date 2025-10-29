import os
import io
import google.generativeai as genai
# We MUST import send_from_directory
from flask import Flask, request, jsonify, send_from_directory 
from dotenv import load_dotenv
from flask_cors import CORS
import PyPDF2

# Load environment variables from .env file
load_dotenv()

# --- Step 1: Configure the Gemini API ---
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)
model = None 

# --- Step 2: Set up the Flask Server ---
# We point Flask to our 'static' folder
app = Flask(__name__, static_folder='static') 
CORS(app)

document_context = ""

# --- Step 3: Endpoint for File Uploads ---
@app.route('/upload', methods=['POST'])
def upload_file():
    global document_context
    
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

        document_context = file_content 
        
        if not document_context:
             return jsonify({"error": "Could not read text from file"}), 500

        print(f"--- Document loaded, {len(document_context)} characters ---")
        return jsonify({"message": "File processed successfully"}), 200

    except Exception as e:
        print(f"An error occurred during file processing: {e}")
        return jsonify({"error": f"Failed to process file: {e}"}), 500


# --- Step 4: Chat Endpoint for RAG ---
@app.route('/chat', methods=['POST'])
def chat():
    global document_context, model
    
    try:
        if not document_context:
            return jsonify({"error": "Please upload a document first."}), 400
        
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
        
        request_data = request.json
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

# --- Step 5: Add routes to SERVE the frontend files ---

# Route for the homepage (index.html)
# This is the new part that fixes your "Not Found" error
@app.route('/')
def serve_index():
    # This tells Flask to send 'index.html' from the 'static' folder
    return send_from_directory(app.static_folder, 'index.html')

# Route for all other static files (CSS, JS)
# This makes sure your CSS and JS files are found
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# This makes the server run when you execute the script
if __name__ == '__main__':
    app.run(port=5000, debug=True)

