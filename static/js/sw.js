// Service worker do HiringScope: recebe as notificações push e abre o site ao clicar.
// Não guarda páginas em cache; o site continua carregando sempre do servidor.

self.addEventListener('install', function () {
    self.skipWaiting();
});

self.addEventListener('activate', function (event) {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function (event) {
    var dados = {};
    try { dados = event.data ? event.data.json() : {}; } catch (e) { /* notificação sem conteúdo legível */ }

    var opcoes = {
        body: dados.corpo || '',
        icon: '/static/img/icon-192.png',
        badge: '/static/img/favicon.png',
        data: { url: dados.url || '/' }
    };
    // Mensagens da mesma conversa substituem a notificação anterior em vez de empilhar
    if (dados.tag) {
        opcoes.tag = dados.tag;
        opcoes.renotify = true;
    }

    event.waitUntil(self.registration.showNotification(dados.titulo || 'HiringScope', opcoes));
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var destino = new URL((event.notification.data && event.notification.data.url) || '/', self.location.origin);
    // Só abre páginas do próprio site
    if (destino.origin !== self.location.origin) destino = new URL('/', self.location.origin);
    destino = destino.href;

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (janelas) {
            // Se o site já está aberto em alguma aba, usa ela; senão abre uma nova
            for (var i = 0; i < janelas.length; i++) {
                var janela = janelas[i];
                if ('focus' in janela) {
                    if ('navigate' in janela) janela.navigate(destino);
                    return janela.focus();
                }
            }
            return self.clients.openWindow(destino);
        })
    );
});
