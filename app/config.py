"""Configuração do app. Tudo vem de variáveis de ambiente (Render > Environment)."""
import os

VERSAO = "1.0.1"
DATA_VERSAO = "2026-09-25"

APP_NOME = os.getenv("APP_NOME", "Roteiro Viral")

# Chaves das IAs
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Modelo que escreve a análise e o roteiro (pode trocar sem mexer no código)
CLAUDE_MODELO = os.getenv("CLAUDE_MODELO", "claude-opus-5-5").strip()
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "32000"))

# Modelos de transcrição, em ordem de tentativa (separados por vírgula)
TRANSCRICAO_MODELOS = [
    m.strip()
    for m in os.getenv("TRANSCRICAO_MODELOS", "gpt-transcribe,gpt-4o-transcribe,whisper-1").split(",")
    if m.strip()
]

# Acesso
APP_SENHA = os.getenv("APP_SENHA", "").strip()
SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-no-render")
SESSAO_DIAS = int(os.getenv("SESSAO_DIAS", "90"))

# Vídeo
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
MAX_DURACAO_S = int(os.getenv("MAX_DURACAO_S", "300"))  # vídeos até 5 min
MAX_QUADROS = int(os.getenv("MAX_QUADROS", "16"))
LARGURA_QUADRO = int(os.getenv("LARGURA_QUADRO", "512"))

# Cookies do Instagram em formato Netscape (opcional, melhora muito o download pelo link)
IG_COOKIES = os.getenv("IG_COOKIES", "").strip()

# Perfil padrão da creator (fica salvo no app e pode ser editado na tela Perfil)
PERFIL_PADRAO = {
    "nome": "Alynne",
    "instagram": "@alynnedmoura",
    "descricao": (
        "Creator brasileira de lifestyle, fitness e beleza. Comunicação natural, feminina, "
        "próxima e espontânea. Conteúdo com aparência de rotina real, evitando linguagem "
        "excessivamente publicitária. Prioriza storytelling, identificação, experiências "
        "pessoais, dicas práticas e conversas entre amigas. Visual clean, sofisticado e natural."
    ),
    "publico": "",
    "jeito_de_falar": "",
    "evitar": "",
}
