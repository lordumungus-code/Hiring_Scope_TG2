// ============================================
// FOTOS DO SERVIÇO (cadastro e edição)
// Seleção de várias fotos com miniaturas, remoção individual
// e redução no navegador antes do envio.
// ============================================

function initFotosServico(opcoes) {
    const input = document.getElementById(opcoes.inputId);
    const grade = document.getElementById(opcoes.previewId);
    const contador = document.getElementById(opcoes.contadorId);
    if (!input || !grade) return;

    const LADO_MAXIMO = 1280;
    let arquivos = [];

    // Quantas fotos novas ainda cabem (na edição, depende das que já existem e das marcadas para remover)
    function limite() {
        return typeof opcoes.limite === 'function' ? opcoes.limite() : opcoes.limite;
    }

    // Reduz a foto no navegador: envio mais rápido e sem estourar o tamanho máximo
    function reduzir(arquivo) {
        return new Promise(function(resolve) {
            const img = new Image();
            const url = URL.createObjectURL(arquivo);
            img.onload = function() {
                URL.revokeObjectURL(url);
                const escala = Math.min(1, LADO_MAXIMO / Math.max(img.width, img.height));
                const canvas = document.createElement('canvas');
                canvas.width = Math.round(img.width * escala);
                canvas.height = Math.round(img.height * escala);
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                canvas.toBlob(function(blob) {
                    if (!blob) return resolve(arquivo);
                    const nome = arquivo.name.replace(/\.[^.]+$/, '') + '.jpg';
                    resolve(new File([blob], nome, { type: 'image/jpeg' }));
                }, 'image/jpeg', 0.85);
            };
            // Formato que o navegador não consegue abrir: envia como está e o servidor decide
            img.onerror = function() {
                URL.revokeObjectURL(url);
                resolve(arquivo);
            };
            img.src = url;
        });
    }

    function sincronizar() {
        const dt = new DataTransfer();
        arquivos.forEach(function(a) { dt.items.add(a); });
        input.files = dt.files;
    }

    function desenhar() {
        grade.innerHTML = '';
        arquivos.forEach(function(arquivo, i) {
            const item = document.createElement('div');
            item.className = 'foto-item';

            const img = document.createElement('img');
            img.src = URL.createObjectURL(arquivo);
            img.alt = 'Foto ' + (i + 1);
            item.appendChild(img);

            if (i === 0 && opcoes.primeiraECapa) {
                const selo = document.createElement('span');
                selo.className = 'foto-selo';
                selo.textContent = 'Capa';
                item.appendChild(selo);
            }

            const remover = document.createElement('button');
            remover.type = 'button';
            remover.className = 'foto-remover';
            remover.title = 'Remover foto';
            remover.innerHTML = '<i class="fas fa-times"></i>';
            remover.addEventListener('click', function() {
                arquivos.splice(i, 1);
                sincronizar();
                desenhar();
            });
            item.appendChild(remover);

            grade.appendChild(item);
        });

        grade.style.display = arquivos.length ? 'grid' : 'none';
        if (contador) {
            contador.textContent = arquivos.length
                ? arquivos.length + ' foto(s) selecionada(s)'
                : 'Nenhuma foto escolhida';
        }
    }

    input.addEventListener('change', async function() {
        const escolhidos = Array.from(input.files).filter(function(a) {
            return a.type.startsWith('image/');
        });
        const vagas = Math.max(0, limite() - arquivos.length);

        if (escolhidos.length > vagas) {
            alert('Você pode ter no máximo ' + opcoes.maxFotos + ' fotos por serviço.');
        }

        if (contador) contador.textContent = 'Preparando fotos...';
        const reduzidos = await Promise.all(escolhidos.slice(0, vagas).map(reduzir));
        arquivos = arquivos.concat(reduzidos);
        sincronizar();
        desenhar();
    });

    // Na edição: se o limite diminuir (desmarcou uma remoção), corta o excesso
    return {
        ajustarAoLimite: function() {
            if (arquivos.length > limite()) {
                arquivos = arquivos.slice(0, Math.max(0, limite()));
                sincronizar();
                desenhar();
            }
        }
    };
}
