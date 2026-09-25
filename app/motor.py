"""Motor de análise: monta o pedido para o Claude com os dados reais do vídeo e devolve o JSON."""
import base64
import json
import logging

from . import config, prompts

log = logging.getLogger("roteiro.motor")

PALAVRAS_POR_SEGUNDO = 2.5

MAPA_CRIAR = {
    "Reels": "Plataforma: Instagram Reels. Objetivo: alcance e engajamento.",
    "TikTok": "Plataforma: TikTok. Objetivo: alcance e retenção.",
    "UGC": "Formato UGC: vídeo com cara de conteúdo espontâneo mostrando um produto, que também serve para marca. Plataforma: Reels/TikTok.",
    "Conteúdo pessoal": "Objetivo: conexão e identificação com a vida real dela. Plataforma: Instagram Reels.",
    "Venda": "Objetivo: levar o público a comprar ou pedir o link do produto, sem cara de propaganda. Plataforma: Instagram Reels.",
    "Educativo": "Objetivo: ensinar algo prático que gere salvamento e compartilhamento. Plataforma: Instagram Reels.",
}


class ErroMotor(Exception):
    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def _fmt_num(n) -> str:
    if n is None:
        return "não disponível"
    return f"{n:,}".replace(",", ".")


def limite_palavras(duracao_s: int) -> int:
    return int(round(duracao_s * PALAVRAS_POR_SEGUNDO))


def bloco_perfil(perfil: dict) -> str:
    p = {**config.PERFIL_PADRAO, **{k: v for k, v in (perfil or {}).items() if isinstance(v, str)}}
    linhas = [
        "PERFIL DA CREATOR",
        f"Nome: {p.get('nome') or 'não informado'}",
        f"Instagram: {p.get('instagram') or 'não informado'}",
        f"Descrição: {p.get('descricao') or 'não informada'}",
        f"Público: {p.get('publico') or 'não informado (escolha coerente com a descrição)'}",
        f"Jeito de falar (expressões que ela usa): {p.get('jeito_de_falar') or 'não informado'}",
        f"Evitar (palavras/assuntos que ela não usa): {p.get('evitar') or 'não informado'}",
    ]
    return "\n".join(linhas)


def bloco_pedido(pedido: dict) -> str:
    criar = pedido.get("criar") or "Reels"
    try:
        duracao = int(str(pedido.get("duracao") or "30").rstrip("s"))
    except ValueError:
        duracao = 30
    estilo = pedido.get("estilo") or "Natural"
    linhas = [
        "PEDIDO DA CREATOR",
        f"O que ela quer criar: {criar}. {MAPA_CRIAR.get(criar, '')}",
        f"Nicho: {pedido.get('nicho') or 'não informado (use o perfil)'}",
        f"TEMA DO NOVO VÍDEO (obedecer literalmente): {pedido.get('tema') or 'NÃO INFORMADO (proponha um coerente com o perfil e avise)'}",
        f"Produto: {pedido.get('produto') or 'nenhum produto específico'}",
        f"Estilo desejado: {estilo}",
        f"Tom de voz: {estilo.lower()}, dentro do jeito descrito no perfil",
        f"Duração desejada: {duracao}s",
        f"LIMITE DE PALAVRAS FALADAS (cenas + CTA): cerca de {limite_palavras(duracao)} palavras",
    ]
    if pedido.get("observacoes"):
        linhas.append(f"Observações dela: {pedido['observacoes']}")
    return "\n".join(linhas)


def bloco_video(dados: dict) -> str:
    cortes = dados.get("cortes") or []
    dur = dados.get("duracao") or 0
    if cortes:
        planos = len(cortes) + 1
        media = dur / planos if planos else 0
        cortes_txt = (
            f"{len(cortes)} cortes detectados ({planos} planos, média de {media:.1f}s por plano). "
            f"Momentos dos cortes (s): {', '.join(f'{c:.1f}' for c in cortes[:60])}"
        )
    else:
        cortes_txt = "Nenhum corte detectado (provável plano único ou cortes muito suaves)."

    transcricao = dados.get("transcricao")
    if transcricao:
        trans_txt = transcricao
    elif dados.get("transcricao_status") == "sem_audio":
        trans_txt = "O vídeo não tem áudio."
    elif dados.get("transcricao_status") == "sem_chave":
        trans_txt = "Transcrição indisponível (fala não analisada). Baseie-se nos quadros e na legenda."
    elif dados.get("transcricao_status") == "falhou":
        trans_txt = "A transcrição falhou. Baseie-se nos quadros e na legenda."
    else:
        trans_txt = "Nenhuma fala detectada (vídeo provavelmente só com música ou sem voz)."

    linhas = [
        "DADOS DO VÍDEO ANALISADO (use só isto; não presuma o resto)",
        f"Origem: {dados.get('plataforma') or 'não informada'}",
        f"Autor: {dados.get('autor') or 'não disponível'}",
        f"Data de publicação: {dados.get('data') or 'não disponível'}",
        f"Visualizações: {_fmt_num(dados.get('views'))} | Curtidas: {_fmt_num(dados.get('likes'))} | Comentários: {_fmt_num(dados.get('comentarios'))}",
        f"Duração: {dur:.1f}s | Formato: {dados.get('largura')}x{dados.get('altura')}",
        f"Edição: {cortes_txt}",
        "",
        "Legenda original do post:",
        (dados.get("legenda") or "não disponível")[:2500],
        "",
        "Transcrição da fala (texto original, NÃO copiar):",
        trans_txt[:12000],
    ]
    return "\n".join(linhas)


# ------------------------------------------------------------------ formato JSON
# v1.0.1: o schema é grande demais para a "saída estruturada" da API (erro 400
# "compiled grammar is too large"). Agora o formato vai descrito no prompt e o
# app valida e completa o JSON do lado de cá, com 1 tentativa de correção.

def esqueleto(no: dict):
    """Modelo do JSON esperado, com a descrição de cada campo no lugar do valor."""
    tipo = no.get("type")
    if tipo == "object":
        return {k: esqueleto(v) for k, v in no["properties"].items()}
    if tipo == "array":
        return [esqueleto(no["items"])]
    if tipo == "boolean":
        return True
    return f"<{no.get('description', 'texto')}>"


def instrucao_json(schema: dict) -> str:
    return (
        "\n\n==================================================\n"
        "RESPOSTA EM JSON (obrigatório)\n"
        "==================================================\n"
        "Responda SOMENTE com um objeto JSON válido: sem texto antes ou depois, sem ``` e sem comentários.\n"
        "Use exatamente as chaves abaixo. Os textos entre < > explicam o que vai em cada campo (troque pelo "
        "conteúdo real). Listas levam quantos itens forem pedidos. Os campos true/false da checagem são booleanos.\n"
        + json.dumps(esqueleto(schema), ensure_ascii=False, indent=1)
    )


def extrair_json(texto: str) -> dict:
    t = (texto or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        inicio, fim = t.find("{"), t.rfind("}")
        if inicio < 0 or fim <= inicio:
            raise ValueError("sem objeto JSON na resposta")
        try:
            obj = json.loads(t[inicio : fim + 1])
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido: {e}")
    if not isinstance(obj, dict) or not isinstance(obj.get("roteiro"), dict):
        raise ValueError("JSON sem o roteiro")
    return obj


def normalizar(valor, no: dict):
    """Garante todas as chaves e tipos do schema, para a tela nunca quebrar."""
    tipo = no.get("type")
    if tipo == "object":
        base = valor if isinstance(valor, dict) else {}
        return {k: normalizar(base.get(k), v) for k, v in no["properties"].items()}
    if tipo == "array":
        if valor is None or valor == "":
            valor = []
        elif not isinstance(valor, list):
            valor = [valor]
        return [normalizar(v, no["items"]) for v in valor if v is not None and v != ""]
    if tipo == "boolean":
        if isinstance(valor, str):
            return valor.strip().lower() in ("true", "sim", "yes", "1")
        return bool(valor)
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


# ------------------------------------------------------------------ chamada

def _enviar(cliente, system: str, mensagens: list):
    import anthropic

    try:
        with cliente.messages.stream(
            model=config.CLAUDE_MODELO,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            system=system,
            messages=mensagens,
        ) as stream:
            final = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise ErroMotor("A chave da Anthropic (Claude) está inválida. Confira no Render.")
    except anthropic.RateLimitError:
        raise ErroMotor("Muitos pedidos seguidos para a IA. Espere um minuto e tente de novo.")
    except anthropic.APIStatusError as e:
        log.exception("Erro da API Claude")
        raise ErroMotor(f"A IA recusou o pedido ({e.status_code}). Tente de novo em instantes.")
    except anthropic.APIConnectionError:
        raise ErroMotor("Não consegui falar com a IA agora (conexão). Tente de novo.")

    if final.stop_reason == "refusal":
        raise ErroMotor("A IA não quis gerar esse roteiro. Tente mudar o tema ou o vídeo de referência.")
    if final.stop_reason == "max_tokens":
        raise ErroMotor("A resposta ficou grande demais e foi cortada. Tente uma duração menor.")
    return final


def _texto(final) -> str:
    return "".join(getattr(b, "text", "") for b in final.content if getattr(b, "type", "") == "text")


def _chamar_claude(system: str, conteudo: list, schema: dict) -> dict:
    if not config.ANTHROPIC_API_KEY:
        raise ErroMotor("Falta configurar a chave ANTHROPIC_API_KEY no Render.")

    import anthropic

    cliente = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=600, max_retries=2)
    system_final = system + instrucao_json(schema)
    mensagens = [{"role": "user", "content": conteudo}]

    final = _enviar(cliente, system_final, mensagens)
    texto = _texto(final)
    entrada = getattr(final.usage, "input_tokens", 0) or 0
    saida = getattr(final.usage, "output_tokens", 0) or 0
    try:
        bruto = extrair_json(texto)
    except ValueError as e:
        log.warning("Resposta fora do formato (%s). Pedindo correção.", e)
        if texto.strip():
            mensagens.append({"role": "assistant", "content": texto})
        mensagens.append(
            {
                "role": "user",
                "content": "A resposta anterior não veio como um objeto JSON válido e completo. "
                "Responda de novo SOMENTE com o objeto JSON completo, exatamente no formato pedido.",
            }
        )
        final = _enviar(cliente, system_final, mensagens)
        texto = _texto(final)
        entrada += getattr(final.usage, "input_tokens", 0) or 0
        saida += getattr(final.usage, "output_tokens", 0) or 0
        try:
            bruto = extrair_json(texto)
        except ValueError:
            log.error("Resposta inválida mesmo após correção: %s", texto[:500])
            raise ErroMotor("A IA devolveu um formato inesperado. Tente de novo.")

    resultado = normalizar(bruto, schema)
    resultado["_uso"] = {"modelo": config.CLAUDE_MODELO, "entrada": entrada, "saida": saida}
    return resultado


def gerar(dados_video: dict, quadros: list[tuple[float, bytes]], pedido: dict, perfil: dict) -> dict:
    system = prompts.PERSONA + prompts.CALIBRAGEM
    conteudo: list = [{"type": "text", "text": bloco_video(dados_video)}]
    if quadros:
        conteudo.append(
            {
                "type": "text",
                "text": f"QUADROS DO VÍDEO ({len(quadros)} imagens em ordem, com o segundo de cada uma):",
            }
        )
        for t, jpg in quadros:
            conteudo.append({"type": "text", "text": f"Quadro em {t:.1f}s"})
            conteudo.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(jpg).decode()},
                }
            )
    conteudo.append({"type": "text", "text": bloco_perfil(perfil) + "\n\n" + bloco_pedido(pedido)})
    conteudo.append(
        {
            "type": "text",
            "text": "Faça as etapas 1 a 5, rode a checagem de qualidade, revise o que for preciso e responda no JSON.",
        }
    )
    return _chamar_claude(system, conteudo, prompts.SCHEMA_COMPLETO)


def ajustar(resultado_atual: dict, dados_video: dict, pedido: dict, perfil: dict, instrucao: str) -> dict:
    system = prompts.PERSONA + prompts.CALIBRAGEM + prompts.INSTRUCAO_AJUSTE
    atual = {k: resultado_atual.get(k) for k in ("roteiro", "variacoes")}
    conteudo = [
        {"type": "text", "text": bloco_video(dados_video or {})},
        {
            "type": "text",
            "text": "ANÁLISE E FÓRMULA JÁ FEITAS (manter):\n"
            + json.dumps(
                {"analise": resultado_atual.get("analise"), "formula": resultado_atual.get("formula")},
                ensure_ascii=False,
            ),
        },
        {"type": "text", "text": "ROTEIRO ATUAL:\n" + json.dumps(atual, ensure_ascii=False)},
        {"type": "text", "text": bloco_perfil(perfil) + "\n\n" + bloco_pedido(pedido)},
        {"type": "text", "text": f"PEDIDO DE AJUSTE DA CREATOR: {instrucao}"},
    ]
    novo = _chamar_claude(system, conteudo, prompts.SCHEMA_AJUSTE)
    mesclado = {**resultado_atual, **novo}
    return mesclado
