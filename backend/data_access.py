"""Camada de acesso a dados (leitura, análise e escrita) para as tabelas MySQL do EJFlow."""
from __future__ import annotations

import hashlib
import os
import re
import pandas as pd

TABLES = ('empresas', 'clientes', 'projetos', 'membros', 'demanda', 'sprints', 'tarefas')
REQUIRED = {
    'empresas': {'id', 'nome', 'rep'},
    'clientes': {'id', 'nome', 'email'},
    'projetos': {'id', 'id_empresa', 'nome', 'descricao'},
    'membros': {'id', 'id_empresa', 'nome', 'email', 'cargo'},
    'demanda': {'id_projeto', 'id_cliente'},
    'sprints': {'id', 'id_projeto', 'isDone', 'data_in', 'data_fin'},
    'tarefas': {'id', 'id_projeto', 'id_sprint', 'estado', 'descricao', 'data_cria', 'data_fin'},
}

_TABLE_NAME_CACHE: dict[tuple[str, str], str] = {}


def settings():
    """Variáveis de ambiente ou secrets.toml; nunca imprimir a senha."""
    try:
        import streamlit as st
        secrets = dict(st.secrets)
    except Exception:
        secrets = {}

    def read(key, default=''):
        if os.getenv(key) == None:
            return default
        return os.getenv(key) 

    return {
        'host': read('MYSQL_HOST', '172.18.0.1'),
        'port': int(read('MYSQL_PORT', 3306)),
        'user': read('MYSQL_USER', 'root'),
        'password': read('MYSQL_PASSWORD', 'sua_senha_secreta'),
        'database': read('MYSQL_DATABASE', 'meu_banco'),
    }


def validate_name(name):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
        raise ValueError('O nome do schema contém caracteres não permitidos.')
    return '`' + name + '`'


def _open_connection(config):
    """Abre conexão MySQL a partir de um dict de configuração ou de um pool de conexões."""
    if hasattr(config, 'get_connection'):
        connection = config.get_connection()
        database = connection.database
        return connection, database
    import mysql.connector
    connection = mysql.connector.connect(
        host=config['host'],
        port=config['port'],
        user=config['user'],
        password=config['password'],
        database=config['database'],
        connection_timeout=8,
        use_pure=True,
    )
    return connection, config['database']


def _resolve_table(cursor, database, table):
    """Resolve o nome físico da tabela no schema (ex.: 'TAREFAS' vs 'tarefas')."""
    cache_key = (database, table.lower())
    if cache_key in _TABLE_NAME_CACHE:
        return validate_name(_TABLE_NAME_CACHE[cache_key])
    cursor.execute(
        'SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES '
        'WHERE TABLE_SCHEMA = %s AND LOWER(TABLE_NAME) = %s',
        (database, table.lower()),
    )
    rows = cursor.fetchall()
    names = {r['TABLE_NAME'] if isinstance(r, dict) else r[0] for r in rows}
    if len(names) > 1 and table not in names:
        raise RuntimeError(f"Nome ambíguo para a tabela '{table}'.")
    physical = table if table in names else next(iter(names), table)
    if names:
        _TABLE_NAME_CACHE[cache_key] = physical
    return validate_name(physical)


def fetch_all(config):
    connection, database = _open_connection(config)
    db = validate_name(database)
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute('SELECT DATABASE() AS db, CURRENT_USER() AS usuario')
            about = cursor.fetchone()
            result = {}
            columns = {}
            for table in TABLES:
                cursor.execute(
                    'SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS '
                    'WHERE TABLE_SCHEMA = %s AND LOWER(TABLE_NAME) = %s',
                    (database, table.lower()),
                )
                metadata = cursor.fetchall()
                physical_names = {r['TABLE_NAME'] for r in metadata}
                physical_name = table if table in physical_names else next(iter(physical_names), table)
                if len(physical_names) > 1 and table not in physical_names:
                    raise RuntimeError(f"Nome ambíguo para a tabela '{table}'.")
                actual_cols = {r['COLUMN_NAME'] for r in metadata if r['TABLE_NAME'] == physical_name}
                columns[table] = actual_cols
                missing = REQUIRED[table] - actual_cols
                if missing:
                    raise RuntimeError(f"A tabela '{table}' não tem as colunas esperadas: {', '.join(sorted(missing))}")
                cursor.execute(f'SELECT * FROM {db}.{validate_name(physical_name)}')
                result[table] = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
            return result, columns, about
        finally:
            cursor.close()
    finally:
        connection.close()


def fetch_query(config, query, params=None, fetchone=False, table=None):
    """Executa uma consulta SELECT retornando dict (fetchone=True) ou list[dict]."""
    connection, database = _open_connection(config)
    validate_name(database)
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            sql = query.format(table=_resolve_table(cursor, database, table)) if table else query
            cursor.execute(sql, params or ())
            return cursor.fetchone() if fetchone else cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()


def normalize(raw):
    """Preserva a cardinalidade original e cria chaves auxiliares para filtros."""
    d = {k: v.copy() for k, v in raw.items()}
    for name in ('empresas', 'clientes', 'projetos', 'membros', 'sprints', 'tarefas'):
        if 'id' in d[name]:
            d[name]['id'] = pd.to_numeric(d[name]['id'], errors='coerce').astype('Int64')
    for name, col in [
        ('projetos', 'id_empresa'), ('membros', 'id_empresa'), ('clientes', 'id_empresa'),
        ('sprints', 'id_projeto'), ('tarefas', 'id_projeto'), ('tarefas', 'id_sprint'),
        ('demanda', 'id_projeto'), ('demanda', 'id_cliente'),
    ]:
        if col in d[name]:
            d[name][col] = pd.to_numeric(d[name][col], errors='coerce').astype('Int64')
    for name in ('tarefas', 'sprints'):
        for col in (('data_cria', 'data_fin') if name == 'tarefas' else ('data_in', 'data_fin')):
            d[name][col] = pd.to_datetime(d[name][col], errors='coerce')
    if 'isDone' in d['sprints']:
        d['sprints']['isDone'] = pd.to_numeric(d['sprints']['isDone'], errors='coerce')
    for c in ('nome', 'rep'):
        d['empresas'][c] = d['empresas'][c].fillna('').astype(str)
    for name in ('projetos', 'clientes', 'membros'):
        d[name]['nome'] = d[name]['nome'].fillna('').astype(str)
    d['tarefas']['estado'] = d['tarefas']['estado'].fillna('nao_informado').astype(str)
    return d


def make_analytics(d, company_ids=None, project_ids=None, task_status=None):
    """Filtra entidades e só então agrega. Sem contagens infladas por JOIN muitos-para-muitos."""
    projects = d['projetos'].copy()
    if company_ids is not None:
        projects = projects[projects['id_empresa'].isin(company_ids)]
    if project_ids is not None:
        projects = projects[projects['id'].isin(project_ids)]
    p_ids = projects['id'].dropna().tolist()
    c_ids = projects['id_empresa'].dropna().unique().tolist()
    companies = d['empresas'][d['empresas']['id'].isin(c_ids)].copy()
    members = d['membros'][d['membros']['id_empresa'].isin(c_ids)].copy()
    sprints = d['sprints'][d['sprints']['id_projeto'].isin(p_ids)].copy()
    tasks_all = d['tarefas'][d['tarefas']['id_projeto'].isin(p_ids)].copy()
    tasks = tasks_all.copy()
    if task_status is not None:
        tasks = tasks[tasks['estado'].isin(task_status)]
    demands = d['demanda'][d['demanda']['id_projeto'].isin(p_ids)].drop_duplicates().copy()
    clients = d['clientes'][d['clientes']['id'].isin(demands['id_cliente'])].copy()
    totals = tasks.groupby('id_projeto', dropna=False).agg(
        total_tarefas=('id', 'count'),
        concluidas=('estado', lambda x: int((x == 'concluida').sum())),
        em_andamento=('estado', lambda x: int((x == 'em_andamento').sum())),
        nao_iniciadas=('estado', lambda x: int((x == 'nao_iniciada').sum())),
    ).reset_index()
    sprint_stats = sprints.groupby('id_projeto', dropna=False).agg(
        total_sprints=('id', 'count'),
        sprints_concluidas=('isDone', lambda x: int((x == 1).sum())),
    ).reset_index()
    client_stats = demands.groupby('id_projeto').agg(clientes=('id_cliente', 'nunique')).reset_index()
    summary = projects.merge(
        d['empresas'][['id', 'nome']].rename(columns={'id': 'id_empresa', 'nome': 'empresa'}),
        on='id_empresa',
        how='left',
    )
    summary = summary.merge(totals, left_on='id', right_on='id_projeto', how='left').drop(columns=['id_projeto'])
    summary = summary.merge(sprint_stats, left_on='id', right_on='id_projeto', how='left').drop(columns=['id_projeto'])
    summary = summary.merge(client_stats, left_on='id', right_on='id_projeto', how='left').drop(columns=['id_projeto'])
    for c in ['total_tarefas', 'concluidas', 'em_andamento', 'nao_iniciadas', 'total_sprints', 'sprints_concluidas', 'clientes']:
        summary[c] = summary[c].fillna(0).astype(int)
    summary['taxa_conclusao'] = 100 * summary['concluidas'].div(summary['total_tarefas'].where(summary['total_tarefas'].gt(0)))
    return {
        'projects': projects,
        'companies': companies,
        'members': members,
        'sprints': sprints,
        'tasks': tasks,
        'tasks_all': tasks_all,
        'demands': demands,
        'clients': clients,
        'summary': summary,
    }


def sprint_analytics(sprints, tasks):
    """Conta somente vínculos cujo projeto coincide, incluindo sprints vazias."""
    keys = ['id_projeto', 'id_sprint']
    counts = tasks.groupby(keys).agg(
        tarefas=('estado', 'size'),
        concluidas=('estado', lambda states: states.eq('concluida').sum()),
    ).reset_index()
    result = sprints.rename(columns={'id': 'id_sprint'}).merge(counts, on=keys, how='left')
    result[['tarefas', 'concluidas']] = result[['tarefas', 'concluidas']].fillna(0).astype(int)
    result['pendentes'] = result['tarefas'] - result['concluidas']
    result['taxa_conclusao'] = 100 * result['concluidas'].div(result['tarefas'].where(result['tarefas'].gt(0)))
    duration = (result['data_fin'] - result['data_in']).dt.total_seconds() / 86400
    result['duracao_dias'] = duration.where(duration.ge(0))
    return result


def data_quality(d):
    t, s, p = d['tarefas'], d['sprints'], d['projetos']
    sprint_map = s[['id', 'id_projeto']].rename(columns={'id': 'id_sprint', 'id_projeto': 'sprint_project'})
    check = t[t['id_sprint'].notna()].merge(sprint_map, on='id_sprint', how='left', indicator=True)
    mismatches = int((check['sprint_project'].notna() & (check['id_projeto'] != check['sprint_project'])).sum())
    checks = [
        ('Projetos sem empresa válida', int((~p['id_empresa'].isin(d['empresas']['id'])).sum())),
        ('Tarefas sem sprint', int(t['id_sprint'].isna().sum())),
        ('Tarefas vinculadas a sprint de outro projeto', mismatches),
        ('Tarefas com referência a sprint inexistente', int(check['_merge'].eq('left_only').sum())),
        ('Tarefas com fim anterior à criação', int(t['data_fin'].lt(t['data_cria']).sum())),
        ('Tarefas sem estado reconhecido', int((~t['estado'].isin(['concluida', 'em_andamento', 'nao_iniciada'])).sum())),
        ('Tarefas concluídas sem data de finalização', int(((t['estado'] == 'concluida') & t['data_fin'].isna()).sum())),
        ('Tarefas não concluídas com data de finalização', int(((t['estado'] != 'concluida') & t['data_fin'].notna()).sum())),
        ('Sprints sem data inicial ou final', int((s['data_in'].isna() | s['data_fin'].isna()).sum())),
        ('Sprints com fim anterior ao início', int(((s['data_fin'] < s['data_in']) & s['data_fin'].notna() & s['data_in'].notna()).sum())),
        ('Projetos sem tarefas cadastradas', int((~p['id'].isin(t['id_projeto'])).sum())),
        ('Clientes sem demanda associada', int((~d['clientes']['id'].isin(d['demanda']['id_cliente'])).sum())),
    ]
    if 'id_empresa' in d['clientes']:
        contracts = d['clientes'].set_index('id')['id_empresa']
        owners = d['demanda']['id_projeto'].map(p.set_index('id')['id_empresa'])
        contracted = d['demanda']['id_cliente'].map(contracts)
        conflicts = owners.notna() & contracted.notna() & owners.ne(contracted)
        checks.append(('Demandas fora da empresa cadastrada para o cliente', int(conflicts.sum())))
    return checks


# ==========================================
# FUNÇÕES DE LEITURA POR ENTIDADE
# ==========================================

def listar_empresas(config):
    return fetch_query(config, 'SELECT * FROM {table} ORDER BY id;', table='empresas')


def obter_empresa(config, id_empresa):
    return fetch_query(config, 'SELECT * FROM {table} WHERE id = %s;', (id_empresa,), fetchone=True, table='empresas')


def listar_clientes(config):
    return fetch_query(config, 'SELECT * FROM {table} ORDER BY id;', table='clientes')


def obter_cliente(config, id_cliente):
    return fetch_query(config, 'SELECT * FROM {table} WHERE id = %s;', (id_cliente,), fetchone=True, table='clientes')


def listar_membros(config, id_empresa=None):
    if id_empresa is not None:
        return fetch_query(config, 'SELECT * FROM {table} WHERE id_empresa = %s ORDER BY id;', (id_empresa,), table='membros')
    return fetch_query(config, 'SELECT * FROM {table} ORDER BY id;', table='membros')


def obter_membro(config, id_membro):
    return fetch_query(config, 'SELECT * FROM {table} WHERE id = %s;', (id_membro,), fetchone=True, table='membros')


def listar_projetos(config, id_empresa=None):
    if id_empresa is not None:
        return fetch_query(config, 'SELECT * FROM {table} WHERE id_empresa = %s ORDER BY id;', (id_empresa,), table='projetos')
    return fetch_query(config, 'SELECT * FROM {table} ORDER BY id;', table='projetos')


def obter_projeto(config, id_projeto):
    return fetch_query(config, 'SELECT * FROM {table} WHERE id = %s;', (id_projeto,), fetchone=True, table='projetos')


def listar_demandas(config, id_projeto=None, id_cliente=None):
    clauses = []
    params = []
    if id_projeto is not None:
        clauses.append('id_projeto = %s')
        params.append(id_projeto)
    if id_cliente is not None:
        clauses.append('id_cliente = %s')
        params.append(id_cliente)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    return fetch_query(config, f'SELECT * FROM {{table}}{where} ORDER BY id_projeto, id_cliente;', tuple(params), table='demanda')


def listar_sprints(config, id_projeto=None):
    if id_projeto is not None:
        return fetch_query(config, 'SELECT * FROM {table} WHERE id_projeto = %s ORDER BY id;', (id_projeto,), table='sprints')
    return fetch_query(config, 'SELECT * FROM {table} ORDER BY id;', table='sprints')


def obter_sprint(config, id_sprint):
    return fetch_query(config, 'SELECT * FROM {table} WHERE id = %s;', (id_sprint,), fetchone=True, table='sprints')


def listar_tarefas(config, id_projeto=None, id_sprint=None, estado=None):
    clauses = []
    params = []
    if id_projeto is not None:
        clauses.append('id_projeto = %s')
        params.append(id_projeto)
    if id_sprint is not None:
        clauses.append('id_sprint = %s')
        params.append(id_sprint)
    if estado is not None:
        clauses.append('estado = %s')
        params.append(estado)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    return fetch_query(config, f'SELECT * FROM {{table}}{where} ORDER BY id;', tuple(params), table='tarefas')


def obter_tarefa(config, id_tarefa):
    return fetch_query(config, 'SELECT * FROM {table} WHERE id = %s;', (id_tarefa,), fetchone=True, table='tarefas')


# ==========================================
# EXECUÇÃO DE COMANDOS DE ESCRITA
# ==========================================

def execute_command(config, query, params=None, table=None):
    """Executa comandos INSERT, UPDATE e DELETE."""
    connection, database = _open_connection(config)
    validate_name(database)
    try:
        cursor = connection.cursor()
        try:
            sql = query.format(table=_resolve_table(cursor, database, table)) if table else query
            cursor.execute(sql, params or ())
            connection.commit()
            return True
        except Exception as e:
            connection.rollback()
            print(f'Erro: {e}')
            return False
        finally:
            cursor.close()
    finally:
        connection.close()


# ==========================================
# FUNÇÕES DE INSERÇÃO
# ==========================================

def inserir_nova_empresa(config, id_empresa, nome, rep):
    query = 'INSERT INTO {table} (id, nome, rep) VALUES (%s, %s, %s);'
    return execute_command(config, query, (id_empresa, nome, rep), table='empresas')


def inserir_novo_membro(config, id_membro, id_empresa, nome, email, cargo):
    query = 'INSERT INTO {table} (id, id_empresa, nome, email, cargo) VALUES (%s, %s, %s, %s, %s);'
    return execute_command(config, query, (id_membro, id_empresa, nome, email, cargo), table='membros')


def inserir_novo_cliente(config, nome, email, id_empresa):
    query = 'INSERT INTO {table} (nome, email, id_empresa) VALUES (%s, %s, %s);'
    return execute_command(config, query, (nome, email, id_empresa), table='clientes')


def inserir_novo_projeto(config, id_projeto, id_empresa, nome, descricao, id_cliente=None):
    query_projeto = 'INSERT INTO {table} (id, id_empresa, nome, descricao) VALUES (%s, %s, %s, %s);'
    sucesso = execute_command(config, query_projeto, (id_projeto, id_empresa, nome, descricao), table='projetos')
    if sucesso and id_cliente is not None:
        query_demanda = 'INSERT INTO {table} (id_projeto, id_cliente) VALUES (%s, %s);'
        return execute_command(config, query_demanda, (id_projeto, id_cliente), table='demanda')
    return sucesso


def inserir_nova_sprint(config, id_projeto, is_done, data_in, data_fin):
    query = 'INSERT INTO {table} (id_projeto, isDone, data_in, data_fin) VALUES (%s, %s, %s, %s);'
    return execute_command(config, query, (id_projeto, is_done, data_in, data_fin), table='sprints')


def inserir_nova_tarefa(config, id_projeto, descricao, estado='nao_iniciada', id_sprint=None, data_cria=None, data_fin=None):
    query = (
        'INSERT INTO {table} (id_projeto, id_sprint, estado, descricao, data_cria, data_fin) '
        'VALUES (%s, %s, %s, %s, %s, %s);'
    )
    return execute_command(config, query, (id_projeto, id_sprint, estado, descricao, data_cria, data_fin), table='tarefas')


# ==========================================
# FUNÇÕES DE ATUALIZAÇÃO E VÍNCULO
# ==========================================

def atualizar_estado_tarefa(config, id_tarefa, novo_estado):
    query = 'UPDATE {table} SET estado = %s WHERE id = %s;'
    return execute_command(config, query, (novo_estado, id_tarefa), table='tarefas')


def associar_tarefa_a_sprint(config, id_tarefa, id_sprint):
    """Vincula uma tarefa existente a uma sprint existente."""
    query = 'UPDATE {table} SET id_sprint = %s WHERE id = %s;'
    return execute_command(config, query, (id_sprint, id_tarefa), table='tarefas')


def vincular_projeto_cliente(config, id_projeto, id_cliente):
    """Associa um projeto existente a um cliente na tabela demanda."""
    query = 'INSERT INTO {table} (id_projeto, id_cliente) VALUES (%s, %s);'
    return execute_command(config, query, (id_projeto, id_cliente), table='demanda')


# ==========================================
# FUNÇÕES DE DELEÇÃO E DESVINCULAÇÃO
# ==========================================

def deletar_empresa(config, id_empresa):
    return execute_command(config, 'DELETE FROM {table} WHERE id = %s;', (id_empresa,), table='empresas')


def deletar_cliente(config, id_cliente):
    return execute_command(config, 'DELETE FROM {table} WHERE id = %s;', (id_cliente,), table='clientes')


def deletar_membro(config, id_membro):
    return execute_command(config, 'DELETE FROM {table} WHERE id = %s;', (id_membro,), table='membros')


def deletar_projeto(config, id_projeto):
    return execute_command(config, 'DELETE FROM {table} WHERE id = %s;', (id_projeto,), table='projetos')


def deletar_sprint(config, id_sprint):
    return execute_command(config, 'DELETE FROM {table} WHERE id = %s;', (id_sprint,), table='sprints')


def deletar_tarefa(config, id_tarefa):
    return execute_command(config, 'DELETE FROM {table} WHERE id = %s;', (id_tarefa,), table='tarefas')


def desvincular_projeto_cliente(config, id_projeto, id_cliente):
    """Remove a associação entre um projeto e um cliente na tabela demanda."""
    query = 'DELETE FROM {table} WHERE id_projeto = %s AND id_cliente = %s;'
    return execute_command(config, query, (id_projeto, id_cliente), table='demanda')


# ==========================================
# FUNÇÕES DE AUTENTICAÇÃO E SENHAS
# ==========================================

def criptografar_em_hash(texto) -> str:
    """Retorna o hash SHA-256 em hexadecimal do texto informado."""
    return hashlib.sha256(str(texto).encode('utf-8')).hexdigest()


Criptografar_Em_Hash = criptografar_em_hash


def autenticar_usuario(config, email, senha):
    """Verifica credenciais comparando o hash SHA-256 da senha digitada com o banco."""
    if not email or not senha:
        return None

    senha_hash = criptografar_em_hash(senha)

    membro = fetch_query(
        config,
        "SELECT id, id_empresa, nome, email, cargo FROM {table} "
        "WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s)) AND senha = %s AND senha <> '' LIMIT 1;",
        (email, senha_hash),
        fetchone=True,
        table='membros',
    )
    if membro:
        membro['tipo'] = 'membro'
        return membro

    cliente = fetch_query(
        config,
        "SELECT id, nome, email FROM {table} "
        "WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s)) AND senha = %s AND senha <> '' LIMIT 1;",
        (email, senha_hash),
        fetchone=True,
        table='clientes',
    )
    if cliente:
        cliente['tipo'] = 'cliente'
        return cliente

    return None


def definir_senha_usuario(config, tipo_usuario, id_usuario, nova_senha):
    """Criptografa a nova senha em SHA-256 e salva na tabela 'membros' ou 'clientes'."""
    if tipo_usuario not in ('membro', 'cliente') or not nova_senha:
        return False
    tabela = 'membros' if tipo_usuario == 'membro' else 'clientes'
    senha_hash = criptografar_em_hash(nova_senha)
    return execute_command(
        config,
        'UPDATE {table} SET senha = %s WHERE id = %s;',
        (senha_hash, id_usuario),
        table=tabela,
    )


def remover_senha_usuario(config, tipo_usuario, id_usuario):
    """Remove a senha (define como '') revogando o login do 'membro' ou 'cliente'."""
    if tipo_usuario not in ('membro', 'cliente'):
        return False
    tabela = 'membros' if tipo_usuario == 'membro' else 'clientes'
    return execute_command(
        config,
        "UPDATE {table} SET senha = '' WHERE id = %s;",
        (id_usuario,),
        table=tabela,
    )
