import base64
import io

from PIL import Image, ImageOps

TAMANHO_MAXIMO = 1280  # maior lado, em pixels


def processar_imagem(arquivo):
    """Valida, reduz e converte uma imagem enviada para JPEG em base64.

    Retorna None se o arquivo não for uma imagem válida.
    """
    try:
        imagem = Image.open(arquivo.stream)
        imagem = ImageOps.exif_transpose(imagem)  # respeita a rotação das fotos de celular

        # JPEG não tem transparência: fundo branco no lugar
        if imagem.mode in ('RGBA', 'LA', 'P'):
            imagem = imagem.convert('RGBA')
            fundo = Image.new('RGB', imagem.size, (255, 255, 255))
            fundo.paste(imagem, mask=imagem.split()[-1])
            imagem = fundo
        else:
            imagem = imagem.convert('RGB')

        imagem.thumbnail((TAMANHO_MAXIMO, TAMANHO_MAXIMO))

        saida = io.BytesIO()
        imagem.save(saida, 'JPEG', quality=82, optimize=True)
        return base64.b64encode(saida.getvalue()).decode('utf-8')
    except Exception:
        return None
