/**
 * Client API SPOTIFIÉ - wrapper fetch + utils auth.
 * Disponible globalement sous window.API.
 */
(function () {
    const BASE = ''; // même origin (servi par Flask)

    async function request(path, options = {}) {
        const opts = {
            method: options.method || 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {})
            },
        };
        if (options.body !== undefined) {
            opts.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
        }
        const res = await fetch(BASE + path, opts);
        const ct = res.headers.get('content-type') || '';
        const data = ct.includes('application/json') ? await res.json() : await res.text();
        if (!res.ok) {
            const err = new Error((data && data.error) || res.statusText);
            err.status = res.status;
            err.data = data;
            throw err;
        }
        return data;
    }

    const API = {
        // Auth
        register: (email, password, display_name) =>
            request('/api/auth/register', { method: 'POST', body: { email, password, display_name } }),
        login: (email, password) =>
            request('/api/auth/login', { method: 'POST', body: { email, password } }),
        logout: () => request('/api/auth/logout', { method: 'POST' }),
        me: () => request('/api/auth/me'),
        updateMe: (data) => request('/api/auth/me', { method: 'PUT', body: data }),
        changePassword: (current_password, new_password) =>
            request('/api/auth/password', { method: 'PUT', body: { current_password, new_password } }),
        deleteAccount: (password) =>
            request('/api/auth/me', { method: 'DELETE', body: { password } }),
        updatePrefs: (exotic_factor) =>
            request('/api/auth/preferences', { method: 'POST', body: { exotic_factor } }),
        spotifyLoginUrl: '/api/auth/spotify/login',
        spotifyDisconnect: () => request('/api/auth/spotify/disconnect', { method: 'POST' }),

        // Tracks
        listTracks: (q = '', limit = 50) =>
            request(`/api/tracks?q=${encodeURIComponent(q)}&limit=${limit}`),
        interact: (trackId, action) =>
            request(`/api/tracks/${trackId}/interact`, { method: 'POST', body: { action } }),
        likedTracks: () => request('/api/tracks/liked'),
        unlike: (trackId) => request(`/api/tracks/${trackId}/like`, { method: 'DELETE' }),
        genres: () => request('/api/tracks/genres'),

        // Recommendations
        recommendations: (n = 3) => request(`/api/recommendations?n=${n}`),
        explainTaste: () => request('/api/recommendations/explain'),

        // Playlists - CRUD
        playlists: () => request('/api/playlists'),
        getPlaylist: (id) => request(`/api/playlists/${id}`),
        createPlaylist: (name, description = '', cover_url = null) =>
            request('/api/playlists', { method: 'POST', body: { name, description, cover_url } }),
        updatePlaylist: (id, data) =>
            request(`/api/playlists/${id}`, { method: 'PUT', body: data }),
        deletePlaylist: (id) =>
            request(`/api/playlists/${id}`, { method: 'DELETE' }),
        addTrackToPlaylist: (playlistId, trackId) =>
            request(`/api/playlists/${playlistId}/tracks`, { method: 'POST', body: { track_id: trackId } }),
        removeTrackFromPlaylist: (playlistId, trackId) =>
            request(`/api/playlists/${playlistId}/tracks/${trackId}`, { method: 'DELETE' }),
        exportPlaylist: (id) =>
            request(`/api/playlists/${id}/export`, { method: 'POST' }),
    };

    // Utils
    API.requireAuth = async function () {
        try { return await API.me(); }
        catch (e) {
            if (e.status === 401) {
                window.location.href = '/login.html';
            }
            throw e;
        }
    };

    API.toast = function (msg, type = 'info') {
        let bar = document.getElementById('app-toast');
        if (!bar) {
            bar = document.createElement('div');
            bar.id = 'app-toast';
            bar.style.cssText = `
                position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
                background: rgba(20,20,30,0.95); color: #f8fafc; padding: 14px 24px;
                border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,.5);
                z-index: 9999; font-weight: 500; border: 1px solid rgba(99,102,241,0.4);
                transition: opacity .3s, transform .3s; opacity: 0;
            `;
            document.body.appendChild(bar);
        }
        bar.textContent = msg;
        bar.style.borderColor = type === 'error' ? '#ef4444' : type === 'success' ? '#22c55e' : 'rgba(99,102,241,0.4)';
        bar.style.opacity = '1';
        bar.style.transform = 'translateX(-50%) translateY(0)';
        clearTimeout(bar._t);
        bar._t = setTimeout(() => { bar.style.opacity = '0'; }, 3000);
    };

    window.API = API;
})();
