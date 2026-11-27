# Instruções — Banco de Dados Mockado, Docker e Validação da API/CORS

Este guia explica como inicializar, recarregar e validar os dados mockados no contêiner MySQL (`db`), além de verificar a comunicação entre `frontend` (Streamlit), `backend` (FastAPI) e a política de CORS.

---

## 1. Como os dados mockados são carregados

O projeto utiliza o arquivo [`sql/init_mock_data.sql`](sql/init_mock_data.sql), que cria as 7 tabelas esperadas pela API (`empresas`, `clientes`, `projetos`, `membros`, `demanda`, `sprints`, `tarefas`) e insere registros iniciais de forma idempotente (`CREATE TABLE IF NOT EXISTS` e `INSERT IGNORE`).

No [`compose.yaml`](compose.yaml), o script está montado no serviço `db`:

```yaml
volumes:
  - mysql_data:/var/lib/mysql
  - ./sql/init_mock_data.sql:/docker-entrypoint-initdb.d/01_init_mock_data.sql:ro
```

- **Volume novo (primeira inicialização):** o MySQL executa automaticamente tudo o que estiver em `/docker-entrypoint-initdb.d/` ao criar o banco pela primeira vez.
- **Volume já existente:** o MySQL **não** executa `/docker-entrypoint-initdb.d/` novamente se o volume `mysql_data` já foi inicializado antes. Nesse caso, aplique o script manualmente (seção 2).

---

## 2. Comandos para carregar ou resetar os dados no Docker

### Opção A — Aplicar os dados mockados no contêiner `db` já em execução (sem apagar o volume)

```bash
docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < sql/init_mock_data.sql
```

### Opção B — Recriar o banco do zero (apaga os dados atuais do volume `mysql_data`)

> **Atenção:** o parâmetro `-v` remove o volume `mysql_data`. Use apenas quando quiser recomeçar do zero.

```bash
docker compose down -v
docker compose up -d --build
```

Na subida, o MySQL criará o schema e importará [`sql/init_mock_data.sql`](sql/init_mock_data.sql) automaticamente.

---

## 3. Verificar se as tabelas e dados foram criados

```bash
docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "
SHOW TABLES;
SELECT
  (SELECT COUNT(*) FROM empresas) AS empresas,
  (SELECT COUNT(*) FROM clientes) AS clientes,
  (SELECT COUNT(*) FROM projetos) AS projetos,
  (SELECT COUNT(*) FROM membros) AS membros,
  (SELECT COUNT(*) FROM demanda) AS demanda,
  (SELECT COUNT(*) FROM sprints) AS sprints,
  (SELECT COUNT(*) FROM tarefas) AS tarefas;
"'
```

---

## 4. Validar comunicação Frontend → Backend → MySQL e CORS

### 4.1. Conferir saúde dos contêineres

```bash
docker compose ps
```

Todos os serviços (`db`, `backend` e `frontend`) devem aparecer como `healthy`.

### 4.2. Testar endpoints da API

- Documentação Swagger: `http://localhost:8000/docs`
- Dashboard Streamlit: `http://localhost:8503`
- Healthcheck da API:
  ```bash
  curl -sS http://localhost:8000/health
  ```
- Consulta completa usada pelo frontend (a partir de dentro do contêiner `frontend`, pela rede interna do Docker):
  ```bash
  docker compose exec -T frontend python -c "import os, requests; r = requests.get(os.getenv('API_BASE_URL') + '/dados', timeout=10); print(r.status_code, list(r.json().get('tables', {}).keys()))"
  ```

### 4.3. Validar política de CORS

- **Origem permitida (`http://localhost:8503`)** — deve retornar `200 OK` com `access-control-allow-origin: http://localhost:8503`:
  ```bash
  curl -i -X OPTIONS http://localhost:8000/empresas \
    -H "Origin: http://localhost:8503" \
    -H "Access-Control-Request-Method: GET"
  ```

- **Origem bloqueada (`http://origem-nao-autorizada.com`)** — deve retornar `400 Bad Request` sem o cabeçalho `access-control-allow-origin`:
  ```bash
  curl -i -X OPTIONS http://localhost:8000/empresas \
    -H "Origin: http://origem-nao-autorizada.com" \
    -H "Access-Control-Request-Method: GET"
  ```

---

## 5. Nota sobre CORS e Docker no Streamlit

O Streamlit ([`frontend/app.py`](frontend/app.py)) consulta a API pelo lado do servidor em Python (`requests`), usando o endereço interno `API_BASE_URL=http://backend:8000`. Por isso:

1. **CORS não bloqueia** chamadas servidor-para-servidor feitas pelo Streamlit — ele atua em requisições originadas pelo navegador (ou em testes de preflight `OPTIONS`).
2. **Rodar em Docker não impede** a comunicação entre `frontend` e `backend`, desde que o `frontend` use o nome do serviço (`http://backend:8000`) em vez de `localhost:8000`.
3. Se o painel exibir *"API do EJFlow indisponível"*, verifique os logs do backend (`docker compose logs --tail=50 backend`): na maioria das vezes o erro é no banco de dados (por exemplo, tabelas ainda não criadas) gerando HTTP `500` na rota `/dados`.

---

## 6. Credenciais iniciais de acesso (dados mockados)

O script [`sql/init_mock_data.sql`](sql/init_mock_data.sql) cria a coluna `senha` (hash SHA-256) em `membros` e `clientes` e define uma senha inicial apenas para os registros de ID `1`:

- **Perfil Membro (acesso completo):** `joao.pedro@techsolutions.com` / senha: `Senha`
- **Perfil Cliente (visão restrita):** `contato@alpha.com` / senha: `Senha`
