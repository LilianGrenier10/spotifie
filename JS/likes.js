/**
 * Page Mes likes : liste des morceaux likés, lecture, retrait du like, ajout playlist.
 */
(async function () {
    try { await window.API.requireAuth(); }
    catch (_) { return; }

    const $ = (s) => document.querySelector(s);
    const container = $('#likes-container');
    const emptyState = $('#empty-state');
    const counter = $('#likes-count');
    const audio = $('#audio-player');

    // --- modal "ajouter à playlist" ---
    const modal = $('#playlist-modal');
    const modalList = $('#playlist-modal-list');
    const newPlaylistName = $('#new-playlist-name');
    let pendingTrackId = null;

    $('#modal-cancel').addEventListener('click', () => modal.style.display = 'none');
    $('#modal-create').addEventListener('click', async () => {
        const name = newPlaylistName.value.trim();
        if (!name) return;
        try {
            const pl = await window.API.createPlaylist(name);
            await window.API.addTrackToPlaylist(pl.id, pendingTrackId);
            window.API.toast(`Ajouté à « ${name} »`, 'success');
            modal.style.display = 'none';
            newPlaylistName.value = '';
        } catch (e) {
            window.API.toast(e.message || 'Erreur', 'error');
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
                div.innerHTML = `<span><i class="fa-solid fa-music"></i> ${escapeHtml(p.name)}</span><span style="color:var(--text-muted); font-size:0.85rem;">${p.tracks.length} morceau${p.tracks.length > 1 ? 'x' : ''}</span>`;
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
            modalList.innerHTML = `<p style="color:#f87171">${escapeHtml(e.message)}</p>`;
        }
    }

    // --- audio player partagé ---
    let currentRow = null;
    audio.addEventListener('timeupdate', () => {
        if (!currentRow || !audio.duration) return;
        const bar = currentRow.querySelector('.like-progress-bar');
        if (bar) bar.style.width = (audio.currentTime / audio.duration * 100) + '%';
    });
    audio.addEventListener('ended', stopAudio);

    function stopAudio() {
        audio.pause();
        if (currentRow) {
            currentRow.classList.remove('playing');
            const ic = currentRow.querySelector('.btn-play i');
            if (ic) ic.classList.replace('fa-pause', 'fa-play');
        }
        currentRow = null;
    }

    function togglePlay(row, track) {
        if (currentRow === row) { stopAudio(); return; }
        stopAudio();
        if (!track.preview_url) {
            window.API.toast("Pas d'extrait audio disponible", 'error');
            return;
        }
        audio.src = track.preview_url;
        audio.play().then(() => {
            currentRow = row;
            row.classList.add('playing');
            row.querySelector('.btn-play i').classList.replace('fa-play', 'fa-pause');
            window.API.interact(track.id, 'play').catch(() => {});
        }).catch(err => window.API.toast("Lecture impossible", 'error'));
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
        })[c]);
    }

    function makeRow(track) {
        const row = document.createElement('div');
        row.className = 'like-row';
        row.dataset.trackId = track.id;
        row.innerHTML = `
            <img class="like-cover" src="${escapeHtml(track.image_url || '/img/album placeholder.jpg')}"
                 alt="" onerror="this.src='/img/album placeholder.jpg'">
            <div class="like-row-content">
                <div class="like-title">${escapeHtml(track.title)}${track.genre ? `<span class="like-genre-pill">${escapeHtml(track.genre)}</span>` : ''}</div>
                <div class="like-artist">${escapeHtml(track.artist)}${track.album ? ` · ${escapeHtml(track.album)}` : ''}</div>
                <div class="like-progress"><div class="like-progress-bar"></div></div>
            </div>
            <div class="like-actions">
                <button class="btn btn-play" title="Écouter"><i class="fa-solid fa-play"></i></button>
                <button class="btn btn-add" title="Ajouter à une playlist"><i class="fa-solid fa-plus"></i></button>
                <button class="btn btn-dislike" title="Retirer le like"><i class="fa-solid fa-heart-crack"></i></button>
            </div>
        `;
        row.querySelector('.btn-play').addEventListener('click', () => togglePlay(row, track));
        row.querySelector('.btn-add').addEventListener('click', () => openAddToPlaylist(track.id));
        row.querySelector('.btn-dislike').addEventListener('click', async () => {
            if (currentRow === row) stopAudio();
            try {
                await window.API.unlike(track.id);
                row.style.transition = 'all .25s';
                row.style.opacity = '0';
                row.style.transform = 'translateX(60px)';
                setTimeout(loadLikes, 250);
            } catch (e) { window.API.toast(e.message, 'error'); }
        });
        return row;
    }

    async function loadLikes() {
        container.innerHTML = '<p style="color: var(--text-muted)">Chargement…</p>';
        try {
            const tracks = await window.API.likedTracks();
            counter.textContent = `${tracks.length} morceau${tracks.length > 1 ? 'x' : ''}`;
            container.innerHTML = '';
            if (!tracks.length) {
                emptyState.style.display = '';
                return;
            }
            emptyState.style.display = 'none';
            for (const t of tracks) container.appendChild(makeRow(t));
        } catch (e) {
            container.innerHTML = `<p style="color:#f87171">${escapeHtml(e.message)}</p>`;
        }
    }

    loadLikes();
})();
