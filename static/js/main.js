/*
========================================
URBAN RURAL CONNECTOR - MAIN JAVASCRIPT
========================================
*/

document.addEventListener('DOMContentLoaded', function () {

    // ==================== HERO SECTION SPACING ====================
    const hero = document.querySelector('.hero');
    if (hero) {
        hero.style.marginTop = '80px';
    }

    // ==================== MOBILE MENU TOGGLE ====================
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const navLinks = document.querySelector('.nav-links');

    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', function () {
            navLinks.classList.toggle('active');
            this.classList.toggle('active');
        });
    }

    // ==================== SMOOTH SCROLLING (ORIGINAL) ====================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });

    // ==================== FORM VALIDATION (ORIGINAL) ====================
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function (e) {
            const inputs = this.querySelectorAll('input[required], textarea[required]');
            let isValid = true;

            inputs.forEach(input => {
                if (!input.value.trim()) {
                    isValid = false;
                    input.style.borderColor = 'var(--error-red)';
                } else {
                    input.style.borderColor = '#E0DCD5';
                }
            });

            if (!isValid) {
                e.preventDefault();
                alert('Please fill in all required fields');
            }
        });
    });

    // ==================== IMAGE LAZY LOADING (ORIGINAL) ====================
    const images = document.querySelectorAll('img[data-src]');
    if (images.length > 0) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    img.unobserve(img);
                }
            });
        });
        images.forEach(img => imageObserver.observe(img));
    }

    // ==================== NAVBAR SCROLL SHADOW ====================
    window.addEventListener('scroll', () => {
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            if (window.scrollY > 50) {
                navbar.style.boxShadow = 'var(--shadow-md)';
                navbar.style.backgroundColor = '#ffffff';
            } else {
                navbar.style.boxShadow = 'var(--shadow-sm)';
            }
        }
    });

    // ==================== SMART CHATBOT LOGIC ====================
    const chatCircle = document.getElementById('chat-circle');
    const chatBox = document.getElementById('chat-box');
    const chatBoxToggle = document.getElementById('chat-box-toggle');
    const chatSubmit = document.getElementById('chat-submit');
    const chatInput = document.getElementById('chat-input');
    const chatContent = document.getElementById('chat-content');

    // Toggle Chat Window
    if (chatCircle && chatBox) {
        chatCircle.addEventListener('click', () => {
            chatBox.style.display = chatBox.style.display === 'none' ? 'flex' : 'none';
        });
    }

    if (chatBoxToggle) {
        chatBoxToggle.addEventListener('click', () => {
            chatBox.style.display = 'none';
        });
    }

    // Main Send Function
    function handleChatSend() {
        const message = chatInput.value.trim();
        if (!message) return;

        // Display User Message
        appendMessage("User", message);
        chatInput.value = '';

        // Detect section based on URL
        let section = "general";
        const url = window.location.href.toLowerCase();
        if (url.includes("farmer") || url.includes("rural")) section = "rural";
        else if (url.includes("market") || url.includes("urban")) section = "urban";
        else if (url.includes("transport")) section = "transport";

        // API Call to Flask
        fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, section: section })
        })
        .then(res => {
            if (!res.ok) throw new Error('Server not reachable');
            return res.json();
        })
        .then(data => {
            appendMessage("Bot", data.response);
        })
        .catch(err => {
            console.error("Chat Error:", err);
            appendMessage("Bot", "Sorry, I'm having trouble connecting. Check if Flask is running.");
        });
    }

    // Trigger on Click
    if (chatSubmit) {
        chatSubmit.addEventListener('click', handleChatSend);
    }

    // Trigger on "Enter" Key
    if (chatInput) {
        chatInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                handleChatSend();
            }
        });
    }

    function appendMessage(sender, text) {
        if (!chatContent) return;
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-msg ${sender.toLowerCase()}`;
        msgDiv.innerHTML = `<strong>${sender}:</strong> ${text}`;
        chatContent.appendChild(msgDiv);
        chatContent.scrollTop = chatContent.scrollHeight;
    }

    console.log('%c🌾 URC System & Chatbot Active', 'color: #6B8E23; font-weight: bold;');
});

// ==================== UTILITY FUNCTIONS (ORIGINAL) ====================
function formatPrice(price) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 0
    }).format(price);
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background-color: ${type === 'success' ? '#4CAF50' : '#E53935'};
        color: white;
        border-radius: 8px;
        z-index: 9999;
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
}