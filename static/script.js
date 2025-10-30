// Wait for the entire HTML document to be loaded before running the script
document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. GET ALL HTML ELEMENTS ---
    // Document Management
    const documentSelector = document.getElementById('document-selector');
    const deleteDocumentButton = document.getElementById('delete-document-button');
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const uploadStatus = document.getElementById('upload-status');
    
    // Chat Interface
    const chatWindow = document.getElementById('chat-window');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    // --- 2. STATE MANAGEMENT ---
    let userID = getOrSetUserID();
    // Get the last active document ID from storage, specific to this user
    let activeDocumentID = localStorage.getItem(`activeDocumentID_${userID}`);
    
    // Log for debugging
    console.log("Script loaded and DOM is ready. UserID:", userID);
    if (activeDocumentID) {
        console.log("Found active document in storage:", activeDocumentID);
    }

    // --- 3. CORE FUNCTIONS ---

    /**
     * Creates a unique User ID if one doesn't exist,
     * stores it in localStorage, and returns it.
     */
    function getOrSetUserID() {
        let uid = localStorage.getItem('userID');
        if (!uid) {
            uid = 'user_' + new Date().getTime() + '_' + Math.random().toString(36).substring(2, 9);
            localStorage.setItem('userID', uid);
        }
        return uid;
    }

    /**
     * Fetches the user's document list from the server and populates the dropdown.
     */
    async function loadDocuments() {
        console.log("Loading documents for user:", userID);
        addInfoMessage("Loading your documents...");
        
        try {
            // Use relative URL /get_documents
            const response = await fetch('/get_documents', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userID: userID })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to fetch documents');
            }
            
            const data = await response.json();
            documentSelector.innerHTML = '<option value="">No document selected</option>'; // Clear existing
            
            if (data.documents && data.documents.length > 0) {
                data.documents.forEach(doc => {
                    const option = document.createElement('option');
                    option.value = doc.documentID;
                    option.textContent = doc.filename;
                    documentSelector.appendChild(option);
                });
                
                // Try to re-select the last active document
                if (activeDocumentID && data.documents.some(doc => doc.documentID === activeDocumentID)) {
                    documentSelector.value = activeDocumentID;
                } else if (data.documents.length > 0) {
                    // Or default to the first document
                    documentSelector.value = data.documents[0].documentID;
                    activeDocumentID = data.documents[0].documentID;
                    localStorage.setItem(`activeDocumentID_${userID}`, activeDocumentID);
                }
                
                console.log("Documents loaded. Active doc ID:", activeDocumentID);
            } else {
                console.log("No documents found for this user.");
                activeDocumentID = null;
                localStorage.removeItem(`activeDocumentID_${userID}`);
            }
            
            // After loading, update the chat history and UI state
            loadChatHistory();
            
        } catch (error) {
            console.error('Error loading documents:', error);
            addErrorMessage("Could not load your documents. Please refresh.");
        }
    }

    /**
     * Fetches the chat history for the currently active document.
     */
    async function loadChatHistory() {
        if (!activeDocumentID || activeDocumentID === "") {
            console.log("No active document, clearing chat.");
            clearChatWindow();
            addInfoMessage("Please upload a document or select one to begin.");
            updateChatUI(false); // Disable chat
            return;
        }

        console.log("Loading chat history for doc:", activeDocumentID);
        addInfoMessage("Loading chat history...");
        
        try {
            // Use relative URL /get_chat_history
            const response = await fetch('/get_chat_history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userID: userID, documentID: activeDocumentID })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to fetch chat history');
            }

            const data = await response.json();
            clearChatWindow();

            if (data.chatHistory && data.chatHistory.length > 0) {
                data.chatHistory.forEach(message => {
                    if (message.role === 'user') {
                        addMessage(message.text, 'user-message');
                    } else if (message.role === 'model') {
                        addMessage(message.text, 'ai-message');
                    }
                });
                addInfoMessage("Chat history loaded.");
            } else {
                addInfoMessage("No chat history for this document. Ask a question to start!");
            }
            
            updateChatUI(true); // Enable chat

        } catch (error) {
            console.error('Error loading chat history:', error);
            addErrorMessage("Could not load chat history.");
            updateChatUI(false); // Disable chat
        }
    }

    /**
     * Handles the file upload process.
     */
    async function handleFileUpload() {
        const file = fileInput.files[0];
        if (!file) {
            showStatus("Please select a file first.", 'error');
            return;
        }

        showStatus("Uploading and processing file...", 'info');
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('userID', userID); // Send the userID with the file

        try {
            // Use relative URL /upload
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData // No Content-Type header needed, browser sets it
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "File upload failed");
            }

            const data = await response.json();
            showStatus(data.message, 'success');
            
            // Add the new document to the dropdown
            const option = document.createElement('option');
            option.value = data.documentID;
            option.textContent = data.filename;
            documentSelector.prepend(option); // Add to the top
            
            // Automatically select the new document
            documentSelector.value = data.documentID;
            activeDocumentID = data.documentID;
            localStorage.setItem(`activeDocumentID_${userID}`, activeDocumentID);
            
            // Load its (empty) chat history
            loadChatHistory();
            
            fileInput.value = ''; // Clear the file input

        } catch (error) {
            console.error("Upload error:", error);
            showStatus(error.message, 'error');
        }
    }

    /**
     * Sends a new chat message to the server.
     */
    async function handleSendMessage() {
        const message = messageInput.value.trim();
        if (message === "" || !activeDocumentID) return;

        addMessage(message, 'user-message');
        messageInput.value = ""; // Clear the input
        updateChatUI(false); // Disable input while AI is thinking
        addMessage("Thinking...", 'ai-message', true); // Add temporary thinking message

        try {
            // Use relative URL /chat
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    userID: userID,
                    documentID: activeDocumentID,
                    message: message
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Error from server");
            }

            const data = await response.json();
            
            // Remove the "Thinking..." message
            const thinkingMessage = document.getElementById('thinking-message');
            if (thinkingMessage) {
                thinkingMessage.remove();
            }
            
            // Add the real AI reply
            addMessage(data.reply, 'ai-message');
            
        } catch (error) {
            console.error("Chat error:", error);
            // Remove the "Thinking..." message and show error
            const thinkingMessage = document.getElementById('thinking-message');
            if (thinkingMessage) {
                thinkingMessage.remove();
            }
            addErrorMessage(`Error: ${error.message}`);
        } finally {
            updateChatUI(true); // Re-enable chat UI
        }
    }
    
    /**
     * Deletes the currently selected document.
     */
    async function handleDeleteDocument() {
        if (!activeDocumentID || activeDocumentID === "") {
            alert("No document selected to delete.");
            return;
        }

        const selectedOption = documentSelector.options[documentSelector.selectedIndex];
        const filename = selectedOption.textContent;
        
        if (!confirm(`Are you sure you want to delete "${filename}"? This will erase all its chat history.`)) {
            return;
        }

        console.log("Deleting document:", activeDocumentID);
        
        try {
            // Use relative URL /delete_document
            const response = await fetch('/delete_document', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userID: userID, documentID: activeDocumentID })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to delete document');
            }
            
            // Remove the document from the dropdown
            selectedOption.remove();
            
            // Reload the document list (to select a new default)
            loadDocuments();
            
            alert(`Document "${filename}" deleted successfully.`);

        } catch (error) {
            console.error('Error deleting document:', error);
            alert("Could not delete the document. Please try again.");
        }
    }

    // --- 4. HELPER & UI FUNCTIONS ---

    function showStatus(message, type) {
        uploadStatus.textContent = message;
        uploadStatus.className = `status-message ${type}`;
    }

    function addMessage(text, className, isThinking = false) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', className);
        messageElement.textContent = text;
        
        if (isThinking) {
            messageElement.id = 'thinking-message';
        }
        
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight; // Auto-scroll to bottom
    }

    function addInfoMessage(text) {
        addMessage(text, 'info-message');
    }
    
    function addErrorMessage(text) {
        addMessage(text, 'system-message');
    }

    function clearChatWindow() {
        chatWindow.innerHTML = '';
    }
    
    function updateChatUI(enabled) {
        // Check if a document is selected
        const docIsSelected = activeDocumentID && activeDocumentID !== "";

        if (enabled && docIsSelected) {
            messageInput.disabled = false;
            sendButton.disabled = false;
            messageInput.placeholder = "Ask a question about your document...";
        } else {
            messageInput.disabled = true;
            sendButton.disabled = true;
            if (!docIsSelected) {
                messageInput.placeholder = "Please select a document first.";
            } else {
                messageInput.placeholder = "Processing...";
            }
        }
        
        // Separately manage the delete button
        deleteDocumentButton.disabled = !docIsSelected;
    }
    
    // --- 5. ATTACH EVENT LISTENERS ---
    
    // When the upload button is clicked
    uploadButton.addEventListener('click', handleFileUpload);
    
    // When the send button is clicked
    sendButton.addEventListener('click', handleSendMessage);
    
    // When Enter is pressed in the message input
    messageInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !sendButton.disabled) {
            handleSendMessage();
        }
    });

    // When the user changes the selected document
    documentSelector.addEventListener('change', () => {
        activeDocumentID = documentSelector.value;
        // Store the active doc ID *per user*
        localStorage.setItem(`activeDocumentID_${userID}`, activeDocumentID);
        console.log("Switched active document to:", activeDocumentID);
        loadChatHistory();
    });

    // When the delete button is clicked
    deleteDocumentButton.addEventListener('click', handleDeleteDocument);
    
    // --- 6. INITIALIZE THE APP ---
    // Load the user's documents as soon as the page loads
    loadDocuments();
});

