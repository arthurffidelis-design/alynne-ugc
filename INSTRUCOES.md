# Como subir o Roteiro Viral (v1.0.0)

Repositório novo, tudo pela web (GitHub + Render). Leva uns 15 minutos.

## Antes de começar, tenha em mãos

- **Chave da Anthropic** (a mesma conta do Aurion serve): console.anthropic.com > API Keys.
- **Chave da OpenAI** (só para transcrever a fala): platform.openai.com > API keys. Coloque uns US$ 5 de crédito.
- **Uma senha** para a Alynne entrar no app.

## 1. GitHub

1. github.com > **New repository** > nome `roteiro-viral-alynne` > **Private** > Create.
2. Na tela do repositório vazio, clique em **uploading an existing file**.
3. Descompacte o zip no computador e arraste **o conteúdo** da pasta (as pastas `app` e `tests` e os arquivos soltos, inclusive `render.yaml`, `requirements.txt`, `.python-version`, `.gitignore`).
   - Se os arquivos que começam com ponto não aparecerem para arrastar, tudo bem: o app funciona sem eles. Só confira que `render.yaml` e `requirements.txt` subiram.
4. Confira que **não existe nenhum arquivo `.env`** com chaves. Só o `.env.example` (sem chaves reais).
5. **Commit changes**.

## 2. Render

1. dashboard.render.com > **New** > **Blueprint** > escolha o repositório `roteiro-viral-alynne`.
2. O Render lê o `render.yaml` e pede os valores:
   - `ANTHROPIC_API_KEY`: a chave da Anthropic
   - `OPENAI_API_KEY`: a chave da OpenAI
   - `APP_SENHA`: a senha da Alynne
   - `IG_COOKIES`: deixe vazio por enquanto
3. **Apply**. O primeiro deploy leva de 3 a 5 minutos.
4. O plano no blueprint é **Starter** (sem "hibernar"). Se quiser testar de graça, troque para Free em Settings; a primeira abertura depois de 15 min parado demora uns 50 segundos.

## 3. Conferir

Abra `https://roteiro-viral-alynne.onrender.com/versao` (ou a URL que o Render mostrar). Precisa aparecer:

```
"versao": "1.0.0", "claude": true, "openai": true
```

## 4. Primeiro teste

1. Abra o site, entre com a senha.
2. Teste com um link do **TikTok** (é o mais estável) e depois com um Reel do Instagram.
3. Se o Instagram bloquear, o app mostra o botão **Enviar o arquivo do vídeo**: grave a tela com som e envie. Funciona igual.

## 5. No celular da Alynne

- **iPhone**: abrir no Safari > botão Compartilhar > **Adicionar à Tela de Início**.
- **Android**: abrir no Chrome > menu ⋮ > **Instalar app**. Depois disso, no Instagram: Compartilhar > Roteiro, e o link já chega preenchido.
- Na primeira vez, abra **Perfil** e preencha "Seu jeito de falar" com expressões que ela usa de verdade. É o campo que mais melhora a voz dos roteiros.

## Se o download pelo Instagram falhar muito (opcional)

1. Em um computador, entre no Instagram com uma **conta secundária** (nunca a da Alynne).
2. Instale a extensão "Get cookies.txt LOCALLY" no Chrome e exporte os cookies de instagram.com.
3. Cole o conteúdo inteiro do arquivo em `IG_COOKIES` no Render (Environment) e salve. O Render reinicia sozinho.

## Atualizações futuras

Cada nova versão vem com o número em `/versao`. Depois de subir, sempre confira esse endereço.
