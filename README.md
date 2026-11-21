# 📊 Dashboard EJFlow

Dashboard interativo desenvolvido em **Python e Streamlit**, integrado a um banco de dados **MySQL**, com o objetivo de facilitar a visualização, o gerenciamento e a análise de informações relacionadas a empresas e projetos.

O projeto utiliza **Docker e Docker Compose** para executar a aplicação e o banco de dados em contêineres independentes, proporcionando maior portabilidade, padronização do ambiente e facilidade de execução.

## 🚀 Funcionalidades

- Visualização interativa de gráficos e indicadores.
- Consulta de informações armazenadas no MySQL.
- Gerenciamento de empresas, incluindo cadastro e exclusão.
- Atualização e visualização de dados pela interface Streamlit.
- Integração entre aplicação e banco de dados utilizando Docker.

## 🛠️ Tecnologias utilizadas

| Tecnologia | Finalidade |
|---|---|
| Python | Desenvolvimento da aplicação |
| Streamlit | Interface web e dashboard |
| MySQL 8.0 | Banco de dados relacional |
| Pandas | Manipulação e análise de dados |
| Plotly | Visualização interativa de dados |
| Docker | Conteinerização da aplicação |
| Docker Compose | Gerenciamento dos contêineres |
| Git e GitHub | Versionamento do projeto |

## 🐳 Arquitetura da aplicação

A aplicação utiliza dois serviços principais:

**Streamlit (`app`):** responsável pela interface web, apresentação dos gráficos e interação com o usuário.

**MySQL (`db`):** responsável pelo armazenamento e gerenciamento das informações utilizadas pelo dashboard.

Os serviços comunicam-se pela rede interna do Docker Compose.

```text
                 Usuário
                    |
                    v
             Navegador Web
                    |
                    v
           localhost:8503
                    |
                    v
        +---------------------+
        | Streamlit Dashboard |
        |    Container app    |
        +---------------------+
                    |
                    | Rede Docker
                    v
        +---------------------+
        |        MySQL        |
        |    Container db     |
        |     Porta 3306      |
        +---------------------+
                    |
                    v
              Volume Docker
              (mysql_data)
```

## 📋 Pré-requisitos

Para executar o projeto utilizando Docker, é necessário instalar:

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

Não é necessário instalar Python ou MySQL diretamente na máquina para executar a aplicação conteinerizada.

## ⚙️ Instalação e execução

### 1. Clonar o repositório

```bash
git clone https://github.com/thamiryscb/dashboard_EJFlow.git
cd dashboard_EJFlow
```

### 2. Configurar as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto, utilizando o seguinte modelo:

```env
MYSQL_DATABASE=projeto_banco_de_dados
MYSQL_USER=ejflow
MYSQL_PASSWORD=substitua_por_uma_senha_segura
MYSQL_ROOT_PASSWORD=substitua_por_outra_senha_segura
```

As credenciais serão utilizadas pelo Docker Compose para configurar o banco de dados e permitir a comunicação com a aplicação.

**Importante:** o arquivo `.env` contém informações sensíveis e não deve ser enviado ao GitHub.

### 3. Construir e iniciar os contêineres

No terminal, execute:

```bash
docker compose up -d --build
```

Esse comando constrói a imagem da aplicação, cria os contêineres necessários e inicia os serviços em segundo plano.

### 4. Verificar os serviços

```bash
docker compose ps
```

Os serviços esperados são:

| Serviço | Descrição |
|---|---|
| `app` | Aplicação Streamlit |
| `db` | Banco de dados MySQL |

O serviço MySQL deve apresentar o estado `healthy`.

### 5. Inicializar o banco de dados

Na primeira execução, é necessário garantir que as tabelas e os dados utilizados pelo dashboard estejam presentes no MySQL.

O projeto possui o script:

```text
sql/projeto_banco_de_dados.sql
```

Caso o banco ainda não tenha sido inicializado, copie o script para o contêiner:

```bash
docker compose cp ./sql/projeto_banco_de_dados.sql db:/tmp/projeto_banco_de_dados.sql
```

Em seguida, acesse o MySQL:

```bash
docker compose exec db mysql -u root -p
```

Informe a senha do administrador e execute:

```sql
USE projeto_banco_de_dados;
SOURCE /tmp/projeto_banco_de_dados.sql;
SHOW TABLES;
```

**Atenção:** importe o script somente quando necessário. Antes de executá-lo novamente, verifique se existem dados importantes, pois o comportamento depende das instruções SQL presentes no arquivo.

Na configuração testada, foram identificadas sete tabelas:

- `TAREFAS`
- `clientes`
- `demanda`
- `empresas`
- `membros`
- `projetos`
- `sprints`

### 6. Acessar o dashboard

Após a inicialização dos serviços, abra o navegador e acesse:

**http://localhost:8503**

O dashboard estará disponível enquanto os contêineres estiverem em execução.

## 💻 Comandos úteis

| Comando | Descrição |
|---|---|
| `docker compose up -d` | Inicia os contêineres |
| `docker compose up -d --build` | Reconstrói e inicia a aplicação |
| `docker compose ps` | Verifica o estado dos serviços |
| `docker compose logs -f app` | Exibe os logs da aplicação |
| `docker compose logs -f db` | Exibe os logs do MySQL |
| `docker compose stop` | Interrompe os serviços |
| `docker compose down` | Remove os contêineres e a rede criada pelo Compose |

**Observação:** o comando `docker compose down` preserva os volumes nomeados por padrão. Evite utilizar `docker compose down -v` quando desejar manter os dados armazenados no MySQL.

## 💾 Persistência dos dados

O MySQL utiliza um volume Docker chamado `mysql_data`, responsável por armazenar os arquivos do banco de dados.

Dessa forma, os dados permanecem disponíveis mesmo após a interrupção ou recriação dos contêineres, desde que o volume não seja removido.

## 🔐 Segurança

O projeto utiliza variáveis de ambiente para configurar a conexão com o banco de dados.

Recomendações:

- Não publicar senhas ou credenciais no repositório.
- Adicionar `.env` ao `.gitignore`.
- Não versionar `.streamlit/secrets.toml` contendo informações sensíveis.
- Utilizar um usuário específico da aplicação em vez do usuário `root`.
- Manter senhas distintas para o administrador do MySQL e o usuário da aplicação.

## 📁 Estrutura principal do projeto

```text
dashboard_EJFlow/
│
├── app.py
├── data_access.py
├── requirements.txt
├── Dockerfile
├── compose.yaml
├── .dockerignore
├── .gitignore
├── README.md
│
└── sql/
    └── projeto_banco_de_dados.sql
```

Arquivos recomendados para configuração local:

- `.env`: contém as credenciais reais e não deve ser versionado.
- `.env.example`: pode ser adicionado ao repositório com valores fictícios para facilitar a configuração por outros usuários.

## ✅ Validação da conteinerização

A execução local foi testada com Docker Compose.

Foram verificados:

- Construção bem-sucedida da imagem Docker.
- Inicialização dos contêineres Streamlit e MySQL.
- Estado saudável do serviço MySQL.
- Existência das sete tabelas no banco de dados.
- Acesso à aplicação pela porta `8503`.
- Exibição dos gráficos e informações do dashboard.
- Funcionamento das operações de cadastro e exclusão de empresas.

Esses testes confirmaram o funcionamento da aplicação conteinerizada no ambiente local utilizado.

## 📌 Considerações finais

A conteinerização do Dashboard EJFlow permite executar a aplicação Streamlit e o banco de dados MySQL de maneira integrada, utilizando o Docker Compose para gerenciar os serviços.

Essa abordagem reduz a necessidade de configurações manuais no ambiente de desenvolvimento, facilita a reprodução da aplicação e estabelece uma base para futuras melhorias e implantação em outros ambientes.

---

**Projeto:** Dashboard EJFlow  
**Tecnologias principais:** Python, Streamlit, MySQL e Docker  
**Ambiente validado:** Execução local com Docker Compose