"""Contrato formal de prestação de serviços: texto das cláusulas, selo (hash) e PDF."""
import hashlib
import json
import os
from datetime import datetime, timedelta

from fpdf import FPDF

PRECO_CONTRATO_FORMAL = 4.90
VALIDADE_CODIGO = 10          # minutos
MAX_TENTATIVAS_CODIGO = 5

FORMAS_PAGAMENTO = ['PIX', 'Transferência bancária', 'Dinheiro', 'Cartão de crédito', 'Parcelado', 'A combinar']

# Campos que o prestador preenche (nome do campo -> tamanho máximo)
CAMPOS_TERMOS = {
    'descricao': 3000, 'data_servico': 10, 'hora_inicio': 5, 'prazo': 200, 'local': 300, 'cidade': 120,
    'forma_pagamento': 40, 'venc_saldo': 10, 'observacoes': 3000,
}


def brl(valor):
    """1234.5 -> 'R$ 1.234,50'"""
    texto = f'{float(valor or 0):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {texto}'


def data_br(iso):
    """'2026-10-15' -> '15/10/2026'"""
    try:
        return datetime.strptime(iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return iso or ''


def horario_brasilia(momento):
    """Datas ficam em UTC no banco; no contrato aparecem no horário de Brasília"""
    if not momento:
        return ''
    return (momento - timedelta(hours=3)).strftime('%d/%m/%Y às %H:%M') + ' (horário de Brasília)'


def site_url():
    return (os.environ.get('SITE_URL') or 'https://hiring-scope.com.br').rstrip('/')


def carregar_termos(formal):
    try:
        return json.loads(formal.termos_json) if formal.termos_json else {}
    except ValueError:
        return {}


def termos_iniciais(contrato):
    """Rascunho já preenchido com o que o site sabe sobre o serviço e as partes"""
    servico = contrato.servico
    return {
        'contratante': dados_da_parte(contrato.cliente),
        'contratado': dados_da_parte(contrato.prestador),
        'servico_titulo': servico.titulo,
        'descricao': servico.descricao or '',
        'valor_total': contrato.preco_acordado or servico.preco or 0,
        'entrada': 0,
        'multa': 20,
        'forma_pagamento': 'PIX',
    }


def dados_da_parte(usuario, anteriores=None):
    """Nome, e-mail e telefone vêm do cadastro; CPF e endereço são informados no contrato"""
    anteriores = anteriores or {}
    return {
        'nome': usuario.nome,
        'email': usuario.email,
        'telefone': usuario.telefone or '',
        'doc': anteriores.get('doc', ''),
        'endereco': anteriores.get('endereco', ''),
    }


def pendencias(termos):
    """O que falta o prestador preencher antes de enviar para assinatura"""
    faltando = []
    if not termos.get('contratado', {}).get('doc'):
        faltando.append('seu CPF ou CNPJ')
    if not termos.get('contratado', {}).get('endereco'):
        faltando.append('seu endereço')
    if not (termos.get('descricao') or '').strip():
        faltando.append('descrição do serviço')
    if not termos.get('data_servico'):
        faltando.append('data do serviço')
    if not (termos.get('local') or '').strip():
        faltando.append('local do serviço')
    if not (termos.get('cidade') or '').strip():
        faltando.append('cidade/UF')
    if not termos.get('valor_total') or termos['valor_total'] <= 0:
        faltando.append('valor total')
    return faltando


def montar_clausulas(termos):
    """Texto do contrato, usado tanto na tela quanto no PDF. Lista de (título, [parágrafos])"""
    total = termos.get('valor_total') or 0
    entrada = min(termos.get('entrada') or 0, total)
    saldo = total - entrada
    multa = termos.get('multa') or 0

    quando = f"no dia {data_br(termos.get('data_servico'))}"
    if termos.get('hora_inicio'):
        quando += f", com início às {termos['hora_inicio']}"
    if termos.get('prazo'):
        quando += f". Prazo/duração: {termos['prazo']}"

    pagamento = f"O valor total dos serviços é de {brl(total)}, a ser pago por {termos.get('forma_pagamento') or 'forma a combinar'}."
    if entrada > 0:
        pagamento += f" Será pago um sinal de {brl(entrada)}, e o saldo de {brl(saldo)}"
        pagamento += f" até {data_br(termos['venc_saldo'])}." if termos.get('venc_saldo') else " na conclusão do serviço."
    elif termos.get('venc_saldo'):
        pagamento += f" O pagamento será feito até {data_br(termos['venc_saldo'])}."

    clausulas = [
        ('Cláusula 1ª — Do objeto', [
            f"O(A) CONTRATADO(A) prestará ao CONTRATANTE o serviço \"{termos.get('servico_titulo', '')}\", assim descrito:",
            (termos.get('descricao') or '').strip(),
        ]),
        ('Cláusula 2ª — Do local, data e prazo', [
            f"O serviço será prestado em {termos.get('local', '')}, {termos.get('cidade', '')}, {quando}.",
        ]),
        ('Cláusula 3ª — Do valor e do pagamento', [pagamento]),
        ('Cláusula 4ª — Obrigações do(a) CONTRATADO(A)', [
            "a) Executar o serviço descrito na Cláusula 1ª com zelo e qualidade profissional, no local e prazo combinados;",
            "b) Fornecer as ferramentas e os meios necessários à execução, salvo combinação diferente registrada neste contrato;",
            "c) Zelar pela conservação do local e dos bens do CONTRATANTE durante a execução;",
            "d) Comunicar ao CONTRATANTE, assim que possível, qualquer fato que impeça ou atrase o serviço.",
        ]),
        ('Cláusula 5ª — Obrigações do CONTRATANTE', [
            "a) Efetuar o pagamento na forma e nos prazos da Cláusula 3ª;",
            "b) Dar ao(à) CONTRATADO(A) acesso ao local e as condições necessárias para a execução do serviço;",
            "c) Comunicar qualquer alteração de data, local ou escopo com a maior antecedência possível.",
        ]),
        ('Cláusula 6ª — Do cancelamento', [
            f"A parte que cancelar este contrato sem justo motivo pagará à outra multa de {multa:g}% sobre o valor total."
            if multa > 0 else
            "O cancelamento deste contrato por qualquer das partes não gera multa, devendo ser comunicado com a maior antecedência possível.",
        ]),
    ]

    proxima = 7
    if (termos.get('observacoes') or '').strip():
        clausulas.append((f'Cláusula {proxima}ª — Condições adicionais', [termos['observacoes'].strip()]))
        proxima += 1

    clausulas += [
        (f'Cláusula {proxima}ª — Da plataforma', [
            "Este contrato é firmado diretamente entre CONTRATANTE e CONTRATADO(A). A plataforma HiringScope apenas "
            "disponibiliza o meio eletrônico para sua elaboração, assinatura e guarda, não sendo parte nem responsável "
            "pela execução do serviço ou pelo pagamento.",
        ]),
        (f'Cláusula {proxima + 1}ª — Da assinatura eletrônica', [
            "As partes assinam este contrato eletronicamente, por meio de suas contas na plataforma, confirmadas por "
            "senha pessoal e código enviado ao e-mail cadastrado, e reconhecem este meio como válido para comprovar "
            "autoria e integridade, nos termos do art. 10, § 2º, da Medida Provisória nº 2.200-2/2001 e da Lei nº 14.063/2020. "
            "Ficam registrados data, hora, endereço IP e dispositivo de cada assinatura, e o conteúdo é selado por hash SHA-256.",
        ]),
        (f'Cláusula {proxima + 2}ª — Do foro', [
            f"Fica eleito o foro da comarca de {termos.get('cidade', '')} para resolver questões decorrentes deste contrato.",
        ]),
    ]
    return clausulas


def descricao_da_parte(rotulo, parte):
    texto = f"{rotulo}: {parte.get('nome', '')}"
    texto += f", CPF/CNPJ {parte['doc']}" if parte.get('doc') else ", CPF/CNPJ a informar na assinatura"
    if parte.get('endereco'):
        texto += f", com endereço em {parte['endereco']}"
    if parte.get('telefone'):
        texto += f", telefone {parte['telefone']}"
    texto += f", e-mail {parte.get('email', '')}."
    return texto


def assinaturas(formal):
    """Registro das assinaturas, na ordem em que aparecem no documento"""
    return [
        {'parte': 'CONTRATANTE', 'quando': formal.cliente_assinou_em, 'ip': formal.cliente_ip,
         'dispositivo': formal.cliente_dispositivo},
        {'parte': 'CONTRATADO(A)', 'quando': formal.prestador_assinou_em, 'ip': formal.prestador_ip,
         'dispositivo': formal.prestador_dispositivo},
    ]


def calcular_hash(formal):
    """SHA-256 do conteúdo do contrato + registro das assinaturas.

    Qualquer alteração nos dados guardados muda o resultado; é assim que a verificação detecta adulteração.
    """
    selo = {
        'numero': formal.numero,
        'termos': carregar_termos(formal),
        'assinaturas': [
            {'parte': a['parte'], 'quando': a['quando'].isoformat() if a['quando'] else None,
             'ip': a['ip'], 'dispositivo': a['dispositivo']}
            for a in assinaturas(formal)
        ],
    }
    canonico = json.dumps(selo, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(canonico.encode('utf-8')).hexdigest()


# ============================================
# PDF
# ============================================

def _latin1(texto):
    """As fontes padrão do PDF só têm Latin-1: troca aspas/travessões tipográficos e descarta o resto (emojis)"""
    trocas = {'“': '"', '”': '"', '‘': "'", '’': "'", '–': '-', '—': '-', '…': '...', '•': '-', ' ': ' '}
    for de, para in trocas.items():
        texto = texto.replace(de, para)
    return texto.encode('latin-1', 'ignore').decode('latin-1')


class _PdfContrato(FPDF):
    def __init__(self, formal):
        super().__init__(format='A4')
        self.formal = formal
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(True, margin=30)
        self.alias_nb_pages()

    def header(self):
        self.set_fill_color(11, 43, 92)
        self.rect(0, 0, self.w, 10, 'F')
        self.set_xy(0, 2.5)
        self.set_font('Helvetica', 'B', 8.5)
        self.set_text_color(255, 255, 255)
        rotulo = 'ASSINADO ELETRONICAMENTE' if self.formal.status == 'assinado' else 'AGUARDANDO ASSINATURAS - SEM VALIDADE'
        self.cell(self.w, 5, _latin1(f'HiringScope - Contrato nº {self.formal.numero} - {rotulo}'), align='C')
        self.set_text_color(0, 0, 0)
        self.set_y(18)

    def footer(self):
        self.set_y(-24)
        self.set_draw_color(220, 220, 228)
        self.line(18, self.get_y(), self.w - 18, self.get_y())
        self.ln(2)
        self.set_text_color(90, 90, 90)
        if self.formal.hash_documento:
            self.set_font('Helvetica', '', 7)
            self.cell(0, 3.5, 'Hash SHA-256 do documento:', new_x='LMARGIN', new_y='NEXT')
            self.set_font('Courier', '', 7)
            self.cell(0, 3.5, self.formal.hash_documento, new_x='LMARGIN', new_y='NEXT')
            self.set_font('Helvetica', '', 7)
            self.cell(0, 3.5, _latin1(f'Confira a autenticidade em {site_url()}/contrato/verificar'), new_x='LMARGIN', new_y='NEXT')
        else:
            self.set_font('Helvetica', 'I', 7)
            self.cell(0, 3.5, _latin1('Documento ainda não assinado pelas duas partes.'), new_x='LMARGIN', new_y='NEXT')
        self.set_font('Helvetica', '', 7)
        self.cell(0, 3.5, _latin1(f'Página {self.page_no()} de {{nb}}'), align='R')
        self.set_text_color(0, 0, 0)

    def titulo_secao(self, texto):
        self.ln(3)
        self.set_font('Helvetica', 'B', 10.5)
        self.set_text_color(11, 43, 92)
        self.multi_cell(0, 6, _latin1(texto.upper()), new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(20, 20, 20)

    def paragrafo(self, texto, tamanho=9.5, estilo=''):
        self.set_font('Helvetica', estilo, tamanho)
        self.multi_cell(0, 4.8, _latin1(texto), new_x='LMARGIN', new_y='NEXT')
        self.ln(1.2)


def gerar_pdf(formal):
    """Devolve o PDF do contrato (bytes)"""
    termos = carregar_termos(formal)
    pdf = _PdfContrato(formal)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(11, 43, 92)
    pdf.multi_cell(0, 7, _latin1('CONTRATO DE PRESTAÇÃO DE SERVIÇOS'), align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, _latin1(f"Contrato nº {formal.numero}"), align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(20, 20, 20)

    pdf.titulo_secao('Partes')
    pdf.paragrafo(descricao_da_parte('CONTRATANTE', termos.get('contratante', {})))
    pdf.paragrafo(descricao_da_parte('CONTRATADO(A)', termos.get('contratado', {})))
    pdf.paragrafo('As partes acima identificadas firmam o presente Contrato de Prestação de Serviços, regido pelas cláusulas a seguir.')

    for titulo, paragrafos in montar_clausulas(termos):
        pdf.titulo_secao(titulo)
        for texto in paragrafos:
            if texto:
                pdf.paragrafo(texto)

    pdf.titulo_secao('Registro das assinaturas eletrônicas')
    nomes = {'CONTRATANTE': termos.get('contratante', {}).get('nome', ''),
             'CONTRATADO(A)': termos.get('contratado', {}).get('nome', '')}
    for a in assinaturas(formal):
        if a['quando']:
            pdf.paragrafo(f"{a['parte']} - {nomes[a['parte']]}: assinou em {horario_brasilia(a['quando'])}, IP {a['ip'] or 'não registrado'}.", estilo='B')
            pdf.paragrafo(f"Dispositivo: {a['dispositivo'] or 'não registrado'}", tamanho=8)
        else:
            pdf.paragrafo(f"{a['parte']} - {nomes[a['parte']]}: assinatura pendente.")
    if formal.selado_em:
        pdf.paragrafo(f"Documento selado em {horario_brasilia(formal.selado_em)}.")

    return bytes(pdf.output())
