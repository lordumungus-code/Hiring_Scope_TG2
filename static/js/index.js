function iniciarChat(prestadorId, prestadorNome) {
    if (prestadorId) {
        sessionStorage.setItem('chat_with_id', prestadorId);
        sessionStorage.setItem('chat_with_name', prestadorNome);
        window.location.href = "/chat";
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const usuarioId = urlParams.get('usuario');

    if (usuarioId) {
        sessionStorage.setItem('chat_with_id', usuarioId);
        window.location.href = "/chat";
    }

    const cards = document.querySelectorAll(
        '.featured-card, .category-card, .recent-card, .testimonial-card, .stat-card, .top-prestador-card'
    );

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1 });

    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'all 0.5s ease';
        observer.observe(card);
    });
});