"""Transcreve a fala do vídeo com a OpenAI (o Claude não escuta áudio)."""
import logging

from . import config

log = logging.getLogger("roteiro.transcricao")

DICA = (
    "Vídeo curto de Instagram ou TikTok, provavelmente em português do Brasil, "
    "falado de forma informal por uma creator."
)


def transcrever(caminho_audio: str) -> tuple[str, str]:
    """Devolve (texto, modelo_usado). Texto vazio se não houver fala ou se não houver chave."""
    if not config.OPENAI_API_KEY or not caminho_audio:
        return "", ""

    from openai import OpenAI

    cliente = OpenAI(api_key=config.OPENAI_API_KEY, timeout=180)
    ultimo_erro = None
    for modelo in config.TRANSCRICAO_MODELOS:
        try:
            with open(caminho_audio, "rb") as f:
                kwargs = {"model": modelo, "file": f}
                if modelo != "whisper-1":
                    kwargs["prompt"] = DICA
                resposta = cliente.audio.transcriptions.create(**kwargs)
            texto = (getattr(resposta, "text", "") or "").strip()
            return texto, modelo
        except Exception as e:  # tenta o próximo modelo da lista
            ultimo_erro = e
            log.warning("Transcrição falhou com %s: %s", modelo, e)
    raise RuntimeError(f"Falha na transcrição: {ultimo_erro}")
