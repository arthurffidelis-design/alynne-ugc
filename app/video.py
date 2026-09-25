"""Baixa o vídeo pelo link e extrai o que a IA precisa para "assistir":
quadros com o tempo de cada um, cortes de edição detectados e o áudio para transcrição."""
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

from . import config


class ErroVideo(Exception):
    """Erro com mensagem amigável para mostrar para a Alynne."""

    def __init__(self, mensagem: str, codigo: str = "erro_video"):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


@dataclass
class InfoVideo:
    caminho: str
    plataforma: str = "desconhecida"
    url: str = ""
    autor: str = ""
    legenda: str = ""
    titulo: str = ""
    views: int | None = None
    likes: int | None = None
    comentarios: int | None = None
    data: str = ""
    duracao: float = 0.0
    largura: int = 0
    altura: int = 0
    tem_audio: bool = True
    avisos: list = field(default_factory=list)


# ---------------------------------------------------------------- utilidades

def ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        caminho = shutil.which("ffmpeg")
        if not caminho:
            raise ErroVideo("O servidor está sem o ffmpeg instalado.", "sem_ffmpeg")
        return caminho


def extrair_url(texto: str) -> str:
    """Aceita o texto colado inteiro (às vezes vem com frase junto) e pega só o link."""
    if not texto:
        return ""
    achado = re.search(r"https?://[^\s<>\"']+", texto)
    return achado.group(0).rstrip(".,;)") if achado else ""


def plataforma_do_link(url: str) -> str:
    u = url.lower()
    if "instagram.com" in u or "instagr.am" in u:
        return "instagram"
    if "tiktok.com" in u:
        return "tiktok"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "kwai" in u:
        return "kwai"
    return "outra"


def _data_br(yyyymmdd: str | None) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return ""
    return f"{yyyymmdd[6:8]}/{yyyymmdd[4:6]}/{yyyymmdd[0:4]}"


# ---------------------------------------------------------------- download

def baixar(url: str, pasta: str) -> InfoVideo:
    import yt_dlp

    plataforma = plataforma_do_link(url)
    opcoes = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": os.path.join(pasta, "video.%(ext)s"),
        "format": "best[height<=720][ext=mp4]/best[height<=720]/bv*[height<=720]+ba/best",
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_bin(),
        "retries": 2,
        "socket_timeout": 30,
        "max_filesize": config.MAX_UPLOAD_MB * 1024 * 1024,
    }
    if plataforma == "instagram" and config.IG_COOKIES:
        arquivo_cookies = os.path.join(pasta, "cookies.txt")
        with open(arquivo_cookies, "w", encoding="utf-8") as f:
            f.write(config.IG_COOKIES.replace("\\n", "\n"))
        opcoes["cookiefile"] = arquivo_cookies

    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:  # yt-dlp levanta vários tipos diferentes
        texto = str(e).lower()
        if "429" in texto or "rate" in texto or "login" in texto or "cookie" in texto:
            raise ErroVideo(
                "O Instagram bloqueou o download pelo link agora. Envie o arquivo do vídeo "
                "(pode ser gravação de tela com som) que eu analiso do mesmo jeito.",
                "download_bloqueado",
            )
        if "private" in texto or "privad" in texto:
            raise ErroVideo("Esse vídeo é de um perfil privado. Envie o arquivo do vídeo.", "privado")
        raise ErroVideo(
            "Não consegui baixar esse vídeo pelo link. Envie o arquivo do vídeo que eu analiso do mesmo jeito.",
            "download_falhou",
        )

    if info and info.get("_type") == "playlist":
        entradas = [e for e in (info.get("entries") or []) if e]
        info = entradas[0] if entradas else info

    arquivos = [a for a in os.listdir(pasta) if a.startswith("video.")]
    if not arquivos:
        raise ErroVideo("Esse link não tem um vídeo que eu consiga baixar (pode ser foto ou carrossel).", "sem_video")

    caminho = os.path.join(pasta, arquivos[0])
    dados = InfoVideo(
        caminho=caminho,
        plataforma=plataforma,
        url=url,
        autor=(info.get("uploader") or info.get("channel") or info.get("uploader_id") or "") if info else "",
        legenda=(info.get("description") or "") if info else "",
        titulo=(info.get("title") or "") if info else "",
        views=info.get("view_count") if info else None,
        likes=info.get("like_count") if info else None,
        comentarios=info.get("comment_count") if info else None,
        data=_data_br(info.get("upload_date")) if info else "",
    )
    return completar_com_arquivo(dados)


def de_arquivo(caminho: str, nome_original: str = "") -> InfoVideo:
    dados = InfoVideo(caminho=caminho, plataforma="arquivo enviado", titulo=nome_original)
    return completar_com_arquivo(dados)


# ---------------------------------------------------------------- análise técnica

def _rodar(args: list, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def completar_com_arquivo(dados: InfoVideo) -> InfoVideo:
    """Lê duração, resolução e se tem áudio direto do arquivo."""
    proc = _rodar([ffmpeg_bin(), "-hide_banner", "-i", dados.caminho], timeout=60)
    saida = proc.stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", saida)
    if not m:
        raise ErroVideo("Não consegui abrir esse arquivo de vídeo. Tente outro formato (mp4 ou mov).", "arquivo_invalido")
    dados.duracao = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    r = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", saida)
    if r:
        dados.largura, dados.altura = int(r.group(1)), int(r.group(2))
    else:
        raise ErroVideo("Esse arquivo não tem imagem de vídeo.", "sem_video")
    dados.tem_audio = "Audio:" in saida
    if dados.duracao > config.MAX_DURACAO_S:
        dados.avisos.append(
            f"O vídeo tem {int(dados.duracao)}s; analisei só os primeiros {config.MAX_DURACAO_S}s."
        )
    return dados


def detectar_cortes(caminho: str, duracao: float) -> list[float]:
    """Marca os momentos em que a imagem muda de plano (corte de edição)."""
    limite = min(duracao, config.MAX_DURACAO_S)
    proc = _rodar(
        [
            ffmpeg_bin(), "-hide_banner", "-t", f"{limite:.2f}", "-i", caminho,
            "-vf", "scale=160:-2,select='gt(scene,0.30)',showinfo",
            "-an", "-f", "null", "-",
        ],
        timeout=240,
    )
    tempos = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]
    cortes: list[float] = []
    for t in sorted(tempos):
        if t < 0.2:
            continue
        if cortes and t - cortes[-1] < 0.35:
            continue
        cortes.append(round(t, 2))
    return cortes


def escolher_tempos(duracao: float, cortes: list[float], maximo: int) -> list[float]:
    """Quadros extras no começo (gancho) + um quadro logo depois de cada corte + distribuição uniforme."""
    fim = max(0.1, min(duracao, config.MAX_DURACAO_S) - 0.15)
    candidatos = [t for t in (0.2, 1.0, 2.0, 3.0) if t < fim]
    orcamento_cortes = max(0, maximo - len(candidatos) - 4)
    if cortes:
        passo = max(1, len(cortes) // max(1, orcamento_cortes)) if orcamento_cortes else len(cortes) + 1
        candidatos += [min(fim, c + 0.3) for c in cortes[::passo]][:orcamento_cortes]
    faltam = maximo - len(candidatos)
    if faltam > 0:
        candidatos += [fim * (i + 1) / (faltam + 1) for i in range(faltam)]
    candidatos.append(fim)

    escolhidos: list[float] = []
    for t in sorted(set(round(x, 2) for x in candidatos)):
        if 0 <= t <= fim and (not escolhidos or t - escolhidos[-1] >= 0.5):
            escolhidos.append(t)
    if len(escolhidos) > maximo:  # mantém o gancho e espalha o resto
        inicio = [t for t in escolhidos if t <= 3.0]
        resto = [t for t in escolhidos if t > 3.0]
        vagas = maximo - len(inicio)
        if vagas > 0 and resto:
            passo = len(resto) / vagas
            resto = [resto[int(i * passo)] for i in range(vagas)]
        escolhidos = (inicio + resto)[:maximo]
    return escolhidos


def extrair_quadros(caminho: str, tempos: list[float], pasta: str) -> list[tuple[float, bytes]]:
    quadros = []
    for i, t in enumerate(tempos):
        destino = os.path.join(pasta, f"quadro_{i:02d}.jpg")
        _rodar(
            [
                ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{t:.2f}", "-i", caminho, "-frames:v", "1",
                "-vf", f"scale={config.LARGURA_QUADRO}:-2", "-q:v", "5", destino,
            ],
            timeout=60,
        )
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            with open(destino, "rb") as f:
                quadros.append((t, f.read()))
    return quadros


def extrair_audio(caminho: str, pasta: str) -> str | None:
    destino = os.path.join(pasta, "audio.mp3")
    proc = _rodar(
        [
            ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
            "-t", str(config.MAX_DURACAO_S), "-i", caminho,
            "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", destino,
        ],
        timeout=180,
    )
    if proc.returncode != 0 or not os.path.exists(destino) or os.path.getsize(destino) < 1000:
        return None
    return destino
