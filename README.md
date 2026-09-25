# Roteiro Viral

App web da Alynne (@alynnedmoura). Ela cola o link de um vídeo que viralizou (ou envia o arquivo), a IA assiste o vídeo, entende a estrutura que prendeu as pessoas e entrega um roteiro novo, com o tema dela e a voz dela, pronto para ler, gravar e editar.

Versão 1.0.0 (24/09/2026).

## O que ela faz no app

1. Cola o link (Instagram, TikTok, YouTube Shorts) ou envia o vídeo salvo/gravação de tela.
2. Escolhe o que quer criar (Reels, TikTok, UGC, Conteúdo pessoal, Venda, Educativo), nicho, tema do novo vídeo, produto, estilo e duração.
3. Toca em **✨ GERAR MEU ROTEIRO** e acompanha as etapas (1 a 2 minutos).
4. Recebe: por que o vídeo funcionou (fórmula viral), roteiro cena por cena (fala, o que mostrar, enquadramento, ação, texto na tela), CTA, legenda, edição, B-roll, 3 ganchos e 2 CTAs extras (com botão "Usar"), segunda ideia e checklist de gravação.
5. **Modo gravar**: tela escura, uma cena por vez, letra grande, para gravar lendo.
6. **Ajustar**: "Mais curto", "Mais do meu jeito de falar", "Outro gancho", "Outra ideia" ou texto livre. Dá para voltar para a versão anterior.
7. **Meus roteiros**: histórico salvo no aparelho. **Perfil da Creator**: descrição, público, jeito de falar e o que nunca usar.

Instalável na tela inicial (PWA). No Android, depois de instalado, o app aparece no menu "Compartilhar" do Instagram e do TikTok.

## Como a IA "assiste" o vídeo

```
link ──► yt-dlp baixa (até 720p) ──┐
arquivo enviado ───────────────────┤
                                   ▼
                ffmpeg: duração, cortes de edição (detecção de cena),
                até 16 quadros com o segundo de cada um (foco nos 3 primeiros
                segundos + 1 quadro depois de cada corte) e o áudio
                                   │
                OpenAI transcreve a fala (o Claude não escuta áudio)
                                   │
                Claude recebe: legenda, números do post, cortes, transcrição,
                quadros, perfil e pedido ──► JSON no formato da persona
```

A persona do motor está em `app/prompts.py` (texto original do direcionamento) com a **calibragem** que corrige o que a Alynne não gostou no material anterior: longo e teórico demais, não soava como ela, tema diferente do que ela queria.

## Estrutura

```
app/
  main.py          rotas, senha, fila de processamento, /versao
  video.py         download (yt-dlp), cortes, quadros e áudio (ffmpeg)
  transcricao.py   fala do vídeo (OpenAI)
  motor.py         monta o pedido e chama o Claude (saída JSON com schema)
  prompts.py       persona + calibragem + schema de saída
  config.py        variáveis de ambiente e perfil padrão da Alynne
  static/          tela (HTML, CSS, JS), ícones, manifest e service worker
tests/             testes de regressão (sem chamar as IAs)
render.yaml        blueprint do Render
```

## Variáveis de ambiente (Render > Environment)

| Variável | Obrigatória | Para quê |
|---|---|---|
| `ANTHROPIC_API_KEY` | sim | Claude escreve a análise e o roteiro |
| `OPENAI_API_KEY` | recomendada | transcrever a fala do vídeo. Sem ela, a análise usa só imagens e legenda |
| `APP_SENHA` | sim | senha de entrada (a sessão dura 90 dias no aparelho) |
| `SECRET_KEY` | sim | assina a sessão (o blueprint gera sozinho) |
| `CLAUDE_MODELO` | não | padrão `claude-opus-5-5`. `claude-sonnet-5` custa metade |
| `TRANSCRICAO_MODELOS` | não | ordem de tentativa, padrão `gpt-transcribe,gpt-4o-transcribe,whisper-1` |
| `IG_COOKIES` | não | cookies de uma conta secundária do Instagram (formato Netscape) para o download pelo link falhar menos |
| `MAX_UPLOAD_MB`, `MAX_QUADROS`, `MAX_DURACAO_S` | não | limites (200 MB, 16 quadros, 300 s) |

## Custo estimado por roteiro

Com `claude-opus-5-5`: cerca de 15 a 20 mil tokens de entrada (quadros + textos) e 6 a 10 mil de saída, algo entre US$ 0,15 e US$ 0,30. A transcrição de um Reel custa menos de 1 centavo de dólar. Um ajuste custa menos que a geração (não reenvia os quadros).

## Limite conhecido: Instagram

O Instagram bloqueia downloads vindos de servidores (erro 429). Quando isso acontece o app avisa e oferece enviar o arquivo. Para diminuir os bloqueios, configure `IG_COOKIES` com cookies de uma **conta secundária** (nunca a conta principal da Alynne). TikTok funciona pelo link normalmente.

O `yt-dlp` é instalado na versão mais nova a cada deploy. Se o download pelo link parar de funcionar, faça **Manual Deploy > Clear build cache & deploy** no Render.

## Testes

```
pip install -r requirements-dev.txt
pytest -q
```
