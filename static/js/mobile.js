
(function () {
    'use strict';

    const isMobile = /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|WPDesktop/i.test(
        navigator.userAgent
    );
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

    /* 1. SAFE AREA iOS */
    if (isIOS) {
        document.documentElement.style.setProperty('--safe-area-top', 'env(safe-area-inset-top, 0px)');
        document.documentElement.style.setProperty('--safe-area-bottom', 'env(safe-area-inset-bottom, 0px)');
    }

    /* 2. FIX 100VH */
    function fixVH() {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }

    if (isMobile) {
        fixVH();
        window.addEventListener('resize', fixVH, { passive: true });
        window.addEventListener('orientationchange', () => setTimeout(fixVH, 100));
    }

    /* 3. FEEDBACK DE TOQUE */
    if (isMobile) {
        document.addEventListener('touchstart', function (e) {
            const target = e.target.closest(
                '.card, .market-card, .btn, .list-group-item, .conversation-item, .category-card'
            );
            if (target) {
                target.style.transition = 'transform 0.1s ease';
                target.style.transform = 'scale(0.98)';
            }
        }, { passive: true });

        document.addEventListener('touchend', function (e) {
            const target = e.target.closest(
                '.card, .market-card, .btn, .list-group-item, .conversation-item, .category-card'
            );
            if (target) target.style.transform = '';
        }, { passive: true });
    }

    /* 4. PREVENIR ZOOM DUPLO TOQUE iOS */
    if (isIOS) {
        let lastTouchEnd = 0;
        document.addEventListener('touchend', function (event) {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) event.preventDefault();
            lastTouchEnd = now;
        }, { passive: false });
    }

    /* 5. SCROLL SUAVE ÂNCORAS */
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href && href !== '#') {
                const target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });

    /* 6. LAZY LOADING IMAGENS */
    if ('loading' in HTMLImageElement.prototype) {
        document.querySelectorAll('img:not([loading])').forEach((img) => {
            img.setAttribute('loading', 'lazy');
            img.setAttribute('decoding', 'async');
        });
    }

    /* 7. AUTO-CLOSE DE ALERTS */
    document.querySelectorAll('.alert-dismissible').forEach((alert) => {
        setTimeout(() => {
            if (alert && alert.parentNode) {
                alert.style.transition = 'opacity 0.4s ease';
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 400);
            }
        }, 5000);
    });

    console.log('✅ Mobile optimizations carregadas', { isMobile, isIOS });
})();