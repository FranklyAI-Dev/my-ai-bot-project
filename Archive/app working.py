# Import the necessary libraries
import os
import requests  # <-- We are now using requests, not google.generativeai
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

# Load environment variables from .env file
load_dotenv()

# --- Step 1: Get the API key ---
api_key = os.getenv("GOOGLE_API_KEY")

# --- Step 2: Set up the Flask Server ---
app = Flask(__name__)
CORS(app)

# --- Step 3: Create an API Endpoint ---
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')

    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    # --- Step 4: Manually call the Gemini API using requests ---
    try:
        # We build the request manually to bypass the broken library
        # We will use 'gemini-pro' as it is the most stable model name
        # api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={api_key}"
        
        # api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro-latest:generateContent?key={api_key}"
        
        # api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
        
        # api_url = f"https://generativanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"

        api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-pro:generateContent?key={api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": user_message}]
            }]
        }
        
        headers = {'Content-Type': 'application/json'}

        # Make the POST request
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()  # This will raise an error if the request failed

        # Extract the text from the response
        data = response.json()
        ai_reply = data['candidates'][0]['content']['parts'][0]['text']

        return jsonify({"reply": ai_reply})

    except requests.exceptions.RequestException as http_err:
        # Handle HTTP errors (like 404, 500, etc.)
        print(f"An HTTP error occurred: {http_err}")
        print(f"Response content: {response.text}") # This will show us the error from Google
        return jsonify({"error": "Failed to get response from AI (HTTP Error)"}), 500
    except (KeyError, IndexError) as e:
        # Handle errors from parsing the response (if it's not what we expect)
        print(f"An error occurred parsing the AI response: {e}")
        print(f"Response data: {data}")
        return jsonify({"error": "Failed to parse AI response"}), 500
    except Exception as e:
        # Handle any other errors
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# This makes the server run when you execute the script
if __name__ == '__main__':
    app.run(port=5000, debug=True)