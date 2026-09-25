"""Alynne Studio (ex-Roteiro Viral): app web da Alynne.

Cola o link de um vídeo viral (ou envia o arquivo), a IA assiste o vídeo, entende a
estrutura que fez ele funcionar e entrega um roteiro novo, com a cara dela, pronto para gravar.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, motor, transcricao, video

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("roteiro")

PASTA_STATIC = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title=config.APP_NOME, version=config.VERSAO, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=PASTA_STATIC), name="static")

executor = ThreadPoolExecutor(max_workers=2)
JOBS: dict[str, dict] = {}
TRAVA = threading.Lock()
TENTATIVAS_LOGIN: dict[str, list[float]] = {}

ETAPAS_GERAR = [
    ("baixar", "Pegando o vídeo"),
    ("assistir", "Assistindo: cortes e cenas"),
    ("ouvir", "Ouvindo a fala"),
    ("escrever", "Escrevendo seu roteiro"),
]
ETAPAS_AJUSTAR = [("escrever", "Ajustando seu roteiro")]


# ================================================================ acesso

def _assinar(valor: str) -> str:
    return hmac.new(config.SECRET_KEY.encode(), valor.encode(), hashlib.sha256).hexdigest()


def _token_novo() -> str:
    expira = str(int(time.time()) + config.SESSAO_DIAS * 86400)
    return f"{expira}.{_assinar(expira)}"


def _token_valido(token: str | None) -> bool:
    if not config.APP_SENHA:
        return True
    if not token or "." not in token:
        return False
    expira, assinatura = token.split(".", 1)
    if not hmac.compare_digest(assinatura, _assinar(expira)):
        return False
    return expira.isdigit() and int(expira) > time.time()


LIVRES = {"/api/login", "/api/config"}


@app.middleware("http")
async def proteger_api(request: Request, chamar):
    caminho = request.url.path
    if caminho.startswith("/api/") and caminho not in LIVRES:
        if not _token_valido(request.cookies.get("sessao")):
            return JSONResponse({"erro": "Entre com a senha para continuar.", "codigo": "sem_login"}, status_code=401)
    return await chamar(request)


@app.post("/api/login")
async def login(request: Request):
    ip = request.client.host if request.client else "?"
    agora = time.time()
    recentes = [t for t in TENTATIVAS_LOGIN.get(ip, []) if agora - t < 600]
    if len(recentes) >= 6:
        raise HTTPException(429, "Muitas tentativas. Espere 10 minutos.")
    corpo = await request.json()
    senha = str(corpo.get("senha", ""))
    if config.APP_SENHA and not hmac.compare_digest(senha, config.APP_SENHA):
        recentes.append(agora)
        TENTATIVAS_LOGIN[ip] = recentes
        raise HTTPException(401, "Senha incorreta.")
    TENTATIVAS_LOGIN.pop(ip, None)
    resposta = JSONResponse({"ok": True})
    resposta.set_cookie(
        "sessao", _token_novo(), max_age=config.SESSAO_DIAS * 86400,
        httponly=True, samesite="lax", secure=request.url.scheme == "https",
    )
    return resposta


@app.post("/api/logout")
async def logout():
    resposta = JSONResponse({"ok": True})
    resposta.delete_cookie("sessao")
    return resposta


# ================================================================ páginas e info

@app.get("/")
async def inicio():
    return FileResponse(os.path.join(PASTA_STATIC, "index.html"), headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(os.path.join(PASTA_STATIC, "manifest.webmanifest"), media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        os.path.join(PASTA_STATIC, "sw.js"), media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/versao")
async def versao():
    return {
        "app": config.APP_NOME,
        "versao": config.VERSAO,
        "data": config.DATA_VERSAO,
        "claude": bool(config.ANTHROPIC_API_KEY),
        "openai": bool(config.OPENAI_API_KEY),
        "modelo": config.CLAUDE_MODELO,
        "cookies_instagram": bool(config.IG_COOKIES),
    }


@app.get("/api/config")
async def api_config(request: Request):
    return {
        "app": config.APP_NOME,
        "versao": config.VERSAO,
        "autenticado": _token_valido(request.cookies.get("sessao")),
        "precisa_senha": bool(config.APP_SENHA),
        "perfil_padrao": config.PERFIL_PADRAO,
        "tem_claude": bool(config.ANTHROPIC_API_KEY),
        "tem_transcricao": bool(config.OPENAI_API_KEY),
        "max_upload_mb": config.MAX_UPLOAD_MB,
    }


# ================================================================ jobs

def _novo_job(etapas) -> str:
    _limpar_jobs_antigos()
    job_id = uuid.uuid4().hex[:12]
    with TRAVA:
        JOBS[job_id] = {
            "status": "processando",
            "etapas": [{"id": i, "nome": n, "status": "pendente"} for i, n in etapas],
            "resultado": None,
            "meta": None,
            "erro": None,
            "codigo": None,
            "criado": time.time(),
        }
    return job_id


def _etapa(job_id: str, etapa: str, status: str = "andamento", nome: str | None = None):
    with TRAVA:
        job = JOBS.get(job_id)
        if not job:
            return
        for e in job["etapas"]:
            if e["id"] == etapa:
                e["status"] = status
                if nome:
                    e["nome"] = nome
            elif status == "andamento" and e["status"] == "andamento":
                e["status"] = "feito"


def _falhar(job_id: str, mensagem: str, codigo: str = "erro"):
    with TRAVA:
        job = JOBS.get(job_id)
        if job:
            job.update(status="erro", erro=mensagem, codigo=codigo)
            for e in job["etapas"]:
                if e["status"] == "andamento":
                    e["status"] = "erro"


def _concluir(job_id: str, resultado: dict, meta: dict | None):
    with TRAVA:
        job = JOBS.get(job_id)
        if job:
            for e in job["etapas"]:
                if e["status"] in ("andamento", "pendente"):
                    e["status"] = "feito"
            job.update(status="pronto", resultado=resultado, meta=meta)


def _limpar_jobs_antigos():
    limite = time.time() - 3 * 3600
    with TRAVA:
        for k in [k for k, v in JOBS.items() if v["criado"] < limite]:
            JOBS.pop(k, None)


@app.get("/api/job/{job_id}")
async def ver_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Esse processamento não existe mais. Gere de novo.")
    return {k: v for k, v in job.items() if k != "criado"}


# ================================================================ gerar

def _miniatura(caminho: str, t: float, pasta: str) -> str:
    destino = os.path.join(pasta, "mini.jpg")
    try:
        video._rodar(
            [video.ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}",
             "-i", caminho, "-frames:v", "1", "-vf", "scale=180:-2", "-q:v", "6", destino],
            timeout=30,
        )
        with open(destino, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def _processar(job_id: str, pasta: str, link: str, arquivo: str | None, nome_arquivo: str, pedido: dict, perfil: dict):
    try:
        # 1) pegar o vídeo
        _etapa(job_id, "baixar")
        if arquivo:
            info = video.de_arquivo(arquivo, nome_arquivo)
            if link:
                info.url = link
                info.plataforma = video.plataforma_do_link(link) + " (arquivo enviado)"
        else:
            info = video.baixar(link, pasta)

        # 2) assistir: cortes + quadros
        _etapa(job_id, "assistir")
        cortes = video.detectar_cortes(info.caminho, info.duracao)
        tempos = video.escolher_tempos(info.duracao, cortes, config.MAX_QUADROS)
        quadros = video.extrair_quadros(info.caminho, tempos, pasta)
        if not quadros:
            raise video.ErroVideo("Não consegui ler as imagens desse vídeo. Tente outro arquivo.", "sem_quadros")

        # 3) ouvir a fala
        _etapa(job_id, "ouvir")
        texto, status_trans, modelo_trans = "", "", ""
        if not info.tem_audio:
            status_trans = "sem_audio"
        elif not config.OPENAI_API_KEY:
            status_trans = "sem_chave"
        else:
            audio = video.extrair_audio(info.caminho, pasta)
            if not audio:
                status_trans = "sem_audio"
            else:
                try:
                    texto, modelo_trans = transcricao.transcrever(audio)
                    status_trans = "ok" if texto else "sem_fala"
                except Exception:
                    log.exception("Transcrição falhou")
                    status_trans = "falhou"

        dados = {
            "plataforma": info.plataforma,
            "url": info.url,
            "autor": info.autor,
            "legenda": info.legenda,
            "views": info.views,
            "likes": info.likes,
            "comentarios": info.comentarios,
            "data": info.data,
            "duracao": round(info.duracao, 2),
            "largura": info.largura,
            "altura": info.altura,
            "cortes": cortes,
            "transcricao": texto,
            "transcricao_status": status_trans,
            "transcricao_modelo": modelo_trans,
        }

        # 4) escrever
        _etapa(job_id, "escrever")
        resultado = motor.gerar(dados, quadros, pedido, perfil)

        avisos = list(info.avisos)
        if status_trans == "sem_chave":
            avisos.append("A fala do vídeo não foi analisada (falta a chave da OpenAI no Render).")
        elif status_trans == "falhou":
            avisos.append("Não consegui transcrever a fala; a análise usou as imagens e a legenda.")
        resultado["avisos"] = avisos + list(resultado.get("avisos") or [])

        meta = {**dados, "miniatura": _miniatura(info.caminho, min(1.0, info.duracao / 2), pasta),
                "quadros_analisados": len(quadros)}
        _concluir(job_id, resultado, meta)
    except video.ErroVideo as e:
        _falhar(job_id, e.mensagem, e.codigo)
    except motor.ErroMotor as e:
        _falhar(job_id, e.mensagem, "erro_ia")
    except Exception:
        log.exception("Falha inesperada no job %s", job_id)
        _falhar(job_id, "Algo deu errado do nosso lado. Tente de novo em instantes.", "erro_interno")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def _json_form(texto: str) -> dict:
    try:
        valor = json.loads(texto or "{}")
        return valor if isinstance(valor, dict) else {}
    except json.JSONDecodeError:
        return {}


@app.post("/api/gerar")
async def gerar(
    link: str = Form(""),
    pedido: str = Form("{}"),
    perfil: str = Form("{}"),
    arquivo: UploadFile | None = File(None),
):
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(503, "O app ainda não está com a chave do Claude configurada no Render.")

    url = video.extrair_url(link)
    tem_arquivo = arquivo is not None and bool(arquivo.filename)
    if not url and not tem_arquivo:
        raise HTTPException(400, "Cole o link do vídeo ou envie o arquivo.")

    pasta = tempfile.mkdtemp(prefix="roteiro_")
    caminho_arquivo = None
    nome = ""
    if tem_arquivo:
        nome = os.path.basename(arquivo.filename or "video.mp4")
        extensao = os.path.splitext(nome)[1].lower() or ".mp4"
        caminho_arquivo = os.path.join(pasta, "enviado" + extensao)
        limite = config.MAX_UPLOAD_MB * 1024 * 1024
        total = 0
        with open(caminho_arquivo, "wb") as destino:
            while True:
                pedaco = await arquivo.read(1024 * 1024)
                if not pedaco:
                    break
                total += len(pedaco)
                if total > limite:
                    destino.close()
                    shutil.rmtree(pasta, ignore_errors=True)
                    raise HTTPException(413, f"O arquivo passa de {config.MAX_UPLOAD_MB} MB.")
                destino.write(pedaco)

    job_id = _novo_job(ETAPAS_GERAR)
    if tem_arquivo:
        _etapa(job_id, "baixar", nome="Recebendo o vídeo")
    executor.submit(_processar, job_id, pasta, url, caminho_arquivo, nome, _json_form(pedido), _json_form(perfil))
    return {"job_id": job_id}


# ================================================================ ajustar

def _processar_ajuste(job_id: str, corpo: dict):
    try:
        _etapa(job_id, "escrever")
        resultado = motor.ajustar(
            corpo.get("resultado") or {}, corpo.get("meta") or {}, corpo.get("pedido") or {},
            corpo.get("perfil") or {}, str(corpo.get("instrucao") or "").strip()[:1500],
        )
        _concluir(job_id, resultado, corpo.get("meta"))
    except motor.ErroMotor as e:
        _falhar(job_id, e.mensagem, "erro_ia")
    except Exception:
        log.exception("Falha no ajuste %s", job_id)
        _falhar(job_id, "Algo deu errado no ajuste. Tente de novo.", "erro_interno")


@app.post("/api/ajustar")
async def ajustar(request: Request):
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(503, "O app ainda não está com a chave do Claude configurada no Render.")
    corpo = await request.json()
    if not corpo.get("resultado") or not str(corpo.get("instrucao") or "").strip():
        raise HTTPException(400, "Diga o que você quer ajustar.")
    job_id = _novo_job(ETAPAS_AJUSTAR)
    executor.submit(_processar_ajuste, job_id, corpo)
    return {"job_id": job_id}
