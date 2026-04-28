document.addEventListener('DOMContentLoaded', () => {
    initPlaylists();
});

function initPlaylists() {
    const playlistCards = document.querySelectorAll('.playlist-card');

    playlistCards.forEach(card => {
        const songList = card.querySelector('.song-list');
        const songCountElement = card.querySelector('.song-count');
        
        if (!songList) return;

        const songs = songList.querySelectorAll('.song-item');
        const count = songs.length;

        // Dynamic update of the song count text
        if (songCountElement) {
            songCountElement.textContent = `${count} musique${count > 1 ? 's' : ''}`;
        }
        
        // Dynamic check: more than 3 songs?
        if (count > 3) {
            // Ensure collapsed class is present
            songList.classList.add('collapsed');

            // Check if unfold button already exists, if not create it
            let unfoldBtn = card.querySelector('.unfold-btn');
            if (!unfoldBtn) {
                unfoldBtn = document.createElement('button');
                unfoldBtn.className = 'unfold-btn';
                unfoldBtn.innerHTML = '<i class="fa-solid fa-chevron-down"></i>';
                
                // Append to info container
                const infoContainer = card.querySelector('.playlist-info');
                if (infoContainer) {
                    infoContainer.appendChild(unfoldBtn);
                }
            }

            // (Re)attach event listener
            unfoldBtn.onclick = () => {
                songList.classList.toggle('collapsed');
                unfoldBtn.classList.toggle('active');
                
                const isExpanded = !songList.classList.contains('collapsed');
                unfoldBtn.setAttribute('aria-expanded', isExpanded);
            };
        } else {
            // Remove button if it exists but isn't needed
            const existingBtn = card.querySelector('.unfold-btn');
            if (existingBtn) existingBtn.remove();
            songList.classList.remove('collapsed');
        }
    });
}
