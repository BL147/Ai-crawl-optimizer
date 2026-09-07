/* CineStream Platform Interactive Demo Logic */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Sticky Nav Transition
  const navbar = document.querySelector('.navbar');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  });

  // 2. Interactive Toast for Demo Experience
  const toast = document.getElementById('demo-toast');
  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.style.display = 'block';
    setTimeout(() => {
      toast.style.display = 'none';
    }, 2800);
  }

  // 3. Card click event
  document.querySelectorAll('.media-card').forEach(card => {
    card.addEventListener('click', () => {
      const title = card.querySelector('.card-title')?.textContent || 'Stream Title';
      showToast(`Selected: "${title}" (Live Demo Simulation)`);
    });
  });

  // 4. Hero Button Actions
  const playBtn = document.getElementById('hero-play');
  if (playBtn) {
    playBtn.addEventListener('click', () => {
      showToast('Starting 4K Stream: "Shadow Protocol: Genesis"');
    });
  }

  const infoBtn = document.getElementById('hero-info');
  if (infoBtn) {
    infoBtn.addEventListener('click', () => {
      showToast('Metadata loaded: 4K HDR • 5.1 Surround • Sci-Fi Thriller');
    });
  }

  const signinBtn = document.querySelector('.btn-signin');
  if (signinBtn) {
    signinBtn.addEventListener('click', (e) => {
      e.preventDefault();
      showToast('Sign In: Demo authentication active');
    });
  }
});
