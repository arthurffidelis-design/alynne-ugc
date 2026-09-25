"""Testes de regressão do Roteiro Viral. Rodam sem chamar as IAs (respostas simuladas).

Rodar:  pip install -r requirements-dev.txt && pytest -q   (testes do banco: TEST_DATABASE_URL=postgresql://...)
"""
import copy
import json
import os
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from app import config, main, motor, prompts, transcricao, video

AQUI = os.path.dirname(__file__)
EXEMPLO = json.load(open(os.path.join(AQUI, "exemplo_resultado.json"), encoding="utf-8"))


# ------------------------------------------------------------ utilidades de teste

@pytest.fixture(scope="session")
def video_sintetico(tmp_path_factory):
    """Vídeo vertical de 9s com 3 planos de cores diferentes e áudio (tom)."""
    destino = str(tmp_path_factory.mktemp("v") / "teste.mp4")
    ff = video.ffmpeg_bin()
    subprocess.run(
        [
            ff, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=0xC08060:s=360x640:d=3",
            "-f", "lavfi", "-i", "color=c=0x305070:s=360x640:d=3",
            "-f", "lavfi", "-i", "color=c=0xE0E0D0:s=360x640:d=3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=9",
            "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
            "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", destino,
        ],
        check=True,
    )
    return destino


def _checar_schema_estrito(no, caminho="raiz"):
    """Structured outputs exige additionalProperties=false e todos os campos em required."""
    if no.get("type") == "object":
        assert no.get("additionalProperties") is False, caminho
        assert set(no.get("required", [])) == set(no["properties"].keys()), caminho
        for k, v in no["properties"].items():
            _checar_schema_estrito(v, f"{caminho}.{k}")
    if no.get("type") == "array":
        _checar_schema_estrito(no["items"], caminho + "[]")


# ------------------------------------------------------------ schema e prompts

def test_schema_estrito():
    _checar_schema_estrito(prompts.SCHEMA_COMPLETO)
    _checar_schema_estrito(prompts.SCHEMA_AJUSTE)


def test_exemplo_valida_no_schema():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(EXEMPLO, prompts.SCHEMA_COMPLETO)
    ajuste = {k: EXEMPLO[k] for k in prompts.SCHEMA_AJUSTE["required"]}
    jsonschema.validate(ajuste, prompts.SCHEMA_AJUSTE)


def test_persona_preservada():
    for trecho in ["ETAPA 1", "ETAPA 5", "REGRAS DE QUALIDADE", "Não presuma informações", "Oi gente"]:
        assert trecho in prompts.PERSONA
    assert "TEMA DO NOVO VÍDEO" in prompts.CALIBRAGEM or "Sobre o que será o novo vídeo" in prompts.CALIBRAGEM


def test_pedido_tem_limite_de_palavras():
    texto = motor.bloco_pedido({"tema": "rotina", "duracao": "30s", "estilo": "Natural", "criar": "UGC"})
    assert "75 palavras" in texto and "rotina" in texto and "UGC" in texto


# ------------------------------------------------------------ vídeo

def test_extrair_url():
    assert video.extrair_url("olha isso https://www.instagram.com/reel/ABC123/?igsh=xyz.") == \
        "https://www.instagram.com/reel/ABC123/?igsh=xyz"
    assert video.extrair_url("sem link") == ""
    assert video.plataforma_do_link("https://vm.tiktok.com/abc") == "tiktok"


def test_escolher_tempos_limites():
    tempos = video.escolher_tempos(30.0, [2.1, 4.0, 6.5, 9.9, 15.2, 20.0, 25.5], 16)
    assert 0 < len(tempos) <= 16
    assert tempos == sorted(tempos)
    assert all(0 <= t <= 30 for t in tempos)
    assert tempos[0] < 1  # sempre olha o gancho


def test_pipeline_video(video_sintetico, tmp_path):
    info = video.de_arquivo(video_sintetico, "teste.mp4")
    assert 8.5 < info.duracao < 9.5
    assert (info.largura, info.altura) == (360, 640)
    assert info.tem_audio
    cortes = video.detectar_cortes(info.caminho, info.duracao)
    assert len(cortes) == 2 and abs(cortes[0] - 3) < 0.3 and abs(cortes[1] - 6) < 0.3
    quadros = video.extrair_quadros(info.caminho, video.escolher_tempos(info.duracao, cortes, 8), str(tmp_path))
    assert 3 <= len(quadros) <= 8 and all(jpg[:2] == b"\xff\xd8" for _, jpg in quadros)
    assert video.extrair_audio(info.caminho, str(tmp_path))


# ------------------------------------------------------------ API

@pytest.fixture()
def cliente(monkeypatch):
    monkeypatch.setattr(config, "APP_SENHA", "teste123")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "chave-falsa")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "chave-falsa")
    chamadas = []

    def falso_claude(system, conteudo, schema):
        chamadas.append({"system": system, "conteudo": conteudo, "schema": schema})
        base = copy.deepcopy(EXEMPLO)
        if schema is prompts.SCHEMA_AJUSTE:
            base = {k: base[k] for k in schema["required"]}
            base["roteiro"]["titulo"] = "Versão ajustada"
        return base

    monkeypatch.setattr(motor, "_chamar_claude", falso_claude)
    monkeypatch.setattr(transcricao, "transcrever", lambda caminho: ("fala de teste do vídeo", "falso"))
    c = TestClient(main.app)
    c.chamadas = chamadas
    return c


def _esperar(cliente, job_id, limite=60):
    fim = time.time() + limite
    while time.time() < fim:
        r = cliente.get(f"/api/job/{job_id}").json()
        if r["status"] in ("pronto", "erro"):
            return r
        time.sleep(0.3)
    raise AssertionError("job não terminou")


def test_versao_e_config(cliente):
    assert cliente.get("/versao").json()["versao"] == config.VERSAO
    c = cliente.get("/api/config").json()
    assert c["precisa_senha"] is True and c["autenticado"] is False and c["app"] == "Alynne Studio"
    assert "lifestyle" in c["perfil_padrao"]["descricao"]


def test_login_obrigatorio(cliente):
    assert cliente.post("/api/gerar", data={"link": "https://x.com"}).status_code == 401
    assert cliente.post("/api/login", json={"senha": "errada"}).status_code == 401
    assert cliente.post("/api/login", json={"senha": "teste123"}).status_code == 200
    assert cliente.get("/api/config").json()["autenticado"] is True


def test_gerar_com_arquivo_e_ajustar(cliente, video_sintetico):
    cliente.post("/api/login", json={"senha": "teste123"})
    pedido = {"criar": "UGC", "nicho": "beleza", "tema": "minha rotina de skincare", "produto": "",
              "estilo": "Papo entre amigas", "duracao": "30s"}
    with open(video_sintetico, "rb") as f:
        r = cliente.post(
            "/api/gerar",
            data={"link": "", "pedido": json.dumps(pedido), "perfil": json.dumps({"jeito_de_falar": "amiga"})},
            files={"arquivo": ("teste.mp4", f, "video/mp4")},
        )
    assert r.status_code == 200, r.text
    job = _esperar(cliente, r.json()["job_id"])
    assert job["status"] == "pronto", job
    assert all(e["status"] == "feito" for e in job["etapas"])
    assert job["resultado"]["roteiro"]["cenas"]
    assert job["meta"]["transcricao"] == "fala de teste do vídeo"
    assert len(job["meta"]["cortes"]) == 2
    assert job["meta"]["miniatura"].startswith("data:image/jpeg;base64,")

    # o que foi mandado para a IA: dados reais + quadros + pedido com o tema literal
    enviado = cliente.chamadas[-1]["conteudo"]
    textos = " ".join(b.get("text", "") for b in enviado if b["type"] == "text")
    assert "minha rotina de skincare" in textos and "fala de teste do vídeo" in textos and "amiga" in textos
    assert sum(1 for b in enviado if b["type"] == "image") >= 3

    r2 = cliente.post("/api/ajustar", json={"resultado": job["resultado"], "meta": job["meta"], "pedido": pedido,
                                            "perfil": {}, "instrucao": "Mais curto"})
    ajuste = _esperar(cliente, r2.json()["job_id"])
    assert ajuste["status"] == "pronto"
    assert ajuste["resultado"]["roteiro"]["titulo"] == "Versão ajustada"
    assert ajuste["resultado"]["analise"] == job["resultado"]["analise"]  # análise preservada


def test_erro_de_download_vira_mensagem_amigavel(cliente, monkeypatch):
    cliente.post("/api/login", json={"senha": "teste123"})

    def falha(url, pasta):
        raise video.ErroVideo("O Instagram bloqueou o download pelo link agora.", "download_bloqueado")

    monkeypatch.setattr(video, "baixar", falha)
    r = cliente.post("/api/gerar", data={"link": "https://www.instagram.com/reel/X/", "pedido": "{}", "perfil": "{}"})
    job = _esperar(cliente, r.json()["job_id"])
    assert job["status"] == "erro" and job["codigo"] == "download_bloqueado"


def test_sem_link_nem_arquivo(cliente):
    cliente.post("/api/login", json={"senha": "teste123"})
    assert cliente.post("/api/gerar", data={"link": "oi", "pedido": "{}"}).status_code == 400


# ------------------------------------------------------------ v1.0.1: JSON sem "saída estruturada"

def test_instrucao_json_tem_todas_as_chaves():
    texto = motor.instrucao_json(prompts.SCHEMA_COMPLETO)
    for chave in ["analise", "formula", "roteiro", "cenas", "texto_na_tela", "ganchos_extras", "checagem_qualidade",
                  "campos_para_preencher", "avisos"]:
        assert f'"{chave}"' in texto


def test_extrair_json_tolerante():
    bruto = json.dumps(EXEMPLO, ensure_ascii=False)
    assert motor.extrair_json(bruto)["roteiro"]["titulo"]
    assert motor.extrair_json("```json\n" + bruto + "\n```")["roteiro"]["titulo"]
    assert motor.extrair_json("Aqui está:\n" + bruto + "\nPronto.")["roteiro"]["titulo"]
    for ruim in ["", "sem json", '{"roteiro": ', '{"outra": 1}']:
        with pytest.raises(ValueError):
            motor.extrair_json(ruim)


def test_normalizar_completa_campos_e_tipos():
    parcial = {"roteiro": {"titulo": "T", "cenas": [{"fala": "oi", "tempo": 3}], "broll": "uma ideia"},
               "checagem_qualidade": {"gancho_forte": "true"}}
    n = motor.normalizar(parcial, prompts.SCHEMA_COMPLETO)
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(n, prompts.SCHEMA_COMPLETO)
    assert n["roteiro"]["cenas"][0]["tempo"] == "3"
    assert n["roteiro"]["broll"] == ["uma ideia"]
    assert n["checagem_qualidade"]["gancho_forte"] is True
    assert n["variacoes"]["ganchos_extras"] == []


class _Final:
    def __init__(self, texto):
        self.content = [type("B", (), {"type": "text", "text": texto})()]
        self.stop_reason = "end_turn"
        self.usage = type("U", (), {"input_tokens": 10, "output_tokens": 5})()


class _ClienteFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        cliente = self

        class _Stream:
            def __init__(self, kwargs):
                cliente.chamadas.append(kwargs)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                return _Final(cliente.respostas.pop(0))

        self.messages = type("M", (), {"stream": lambda _s, **kw: _Stream(kw)})()


def _instalar_cliente(monkeypatch, respostas):
    import anthropic

    falso = _ClienteFalso(respostas)
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: falso)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "chave-falsa")
    return falso


def test_chamada_sem_output_config(monkeypatch):
    falso = _instalar_cliente(monkeypatch, [json.dumps(EXEMPLO, ensure_ascii=False)])
    r = motor._chamar_claude("sistema", [{"type": "text", "text": "x"}], prompts.SCHEMA_COMPLETO)
    assert r["roteiro"]["titulo"] == EXEMPLO["roteiro"]["titulo"]
    assert "output_config" not in falso.chamadas[0]
    assert "RESPOSTA EM JSON" in falso.chamadas[0]["system"]
    assert r["_uso"]["entrada"] == 10


def test_chamada_corrige_json_quebrado(monkeypatch):
    falso = _instalar_cliente(monkeypatch, ["ops, não é json", json.dumps(EXEMPLO, ensure_ascii=False)])
    r = motor._chamar_claude("sistema", [{"type": "text", "text": "x"}], prompts.SCHEMA_COMPLETO)
    assert r["roteiro"]["cenas"] and len(falso.chamadas) == 2
    assert falso.chamadas[1]["messages"][-1]["role"] == "user"
    assert r["_uso"]["entrada"] == 20


def test_chamada_desiste_depois_de_2_tentativas(monkeypatch):
    _instalar_cliente(monkeypatch, ["nada", "nada de novo"])
    with pytest.raises(motor.ErroMotor):
        motor._chamar_claude("sistema", [{"type": "text", "text": "x"}], prompts.SCHEMA_COMPLETO)


# ------------------------------------------------------------ v1.1.1: banco de dados
# Rodam só com TEST_DATABASE_URL apontando para um Postgres de teste (as tabelas são limpas).
from app import db

URL_TESTE = os.getenv("TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not URL_TESTE, reason="sem TEST_DATABASE_URL")


@pytest.fixture()
def banco(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", URL_TESTE)
    db.fechar()
    assert db.iniciar() == "ok"
    with db._pool.connection() as con:
        con.execute("TRUNCATE roteiros, preferencias")
    yield db
    db.fechar()


def test_sem_banco_responde_503(cliente):
    db.fechar()
    cliente.post("/api/login", json={"senha": "teste123"})
    assert cliente.get("/api/roteiros").status_code == 503
    assert cliente.get("/api/config").json()["banco"] == "desligado"


@precisa_banco
def test_banco_salva_lista_e_respeita_versao_mais_nova(banco):
    item = {"id": "abc", "criado": 1_000, "atualizado": 2_000, "pedido": {"tema": "rotina"},
            "meta": {"miniatura": "data:x"}, "resultado": EXEMPLO, "checklist": {}}
    assert db.salvar_roteiro(item)
    lista = db.listar_roteiros()
    assert lista["itens"][0]["titulo"] == EXEMPLO["roteiro"]["titulo"] and lista["itens"][0]["tema"] == "rotina"
    velho = {**item, "atualizado": 1_500, "pedido": {"tema": "velho"}}
    assert not db.salvar_roteiro(velho)  # cópia antiga não sobrescreve
    assert db.obter_roteiro("abc")["pedido"]["tema"] == "rotina"
    db.apagar_roteiro("abc")
    assert db.obter_roteiro("abc") is None
    assert not db.salvar_roteiro({**item, "atualizado": 9_999_999_999_999})  # apagado não volta
    assert db.listar_roteiros() == {"itens": [], "apagados": ["abc"]}


@precisa_banco
def test_preferencias_vale_a_mais_nova(banco):
    assert db.salvar_preferencia("inspiracoes", [{"usuario": "a"}], 2_000)
    assert not db.salvar_preferencia("inspiracoes", [], 1_000)
    assert db.preferencias()["inspiracoes"]["valor"] == [{"usuario": "a"}]
    with pytest.raises(ValueError):
        db.salvar_preferencia("qualquer", 1)


@precisa_banco
def test_api_com_banco_guarda_roteiro_no_servidor(cliente, banco, video_sintetico):
    cliente.post("/api/login", json={"senha": "teste123"})
    pedido = {"tema": "rotina da noite", "duracao": "30s"}
    with open(video_sintetico, "rb") as f:
        r = cliente.post("/api/gerar", data={"pedido": json.dumps(pedido), "perfil": "{}"},
                         files={"arquivo": ("t.mp4", f, "video/mp4")})
    job = _esperar(cliente, r.json()["job_id"])
    assert job["status"] == "pronto" and job["item_id"]
    lista = cliente.get("/api/roteiros").json()
    assert [i["id"] for i in lista["itens"]] == [job["item_id"]]
    salvo = cliente.get(f"/api/roteiros/{job['item_id']}").json()
    assert salvo["pedido"]["tema"] == "rotina da noite" and salvo["meta"]["miniatura"].startswith("data:image")

    r2 = cliente.post("/api/ajustar", json={"resultado": job["resultado"], "meta": job["meta"], "pedido": pedido,
                                            "perfil": {}, "instrucao": "Mais curto", "item_id": job["item_id"]})
    _esperar(cliente, r2.json()["job_id"])
    ajustado = cliente.get(f"/api/roteiros/{job['item_id']}").json()
    assert ajustado["resultado"]["roteiro"]["titulo"] == "Versão ajustada"
    assert ajustado["anterior"]["roteiro"]["titulo"] == EXEMPLO["roteiro"]["titulo"] and ajustado["ajustes"] == 1

    # o celular manda a versão dele (migração / edição de checklist)
    ajustado["checklist"] = {"Gancho": True}
    ajustado["atualizado"] = ajustado["atualizado"] + 10
    assert cliente.put(f"/api/roteiros/{job['item_id']}", json=ajustado).json()["gravou"] is True
    assert cliente.put("/api/roteiros/outro", json=ajustado).status_code == 400
    assert cliente.put("/api/preferencias/perfil", json={"valor": {"jeito_de_falar": "amiga"}, "atualizado": 5}).json()["gravou"]
    assert cliente.get("/api/preferencias").json()["perfil"]["valor"]["jeito_de_falar"] == "amiga"
    assert cliente.put("/api/preferencias/senha", json={"valor": 1}).status_code == 400
    assert cliente.delete(f"/api/roteiros/{job['item_id']}").json()["ok"]
    assert cliente.get(f"/api/roteiros/{job['item_id']}").status_code == 404
