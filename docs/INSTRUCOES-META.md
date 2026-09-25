# Como criar o app no Meta for Developers (para a Análise de Perfil, v2.0)

O Alynne Studio vai ler os dados do Instagram da Alynne pela **API oficial do Instagram com login do Facebook**. É esse tipo de login que permite ver também os perfis de inspiração (Business Discovery). O app fica em **modo Desenvolvimento** para sempre: como é só para a conta dela, não precisa de revisão da Meta.

Tempo: uns 20 minutos. Os nomes dos menus aparecem em português, com o original em inglês entre parênteses caso o painel esteja em inglês.

## Antes de começar

- A conta @alynnedmoura precisa ser profissional (Criador ou Empresa) e estar ligada a uma Página do Facebook. Você já confirmou que está.
- Decida **quem vai autorizar a conexão**, porque no modo Desenvolvimento só quem tem papel no app consegue:
  - **Opção 1 (mais simples):** você, desde que seja administrador da Página do Facebook dela, com controle total. Confira na Página: Configurações > Acesso à Página.
  - **Opção 2:** a própria Alynne, adicionada como Testadora no app (passo 6).

## 1. Criar a conta de desenvolvedor

1. Acesse **developers.facebook.com** e entre com o seu Facebook.
2. Se for a primeira vez, clique em **Começar (Get Started)** e conclua o cadastro: aceitar os termos, confirmar e-mail/telefone e escolher "Desenvolvedor".

## 2. Criar o app

1. Clique em **Meus apps (My Apps)** e depois em **Criar app (Create App)**.
2. **Detalhes do app:** nome `Alynne Studio`, e-mail de contato seu. Clique em **Avançar**.
3. **Casos de uso:** role até o fim e escolha **Outro (Other)**. Avançar.
4. **Tipo de app:** escolha **Empresa (Business)**. Avançar.
5. **Portfólio empresarial:** se aparecer, pode seguir sem conectar agora.
6. Clique em **Criar app** e confirme a senha do Facebook.

## 3. Adicionar o Instagram

1. No painel do app, em **Adicionar produtos ao app (Add products to your app)**, ache **Instagram** e clique em **Configurar (Set up)**.
2. Escolha **Configuração da API com login do Facebook (API setup with Facebook login)**.

## 4. Adicionar o Login do Facebook para Empresas

1. Ainda em Adicionar produtos, ache **Login do Facebook para Empresas (Facebook Login for Business)** e clique em **Configurar**.
2. Vá em **Login do Facebook para Empresas > Configurações (Settings)**:
   - **URIs de redirecionamento do OAuth válidos (Valid OAuth Redirect URIs):**
     `https://roteiro-viral-alynne.onrender.com/api/meta/callback`
   - Deixe **Login do OAuth do cliente** e **Login do OAuth da Web** ligados.
   - Clique em **Salvar alterações**.
3. Vá em **Login do Facebook para Empresas > Configurações de login (Configurations)** e clique em **Criar configuração (Create configuration)**:
   - Nome: `Alynne Studio - leitura`
   - Tipo de token: **Token de acesso do usuário (User access token)**
   - Permissões (marque todas estas):
     - `instagram_basic`
     - `instagram_manage_insights`
     - `instagram_manage_comments`
     - `pages_show_list`
     - `pages_read_engagement`
     - `business_management`
   - Crie e **anote o ID da configuração (Configuration ID)**.

## 5. Pegar o ID e a chave secreta do app

1. Vá em **Configurações do app > Básico (App settings > Basic)**.
2. Anote o **ID do app (App ID)**.
3. Em **Chave secreta do app (App secret)**, clique em **Mostrar**, confirme a senha e copie.
4. Em **Domínios do app (App domains)**, coloque `roteiro-viral-alynne.onrender.com` e salve.

## 6. Dar papel para quem vai autorizar (só na opção 2)

1. Vá em **Funções do app > Funções (App roles > Roles)** e clique em **Adicionar pessoas (Add people)**.
2. Escolha **Testador (Tester)** e busque o Facebook da Alynne.
3. Ela aceita o convite em **developers.facebook.com/requests**. Se o site pedir, ela cria a conta de desenvolvedor em 2 minutos (passo 1).

## 7. Testar antes da v2.0 (opcional, 2 minutos)

1. Abra **developers.facebook.com/tools/explorer** (Explorador da Graph API).
2. À direita, escolha o app **Alynne Studio**. Em **Usuário ou Página**, escolha "Obter token de acesso do usuário".
3. Marque as permissões do passo 4 e clique em **Generate Access Token**. Na janela do Facebook, selecione a Página e a conta do Instagram dela.
4. No campo de consulta, cole:
   `me/accounts?fields=name,instagram_business_account{username,followers_count,media_count}`
   e clique em **Enviar**.
5. Se aparecer `"username": "alynnedmoura"`, está tudo certo.

## 8. Guardar as chaves no Render (não mande por chat)

No Render, abra o serviço **roteiro-viral-alynne** e vá em **Environment**. Crie as variáveis:

| Variável | Valor |
|---|---|
| `META_APP_ID` | ID do app (passo 5) |
| `META_APP_SECRET` | Chave secreta (passo 5) |
| `META_CONFIG_ID` | ID da configuração (passo 4) |

A chave secreta dá acesso ao app, então deixe só no Render.

## O que fica para a v2.0

- Botão **Conectar Instagram** na aba Análise. Quem tem papel no app autoriza uma vez e o Studio guarda o token da Página, que não expira.
- Rotina de toda segunda às 8h (Recife) para buscar os posts, as métricas, os comentários e os perfis de inspiração.
- Os perfis de inspiração precisam ser contas profissionais para a Meta liberar os dados. Se algum for conta pessoal, o Studio avisa.
- **Nunca publique o app (modo Ativo).** Em Desenvolvimento ele funciona para a conta dela sem revisão.
