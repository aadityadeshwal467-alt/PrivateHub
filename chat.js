document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const messageContainer = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const statusIndicator = document.getElementById('connection-status');

    socket.on('connect', () => {
        statusIndicator.textContent = 'Connected';
        statusIndicator.classList.remove('offline');
        statusIndicator.classList.add('online');
    });

    socket.on('disconnect', () => {
        statusIndicator.textContent = 'Disconnected';
        statusIndicator.classList.remove('online');
        statusIndicator.classList.add('offline');
    });

    socket.on('message', (data) => {
        appendMessage(data);
        scrollToBottom();
    });

    // Handle history loading if implemented
    socket.on('load_history', (messages) => {
        messageContainer.innerHTML = '';
        messages.forEach(msg => appendMessage(msg));
        scrollToBottom();
    });

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const content = messageInput.value.trim();
        if (content) {
            socket.emit('send_message', { content: content });
            messageInput.value = '';
        }
    });

    function appendMessage(data) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message');
        const isMe = data.username === CURRENT_USER;
        if (isMe) msgDiv.classList.add('message-own');

        const header = document.createElement('div');
        header.classList.add('message-header');
        header.innerHTML = `<span class="username">${data.username}</span> <span class="time">${data.timestamp}</span>`;

        const body = document.createElement('div');
        body.classList.add('message-body');
        body.textContent = data.content;

        msgDiv.appendChild(header);
        msgDiv.appendChild(body);
        messageContainer.appendChild(msgDiv);
    }

    function scrollToBottom() {
        messageContainer.scrollTop = messageContainer.scrollHeight;
    }
});
