# Atualização Roteiro Viral v1.0.1 (correção do erro 400)

**O que corrige:** o Claude recusava o pedido com "compiled grammar is too large". O formato da resposta agora vai descrito no prompt e o app valida o JSON do lado dele, com 1 tentativa automática de correção.

## Arquivos alterados (4)

- app/motor.py
- app/config.py (versão 1.0.1)
- app/static/index.html (força o navegador a pegar a versão nova)
- tests/test_app.py (18 testes passando)

## Como subir pelo GitHub web

1. Abra o repositório `roteiro-viral-alynne` no GitHub.
2. Clique em **Add file** e depois em **Upload files**.
3. Arraste as pastas **app** e **tests** deste zip. Elas contêm só os 4 arquivos alterados, e o GitHub mantém os caminhos e substitui os arquivos antigos. Não precisa arrastar este INSTRUCOES.md.
4. Clique em **Commit changes**.
5. O Render faz o deploy sozinho (2 a 4 minutos). Abra `/versao` e confira se aparece `"versao": "1.0.1"`.
6. Gere o roteiro de teste de novo.
