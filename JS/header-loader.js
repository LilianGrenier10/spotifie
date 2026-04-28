document.addEventListener("DOMContentLoaded", function () {
    const placeholder = document.getElementById("header-placeholder");
    if (!placeholder) return;

    fetch("/header.html")
        .then(r => r.text())
        .then(async (html) => {
            placeholder.innerHTML = html;
            highlightActiveLink();
            await applyAuthState();
            wireLogout();
        })
        .catch(err => console.error("Erreur header:", err));

    function highlightActiveLink() {
        const currentPage = window.location.pathname.split("/").pop() || "index.html";
        document.querySelectorAll("header nav a, header .header-actions a")
            .forEach(link => {
                if (link.getAttribute("data-page") === currentPage) {
                    link.classList.add("active");
                }
            });
    }

    async function applyAuthState() {
        let user = null;
        try { user = await window.API.me(); } catch (_) { /* pas connecté */ }

        document.querySelectorAll('[data-auth-only]').forEach(el => {
            el.style.display = user ? '' : 'none';
        });
        document.querySelectorAll('[data-guest-only]').forEach(el => {
            el.style.display = user ? 'none' : '';
        });

        // Si l'utilisateur est connecté on affiche son nom à la place de "Connexion"
        if (user) {
            const actions = document.querySelector('header .header-actions');
            if (actions) {
                const greeting = document.createElement('span');
                greeting.textContent = `👤 ${user.display_name || user.email}`;
                greeting.style.cssText = 'color: var(--text-muted); font-size: 0.95rem; margin-right: 8px;';
                actions.prepend(greeting);
            }
        }
    }

    function wireLogout() {
        const btn = document.getElementById('logout-btn');
        if (!btn) return;
        btn.addEventListener('click', async () => {
            await window.API.logout();
            window.location.href = '/index.html';
        });
    }
});
