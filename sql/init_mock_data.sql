-- ============================================================================
-- EJFlow - Schema completo e dados mockados para MySQL 8.0
-- Executado automaticamente pelo Docker na primeira criação do volume
-- (/docker-entrypoint-initdb.d) ou manualmente em um contêiner já existente.
-- ============================================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 1. EMPRESAS
CREATE TABLE IF NOT EXISTS empresas (
    id INT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    rep VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. CLIENTES
CREATE TABLE IF NOT EXISTS clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    id_empresa INT NOT NULL,
    CONSTRAINT chk_email_formato CHECK (
        email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    ),
    CONSTRAINT fk_cliente_empresa FOREIGN KEY (id_empresa)
        REFERENCES empresas(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. PROJETOS
CREATE TABLE IF NOT EXISTS projetos (
    id INT PRIMARY KEY,
    id_empresa INT NOT NULL,
    nome VARCHAR(255) NOT NULL,
    descricao VARCHAR(1000) NOT NULL,
    CONSTRAINT fk_projeto_empresa FOREIGN KEY (id_empresa)
        REFERENCES empresas(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. MEMBROS
CREATE TABLE IF NOT EXISTS membros (
    id INT PRIMARY KEY,
    id_empresa INT NOT NULL,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    cargo VARCHAR(100) NOT NULL,
    CONSTRAINT fk_membro_empresa FOREIGN KEY (id_empresa)
        REFERENCES empresas(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. DEMANDA (Relação N:N entre Projetos e Clientes)
CREATE TABLE IF NOT EXISTS demanda (
    id_projeto INT NOT NULL,
    id_cliente INT NOT NULL,
    CONSTRAINT pk_demanda PRIMARY KEY (id_projeto, id_cliente),
    CONSTRAINT fk_p_client FOREIGN KEY (id_projeto)
        REFERENCES projetos(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_c_project FOREIGN KEY (id_cliente)
        REFERENCES clientes(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. SPRINTS
CREATE TABLE IF NOT EXISTS sprints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_projeto INT NOT NULL,
    isDone TINYINT(1) DEFAULT 0,
    data_in DATETIME,
    data_fin DATETIME,
    CONSTRAINT fk_sprint_projeto FOREIGN KEY (id_projeto)
        REFERENCES projetos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. TAREFAS
CREATE TABLE IF NOT EXISTS tarefas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_projeto INT NOT NULL,
    id_sprint INT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'nao_iniciada',
    descricao VARCHAR(1000),
    data_cria DATETIME,
    data_fin DATETIME,
    CONSTRAINT chk_estado_tarefa CHECK (
        estado IN ('nao_iniciada', 'em_andamento', 'concluida')
    ),
    CONSTRAINT fk_tarefa_sprint FOREIGN KEY (id_sprint)
        REFERENCES sprints(id),
    CONSTRAINT fk_tarefa_projeto FOREIGN KEY (id_projeto)
        REFERENCES projetos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================================
-- DADOS MOCKADOS (idempotentes com INSERT IGNORE)
-- ============================================================================

INSERT IGNORE INTO empresas (id, nome, rep) VALUES
(1, 'Tech Solutions Ltda', 'Carlos Silva'),
(2, 'Inovação & Futuro S.A.', 'Ana Souza'),
(3, 'Global Logistics Corp', 'Marcos Oliveira');

INSERT IGNORE INTO clientes (id, nome, email, id_empresa) VALUES
(1, 'Empresa Parceira Alpha', 'contato@alpha.com', 1),
(2, 'Varejo Norte Express', 'projetos@varejonorte.com.br', 1),
(3, 'Consultoria Beta Corp', 'suporte@betacorp.com.br', 2),
(4, 'Comércio Gama', 'comercial@gama.net', 3);

INSERT IGNORE INTO projetos (id, id_empresa, nome, descricao) VALUES
(101, 1, 'Sistema de E-commerce', 'Desenvolvimento de plataforma de vendas online com integração de pagamentos.'),
(102, 1, 'App Mobile de Entregas', 'Aplicativo para acompanhamento de rotas e entregas em tempo real.'),
(103, 2, 'Portal de RH Interno', 'Sistema web para gestão de férias, holerites e benefícios dos funcionários.'),
(104, 3, 'Dashboard de Logística', 'Painel analítico para monitoramento da frota e custos de frete.');

INSERT IGNORE INTO membros (id, id_empresa, nome, email, cargo) VALUES
(1, 1, 'João Pedro', 'joao.pedro@techsolutions.com', 'Desenvolvedor Full Stack'),
(2, 1, 'Mariana Lima', 'mariana.lima@techsolutions.com', 'Product Owner'),
(3, 1, 'Rafael Costa', 'rafael.costa@techsolutions.com', 'Engenheiro de QA'),
(4, 2, 'Lucas Mendes', 'lucas.mendes@inovacao.com', 'Arquiteto de Software'),
(5, 2, 'Camila Ferreira', 'camila.ferreira@inovacao.com', 'UX/UI Designer'),
(6, 3, 'Beatriz Costa', 'beatriz.costa@global.com', 'Analista de Dados');

INSERT IGNORE INTO demanda (id_projeto, id_cliente) VALUES
(101, 1),
(101, 2),
(102, 1),
(103, 3),
(104, 4);

INSERT IGNORE INTO sprints (id, id_projeto, isDone, data_in, data_fin) VALUES
(1, 101, 1, '2026-03-01 08:00:00', '2026-03-15 18:00:00'),
(2, 101, 0, '2026-03-16 08:00:00', '2026-03-30 18:00:00'),
(3, 102, 0, '2026-03-05 08:00:00', '2026-03-20 18:00:00'),
(4, 103, 1, '2026-02-10 08:00:00', '2026-02-24 18:00:00'),
(5, 104, 0, '2026-03-10 08:00:00', '2026-03-24 18:00:00');

INSERT IGNORE INTO tarefas (id, id_projeto, id_sprint, estado, descricao, data_cria, data_fin) VALUES
(1, 101, 1, 'concluida', 'Configurar o ambiente de desenvolvimento e banco de dados inicial', '2026-03-01 09:00:00', '2026-03-03 17:00:00'),
(2, 101, 1, 'concluida', 'Desenvolver a tela de login e autenticação JWT', '2026-03-04 09:00:00', '2026-03-10 17:00:00'),
(3, 101, 2, 'em_andamento', 'Integrar gateway de pagamento (Cartão e PIX)', '2026-03-16 10:00:00', NULL),
(4, 101, 2, 'nao_iniciada', 'Realizar testes de carga na API de produtos', '2026-03-16 10:00:00', NULL),
(5, 102, 3, 'concluida', 'Definir arquitetura de rastreamento GPS em tempo real', '2026-03-05 08:30:00', '2026-03-09 16:00:00'),
(6, 102, 3, 'em_andamento', 'Criar wireframes das telas principais do aplicativo', '2026-03-10 08:30:00', NULL),
(7, 102, NULL, 'nao_iniciada', 'Configurar notificações push para atualização de entrega', '2026-03-12 11:00:00', NULL),
(8, 103, 4, 'concluida', 'Mapear requisitos de regras de negócio de férias', '2026-02-10 09:00:00', '2026-02-15 16:00:00'),
(9, 103, 4, 'concluida', 'Implementar emissão de holerite em PDF', '2026-02-16 09:00:00', '2026-02-23 18:00:00'),
(10, 104, 5, 'em_andamento', 'Construir pipeline de indicadores de custo por rota', '2026-03-10 09:30:00', NULL),
(11, 104, NULL, 'nao_iniciada', 'Criar alertas automáticos de atraso na entrega', '2026-03-14 14:00:00', NULL);
