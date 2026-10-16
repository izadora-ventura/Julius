# JULIUS — passos que dependem de você

Tudo o que dava para fazer e testar automaticamente já está feito. Os itens abaixo exigem uma conta sua, uma chave ou uma decisão. Nenhum deles tem custo: todos usam planos gratuitos.

Nunca cole chaves ou senhas no código nem as envie ao GitHub. Elas vão só no arquivo `backend/.env`, que fica fora do Git, ou no painel do serviço de hospedagem.

---

## 1. Ligar a IA (Gemini, grátis) — opcional

1. Acesse https://aistudio.google.com/apikey com sua conta Google e clique em **Create API key**.
2. Abra `C:\dev\julius\backend\.env` no Bloco de Notas. Se o arquivo não existir, rode primeiro o `scripts\setup.ps1`.
3. Altere estas duas linhas:
   ```
   AI_PROVIDER=gemini
   GEMINI_API_KEY=cole-a-chave-aqui
   ```
   Se usar a versão de computador (`JULIUS.exe`), faça o mesmo em `%LOCALAPPDATA%\JULIUS\julius.env`.
4. Reinicie o JULIUS e pergunte algo aberto no Assistente, como "me dê dicas para economizar". A resposta deve vir marcada como IA.

**Se der errado:** se aparecer "IA indisponível", confira se a chave foi copiada inteira e sem espaços. O app continua funcionando sem IA, com as regras locais.

## 2. Ligar a busca na web do agente — opcional

Requer o passo 1.

1. No mesmo `.env`, mude para `WEB_SEARCH_ENABLED=true`.
2. Sem mais nada, a busca usa o DuckDuckGo, que não pede chave.
3. Para resultados mais estáveis, crie uma chave grátis no Tavily (https://tavily.com) e preencha `TAVILY_API_KEY=`.
4. Reinicie o JULIUS e pergunte "qual a taxa Selic hoje?".

**Atenção:** o texto da busca vai para o provedor externo. O agente é instruído a não incluir seus dados, mas, se isso for uma preocupação, deixe a busca desligada.

## 3. Publicar na internet (Render + Neon, grátis) — opcional

Com isso, celular e outros computadores acessam o JULIUS de qualquer lugar.

1. **Banco:** crie uma conta em https://neon.tech e depois um projeto. Copie a *connection string* e troque o começo `postgresql://` por `postgresql+psycopg://`.
2. **Servidor:** crie uma conta em https://render.com e entre com o GitHub. Vá em **New → Blueprint** e escolha o repositório `izadora-ventura/Julius`. O `render.yaml` já define tudo.
3. Quando o Render pedir, preencha `DATABASE_URL` com a string do passo 1. Se quiser IA, preencha também `GEMINI_API_KEY` e mude `AI_PROVIDER` para `gemini`. O `SECRET_KEY` é gerado sozinho.
4. Aguarde o deploy (5–10 min) e abra o endereço `https://….onrender.com`.
5. Crie sua conta no app. Depois, no Render, mude `ALLOW_REGISTRATION` para `false`, para que ninguém mais se cadastre.
6. No celular, abra o endereço e escolha **Adicionar à tela inicial**.

**Observações:**
- O plano grátis "dorme" após 15 min sem uso; o primeiro acesso depois disso leva cerca de 1 min.
- Este passo não foi executado por mim porque exige suas contas. O Dockerfile e o PostgreSQL ainda não rodaram nesta máquina; o primeiro deploy é a validação real.

## 4. Ligar o PC ao servidor publicado — opcional

Requer o passo 3.

No JULIUS do PC, vá em **Ajustes → Sincronização**, informe o endereço do Render, seu e-mail e sua senha, e clique em **Vincular e sincronizar**. Depois, use **Sincronizar agora** sempre que quiser. Divergências aparecem como conflitos para você decidir.

## 5. Usar em outro aparelho da mesma rede, sem internet — opcional

1. No PC principal, rode: `powershell -ExecutionPolicy Bypass -File scripts\start-lan.ps1`.
2. Quando o Windows perguntar, permita o acesso **somente em redes privadas**.
3. No outro aparelho, abra o endereço que o script mostrar, por exemplo `http://192.168.0.10:8010`.

Use isso só na rede de casa. A conexão é HTTP, sem criptografia.

## 6. Ativar a verificação antes de cada commit — opcional, para quem programa

```powershell
cd C:\dev\julius
& "$env:USERPROFILE\.venvs\julius\Scripts\pre-commit.exe" install
```

## 7. Distribuir o executável — opcional

O `JULIUS.exe` (pasta `C:\dev\julius-build\dist\JULIUS`) **não** deve ir para o Git: são cerca de 58 MB de binários que incham o repositório para sempre. Para compartilhá-lo:

1. Compacte a pasta `dist\JULIUS` em um `.zip`.
2. No GitHub, abra o repositório e vá em **Releases → Draft a new release**. Crie uma tag como `v1.1.0`, anexe o `.zip` e publique.

Para gerar de novo, siga [desktop/README.md](desktop/README.md).

## 8. Repositório original — informativo

O repositório original (`matheusenaa/JULIUS`) tem binários versionados: `JULIUS-PORTABLE.zip` em dois lugares, com cerca de 40 MB cada, e a pasta `JULIUS-Installer`. Também tem um submódulo quebrado chamado `Julius`, sem `.gitmodules`. Nada disso foi trazido para cá.

Se você tiver acesso a esse repositório e quiser limpá-lo, isso é uma decisão do dono dele. Eu não alterei o original.
