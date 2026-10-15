# Documentação técnica

**n8n AI Workflow Engineering — V0.1**

Esta ferramenta existe para duas coisas que costumam ser misturadas: **desenhar** um workflow n8n como código e **ensaiá-lo num ambiente separado** antes de qualquer escrita em produção. O agente (ou o desenvolvedor) propõe o JSON. O Engineering Core valida, varre secrets, compara com o que já existe na instância alvo, gera um plano e só escreve na API quando alguém pede `--apply`. A execução de teste continua humana, na interface do n8n de pré-análise.

O runtime de produção nunca é o primeiro destino.

---

## 1. O que a ferramenta faz e o que ela deixa de fora

| Faz | Não faz |
|-----|---------|
| Valida estrutura, conexões e expressões do JSON | Interpretar linguagem natural |
| Bloqueia secrets embutidos e credenciais com `data` | Guardar ou descriptografar credenciais |
| Faz dry-run de create e update | Ativar, desativar, apagar ou executar workflows |
| Tira snapshot local antes do plano | Escrever no n8n sem `--apply` |
| Cria e atualiza via Public API, workflow novo **inativo** | Republicar um workflow ativo sem autorização explícita |
| Exporta e compara o JSON local com o remoto | Promover sozinha de um ambiente para outro |

A separação de ambientes é **operacional**, não um comando `promote`. A CLI fala com **uma** instância por vez, definida por `N8N_BASE_URL` e `N8N_API_KEY_FILE`. Pré-análise e produção são duas instâncias n8n distintas, cada uma com a sua API key, as suas credenciais e o seu diretório de backup. O mesmo arquivo JSON atravessa os dois, passando de novo pelos mesmos gates.

---

## 2. Modelo de dois ambientes

```text
Requisito
    │
    ▼
Agente / desenvolvedor escreve JSON
    │
    ▼
Pré-análise offline          validate --offline
(sem rede)                   secret scan, estrutura, expressões
    │
    ▼
Ambiente de pré-análise      N8N_BASE_URL = n8n de teste
(instância separada)         dry-run → backup → create --apply (inativo)
                             teste manual na UI desse n8n
                             export + diff
    │
    ▼
Revisão humana               o plano e o resultado do teste são aceitos
    │
    ▼
Produção                     OUTRA URL, OUTRA API key
                             dry-run de novo (nomes e webhooks de produção)
                             backup de produção → create/update --apply
                             ativação continua na UI de produção
```

Por que o ensaio não pode ser só o dry-run: o dry-run prova que o JSON é aceitável e que a escrita **seria** segura. Ele não dispara o fluxo, não chama APIs externas e não mostra o dado que cada nó produziria. Esse ensaio acontece na instância de pré-análise, com o workflow criado **desligado**, executado à mão pelo operador.

Por que a produção não herda o “ok” da pré-análise: nomes duplicados, paths de webhook e IDs de credencial são **locais da instância**. Um workflow válido no n8n de teste pode colidir com outro nome ou outro webhook em produção, e o `id` de credencial do ambiente de teste não existe no de produção.

### O que muda entre os ambientes

| Item | Pré-análise | Produção |
|------|-------------|----------|
| Instância n8n | Local, Docker ou staging dedicado | A instância que atende o negócio |
| `N8N_BASE_URL` | URL dessa instância | URL de produção |
| API key | Arquivo próprio, escopos de workflow | Arquivo próprio, nunca a mesma key |
| Credenciais n8n | Contas, tokens e bancos de teste | Credenciais reais; só referência `id` / `name` |
| `BACKUP_DIRECTORY` | Snapshot do ambiente de teste | Snapshot de produção, separado |
| `WORKFLOW_DIRECTORY` | Pode ser o mesmo repositório | O mesmo JSON versionado |
| Ativação | Não. O fluxo nasce inativo e o teste é manual | Não, pela CLI. Ativação é decisão humana na UI |

Recomendação de layout local, sem commitar segredos:

```text
.secrets/n8n-api-key-staging
.secrets/n8n-api-key-prod
backups/staging/
backups/prod/
```

Dois arquivos de ambiente, por exemplo `.env.staging` e `.env.prod`, cada um com a sua URL, a sua key e o seu diretório de backup. A CLI carrega `.env` por padrão (`src/config/settings.py`). Para apontar outro arquivo, exporte as variáveis antes do comando ou passe o arquivo certo para `load_settings()` se estiver usando o Core em Python. Variáveis já presentes no ambiente **não** são sobrescritas pelo `.env`.

---

## 3. Arquitetura

```text
Consumidor (humano, Cursor, Claude Code, Codex, script, CI)
        │
        ▼
CLI  bin/n8n-workflow-manager  →  src/cli.py
        │
        ▼
Engineering Core
  config/        resolve URL, key file, diretórios
  validation/    estrutura + secret scan (funciona offline)
  api/           cliente HTTP + payload gravável
  deployment/    plano, backup, diff, create, update
        │
        ▼
n8n Public API   X-N8N-API-KEY
        │
        ▼
Instância n8n apontada pela configuração
(pré-análise OU produção — nunca as duas ao mesmo tempo)
```

O Core não importa SDK de nenhum agente. Qualquer cliente que edite JSON e rode shell usa a mesma superfície. MCP, REST própria e Web UI estão no roadmap e, quando existirem, devem chamar este Core em vez de falar com a API do n8n por fora dos gates.

### Módulos

| Caminho | Responsabilidade |
|---------|------------------|
| `bin/n8n-workflow-manager` | Launcher. Define `PYTHONPATH` e executa `src/cli.py` |
| `src/cli.py` | Comandos, códigos de saída, recusa de `activate` / `delete` / `execute` |
| `src/config/settings.py` | `N8N_BASE_URL`, arquivo da API key, diretórios |
| `src/validation/workflow.py` | Campos obrigatórios, nós, conexões, webhooks, expressões |
| `src/validation/secrets.py` | Heurística de segredo inline. Nunca ecoa o valor |
| `src/api/client.py` | `GET/POST/PUT /api/v1/workflows`. Não loga a key |
| `src/api/payload.py` | Recorta o JSON para o contrato de escrita da Public API |
| `src/deployment/manager.py` | Ciclo dry-run / apply, proteção de workflow ativo |
| `src/deployment/backup.py` | Snapshot timestampado + `MANIFEST.txt` |
| `src/deployment/diff.py` | Comparação normalizada local × remoto |

### Por que Public API, e não o banco do n8n

Escrever direto no Postgres do n8n contorna invariantes do produto (versão, credenciais, estado ativo). A Public API é o contrato suportado. O cliente usa só:

- `GET /api/v1/workflows` (paginado, `limit=100`, `cursor`)
- `GET /api/v1/workflows/{id}`
- `POST /api/v1/workflows`
- `PUT /api/v1/workflows/{id}`

Header: `X-N8N-API-KEY`. Timeout padrão: 60s. Respostas 401/403 não devolvem o corpo. Corpos de erro são truncados em 500 caracteres e redactados se parecerem conter a key.

Escopos recomendados da API key: `workflow:list`, `workflow:read`, `workflow:create`, `workflow:update`. Não conceder activate, delete nem execute ao agente — a CLI não chama esses endpoints, e a key também não deveria poder.

---

## 4. Contrato do workflow

O arquivo local é a intenção versionada. O n8n é a verdade em runtime. O JSON aceito é um objeto (ou um array cujo primeiro item é o objeto) com:

| Campo | Regra |
|-------|--------|
| `name` | String não vazia. No create, não pode repetir um nome remoto |
| `nodes` | Array não vazio. Cada nó tem `name` e `type` únicos no fluxo |
| `connections` | Objeto. Origem e destino precisam existir em `nodes` |
| `settings` | Objeto. Na escrita, só chaves da allowlist vão para a API |

Nós conhecidos como gatilho (`manualTrigger`, `webhook`, `scheduleTrigger`, `cron`, `errorTrigger`) podem ficar sem entrada. Qualquer outro nó, num fluxo com mais de um nó, precisa estar ligado. Um gatilho sem saída também é erro.

Expressões `{{ ... }}` e strings que começam com `=` precisam ter chaves balanceadas.

### Credenciais

Cada referência aceita somente `id` e `name`. Chave extra, em especial `data`, reprova a validação. Na exportação, `sanitize_credential_refs` corta de novo qualquer coisa além de `id` / `name`.

Consequência prática da pré-análise: o `id` criado no n8n de teste **não viaja** para produção. No JSON que será aplicado em produção, troque a referência para o `id` / `name` da credencial que já existe na instância de produção. Segredo continua fora do Git; o que entra no arquivo é o ponteiro.

Referências `$env.NOME` são permitidas pelo secret scan. Valor literal longo em campo com nome sensível (`password`, `token`, `api_key`, `authorization`, etc.) é bloqueado.

### Payload de escrita

`to_write_payload` monta o corpo do `POST`/`PUT` e descarta o resto (`id`, `active`, `versionId`, metadados de leitura). Settings permitidos:

`saveExecutionProgress`, `saveManualExecutions`, `saveDataErrorExecution`, `saveDataSuccessExecution`, `executionTimeout`, `errorWorkflow`, `timezone`, `executionOrder`, `callerPolicy`, `callerIds`, `timeSavedPerExecution`, `availableInMCP`.

Nós saem só com as chaves operacionais (`id`, `name`, `type`, `typeVersion`, `position`, `parameters`, `credentials`, `disabled`, `notes`, retry, `onError`, `webhookId`, entre outras da allowlist em `src/api/payload.py`). `staticData` e `pinData` são encaminhados quando presentes — úteis para reproduzir um caso de teste pinado no ambiente de pré-análise, e por isso devem ser revistos antes de irem para produção.

---

## 5. Pipeline de pré-análise

Cada etapa responde uma pergunta diferente. Nenhuma delas substitui as outras.

### 5.1 Validação offline

```bash
./bin/n8n-workflow-manager validate workflows/meu-fluxo.json --offline
```

Não usa rede. Confere JSON, campos, nomes duplicados, conexões quebradas, expressões e secrets. É o primeiro filtro, antes mesmo de existir instância de teste no ar. Saída: JSON `{"ok", "errors", "name"}`. Exit `0` se passou, `2` se não.

Sem `--offline`, e com API key presente, a validação também enriquece com a lista remota da instância **atual**: nome já existente e path de webhook já usado. Esse enriquecimento é o que torna a pré-análise específica do ambiente. Rodar `validate` contra staging não prova nada sobre produção.

### 5.2 Secret scan

Roda dentro de `validate_workflow`. Detecta, sem imprimir o valor:

- bloco PEM / private key
- string no formato de JWT
- token `n8n_api_…`
- `Bearer` literal sem `$env`
- campo de nome sensível com literal longo

### 5.3 Plano (dry-run)

```bash
./bin/n8n-workflow-manager dry-run-create workflows/meu-fluxo.json
./bin/n8n-workflow-manager dry-run-update "Nome do fluxo" workflows/meu-fluxo.json
```

`create` e `update` sem `--apply` fazem a mesma coisa. Ordem interna:

1. Lista os workflows remotos da instância apontada.
2. Grava um backup local dessa lista em `BACKUP_DIRECTORY/<UTC timestamp>/`.
3. Valida o arquivo no modo `create` ou `update`.
4. Monta o payload de escrita e devolve um resumo: nome, quantidade de nós, origens de conexão, chaves de settings, se há credencial.
5. **Não chama** `POST` nem `PUT`.

O backup acontece mesmo no dry-run. O objetivo é ter um snapshot do ambiente antes de qualquer decisão de aplicar, inclusive quando o plano falha.

O objeto `PlanResult` impresso contém `mode`, `apply`, `ok`, `errors`, `name`, `payload_summary`, `wrote` e, quando houver, `remote`, `result`, `backup_path`.

### 5.4 Create no ambiente de pré-análise

```bash
./bin/n8n-workflow-manager create workflows/meu-fluxo.json --apply
```

Só depois do plano aprovado. A API cria o workflow. Se a resposta vier com `active=true`, a CLI marca o plano como falho (`safety abort`) e não trata isso como sucesso — workflow novo precisa nascer inativo. Em seguida o JSON devolvido, já sanitizado, é salvo em `WORKFLOW_DIRECTORY`.

O teste funcional é o passo seguinte, **fora** da CLI: abrir esse workflow na UI do n8n de pré-análise e executar manualmente (Manual Trigger, ou webhook de teste, com dados que não sejam de produção). Inspecionar a execução. Ajustar o JSON. Repetir validate → dry-run → update.

`update` de um workflow remoto com `active=true` é recusado (exit `3`), a menos que se passe `--allow-active-update`. No ambiente de pré-análise isso quase nunca deve ser necessário, porque o fluxo foi criado inativo. Em produção, esse flag é uma autorização explícita para alterar automação que já está ligada.

### 5.5 Export e diff

```bash
./bin/n8n-workflow-manager export "Nome do fluxo"
./bin/n8n-workflow-manager diff "Nome do fluxo"
```

`diff` normaliza `id`, `name`, `active`, `description`, `nodes`, `connections`, `settings`, `staticData`, `pinData`, reduz credenciais a `id`/`name` e compara o arquivo em `WORKFLOW_DIRECTORY` com o remoto. Exit `0` se idêntico, `1` se houver diferença.

Depois de um `update --apply`, `result.differed_from_proposed` pode ser `true` porque a API devolve metadados que o arquivo proposto não tinha. A convergência real é `export` + `diff`, não esse booleano.

### 5.6 O que observar na pré-análise

Antes de levar o mesmo JSON para produção, o relatório humano deve conseguir responder:

- O plano passou sem erro de estrutura, secret, nome ou webhook?
- O workflow foi criado inativo?
- A execução manual no n8n de teste percorreu o caminho esperado, inclusive ramos de erro?
- Credenciais apontam para recursos de teste, e o JSON de produção será reapontado?
- `pinData` / `staticData` de teste foram removidos ou substituídos?
- O backup do ambiente de teste existe e o diff local × remoto está limpo?

---

## 6. Promoção para produção

A promoção é repetir o pipeline contra **outra** configuração. Não há atalho.

1. Confirme que o shell aponta para produção: `./bin/n8n-workflow-manager status` deve mostrar a URL de produção e o arquivo de key de produção.
2. Ajuste credenciais do JSON para os IDs dessa instância. Não copie o `id` do ambiente de teste.
3. `validate <arquivo>` **sem** `--offline`, para pegar colisão de nome e de webhook **em produção**.
4. `dry-run-create` (fluxo novo) ou `dry-run-update` (fluxo que já existe lá). Leia `backup_path` e `errors`.
5. Só então `create … --apply` ou `update … --apply`.
6. `export` e `diff`.
7. Ative na UI de produção quando o diff e a revisão fecharem. A CLI da V0.1 não ativa.

Se o plano falhar em produção depois de ter passado na pré-análise, o motivo esperado é contexto da instância (nome, webhook, credencial, workflow ativo), não uma regressão silenciosa do JSON. Corrija o arquivo e rode o dry-run de novo. Não use `--allow-active-update` para “forçar” a subida.

### Rollback

1. Ache o diretório timestampado em `BACKUP_DIRECTORY` (o `MANIFEST.txt` lista `id|nome`).
2. Copie o JSON desejado para o arquivo de trabalho.
3. `dry-run-update` e, se o plano fechar, `update … --apply`.
4. A UI do n8n também guarda histórico de versão; use-o se o snapshot local não bastar.

O backup é uma fotografia sanitizada do que a API devolveu naquele momento. Não inclui segredo de credencial. Não substitui backup de infraestrutura da instância.

---

## 7. Referência da CLI

```bash
./bin/n8n-workflow-manager <comando> [args]
```

| Comando | Efeito | Toca a API |
|---------|--------|------------|
| `status` | URL, paths, contagem local e lista remota | Leitura, se a key existir |
| `list` | `ID`, `ACTIVE`, `NAME` | Leitura |
| `validate <file> [--mode create\|update] [--offline]` | Relatório de erros | Leitura, salvo `--offline` |
| `dry-run-create <file>` | Plano de criação | Leitura + backup local |
| `create <file> [--apply]` | Plano; escreve só com `--apply` | Escrita só com `--apply` |
| `dry-run-update <workflow> <file>` | Plano de atualização; recusa ativo | Leitura + backup local |
| `update <workflow> <file> [--apply] [--allow-active-update]` | Plano; escreve só com `--apply` | Escrita só com `--apply` |
| `export <workflow>` | Um JSON sanitizado em `WORKFLOW_DIRECTORY` | Leitura |
| `export-all` | Todos os remotos | Leitura |
| `diff <workflow>` | Unified diff normalizado | Leitura |
| `backup` | Snapshot de todos os remotos | Leitura |

`<workflow>` aceita id, nome exato ou slug do nome (`"Hello World"` e `hello-world` resolvem o mesmo remoto).

`publish`, `activate`, `deactivate`, `delete` e `execute` são recusados de propósito, mesmo que alguém os passe como comando.

### Códigos de saída

| Código | Significado |
|--------|-------------|
| 0 | Sucesso. Em `diff`, também significa “idêntico” |
| 1 | Erro genérico (key ausente, fluxo não encontrado, conexão) |
| 2 | Validação ou plano reprovado |
| 3 | Update bloqueado porque o remoto está ativo |
| 130 | Interrompido (Ctrl+C) |

### Configuração

| Variável | Função | Padrão |
|----------|--------|--------|
| `N8N_BASE_URL` | Origem da instância | `http://localhost:5678` |
| `N8N_API_BASE` | Base `/api/v1` explícita, se precisar sobrepor | derivada da URL |
| `N8N_API_KEY_FILE` | Arquivo com a key em uma linha, sem aspas | `.secrets/n8n-api-key` |
| `WORKFLOW_DIRECTORY` | JSON exportado / intenção local | `./workflows` |
| `BACKUP_DIRECTORY` | Snapshots | `./backups/git-backups` |
| `TEMPLATES_DIRECTORY` | Esqueletos | `./templates` |
| `N8N_CONTAINER` | Nome opcional de container; a API continua sendo o canal | vazio |
| `N8N_PREFER_DOCKER_CLI` | Flag reservada na configuração | desligada |

A key é lida uma vez e vai só para o header. Permissão recomendada do arquivo: `chmod 600`. `.env`, `.secrets/` e backups com payload de negócio ficam fora do Git.

---

## 8. Gates de segurança

| Gate | Onde | Comportamento |
|------|------|----------------|
| Dry-run por padrão | `create` / `update` | Sem `--apply`, `wrote` permanece `false` |
| Create inativo | `WorkflowManager.create` | `active=true` na resposta aborta o sucesso |
| Workflow ativo | `WorkflowManager.update` | Recusa, salvo `--allow-active-update` |
| Secret scan | `validation/secrets.py` | Erro de validação; valor não é impresso |
| Forma da credencial | `validate_workflow` | Só `id` e `name` |
| Nome duplicado | modo `create` + lista remota | Erro com id remoto |
| Webhook duplicado | dentro do arquivo e contra os remotos | No update, ignora o próprio workflow |
| Backup antes do plano | `create` / `update` | Diretório UTC + manifesto |
| Redação de erro HTTP | `N8nApiClient` | 401/403 sem corpo; key não volta no texto |

`WorkflowManager` aceita `create_fn`, `update_fn`, `list_fn` e `get_fn` injetáveis. Os testes usam isso para exercer os gates sem instância real. `skip_backup=True` existe para esse uso; a CLI não expõe skip.

---

## 9. Agentes de IA

O Core não gera o fluxo a partir de uma frase. O agente externo faz o desenho; a CLI é o único caminho até a API.

Loop esperado, sempre contra o ambiente de pré-análise primeiro:

1. Rascunhar JSON a partir de `templates/minimal-manual.json` ou de um exemplo em `workflows/examples/`.
2. `validate <file> --offline`.
3. `dry-run-create` ou `dry-run-update` na instância de teste.
4. Mostrar o plano e parar.
5. `--apply` só com aprovação explícita.
6. O humano testa na UI do n8n de pré-análise.
7. `export` + `diff`.
8. Repetir o dry-run na configuração de produção antes de aplicar lá.

Prompts de partida: `examples/prompts/cursor.md`, `examples/prompts/claude-code.md`, `examples/prompts/codex.md`.

---

## 10. Testes da própria ferramenta

Testes unitários não precisam de n8n. Cobrem JSON inválido, secret scan, conexão quebrada, webhook duplicado, dry-run que não escreve, recusa de update ativo e create que aborta se a resposta vier ativa.

```bash
./bin/run-tests
```

Teste de integração (`tests/integration/test_api_live.py`) lista workflows de verdade e fica desligado salvo `N8N_INTEGRATION=1`. Aponte esse teste para a instância de pré-análise, nunca para produção, como procedimento padrão.

---

## 11. Limitações da V0.1

- Uma instância por processo. Trocar de ambiente é trocar URL, key e diretório de backup.
- Não há comando de execução, então a pré-análise funcional é manual na UI.
- Não há mapa automático de credenciais entre ambientes.
- `known_credential_ids` existe na validação, mas a CLI ainda não consulta o catálogo de credenciais da API; a checagem de “id existe neste n8n” fica para conferência humana.
- Não há activate, delete, execute nem publish.
- MCP e uma API própria ainda não existem (`docs/MCP-ROADMAP.md`).
- O cliente não implementa retry. Falha de rede sobe como erro e não deixa escrita pela metade do ponto de vista da CLI: ou o `POST`/`PUT` retornou, ou o plano termina com erro antes de marcar `wrote=true`.

---

## 12. Mapa de documentos

| Documento | Para quê |
|-----------|----------|
| [README](../README.md) | Visão geral e primeiro uso |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Camadas, em inglês |
| [WORKFLOW-LIFECYCLE.md](WORKFLOW-LIFECYCLE.md) | Sequência curta até a ativação |
| [API.md](API.md) | Superfície CLI e HTTP |
| [SECURITY.md](SECURITY.md) | Ameaças e mitigação |
| [AI-AGENTS.md](AI-AGENTS.md) | Loop do agente |
| Este arquivo | Operação técnica: pré-análise num n8n separado e subida para produção |
