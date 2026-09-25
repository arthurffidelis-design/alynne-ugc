"""Banco de dados (Postgres do Render).

Guarda os roteiros e as preferências (perfil, inspirações, último pedido) para não
depender do celular. Sem DATABASE_URL o app continua funcionando só com o que fica
salvo no aparelho, como nas versões anteriores.

Regras de sincronização:
- Cada registro tem "atualizado" (ms). Só grava por cima quem é mais novo, então um
  aparelho com cópia antiga nunca apaga uma versão mais nova.
- Roteiro apagado vira "lápide" (apagado = true) para outro aparelho não ressuscitá-lo.
"""
import json
import logging
import threading
import time

from . import config

log = logging.getLogger("roteiro.db")

_pool = None
_status = "desligado"  # desligado | ok | erro
_trava = threading.Lock()

CHAVES_PREFERENCIAS = ("perfil", "inspiracoes", "ultimo_pedido")
LIMITE_ITEM_BYTES = 2_000_000

ESQUEMA = """
CREATE TABLE IF NOT EXISTS roteiros (
    id          TEXT PRIMARY KEY,
    criado      TIMESTAMPTZ NOT NULL,
    atualizado  TIMESTAMPTZ NOT NULL,
    apagado     BOOLEAN NOT NULL DEFAULT FALSE,
    dados       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS roteiros_criado_idx ON roteiros (criado DESC);

CREATE TABLE IF NOT EXISTS preferencias (
    chave       TEXT PRIMARY KEY,
    valor       JSONB NOT NULL,
    atualizado  TIMESTAMPTZ NOT NULL
);
"""


def agora_ms() -> int:
    return int(time.time() * 1000)


def status() -> str:
    return _status


def disponivel() -> bool:
    return _status == "ok"


def iniciar() -> str:
    """Abre o pool e cria as tabelas. Chamado na subida do app."""
    global _pool, _status
    with _trava:
        if not config.DATABASE_URL:
            _status = "desligado"
            return _status
        try:
            from psycopg_pool import ConnectionPool

            if _pool is None:
                _pool = ConnectionPool(
                    config.DATABASE_URL,
                    min_size=1,
                    max_size=4,
                    kwargs={"autocommit": True},
                    check=ConnectionPool.check_connection,
                    open=True,
                    timeout=15,
                )
            with _pool.connection() as con:
                con.execute(ESQUEMA)
            _status = "ok"
            log.info("Banco conectado.")
        except Exception:
            log.exception("Não consegui conectar ao banco")
            _status = "erro"
        return _status


def fechar():
    global _pool, _status
    with _trava:
        if _pool is not None:
            _pool.close()
            _pool = None
        _status = "desligado"


def _con():
    if not disponivel():
        raise RuntimeError("banco indisponível")
    return _pool.connection()


def _ms(valor) -> int:
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return agora_ms()


# ---------------------------------------------------------------- roteiros

def listar_roteiros() -> dict:
    """Resumo leve para a lista de "Meus roteiros" + ids apagados."""
    with _con() as con:
        linhas = con.execute(
            """
            SELECT id,
                   (extract(epoch FROM criado) * 1000)::bigint,
                   (extract(epoch FROM atualizado) * 1000)::bigint,
                   apagado,
                   dados #>> '{resultado,roteiro,titulo}',
                   dados #>> '{pedido,tema}',
                   dados #>> '{meta,miniatura}'
            FROM roteiros
            ORDER BY criado DESC
            """
        ).fetchall()
    itens, apagados = [], []
    for id_, criado, atualizado, apagado, titulo, tema, mini in linhas:
        if apagado:
            apagados.append(id_)
        else:
            itens.append(
                {"id": id_, "criado": criado, "atualizado": atualizado, "titulo": titulo or "Roteiro",
                 "tema": tema or "", "miniatura": mini or ""}
            )
    return {"itens": itens, "apagados": apagados}


def obter_roteiro(id_: str) -> dict | None:
    with _con() as con:
        linha = con.execute(
            "SELECT dados, (extract(epoch FROM atualizado) * 1000)::bigint FROM roteiros WHERE id = %s AND NOT apagado",
            (id_,),
        ).fetchone()
    if not linha:
        return None
    dados, atualizado = linha
    dados["atualizado"] = atualizado
    return dados


def salvar_roteiro(item: dict) -> bool:
    """Grava se for mais novo que o que já existe (e se não tiver sido apagado depois)."""
    if not isinstance(item, dict) or not item.get("id"):
        raise ValueError("roteiro sem id")
    texto = json.dumps(item, ensure_ascii=False)
    if len(texto.encode("utf-8")) > LIMITE_ITEM_BYTES:
        raise ValueError("roteiro grande demais")
    criado = _ms(item.get("criado"))
    atualizado = _ms(item.get("atualizado"))
    with _con() as con:
        cur = con.execute(
            """
            INSERT INTO roteiros (id, criado, atualizado, apagado, dados)
            VALUES (%s, to_timestamp(%s / 1000.0), to_timestamp(%s / 1000.0), FALSE, %s::jsonb)
            ON CONFLICT (id) DO UPDATE
               SET dados = EXCLUDED.dados, atualizado = EXCLUDED.atualizado, apagado = FALSE
             WHERE roteiros.atualizado <= EXCLUDED.atualizado AND NOT roteiros.apagado
            """,
            (str(item["id"])[:64], criado, atualizado, texto),
        )
        return cur.rowcount > 0


def apagar_roteiro(id_: str) -> None:
    with _con() as con:
        con.execute(
            """
            INSERT INTO roteiros (id, criado, atualizado, apagado, dados)
            VALUES (%s, now(), now(), TRUE, '{}'::jsonb)
            ON CONFLICT (id) DO UPDATE SET apagado = TRUE, dados = '{}'::jsonb, atualizado = now()
            """,
            (str(id_)[:64],),
        )


# ---------------------------------------------------------------- preferências

def preferencias() -> dict:
    with _con() as con:
        linhas = con.execute(
            "SELECT chave, valor, (extract(epoch FROM atualizado) * 1000)::bigint FROM preferencias"
        ).fetchall()
    return {chave: {"valor": valor, "atualizado": atualizado} for chave, valor, atualizado in linhas}


def salvar_preferencia(chave: str, valor, atualizado_ms=None) -> bool:
    if chave not in CHAVES_PREFERENCIAS:
        raise ValueError("preferência desconhecida")
    texto = json.dumps(valor, ensure_ascii=False)
    if len(texto.encode("utf-8")) > 200_000:
        raise ValueError("preferência grande demais")
    with _con() as con:
        cur = con.execute(
            """
            INSERT INTO preferencias (chave, valor, atualizado)
            VALUES (%s, %s::jsonb, to_timestamp(%s / 1000.0))
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, atualizado = EXCLUDED.atualizado
             WHERE preferencias.atualizado <= EXCLUDED.atualizado
            """,
            (chave, texto, _ms(atualizado_ms)),
        )
        return cur.rowcount > 0
