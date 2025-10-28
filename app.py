import os
import io # We need this to handle the in-memory file
import google.generativeai as genai
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import PyPDF2 # Import the new PDF library

# Load environment variables from .env file
load_dotenv()

# --- Step 1: Configure the Gemini API ---
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

# We'll set the model and system instruction *dynamically* later
model = None 

# --- Step 2: Set up the Flask Server ---
app = Flask(__name__)
CORS(app)

# This will store the text content of the uploaded file in memory.
# In a real app, you'd save this to a database.
document_context = ""

# --- Step 3: Create a NEW Endpoint for File Uploads ---
@app.route('/upload', methods=['POST'])
def upload_file():
    global document_context # We're modifying the global variable
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        file_content = ""
        
        # Check if it's a PDF
        if file.filename.endswith('.pdf'):
            # Read the PDF file in memory
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            for page in pdf_reader.pages:
                file_content += page.extract_text() or ""
        
        # Check if it's a TXT
        elif file.filename.endswith('.txt'):
            # Read the text file in memory
            file_content = file.read().decode('utf-8')
        
        else:
            return jsonify({"error": "Unsupported file type"}), 400

        document_context = file_content # Store the extracted text
        
        if not document_context:
             return jsonify({"error": "Could not read text from file"}), 500

        print(f"--- Document loaded, {len(document_context)} characters ---")
        return jsonify({"message": "File processed successfully"}), 200

    except Exception as e:
        print(f"An error occurred during file processing: {e}")
        return jsonify({"error": f"Failed to process file: {e}"}), 500


# --- Step 4: Modify the Existing Chat Endpoint for RAG ---
@app.route('/chat', methods=['POST'])
def chat():
    global document_context, model # We need to access these
    
    try:
        # 1. Check if the document has been uploaded.
        if not document_context:
            return jsonify({"error": "Please upload a document first."}), 400
        
        # 2. Dynamically create the System Prompt (This is the RAG part)
        system_instruction = f"""
        You are a helpful assistant. You must answer questions based *only* on the
        following document context. Do not use any other knowledge.
        
        If the user's question cannot be answered using the document,
        you must say: 'I'm sorry, that information is not in the document.'

        --- DOCUMENT CONTEXT ---
        {document_context}
        --- END OF CONTEXT ---
        """
        
        # 3. Initialize the model *with the new system instruction*
        model = genai.GenerativeModel(
            model_name='gemini-2.5-pro',
            system_instruction=system_instruction
        )
        
        # 4. Get the chat history from the request (same as before)
        request_data = request.json
        chat_history_json = request_data.get('history')

        if not chat_history_json:
            return jsonify({"error": "History cannot be empty"}), 400
        
        # 5. Reformat and start the chat (same as before)
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

# This makes the server run when you execute the script
if __name__ == '__main__':
    app.run(port=5000, debug=True)

