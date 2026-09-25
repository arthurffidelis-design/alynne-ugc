# Atualização Alynne Studio v1.1.1: banco de dados

**O que muda:**
- Roteiros, ajustes, checklist, Perfil da Creator, perfis de inspiração e as últimas escolhas do formulário passam a ficar salvos no banco **alynne-studio-db**.
- O mesmo histórico aparece em qualquer aparelho em que ela entrar.
- O roteiro é salvo no servidor assim que fica pronto. Se o celular fechar no meio, nada se perde.
- **Migração automática:** na primeira abertura depois da atualização, o que está no celular sobe sozinho para o banco e aparece o aviso "X roteiros salvos na nuvem".
- Roteiro apagado em um aparelho some dos outros também.

## Passo 1: ligar o banco ao app (Render)

1. No Render, abra o banco **alynne-studio-db** e vá em **Connections**. Copie a **Internal Database URL** (começa com `postgresql://`).
2. Abra o serviço **roteiro-viral-alynne** e vá em **Environment** > **Add Environment Variable**:
   - Key: `DATABASE_URL`
   - Value: a URL copiada
3. Clique em **Save Changes**. O Render reinicia o app, o que é normal.

## Passo 2: subir o código (GitHub web)

1. No repositório, clique em **Add file** e depois em **Upload files**.
2. Arraste a pasta **app**, a pasta **tests** e os arquivos **requirements.txt**, **render.yaml**, **README.md** e **.env.example**. Não precisa arrastar este INSTRUCOES.md.
3. Clique em **Commit changes**.

## Passo 3: conferir

Abra `/versao`. Precisa aparecer `"versao": "1.1.1"` e `"banco": "ok"`.

- `"banco": "desligado"`: a variável `DATABASE_URL` não foi salva.
- `"banco": "erro"`: a URL está errada. Confira se usou a **Internal** e não a External.

## Passo 4: no celular da Alynne

1. Ela abre o app **pelo mesmo atalho de sempre** (não apague o atalho). É dele que os roteiros antigos vão subir.
2. Aparece "X roteiros salvos na nuvem". Em **Perfil**, embaixo, aparece "versão 1.1.1 · salvo na nuvem".
3. Se ela também usou o app pelo navegador (Safari/Chrome), abrir por lá uma vez sobe o que estiver lá também.

A partir daqui, apagar e recriar o atalho não perde mais nada. Pode trocar para o ícone novo.
