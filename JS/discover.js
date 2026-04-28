/**
 * Page de découverte : 3 recommandations dynamiques + audio + like/dislike + ajout playlist.
 */
(async function () {
    // Auth obligatoire
    let user;
    try {
        user = await window.API.requireAuth();
    } catch (_) { return; }

    const $ = (s) => document.querySelector(s);
    const grid = $('#recommendations');
    const tasteBox = $('#taste-summary');
    const audio = $('#audio-player');
    const exoticSlider = $('#exotic-slider');
    const exoticValue = $('#exotic-value');
    const refreshBtn = $('#refresh-btn');

    // Curseur exotique
    if (typeof user.exotic_factor === 'number') {
        exoticSlider.value = user.exotic_factor;
    }
    exoticValue.textContent = Math.round(parseFloat(exoticSlider.value) * 100) + '%';

    let prefsTimer;
    exoticSlider.addEventListener('input', () => {
        exoticValue.textContent = Math.round(parseFloat(exoticSlider.value) * 100) + '%';
        clearTimeout(prefsTimer);
        prefsTimer = setTimeout(async () => {
            try {
                await window.API.updatePrefs(parseFloat(exoticSlider.value));
            } catch (e) { console.warn(e); }
        }, 400);
    });

    refreshBtn.addEventListener('click', loadRecos);

    // Modal "ajouter à playlist"
    const modal = $('#playlist-modal');
    const modalList = $('#playlist-modal-list');
    const modalCancel = $('#modal-cancel');
    const modalCreate = $('#modal-create');
    const newPlaylistName = $('#new-playlist-name');
    let pendingTrackId = null;

    modalCancel.addEventListener('click', () => modal.style.display = 'none');
    modalCreate.addEventListener('click', async () => {
        const name = newPlaylistName.value.trim();
        if (!name) return;
        try {
            const pl = await window.API.createPlaylist(name);
            await window.API.addTrackToPlaylist(pl.id, pendingTrackId);
            window.API.toast(`Ajouté à « ${name} »`, 'success');
            modal.style.display = 'none';
            newPlaylistName.value = '';
        } catch (e) {
            window.API.toast(e.message || "Erreur", 'error');
        }
    });

    async function openAddToPlaylist(trackId) {
        pendingTrackId = trackId;
        modalList.innerHTML = '<p style="color: var(--text-muted)">Chargement…</p>';
        modal.style.display = 'flex';
        try {
            const playlists = await window.API.playlists();
            if (!playlists.length) {
                modalList.innerHTML = '<p style="color: var(--text-muted)">Aucune playlist. Crée la première ci-dessous !</p>';
                return;
            }
            modalList.innerHTML = '';
            for (const p of playlists) {
                const div = document.createElement('div');
                div.className = 'modal-playlist-item';
                div.innerHTML = `<span><i class="fa-solid fa-music"></i> ${p.name}</span><span style="color:var(--text-muted); font-size:0.85rem;">${p.tracks.length} morceau${p.tracks.length > 1 ? 'x' : ''}</span>`;
                div.onclick = async () => {
                    try {
                        await window.API.addTrackToPlaylist(p.id, trackId);
                        window.API.toast(`Ajouté à « ${p.name} »`, 'success');
                        modal.style.display = 'none';
                    } catch (e) {
                        window.API.toast(e.message || 'Erreur', 'error');
                    }
                };
                modalList.appendChild(div);
            }
        } catch (e) {
            modalList.innerHTML = `<p style="color:#f87171">${e.message}</p>`;
        }
    }

    // Audio: un seul player partagé
    let currentCard = null;

    function stopAudio() {
        audio.pause();
        if (currentCard) {
            currentCard.classList.remove('playing');
            currentCard.querySelector('.btn-play')?.classList.remove('playing');
            currentCard.querySelector('.btn-play i')?.classList.replace('fa-pause', 'fa-play');
        }
        currentCard = null;
    }

    audio.addEventListener('timeupdate', () => {
        if (!currentCard || !audio.duration) return;
        const bar = currentCard.querySelector('.reco-progress-bar');
        if (bar) bar.style.width = (audio.currentTime / audio.duration * 100) + '%';
    });

    audio.addEventListener('ended', stopAudio);

    function togglePlay(card, track) {
        if (currentCard === card) {
            stopAudio();
            return;
        }
        stopAudio();
        if (!track.preview_url) {
            window.API.toast("Pas d'extrait audio disponible (preview_url manquant)", 'error');
            return;
        }
        audio.src = track.preview_url;
        audio.play().then(() => {
            currentCard = card;
            card.classList.add('playing');
            const btn = card.querySelector('.btn-play');
            btn.classList.add('playing');
            btn.querySelector('i').classList.replace('fa-play', 'fa-pause');
            window.API.interact(track.id, 'play').catch(() => {});
        }).catch(err => {
            window.API.toast("Lecture impossible : " + err.message, 'error');
        });
    }

    // Render
    function makeCard(track) {
        const card = document.createElement('div');
        card.className = 'reco-card' + (track.is_exotic ? ' exotic' : '');
        card.dataset.trackId = track.id;

        const img = document.createElement('img');
        img.className = 'reco-cover';
        img.src = track.image_url || '/img/album placeholder.jpg';
        img.alt = track.title;
        img.onerror = () => { img.src = '/img/album placeholder.jpg'; };
        card.appendChild(img);

        const meta = document.createElement('div');
        meta.className = 'reco-meta';
        meta.innerHTML = `
            <div class="reco-title">${escapeHtml(track.title)}</div>
            <div class="reco-artist">${escapeHtml(track.artist)}</div>
            <div class="reco-badges">
                ${track.genre ? `<span class="badge">${escapeHtml(track.genre)}</span>` : ''}
                ${typeof track.similarity === 'number' ? `<span class="badge">match ${Math.round(track.similarity * 100)}%</span>` : ''}
            </div>
            <div class="reco-progress"><div class="reco-progress-bar"></div></div>
        `;
        card.appendChild(meta);

        const actions = document.createElement('div');
        actions.className = 'reco-actions';

        const playBtn = btn('btn-play', 'fa-play', "Écouter l'extrait");
        playBtn.addEventListener('click', () => togglePlay(card, track));
        actions.appendChild(playBtn);

        const likeBtn = btn('btn-like', 'fa-heart', "J'aime");
        likeBtn.addEventListener('click', () => onInteract(card, track, 'like'));
        actions.appendChild(likeBtn);

        const dislikeBtn = btn('btn-dislike', 'fa-xmark', "Je n'aime pas");
        dislikeBtn.addEventListener('click', () => onInteract(card, track, 'dislike'));
        actions.appendChild(dislikeBtn);

        const addBtn = btn('btn-add', 'fa-plus', "Ajouter à une playlist");
        addBtn.addEventListener('click', () => openAddToPlaylist(track.id));
        actions.appendChild(addBtn);

        card.appendChild(actions);
        return card;
    }

    function btn(cls, icon, title) {
        const b = document.createElement('button');
        b.className = `btn ${cls}`;
        b.title = title;
        b.innerHTML = `<i class="fa-solid ${icon}"></i>`;
        return b;
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
        })[c]);
    }

    async function onInteract(card, track, action) {
        try {
            await window.API.interact(track.id, action);
            card.style.transition = 'all .3s';
            card.style.transform = action === 'like' ? 'translateX(80px) rotate(8deg)' : 'translateX(-80px) rotate(-8deg)';
            card.style.opacity = '0';
            setTimeout(loadRecos, 350);
        } catch (e) {
            window.API.toast(e.message, 'error');
        }
    }

    async function loadTaste() {
        try {
            const t = await window.API.explainTaste();
            if (t.likes === 0 && t.dislikes === 0) {
                tasteBox.classList.remove('visible');
                return;
            }
            tasteBox.classList.add('visible');
            tasteBox.innerHTML = `
                <strong>Profil musical</strong> &nbsp; ❤️ ${t.likes} likes · 👎 ${t.dislikes} dislikes
                ${t.liked_genres.length ? `<br><strong>Genres aimés :</strong> ${t.liked_genres.map(g => `<span class="pill">${escapeHtml(g)}</span>`).join('')}` : ''}
            `;
        } catch (e) {
            console.warn(e);
        }
    }

    async function loadRecos() {
        stopAudio();
        grid.innerHTML = '<p class="no-recos">Recherche des meilleures recommandations…</p>';
        await loadTaste();
        try {
            const { recommendations } = await window.API.recommendations(3);
            grid.innerHTML = '';
            if (!recommendations.length) {
                grid.innerHTML = '<p class="no-recos">Catalogue vide. Lance <code>python -m backend.seed</code> côté serveur.</p>';
                return;
            }
            for (const t of recommendations) grid.appendChild(makeCard(t));
        } catch (e) {
            grid.innerHTML = `<p class="no-recos" style="color:#f87171">${e.message}</p>`;
        }
    }

    loadRecos();
})();
