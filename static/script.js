// Wait for the HTML to be fully loaded before running the script
document.addEventListener('DOMContentLoaded', () => {
    
    console.log("Script loaded and DOM is ready.");

    // --- NEW: Get or create a unique User ID for this browser ---
    let userID = localStorage.getItem('userID');
    if (!userID) {
        userID = crypto.randomUUID(); // Generate a new unique ID
        localStorage.setItem('userID', userID);
    }
    console.log("User ID:", userID);
    // --- END NEW ---

    // Get references to all our HTML elements
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const uploadStatus = document.getElementById('upload-status');
    const sendButton = document.getElementById('send-button');
    const messageInput = document.getElementById('message-input');
    const chatWindow = document.getElementById('chat-window');

    let chatHistory = []; // This array holds our conversation memory

    // --- Function to handle file upload ---
    async function uploadDocument() {
        const file = fileInput.files[0];
        if (!file) {
            uploadStatus.textContent = 'Please select a file first.';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('userID', userID); // --- NEW: Add the userID to the request ---

        uploadStatus.textContent = 'Uploading and processing...';
        uploadButton.disabled = true;

        try {
            // Use relative URL for deployment
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "File processing failed.");
            }

            uploadStatus.textContent = 'File processed successfully. You can now chat!';
            
            // Enable the chat controls
            messageInput.disabled = false;
            sendButton.disabled = false;

            // Clear chat window and add first message
            chatWindow.innerHTML = '';
            addMessage("Your document is ready. Ask me anything about it!", 'ai-message');
            chatHistory = []; // Reset history for the new document

        } catch (error) {
            console.error("Error:", error);
            uploadStatus.textContent = `Error: ${error.message}`;
        } finally {
            uploadButton.disabled = false;
        }
    }

    // --- Function to send a chat message ---
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (message === "") return;

        addMessage(message, 'user-message');
        
        // Add user message to history
        chatHistory.push({ role: 'user', text: message });
        messageInput.value = "";

        try {
            // --- NEW: Send both history and userID ---
            const payload = {
                history: chatHistory,
                userID: userID 
            };
            // --- END NEW ---

            // Use relative URL for deployment
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload) // Send the new payload
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Server error");
            }

            const data = await response.json();
            const aiReply = data.reply;
            
            addMessage(aiReply, 'ai-message');
            // Add AI message to history
            chatHistory.push({ role: 'model', text: aiReply });

        } catch (error) {
            console.error("Error:", error);
            addMessage(`Sorry, there was an error: ${error.message}`, 'ai-message');
        }
    }

    // Helper function to add a message to the chat display
    function addMessage(text, className) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', className);
        messageElement.textContent = text;
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // --- Add event listeners for our buttons ---
    uploadButton.addEventListener('click', uploadDocument);
    sendButton.addEventListener('click', sendMessage);
    
    messageInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            if (!sendButton.disabled) { // Only send if not disabled
                sendMessage();
            }
        }
    });

});
