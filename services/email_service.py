import os
import smtplib
from email.mime.text import MIMEText

import requests


def enviar_email(para, assunto, html):
    """Envia um e-mail. Retorna True se o envio foi aceito.

    Usa o que estiver configurado nas variáveis de ambiente:
      1. RESEND_API_KEY (+ EMAIL_FROM)                       -> API HTTP do Resend
      2. SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD (+ EMAIL_FROM) -> SMTP
    """
    remetente = os.environ.get('EMAIL_FROM') or os.environ.get('SMTP_USER')

    try:
        resend_key = os.environ.get('RESEND_API_KEY')
        if resend_key and remetente:
            resposta = requests.post(
                'https://api.resend.com/emails',
                headers={'Authorization': f'Bearer {resend_key}'},
                json={'from': remetente, 'to': [para], 'subject': assunto, 'html': html},
                timeout=10
            )
            if resposta.status_code >= 400:
                print(f"❌ Erro ao enviar e-mail (Resend {resposta.status_code}): {resposta.text[:200]}")
                return False
            return True

        smtp_host = os.environ.get('SMTP_HOST')
        if smtp_host and remetente:
            mensagem = MIMEText(html, 'html', 'utf-8')
            mensagem['Subject'] = assunto
            mensagem['From'] = remetente
            mensagem['To'] = para

            porta = int(os.environ.get('SMTP_PORT', 587))
            servidor_cls = smtplib.SMTP_SSL if porta == 465 else smtplib.SMTP
            with servidor_cls(smtp_host, porta, timeout=10) as servidor:
                if porta != 465:
                    servidor.starttls()
                if os.environ.get('SMTP_USER'):
                    servidor.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASSWORD', ''))
                servidor.sendmail(remetente, [para], mensagem.as_string())
            return True
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail: {e}")
        return False

    print("⚠️ Envio de e-mail não configurado (defina RESEND_API_KEY ou SMTP_HOST, e EMAIL_FROM).")
    return False
