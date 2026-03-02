/* ============================================================
   PORTFOLIO — SAR High-Vis Field Gear Theme
   Shared JavaScript: GSAP animations, cursor, nav, status pill
   ============================================================ */

// ─── Wait for DOM ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

  // ── Guard: if GSAP didn't load (CDN failure) skip animations ─
  if (typeof gsap === 'undefined') return;

  // ── Register GSAP plugins ───────────────────────────────────
  gsap.registerPlugin(ScrollTrigger, Flip);

  // ── Initialise Lucide icons ─────────────────────────────────
  if (window.lucide) lucide.createIcons();

  // ─────────────────────────────────────────────────────────────
  // 1. CUSTOM CURSOR
  // ─────────────────────────────────────────────────────────────
  const cursor = document.getElementById('cursor-blob');
  if (cursor) {
    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;
    let curX = mouseX;
    let curY = mouseY;

    window.addEventListener('mousemove', e => {
      mouseX = e.clientX;
      mouseY = e.clientY;
    });

    // Lag follow using GSAP ticker
    gsap.ticker.add(() => {
      curX += (mouseX - curX) * 0.18;
      curY += (mouseY - curY) * 0.18;
      gsap.set(cursor, { x: curX, y: curY });
    });

    // Grow + colour shift on interactive elements
    const interactives = 'a, button, .card, .skill-card, .academic-card, .interest-tag, .nav-link, .status-option';
    document.querySelectorAll(interactives).forEach(el => {
      el.addEventListener('mouseenter', () => cursor.classList.add('hovered'));
      el.addEventListener('mouseleave', () => cursor.classList.remove('hovered'));
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 2. SVG BACKGROUND GRID
  // ─────────────────────────────────────────────────────────────
  const bgGrid = document.getElementById('bg-grid');
  if (bgGrid) {
    // Subtle warp on scroll using GSAP
    gsap.to(bgGrid, {
      attr: { viewBox: '-20 -20 120 120' },
      ease: 'sine.inOut',
      duration: 8,
      repeat: -1,
      yoyo: true,
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 3. FLOATING BOTTOM NAV — spring entrance
  // ─────────────────────────────────────────────────────────────
  const nav = document.getElementById('bottom-nav');
  if (nav) {
    gsap.to(nav, {
      y: 0,
      duration: 0.9,
      ease: 'elastic.out(1, 0.55)',
      delay: 0.3,
      clearProps: 'y',
    });

    // Mark active nav link
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('.nav-link').forEach(link => {
      const href = link.getAttribute('href');
      if (
        href === currentPage ||
        (currentPage === '' && href === 'index.html') ||
        (currentPage === '/' && href === 'index.html')
      ) {
        link.classList.add('active');
      }
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 4. PAGE TRANSITION
  // ─────────────────────────────────────────────────────────────
  const pageContent = document.getElementById('page-content');

  // Spring entrance
  if (pageContent) {
    gsap.from(pageContent, {
      scale: 1.05,
      opacity: 0,
      duration: 0.6,
      ease: 'elastic.out(1, 0.6)',
    });
  }

  // Shrink+fade on nav click before navigating
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
      const href = link.getAttribute('href');
      // Only intercept if navigating to a different page
      const currentPage = window.location.pathname.split('/').pop() || 'index.html';
      if (href === currentPage) return;

      e.preventDefault();
      if (pageContent) {
        gsap.to(pageContent, {
          scale: 0.95,
          opacity: 0,
          duration: 0.25,
          ease: 'power2.in',
          onComplete: () => { window.location.href = href; },
        });
      } else {
        window.location.href = href;
      }
    });
  });

  // ─────────────────────────────────────────────────────────────
  // 5. ANTI-GRID — random rotations for .card and .skill-card
  // ─────────────────────────────────────────────────────────────
  document.querySelectorAll('.card, .skill-card').forEach(card => {
    const rot = (Math.random() * 6) - 3; // -3 to +3 degrees
    card.style.setProperty('--card-rot', `${rot}deg`);
    card.style.transform = `rotate(${rot}deg)`;
    // Store rotation for 3D tilt reset (avoids re-parsing transform later)
    card.dataset.baseRot = rot;
  });

  // ─────────────────────────────────────────────────────────────
  // 6. STATUS PILL (index.html only)
  // ─────────────────────────────────────────────────────────────
  const statusPill = document.getElementById('status-pill');
  const statusText = document.getElementById('status-text');
  const statusGearBtn = document.getElementById('status-gear-btn');
  const statusDropdown = document.getElementById('status-dropdown');

  if (statusPill && statusText) {
    const statuses = [
      { label: '🏔️ Probably Outside', color: 'var(--sar-orange)' },
      { label: '📚 Studying',          color: 'var(--cobalt-blue)' },
      { label: '📡 On Air (HAM)',       color: 'var(--electric-green)' },
      { label: '🔴 In the Field',       color: 'var(--emergency-red)' },
      { label: '💤 AFK',               color: '#333' },
    ];

    // Two cycling statuses (default)
    const cycleStatuses = [statuses[0], statuses[1]];
    let cycleIdx = 0;
    let cycleTimer = null;

    const applyStatus = ({ label, color }) => {
      gsap.to(statusText, {
        opacity: 0,
        duration: 0.2,
        onComplete: () => {
          statusText.textContent = label;
          statusPill.style.background = color;
          // Use dark text on bright/light backgrounds, light text on dark ones
          const darkBg = color === 'var(--cobalt-blue)' || color === 'var(--emergency-red)' || color === '#333';
          statusPill.style.color = darkBg ? 'var(--chalk-white)' : 'var(--off-black)';
          gsap.to(statusText, { opacity: 1, duration: 0.2 });
        },
      });
    };

    const startCycle = () => {
      cycleTimer = setInterval(() => {
        cycleIdx = (cycleIdx + 1) % cycleStatuses.length;
        applyStatus(cycleStatuses[cycleIdx]);
      }, 4000);
    };

    const stopCycle = () => {
      clearInterval(cycleTimer);
      cycleTimer = null;
    };

    // Check localStorage for override
    const savedStatus = localStorage.getItem('hamo-status');
    if (savedStatus) {
      const found = statuses.find(s => s.label === savedStatus);
      if (found) {
        applyStatus(found);
        // Don't start cycling — override is in effect
      } else {
        applyStatus(cycleStatuses[0]);
        startCycle();
      }
    } else {
      applyStatus(cycleStatuses[0]);
      startCycle();
    }

    // Gear button toggles dropdown
    if (statusGearBtn && statusDropdown) {
      statusGearBtn.addEventListener('click', e => {
        e.stopPropagation();
        statusDropdown.classList.toggle('open');
      });

      // Dropdown option selection
      statusDropdown.querySelectorAll('.status-option').forEach(opt => {
        opt.addEventListener('click', () => {
          const label = opt.dataset.label;
          const found = statuses.find(s => s.label === label);
          if (!found) return;

          if (label === 'clear') {
            localStorage.removeItem('hamo-status');
            stopCycle();
            cycleIdx = 0;
            applyStatus(cycleStatuses[0]);
            startCycle();
          } else {
            localStorage.setItem('hamo-status', label);
            stopCycle();
            applyStatus(found);
          }

          // Update active styling
          statusDropdown.querySelectorAll('.status-option').forEach(o => o.classList.remove('active'));
          opt.classList.add('active');

          statusDropdown.classList.remove('open');
        });
      });

      // Close dropdown on outside click
      document.addEventListener('click', () => {
        statusDropdown.classList.remove('open');
      });

      // Restore active class from storage
      if (savedStatus) {
        const activeOpt = statusDropdown.querySelector(`[data-label="${savedStatus}"]`);
        if (activeOpt) activeOpt.classList.add('active');
      }
    }
  }

  // ─────────────────────────────────────────────────────────────
  // 7. HERO HEADLINE — staggered letter bounce (index.html)
  // ─────────────────────────────────────────────────────────────
  const heroHeadline = document.querySelector('.hero-headline');
  if (heroHeadline) {
    const text = heroHeadline.textContent;
    heroHeadline.innerHTML = text
      .split('')
      .map(char => `<span class="char">${char === ' ' ? '&nbsp;' : char}</span>`)
      .join('');

    gsap.from('.hero-headline .char', {
      y: 80,
      opacity: 0,
      scale: 0.5,
      duration: 0.6,
      ease: 'elastic.out(1, 0.5)',
      stagger: 0.035,
      delay: 0.1,
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 8. HERO ICON float loop
  // ─────────────────────────────────────────────────────────────
  const heroIcon = document.querySelector('.hero-icon-wrap svg');
  if (heroIcon) {
    gsap.to(heroIcon, {
      y: -18,
      duration: 2.8,
      ease: 'sine.inOut',
      repeat: -1,
      yoyo: true,
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 9. INTEREST TAG drift/bob loops
  // ─────────────────────────────────────────────────────────────
  document.querySelectorAll('.interest-tag').forEach(tag => {
    const yAmt = 6 + Math.random() * 8;
    const dur  = 2.0 + Math.random() * 2.0;
    const delay = Math.random() * 1.5;

    gsap.to(tag, {
      y: -yAmt,
      duration: dur,
      ease: 'sine.inOut',
      repeat: -1,
      yoyo: true,
      delay,
    });
  });

  // ─────────────────────────────────────────────────────────────
  // 10. SCROLL REVEAL — quals cards fly in
  // ─────────────────────────────────────────────────────────────
  const directions = [
    { x: -160, y: 0 },
    { x:  160, y: 0 },
    { x: 0,   y: -120 },
    { x: 0,   y:  120 },
  ];

  document.querySelectorAll('.card').forEach((card, i) => {
    const dir = directions[i % directions.length];
    gsap.from(card, {
      scrollTrigger: {
        trigger: card,
        start: 'top 90%',
      },
      x: dir.x,
      y: dir.y,
      opacity: 0,
      rotation: (Math.random() * 12) - 6,
      duration: 0.6,
      ease: 'elastic.out(1, 0.5)',
    });
  });

  // ─────────────────────────────────────────────────────────────
  // 11. SCROLL REVEAL — skill cards
  // ─────────────────────────────────────────────────────────────
  document.querySelectorAll('.skill-card').forEach((card, i) => {
    const dir = directions[i % directions.length];
    gsap.from(card, {
      scrollTrigger: {
        trigger: card,
        start: 'top 90%',
      },
      x: dir.x,
      y: dir.y,
      opacity: 0,
      duration: 0.6,
      ease: 'elastic.out(1, 0.5)',
    });
  });

  // ─────────────────────────────────────────────────────────────
  // 12. SCROLL REVEAL — academic cards slide up
  // ─────────────────────────────────────────────────────────────
  document.querySelectorAll('.academic-card').forEach((card) => {
    gsap.from(card, {
      scrollTrigger: {
        trigger: card,
        start: 'top 88%',
      },
      y: 60,
      opacity: 0,
      duration: 0.55,
      ease: 'elastic.out(1, 0.5)',
    });
  });

  // ─────────────────────────────────────────────────────────────
  // 13. 3D TILT on skill cards
  // ─────────────────────────────────────────────────────────────
  document.querySelectorAll('.skill-card').forEach(card => {
    card.addEventListener('mousemove', e => {
      const rect = card.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top  + rect.height / 2;
      const dx = (e.clientX - cx) / (rect.width  / 2);
      const dy = (e.clientY - cy) / (rect.height / 2);

      const rotX = -dy * 12;
      const rotY =  dx * 12;
      const baseRot = parseFloat(card.dataset.baseRot || 0);

      gsap.to(card, {
        rotateX: rotX,
        rotateY: rotY,
        duration: 0.3,
        ease: 'power2.out',
        transformPerspective: 800,
        overwrite: true,
      });
    });

    card.addEventListener('mouseleave', () => {
      const baseRot = parseFloat(card.dataset.baseRot || 0);
      gsap.to(card, {
        rotateX: 0,
        rotateY: 0,
        rotate: baseRot,
        duration: 0.5,
        ease: 'elastic.out(1, 0.5)',
        transformPerspective: 800,
        overwrite: true,
      });
    });
  });

}); // end DOMContentLoaded
