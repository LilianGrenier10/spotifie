/**
 * Page Mon compte : édition profil + mot de passe + curseur curiosité + suppression.
 */
(async function () {
    let user;
    try { user = await window.API.requireAuth(); }
    catch (_) { return; }

    const $ = (s) => document.querySelector(s);

    // ---- Pré-remplit les formulaires ----
    $('#display_name').value = user.display_name || '';
    $('#email').value = user.email || '';

    const exoticSlider = $('#exotic_factor');
    const exoticValue = $('#exotic_value');
    if (typeof user.exotic_factor === 'number') {
        exoticSlider.value = user.exotic_factor;
    }
    function syncExoticLabel() {
        exoticValue.textContent = Math.round(parseFloat(exoticSlider.value) * 100) + ' %';
    }
    syncExoticLabel();

    let exoticTimer;
    exoticSlider.addEventListener('input', () => {
        syncExoticLabel();
        clearTimeout(exoticTimer);
        exoticTimer = setTimeout(async () => {
            try {
                await window.API.updatePrefs(parseFloat(exoticSlider.value));
                window.API.toast('Préférences mises à jour', 'success');
            } catch (e) { window.API.toast(e.message || 'Erreur', 'error'); }
        }, 400);
    });

    // ---- Formulaire infos ----
    $('#profile-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const display_name = $('#display_name').value.trim();
        const email = $('#email').value.trim();
        try {
            const updated = await window.API.updateMe({ display_name, email });
            window.API.toast('Profil mis à jour', 'success');
            // Mettre à jour le greeting du header (en relançant le loader)
            const greet = document.querySelector('header .header-actions span');
            if (greet) greet.textContent = `👤 ${updated.display_name || updated.email}`;
        } catch (ex) {
            window.API.toast(ex.message || 'Erreur', 'error');
        }
    });

    // ---- Formulaire mot de passe ----
    $('#password-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const current = $('#current_password').value;
        const np = $('#new_password').value;
        const np2 = $('#new_password2').value;
        if (np !== np2) {
            window.API.toast("Les nouveaux mots de passe ne correspondent pas", 'error');
            return;
        }
        try {
            await window.API.changePassword(current, np);
            window.API.toast('Mot de passe modifié', 'success');
            $('#password-form').reset();
        } catch (ex) {
            window.API.toast(ex.message || 'Erreur', 'error');
        }
    });

    // ---- Suppression de compte ----
    const dModal = $('#delete-modal');
    const dPassword = $('#delete-password');
    $('#delete-account-btn').addEventListener('click', () => {
        dPassword.value = '';
        dModal.style.display = 'flex';
        setTimeout(() => dPassword.focus(), 50);
    });
    $('#delete-cancel').addEventListener('click', () => dModal.style.display = 'none');
    $('#delete-confirm').addEventListener('click', async () => {
        const pwd = dPassword.value;
        if (!pwd) return;
        try {
            await window.API.deleteAccount(pwd);
            window.API.toast('Compte supprimé. À bientôt 👋', 'success');
            setTimeout(() => window.location.href = '/index.html', 1200);
        } catch (e) {
            window.API.toast(e.message || 'Erreur', 'error');
        }
    });
})();
