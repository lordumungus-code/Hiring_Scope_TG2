import base64
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests


def enviar_email(para, assunto, html, anexos=None):
    """Envia um e-mail. Retorna True se o envio foi aceito.

    anexos: lista opcional de (nome_do_arquivo, conteudo_em_bytes)

    Usa o que estiver configurado nas variáveis de ambiente:
      1. RESEND_API_KEY (+ EMAIL_FROM)                       -> API HTTP do Resend
      2. SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD (+ EMAIL_FROM) -> SMTP
    """
    remetente = os.environ.get('EMAIL_FROM') or os.environ.get('SMTP_USER')
    anexos = anexos or []

    try:
        resend_key = os.environ.get('RESEND_API_KEY')
        if resend_key and remetente:
            corpo = {'from': remetente, 'to': [para], 'subject': assunto, 'html': html}
            if anexos:
                corpo['attachments'] = [
                    {'filename': nome, 'content': base64.b64encode(conteudo).decode('ascii')}
                    for nome, conteudo in anexos
                ]
            resposta = requests.post(
                'https://api.resend.com/emails',
                headers={'Authorization': f'Bearer {resend_key}'},
                json=corpo,
                timeout=15
            )
            if resposta.status_code >= 400:
                print(f"❌ Erro ao enviar e-mail (Resend {resposta.status_code}): {resposta.text[:200]}")
                return False
            return True

        smtp_host = os.environ.get('SMTP_HOST')
        if smtp_host and remetente:
            mensagem = MIMEMultipart()
            mensagem['Subject'] = assunto
            mensagem['From'] = remetente
            mensagem['To'] = para
            mensagem.attach(MIMEText(html, 'html', 'utf-8'))
            for nome, conteudo in anexos:
                anexo = MIMEApplication(conteudo)
                anexo.add_header('Content-Disposition', 'attachment', filename=nome)
                mensagem.attach(anexo)

            porta = int(os.environ.get('SMTP_PORT', 587))
            servidor_cls = smtplib.SMTP_SSL if porta == 465 else smtplib.SMTP
            with servidor_cls(smtp_host, porta, timeout=15) as servidor:
                if porta != 465:
                    servidor.starttls()
                if os.environ.get('SMTP_USER'):
                    servidor.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASSWORD', ''))
                servidor.sendmail(remetente, [para], mensagem.as_string())
            return True
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail: {e}")
        return False

    # Diz exatamente o que falta, para facilitar a conferência nas variáveis da hospedagem
    faltando = []
    if not os.environ.get('RESEND_API_KEY') and not os.environ.get('SMTP_HOST'):
        faltando.append('RESEND_API_KEY')
    if not remetente:
        faltando.append('EMAIL_FROM')
    print(f"⚠️ Envio de e-mail não configurado. Variável ausente: {', '.join(faltando)}.")
    return False
