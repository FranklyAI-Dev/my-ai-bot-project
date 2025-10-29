// This special function tells the script to WAIT
// until the entire HTML document is fully loaded.
document.addEventListener('DOMContentLoaded', () => {
    
    // This message will prove that the script is running correctly.
    console.log("Script loaded and DOM is ready.");

    // Get references to all our new HTML elements
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const uploadStatus = document.getElementById('upload-status');
    const sendButton = document.getElementById('send-button');
    const messageInput = document.getElementById('message-input');
    const chatWindow = document.getElementById('chat-window');

    // --- NEW: Function to handle file upload ---
    async function uploadDocument() {
        const file = fileInput.files[0];
        if (!file) {
            uploadStatus.textContent = 'Please select a file first.';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        uploadStatus.textContent = 'Uploading and processing...';
        uploadButton.disabled = true;

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "File processing failed.");
            }

            uploadStatus.textContent = 'File processed successfully. You can now chat!';
            
            messageInput.disabled = false;
            sendButton.disabled = false;

            addMessage("Your document is ready. Ask me anything about it!", 'ai-message');

        } catch (error) {
            console.error("Error:", error);
            uploadStatus.textContent = `Error: ${error.message}`;
        } finally {
            uploadButton.disabled = false;
        }
    }

    // --- MODIFIED: Function to send a chat message ---
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (message === "") return;

        addMessage(message, 'user-message');
        messageInput.value = "";

        chatHistory.push({ role: 'user', text: message });

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ history: chatHistory })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Server error");
            }

            const data = await response.json();
            const aiReply = data.reply;
            
            addMessage(aiReply, 'ai-message');
            chatHistory.push({ role: 'model', text: aiReply });

        } catch (error) {
            console.error("Error:", error);
            addMessage(`Sorry, there was an error: ${error.message}`, 'ai-message');
        }
    }

    // This function is unchanged
    let chatHistory = []; // Moved this inside the DOMContentLoaded
    function addMessage(text, className) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', className);
        messageElement.textContent = text;
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // Add event listeners for our two buttons
    uploadButton.addEventListener('click', uploadDocument);
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            // Check if send button is enabled before sending
            if (!sendButton.disabled) {
                sendMessage();
            }
        }
    });

}); // We close the DOMContentLoaded function here

