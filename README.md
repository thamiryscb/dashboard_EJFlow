
# EJFlow — Observatório de Projetos

Sistema web desenvolvido para o gerenciamento e acompanhamento de projetos em empresas juniores, utilizando **Python, Streamlit, Plotly e MySQL**.

O EJFlow permite organizar informações sobre empresas, clientes, membros, projetos, sprints e tarefas, integrando operações de gerenciamento de dados a dashboards com indicadores de desempenho.

## Funcionalidades

### Dashboard e indicadores

- **Visão geral:** quantidade de empresas, projetos, sprints e tarefas, além da taxa de conclusão.
- **Projetos:** distribuição de tarefas, volume de trabalho e acompanhamento das atividades.
- **Sprints e tarefas:** calendário, estados das sprints, tarefas concluídas e pendentes.
- **Clientes e equipes:** informações sobre clientes, membros e empresas.
- **Indicadores gerenciais:** gráficos e métricas calculados a partir dos registros do MySQL.
- **Filtros interativos:** análise das informações conforme os registros selecionados.

### Operações CRUD

O sistema possui uma interface de gerenciamento integrada ao banco de dados MySQL.

| Operação | Funcionalidade |
|---|---|
| **CREATE — INSERT** | Cadastro de empresas, clientes, membros, projetos, sprints e tarefas, além da associação entre clientes e projetos. |
| **READ — SELECT** | Consulta dos registros armazenados e visualização das informações nos dashboards. |
| **UPDATE** | Atualização do estado das tarefas e associação de tarefas às sprints. |
| **DELETE** | Exclusão de empresas, clientes, membros, projetos, sprints e tarefas, além da remoção de associações entre clientes e projetos. |

As operações de atualização disponíveis concentram-se nos estados e vínculos das tarefas. As exclusões respeitam as restrições de integridade referencial definidas no banco.

## Tecnologias utilizadas

- **Python:** desenvolvimento da aplicação.
- **Streamlit:** interface web e formulários.
- **Plotly:** gráficos interativos.
- **MySQL:** armazenamento e gerenciamento dos dados.
- **mysql-connector-python:** comunicação entre Python e MySQL.
- **pandas:** organização e apresentação das informações.

## Estrutura do banco de dados

O banco operacional possui sete tabelas:

| Tabela | Finalidade |
|---|---|
| `empresas` | Informações das empresas juniores. |
| `clientes` | Cadastro dos clientes. |
| `membros` | Integrantes vinculados às empresas. |
| `projetos` | Projetos e empresas responsáveis. |
| `sprints` | Ciclos de desenvolvimento dos projetos. |
| `tarefas` | Atividades, estados e vínculos com projetos e sprints. |
| `demanda` | Associação entre clientes e projetos. |

O modelo relacional utiliza chaves primárias e estrangeiras para estabelecer os relacionamentos e preservar a integridade dos dados.

## Como executar

### 1. Clonar o repositório

```powershell
git clone https://github.com/thamiryscb/dashboard_EJFlow.git
cd dashboard_EJFlow
```

### 2. Instalar as dependências

É necessário possuir Python e MySQL instalados.

No terminal do VS Code, execute:

```powershell
py -m pip install -r requirements.txt
```

### 3. Importar o banco de dados

O projeto necessita de um banco MySQL contendo as tabelas e os relacionamentos utilizados pela aplicação.

Para importar o arquivo SQL disponibilizado no repositório:

1. Abra o MySQL Workbench.
2. Acesse **Server → Data Import**.
3. Selecione **Import from Self-Contained File**.
4. Escolha o arquivo SQL correspondente ao banco operacional.
5. Verifique o schema de destino.
6. Clique em **Start Import**.

Se o banco já estiver criado e configurado, não será necessário importá-lo novamente.

**Atenção:** utilize um script compatível com a estrutura exigida pelo backend. O arquivo de demonstração `banco_sistema_exemplo_limpo.sql` é opcional e deve ser conferido antes de ser utilizado para testar todas as operações de cadastro.

### 4. Configurar a conexão MySQL

Na pasta `.streamlit`, faça uma cópia do arquivo:

`secrets.toml.example`

Renomeie a cópia para:

`secrets.toml`

Configure as informações da conexão:

```toml
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "SUA_SENHA"
MYSQL_DATABASE = "projeto_banco_de_dados"
```

Substitua os valores de exemplo pelas informações do seu MySQL.

O usuário configurado precisa possuir as permissões necessárias para realizar as operações de cadastro, consulta, atualização e exclusão.

**Importante:** o arquivo `secrets.toml` contém credenciais privadas e não deve ser publicado no GitHub. Recomenda-se utilizar um usuário MySQL específico para a aplicação.

### 5. Executar a aplicação

No terminal do VS Code, execute:

```powershell
py -m streamlit run app.py --server.port 8503
```

Acesse:

http://localhost:8503

## Integração entre frontend e backend

O sistema utiliza uma arquitetura integrada entre a interface web e o banco de dados relacional.

- **Frontend:** desenvolvido com Streamlit, responsável pelos formulários, filtros, gráficos e visualizações.
- **Backend:** implementado em Python, responsável pela execução das consultas e operações SQL.
- **Banco de dados:** MySQL, responsável pelo armazenamento e pelos relacionamentos entre os registros.

As informações apresentadas no dashboard são consultadas diretamente no MySQL, permitindo acompanhar os dados cadastrados no sistema.

## Indicadores de desempenho

Entre os indicadores apresentados estão:

- Quantidade de empresas e projetos cadastrados.
- Total de tarefas e sprints.
- Distribuição das tarefas por estado.
- Taxa de conclusão das atividades.
- Volume de tarefas por projeto.
- Conclusão das tarefas por sprint.
- Distribuição de projetos por empresa.
- Quantidade de membros por empresa.

A taxa de conclusão considera a proporção de tarefas com estado `concluida` em relação ao total de tarefas do recorte analisado.

Os indicadores refletem os registros disponíveis no banco de dados conectado.

## Observações

O sistema foi desenvolvido para fins acadêmicos, como parte do projeto **EJFlow — Gerenciador de Projetos para Empresas Juniores**.

Para utilização em ambientes de produção, são recomendados aprimoramentos relacionados à autenticação, ao controle de acesso e à segurança das operações.

## Projeto acadêmico

**Universidade Federal do Rio Grande do Norte (UFRN)**

Disciplina de Banco de Dados — 2026.2
