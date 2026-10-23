// Global application script for SunnyVale Primary School Management System

document.addEventListener("DOMContentLoaded", () => {
    // Re-initialize Lucide icons if available
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // CSRF Protection Hook: Auto-inject csrf_token into all forms
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

    if (csrfToken) {
        // Inject into existing forms
        document.querySelectorAll('form').forEach(form => {
            if (!form.querySelector('input[name="csrf_token"]')) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'csrf_token';
                input.value = csrfToken;
                form.appendChild(input);
            }
        });

        // Event delegation to catch dynamically created or submitted forms
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form && form.tagName === 'FORM' && !form.querySelector('input[name="csrf_token"]')) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'csrf_token';
                input.value = csrfToken;
                form.appendChild(input);
            }
        }, true);
    }

    // Close any modal on 'Escape' key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            const modals = document.querySelectorAll('[id$="Modal"]');
            modals.forEach(modal => {
                modal.classList.add("hidden");
            });
        }
    });

    // Close modal on clicking outside dialog backdrop
    const modals = document.querySelectorAll('[id$="Modal"]');
    modals.forEach(modal => {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                modal.classList.add("hidden");
            }
        });
    });
});
