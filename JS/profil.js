/**
 * Page profil : CRUD playlists + Spotify connect + export.
 */
(async function () {
    let user;
    try { user = await window.API.requireAuth(); }
    catch (_) { return; }

    const $ = (s) => document.querySelector(s);
    const container = $('#playlists-container');
    const emptyState = $('#empty-state');
    const audio = $('#audio-player');

    // Spotify state
    const sStatus = $('#spotify-status');
    const sBtn = $('#spotify-connect-btn');
    const sDisc = $('#spotify-disconnect-btn');

    function renderSpotifyState(connected, spotifyId) {
        if (connected) {
            sStatus.classList.add('connected');
            sStatus.textContent = `Connecté à Spotify (${spotifyId || ''})`;
            sBtn.style.display = 'none';
            sDisc.style.display = '';
        } else {
            sStatus.classList.remove('connected');
            sStatus.textContent = 'Spotify non connecté';
            sBtn.style.display = '';
            sDisc.style.display = 'none';
        }
    }

    renderSpotifyState(user.spotify_connected, user.spotify_id);

    sDisc.addEventListener('click', async () => {
        if (!confirm("Déconnecter ton compte Spotify de SPOTIFIÉ ? Tu pourras te reconnecter ensuite.")) return;
        try {
            await window.API.spotifyDisconnect();
            window.API.toast('Compte Spotify déconnecté', 'success');
            user.spotify_connected = false;
            user.spotify_id = null;
            renderSpotifyState(false, null);
            // Re-render des cartes pour mettre à jour les boutons "Exporter"
            loadPlaylists();
        } catch (e) {
            window.API.toast(e.message || 'Erreur', 'error');
        }
    });

    // Notification post-OAuth
    if (new URLSearchParams(location.search).get('spotify') === 'ok') {
        window.API.toast('Compte Spotify connecté avec succès !', 'success');
        history.replaceState(null, '', location.pathname);
    }

    // Modal création
    const cModal = $('#create-modal');
    const cName = $('#create-name');
    const cDesc = $('#create-description');
    $('#new-playlist-btn').addEventListener('click', () => {
        cName.value = ''; cDesc.value = '';
        cModal.style.display = 'flex';
        setTimeout(() => cName.focus(), 50);
    });
    $('#create-cancel').addEventListener('click', () => cModal.style.display = 'none');
    $('#create-submit').addEventListener('click', async () => {
        const name = cName.value.trim();
        if (!name) return;
        try {
            await window.API.createPlaylist(name, cDesc.value.trim());
            cModal.style.display = 'none';
            window.API.toast('Playlist créée', 'success');
            loadPlaylists();
        } catch (e) {
            window.API.toast(e.message || 'Erreur', 'error');
        }
    });

    // Audio player partagé
    let currentTrackEl = null;
    audio.addEventListener('ended', () => {
        if (currentTrackEl) {
            currentTrackEl.querySelector('.play-mini i')?.classList.replace('fa-pause', 'fa-play');
            currentTrackEl = null;
        }
    });

    function togglePlayMini(trackEl, previewUrl) {
        if (currentTrackEl === trackEl) {
            audio.pause();
            trackEl.querySelector('.play-mini i').classList.replace('fa-pause', 'fa-play');
            currentTrackEl = null;
            return;
        }
        if (currentTrackEl) {
            currentTrackEl.querySelector('.play-mini i').classList.replace('fa-pause', 'fa-play');
        }
        if (!previewUrl) {
            window.API.toast("Pas d'extrait audio disponible", 'error');
            return;
        }
        audio.src = previewUrl;
        audio.play().then(() => {
            currentTrackEl = trackEl;
            trackEl.querySelector('.play-mini i').classList.replace('fa-play', 'fa-pause');
        }).catch(err => {
            window.API.toast("Lecture impossible", 'error');
        });
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
        })[c]);
    }

    function renderPlaylist(p) {
        const card = document.createElement('div');
        card.className = 'playlist-card';
        card.dataset.id = p.id;

        const cover = (p.tracks[0] && p.tracks[0].image_url) || p.cover_url || '/img/album placeholder.jpg';

        card.innerHTML = `
            <div class="playlist-content">
                <div class="playlist-image">
                    <img src="${escapeHtml(cover)}" alt="cover" onerror="this.src='/img/album placeholder.jpg'">
                </div>
                <div class="playlist-info">
                    <h3 contenteditable="false" class="playlist-name">${escapeHtml(p.name)}</h3>
                    <p class="song-count">${p.tracks.length} morceau${p.tracks.length > 1 ? 'x' : ''}</p>
                    <ul class="song-list"></ul>
                    <div class="playlist-actions-bar">
                        <button class="btn-rename"><i class="fa-solid fa-pen"></i> Renommer</button>
                        <button class="btn-export" ${user.spotify_connected ? '' : 'disabled title="Connecte Spotify d&#39;abord"'}><i class="fa-brands fa-spotify"></i> Exporter</button>
                        <button class="btn-delete"><i class="fa-solid fa-trash"></i> Supprimer</button>
                    </div>
                </div>
            </div>
        `;

        const ul = card.querySelector('.song-list');
        if (!p.tracks.length) {
            ul.innerHTML = '<li class="song-item" style="color:var(--text-muted); font-style:italic;">Vide — ajoute des morceaux depuis la page Découvrir</li>';
        } else {
            for (const t of p.tracks) {
                const li = document.createElement('li');
                li.className = 'song-item';
                li.innerHTML = `
                    <button class="play-mini" title="Écouter"><i class="fa-solid fa-play" style="font-size:0.7rem;"></i></button>
                    <div class="song-title">
                        ${escapeHtml(t.title)}
                        <span class="song-artist">— ${escapeHtml(t.artist)}</span>
                    </div>
                    <div class="song-item-actions">
                        <button class="remove-btn" title="Retirer"><i class="fa-solid fa-xmark"></i></button>
                    </div>
                `;
                li.querySelector('.play-mini').addEventListener('click', () => togglePlayMini(li, t.preview_url));
                li.querySelector('.remove-btn').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    try {
                        await window.API.removeTrackFromPlaylist(p.id, t.id);
                        loadPlaylists();
                    } catch (err) { window.API.toast(err.message, 'error'); }
                });
                ul.appendChild(li);
            }
        }

        // Actions
        card.querySelector('.btn-rename').addEventListener('click', async () => {
            const newName = prompt('Nouveau nom :', p.name);
            if (!newName || newName.trim() === p.name) return;
            try {
                await window.API.updatePlaylist(p.id, { name: newName.trim() });
                window.API.toast('Renommée', 'success');
                loadPlaylists();
            } catch (e) { window.API.toast(e.message, 'error'); }
        });

        card.querySelector('.btn-delete').addEventListener('click', async () => {
            if (!confirm(`Supprimer la playlist « ${p.name} » ?`)) return;
            try {
                await window.API.deletePlaylist(p.id);
                window.API.toast('Supprimée', 'success');
                loadPlaylists();
            } catch (e) { window.API.toast(e.message, 'error'); }
        });

        const exportBtn = card.querySelector('.btn-export');
        if (!exportBtn.disabled) {
            exportBtn.addEventListener('click', async () => {
                exportBtn.disabled = true;
                const original = exportBtn.innerHTML;
                exportBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Recherche sur Spotify…';
                try {
                    const r = await window.API.exportPlaylist(p.id);
                    const msg = r.missing && r.missing.length
                        ? `Exportée ! ${r.matched}/${r.total} morceaux trouvés (${r.missing.length} introuvables)`
                        : `Exportée ! ${r.matched}/${r.total} morceaux ajoutés`;
                    window.API.toast(msg, 'success');
                    if (r.missing && r.missing.length) {
                        console.warn('Morceaux non trouvés sur Spotify :', r.missing);
                    }
                    if (r.spotify_url) window.open(r.spotify_url, '_blank');
                } catch (e) {
                    window.API.toast(e.message || "Échec de l'export", 'error');
                } finally {
                    exportBtn.disabled = false;
                    exportBtn.innerHTML = original;
                }
            });
        }

        return card;
    }

    async function loadPlaylists() {
        container.innerHTML = '<p style="color:var(--text-muted)">Chargement…</p>';
        try {
            const playlists = await window.API.playlists();
            container.innerHTML = '';
            if (!playlists.length) {
                emptyState.style.display = '';
                return;
            }
            emptyState.style.display = 'none';
            for (const p of playlists) container.appendChild(renderPlaylist(p));
        } catch (e) {
            container.innerHTML = `<p style="color:#f87171">${e.message}</p>`;
        }
    }

    loadPlaylists();
})();
