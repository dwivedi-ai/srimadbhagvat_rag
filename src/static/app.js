// src/static/app.js
const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const initialView = document.querySelector('.initial-view'); // Get initial view element
// Keep loading indicator reference if needed, but it's visually hidden now
// const loadingIndicator = document.getElementById('loading-indicator');

// Loading message element reference
let loadingMessageElement = null;
let chatHasMessages = false; // Flag to track if messages have been added

// Function to add a message to the chat box
function addMessage(text, sender) {
  // Hide initial view if this is the first message
  if (!chatHasMessages && initialView) {
      initialView.style.display = 'none'; // Hide initial prompt screen
      chatBox.classList.add('has-messages'); // Add class for potential future styling
      chatHasMessages = true;

      // Optional: Show the initial bot message if needed, or remove it entirely
      const initialBotMsg = document.querySelector('.initial-bot-message');
      if (initialBotMsg) {
          // initialBotMsg.style.display = 'block'; // If you want to show it now
      }
  }

  const messageDiv = document.createElement('div');
  messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'bot-message');
  const paragraph = document.createElement('p');
  // Basic Markdown rendering (bold and italics) - optional
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'); // Bold
  text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');     // Italics
  paragraph.innerHTML = text; // Use innerHTML for basic markdown
  // If security is paramount and markdown isn't needed, stick to paragraph.textContent = text;

  messageDiv.appendChild(paragraph);
  chatBox.appendChild(messageDiv);
  chatBox.scrollTop = chatBox.scrollHeight; // Scroll to the bottom
  return messageDiv;
}

// Function to create and show loading indicator in the chat
function showLoadingMessage() {
    // Hide initial view if loading starts before first message
    if (!chatHasMessages && initialView) {
        initialView.style.display = 'none';
        chatBox.classList.add('has-messages');
        chatHasMessages = true;
    }

    // Create loading message container
    loadingMessageElement = document.createElement('div');
    loadingMessageElement.className = 'loading-message'; // Uses new CSS class

    // Create loading dots container
    const dotsContainer = document.createElement('div');
    dotsContainer.className = 'loading-dots';

    // Add three animated dots
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'dot';
        dotsContainer.appendChild(dot);
    }

    loadingMessageElement.appendChild(dotsContainer);
    chatBox.appendChild(loadingMessageElement);
    chatBox.scrollTop = chatBox.scrollHeight; // Scroll to show loading

    return loadingMessageElement;
}

// Function to remove loading message
function removeLoadingMessage() {
    if (loadingMessageElement && loadingMessageElement.parentNode) {
        loadingMessageElement.parentNode.removeChild(loadingMessageElement);
        loadingMessageElement = null;
    }
}

// Function to handle sending the message
async function sendMessage() {
    const question = userInput.value.trim();
    if (!question) return; // Don't send empty messages

    addMessage(question, 'user');
    userInput.value = ''; // Clear input field

    // Show loading indicator in the chat flow
    showLoadingMessage();

    sendButton.disabled = true; // Disable button while processing
    userInput.disabled = true; // Disable input field too

    try {
        // Keep simulated delay or remove for production
        // await new Promise(resolve => setTimeout(resolve, 1500));

        const response = await fetch('/query', { // Ensure this endpoint is correct
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question: question }),
        });

        // Remove loading message *before* adding bot response
        removeLoadingMessage();

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Failed to parse error response' }));
            console.error('API Error:', response.status, errorData);
            addMessage(`Error: ${errorData.error || 'Could not reach the server.'}`, 'bot');
        } else {
            const data = await response.json();
            addMessage(data.answer, 'bot');
        }
    } catch (error) {
        // Remove loading message even if there's an error
        removeLoadingMessage();
        console.error('Network or other error:', error);
        addMessage('Error: Could not connect to the chatbot API. Please check your connection or the server.', 'bot');
    } finally {
        sendButton.disabled = false; // Re-enable button
        userInput.disabled = false; // Re-enable input
        // userInput.focus(); // Focus back on input
    }
}

// Event listeners
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', function(event) {
    // Send message if Enter key is pressed (and not Shift+Enter for new line)
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault(); // Prevent default Enter behavior (new line)
        sendMessage();
    }
});

// --- Initial Setup ---

// Decide whether to show the initial bot message or the example screen first.
// The current setup shows the example screen (`initial-view`) by default via CSS.
// The JS will hide it when the first message is sent or loading starts.

// Optional: Handle clicks on example prompts
const examplePrompts = document.querySelectorAll('.capability-column.selectable ul li');
examplePrompts.forEach(prompt => {
    prompt.addEventListener('click', () => {
        const promptText = prompt.textContent.replace(' →', '').trim();
        userInput.value = promptText;
        userInput.focus();
        // Optionally, send the message immediately:
        // sendMessage();
    });
});


// Initial focus on the input field
userInput.focus();