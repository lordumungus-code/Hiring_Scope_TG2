// ============================================
// NOTIFICAÇÕES PUSH (usuário logado)
// Registra o service worker, mostra o convite e inscreve o navegador.
// ============================================
(function () {
    'use strict';

    var aviso = document.getElementById('avisoPush');
    if (!aviso) return;
    // Navegador sem suporte (ou iPhone fora do modo "tela de início"): não mostra nada
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;

    var CHAVE = aviso.dataset.chave;
    var ADIAR_DIAS = 7;

    function chaveEmBytes(base64) {
        var texto = atob((base64 + '==='.slice((base64.length + 3) % 4)).replace(/-/g, '+').replace(/_/g, '/'));
        var bytes = new Uint8Array(texto.length);
        for (var i = 0; i < texto.length; i++) bytes[i] = texto.charCodeAt(i);
        return bytes;
    }

    function guardado(chave) {
        try { return localStorage.getItem(chave); } catch (e) { return null; }
    }

    function guardar(chave, valor) {
        try { localStorage.setItem(chave, valor); } catch (e) { /* navegador sem armazenamento local */ }
    }

    async function inscrever(registro) {
        var opcoes = { userVisibleOnly: true, applicationServerKey: chaveEmBytes(CHAVE) };
        var inscricao = await registro.pushManager.getSubscription();
        if (!inscricao) {
            try {
                inscricao = await registro.pushManager.subscribe(opcoes);
            } catch (erro) {
                // Inscrição antiga feita com outra chave do servidor: refaz
                var antiga = await registro.pushManager.getSubscription();
                if (!antiga) throw erro;
                await antiga.unsubscribe();
                inscricao = await registro.pushManager.subscribe(opcoes);
            }
        }
        var resposta = await fetch('/push/inscrever', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(inscricao)
        });
        if (!resposta.ok) throw new Error('O servidor não aceitou a inscrição');
    }

    // Ao sair da conta, este navegador deixa de receber os avisos dela
    function desligarAoSair(registro) {
        document.addEventListener('click', function (evento) {
            var link = evento.target.closest ? evento.target.closest('a[href$="/auth/logout"]') : null;
            if (!link) return;
            evento.preventDefault();

            var seguir = function () { window.location.href = link.href; };
            var limite = setTimeout(seguir, 1500);   // não trava o "Sair" se algo demorar

            registro.pushManager.getSubscription().then(function (inscricao) {
                if (!inscricao) return;
                return fetch('/push/remover', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ endpoint: inscricao.endpoint })
                });
            }).catch(function () {}).then(function () {
                clearTimeout(limite);
                seguir();
            });
        });
    }

    navigator.serviceWorker.register('/sw.js').then(function (registro) {
        desligarAoSair(registro);

        if (Notification.permission === 'granted') {
            // Já autorizado: só garante que o servidor conhece este navegador
            inscrever(registro).catch(function (e) { console.warn('Push:', e); });
            return;
        }
        if (Notification.permission === 'denied') return;

        // Ainda não decidiu: mostra o convite (se não adiou há pouco, e depois do aviso de cookies)
        var adiadoAte = parseInt(guardado('hs_push_adiado') || '0', 10);
        if (Date.now() < adiadoAte) return;
        var avisoCookies = document.getElementById('avisoCookies');
        if (avisoCookies && !avisoCookies.hidden) return;

        aviso.hidden = false;

        document.getElementById('avisoPushDepois').addEventListener('click', function () {
            aviso.hidden = true;
            guardar('hs_push_adiado', String(Date.now() + ADIAR_DIAS * 24 * 3600 * 1000));
        });

        document.getElementById('avisoPushAtivar').addEventListener('click', function () {
            var botao = this;
            var erro = document.getElementById('avisoPushErro');
            botao.disabled = true;
            erro.hidden = true;

            Notification.requestPermission().then(function (permissao) {
                if (permissao !== 'granted') {
                    aviso.hidden = true;
                    return;
                }
                return inscrever(registro).then(function () {
                    aviso.hidden = true;
                    registro.showNotification('Notificações ativadas', {
                        body: 'Você será avisado quando chegar mensagem, proposta ou solicitação.',
                        icon: '/static/img/icon-192.png'
                    });
                });
            }).catch(function (e) {
                console.warn('Push:', e);
                erro.textContent = 'Não foi possível ativar agora. Tente de novo mais tarde.';
                erro.hidden = false;
                botao.disabled = false;
            });
        });
    }).catch(function (e) {
        console.warn('Service worker não registrado:', e);
    });
})();
