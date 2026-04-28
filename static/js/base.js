// ============================================
// BASE.JS - Versão Corrigida
// ============================================

// Variáveis globais
let globalSocket = null;
let notificationCount = 0;

// ============================================
// INICIALIZAÇÃO PRINCIPAL
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ DOM carregado - Inicializando sistema');
    initLoader();
    initSearch();
    initSocket();
    initNotifications();
    initImages();
});

// ============================================
// LOADER
// ============================================

function initLoader() {
    console.log('📌 Inicializando loader...');
    
    function hideLoader() {
        const loader = document.getElementById('loader');
        if (loader) {
            loader.style.transition = 'opacity 0.5s ease';
            loader.style.opacity = '0';
            setTimeout(function() {
                loader.style.display = 'none';
                console.log('✅ Loader ocultado');
            }, 500);
        }
    }
    
    // Esconde o loader após 1.5 segundos
    setTimeout(hideLoader, 1500);
}

// ============================================
// BUSCA - CORRIGIDA
// ============================================

function initSearch() {
    console.log('📌 Inicializando sistema de busca...');
    
    function performSearch() {
        const desktopInput = document.getElementById('globalSearchInput');
        const mobileInput = document.getElementById('globalSearchInputMobile');
        let query = '';
        
        if (desktopInput) {
            query = desktopInput.value.trim();
        }
        
        if (!query && mobileInput) {
            query = mobileInput.value.trim();
        }
        
        console.log('🔍 Buscando por:', query || '(vazio)');
        
        // CORRIGIDO: Usar a rota correta do blueprint
        if (query) {
            window.location.href = "/servico/lista?q=" + encodeURIComponent(query);
        } else {
            window.location.href = "/servico/lista";
        }
    }
    
    // Busca Desktop
    const btnDesktop = document.getElementById('globalSearchBtn');
    const inputDesktop = document.getElementById('globalSearchInput');
    
    if (btnDesktop) {
        btnDesktop.addEventListener('click', performSearch);
        console.log('✅ Botão busca desktop configurado');
    } else {
        console.log('⚠️ Botão busca desktop não encontrado');
    }
    
    if (inputDesktop) {
        inputDesktop.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });
        console.log('✅ Input busca desktop configurado');
    }
    
    // Busca Mobile
    const btnMobile = document.getElementById('globalSearchBtnMobile');
    const inputMobile = document.getElementById('globalSearchInputMobile');
    
    if (btnMobile) {
        btnMobile.addEventListener('click', performSearch);
        console.log('✅ Botão busca mobile configurado');
    } else {
        console.log('⚠️ Botão busca mobile não encontrado');
    }
    
    if (inputMobile) {
        inputMobile.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });
        console.log('✅ Input busca mobile configurado');
    }
}

// ============================================
// SOCKET.IO - CHAT E NOTIFICAÇÕES
// ============================================

function initSocket() {
    // Verifica se o usuário está logado
    if (typeof currentUserId !== 'undefined' && currentUserId && currentUserId !== 'null') {
        console.log('📌 Inicializando Socket.IO para usuário:', currentUserId);
        
        try {
            socket = io();
            
            socket.on('connect', function() {
                console.log('✅ Socket.IO conectado');
                socket.emit('join', { user_id: currentUserId });
                console.log('📢 Usuário entrou na sala:', currentUserId);
            });
            
            socket.on('connect_error', function(err) {
                console.log('❌ Erro de conexão Socket.IO:', err);
            });
            
            socket.on('new_private_message', function(data) {
                console.log('📨 Nova mensagem:', data);
                if (!data) return;
                notificationCount++;
                updateNotificationBadges();
                addNotificationToList(data);
                showToast(data.remetente_nome, data.conteudo, 'primary');
            });
            
            socket.on('notification', function(data) {
                console.log('🔔 Notificação:', data);
                if (!data) return;
                showToast(data.titulo, data.mensagem, 'success');
                addSystemNotificationToList(data);
            });
            
            // Eventos de contrato
            socket.on('nova_solicitacao', function(data) {
                console.log('📢 Nova solicitação:', data);
                if (!data) return;
                showToast('Nova Solicitação!', `${data.cliente_nome} solicitou: ${data.servico_titulo}`, 'info');
                addSimpleNotification(data.cliente_nome, `Solicitou o serviço: ${data.servico_titulo}`);
                updateUnreadCount();
            });
            
            socket.on('contrato_aceito', function(data) {
                console.log('✅ Serviço aceito:', data);
                if (!data) return;
                showToast('Serviço Aceito!', `${data.prestador_nome} aceitou: ${data.servico_titulo}`, 'success');
                addSimpleNotification(data.prestador_nome, `Aceitou o serviço: ${data.servico_titulo}`);
                updateUnreadCount();
            });
            
            socket.on('servico_concluido', function(data) {
                console.log('🎉 Serviço concluído:', data);
                if (!data) return;
                showToast('Serviço Concluído!', `${data.prestador_nome} finalizou: ${data.servico_titulo}. Avalie agora!`, 'success');
                addSimpleNotification(data.prestador_nome, `Concluiu o serviço: ${data.servico_titulo}`);
                updateUnreadCount();
            });
            
            socket.on('nova_avaliacao', function(data) {
                console.log('⭐ Nova avaliação:', data);
                if (!data) return;
                showToast('Nova Avaliação!', `${data.cliente_nome} te avaliou com ${data.nota} estrelas!`, 'warning');
                addSimpleNotification(data.cliente_nome, `⭐ Avaliação: ${data.nota}/5`);
                updateUnreadCount();
            });
            
        } catch (error) {
            console.error('❌ Erro ao inicializar Socket.IO:', error);
        }
    } else {
        console.log('ℹ️ Usuário não logado, Socket.IO não inicializado');
    }
}

// ============================================
// NOTIFICAÇÕES
// ============================================

function initNotifications() {
    console.log('📌 Inicializando sistema de notificações...');
    
    if (typeof currentUserId !== 'undefined' && currentUserId && currentUserId !== 'null') {
        setInterval(updateUnreadCount, 10000);
        setTimeout(updateUnreadCount, 1000);
    }
}

function updateNotificationBadges() {
    const chatBadge = document.getElementById('chatNotificationBadge');
    const notifBadge = document.getElementById('notificationBadge');
    
    if (notificationCount > 0) {
        if (chatBadge) {
            chatBadge.style.display = 'inline';
            chatBadge.textContent = notificationCount;
        }
        if (notifBadge) {
            notifBadge.style.display = 'inline';
            notifBadge.textContent = notificationCount;
        }
    } else {
        if (chatBadge) chatBadge.style.display = 'none';
        if (notifBadge) notifBadge.style.display = 'none';
    }
}

async function updateUnreadCount() {
    if (typeof currentUserId === 'undefined' || !currentUserId || currentUserId === 'null') return;
    
    try {
        const response = await fetch('/chat/nao-lidas');
        const data = await response.json();
        console.log('📊 Atualizando badge:', data);
        
        if (data && data.count !== undefined) {
            notificationCount = data.count;
            updateNotificationBadges();
            
            // 🔥 ATUALIZAR TAMBÉM O BADGE NA LISTA DE CONVERSAS
            atualizarBadgesConversas();
        }
    } catch (error) {
        console.error('Erro ao buscar não lidas:', error);
    }
}

// Função para atualizar badges na lista de conversas
function atualizarBadgesConversas() {
    // Buscar mensagens não lidas por conversa
    fetch('/chat/nao-lidas-por-conversa')
        .then(res => res.json())
        .then(data => {
            if (data && data.conversas) {
                for (const [usuarioId, count] of Object.entries(data.conversas)) {
                    const badgeElement = document.getElementById(`badge-${usuarioId}`);
                    if (badgeElement) {
                        if (count > 0) {
                            badgeElement.style.display = 'inline';
                            badgeElement.textContent = count;
                        } else {
                            badgeElement.style.display = 'none';
                        }
                    }
                }
            }
        })
        .catch(err => console.error('Erro ao buscar badges:', err));
}

function addNotificationToList(data) {
    const notifList = document.getElementById('notificationList');
    if (!notifList) return;
    
    const emptyMsg = notifList.querySelector('.text-muted');
    if (emptyMsg && emptyMsg.parentNode) emptyMsg.remove();
    
    const notifItem = document.createElement('div');
    notifItem.className = 'notification-item unread p-3 border-bottom';
    notifItem.style.cursor = 'pointer';
    notifItem.onclick = function() { window.location.href = '/chat'; };
    
    const time = new Date().toLocaleTimeString();
    
    notifItem.innerHTML = `
        <div class="d-flex gap-2">
            <i class="fas fa-envelope text-primary mt-1"></i>
            <div class="flex-grow-1">
                <strong>${escapeHtml(data.remetente_nome || 'Alguém')}</strong>
                <p class="mb-0 small">${escapeHtml(data.conteudo?.substring(0, 50) || 'Nova mensagem')}</p>
                <small class="text-muted">${time}</small>
            </div>
        </div>
    `;
    
    notifList.insertBefore(notifItem, notifList.firstChild);
}

function addSystemNotificationToList(data) {
    const notifList = document.getElementById('notificationList');
    if (!notifList) return;
    
    const emptyMsg = notifList.querySelector('.text-muted');
    if (emptyMsg && emptyMsg.parentNode) emptyMsg.remove();
    
    const notifItem = document.createElement('div');
    notifItem.className = 'notification-item p-3 border-bottom';
    notifItem.innerHTML = `
        <div class="d-flex gap-2">
            <i class="fas fa-bell text-success mt-1"></i>
            <div class="flex-grow-1">
                <strong>${escapeHtml(data.titulo || 'Sistema')}</strong>
                <p class="mb-0 small">${escapeHtml(data.mensagem?.substring(0, 60) || '')}</p>
                <small class="text-muted">Agora</small>
            </div>
        </div>
    `;
    
    notifList.insertBefore(notifItem, notifList.firstChild);
}

function addSimpleNotification(nome, mensagem) {
    const notifList = document.getElementById('notificationList');
    if (!notifList) return;
    
    const emptyMsg = notifList.querySelector('.text-muted');
    if (emptyMsg && emptyMsg.parentNode) emptyMsg.remove();
    
    const notifItem = document.createElement('div');
    notifItem.className = 'notification-item p-3 border-bottom';
    notifItem.style.cursor = 'pointer';
    notifItem.onclick = function() { window.location.href = '/chat'; };
    
    notifItem.innerHTML = `
        <div class="d-flex gap-2">
            <i class="fas fa-bell text-info mt-1"></i>
            <div class="flex-grow-1">
                <strong>${escapeHtml(nome)}</strong>
                <p class="mb-0 small">${escapeHtml(mensagem)}</p>
                <small class="text-muted">Agora</small>
            </div>
        </div>
    `;
    
    notifList.insertBefore(notifItem, notifList.firstChild);
}

// ============================================
// TOASTS
// ============================================

function showToast(title, message, type = 'primary') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const id = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.className = 'toast show';
    toast.id = id;
    
    let bgColor = 'bg-primary';
    let icon = 'envelope';
    if (type === 'success') { bgColor = 'bg-success'; icon = 'check-circle'; }
    else if (type === 'warning') { bgColor = 'bg-warning'; icon = 'star'; }
    else if (type === 'info') { bgColor = 'bg-info'; icon = 'info-circle'; }
    else if (type === 'danger') { bgColor = 'bg-danger'; icon = 'exclamation-circle'; }
    
    toast.innerHTML = `
        <div class="toast-header ${bgColor} text-white">
            <i class="fas fa-${icon} me-2"></i>
            <strong class="me-auto">${escapeHtml(title)}</strong>
            <small>agora</small>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">${escapeHtml(message)}</div>
    `;
    
    container.appendChild(toast);
    setTimeout(function() {
        const el = document.getElementById(id);
        if (el) el.remove();
    }, 5000);
}

// ============================================
// UTILITÁRIOS
// ============================================

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function initImages() {
    const images = document.querySelectorAll('img[src*="uploads/"], img[src*="data:image"]');
    images.forEach(function(img) {
        img.onerror = function() {
            this.style.display = 'none';
            const placeholder = this.parentNode?.querySelector('.user-avatar-nav-placeholder');
            if (placeholder) placeholder.style.display = 'inline-flex';
        };
    });
}

// ============================================
// FUNÇÕES EXPORTADAS
// ============================================

window.showToast = showToast;
window.updateUnreadCount = updateUnreadCount;
window.escapeHtml = escapeHtml;