"""Somente leitura: tabelas e colunas oriundas do SQL do projeto."""
from __future__ import annotations
import os
import re
import pandas as pd

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

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


def settings():
    """Variáveis de ambiente ou secrets.toml; nunca imprimir a senha."""
    try:
        import streamlit as st
        secrets = dict(st.secrets)
    except Exception:
        secrets = {}
    def read(key, default=''):
        return os.getenv(key) or secrets.get(key, default)
    return {
        'host': read('MYSQL_HOST', '127.0.0.1'),
        'port': int(read('MYSQL_PORT', 3306)),
        'user': read('MYSQL_USER', 'root'),
        'password': read('MYSQL_PASSWORD', ''),
        'database': read('MYSQL_DATABASE', 'banco_sistema_demo'),
    }


def validate_name(name):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
        raise ValueError('O nome do schema contém caracteres não permitidos.')
    return '`' + name + '`'

def fetch_all(config):
    import mysql.connector
    db = validate_name(config['database'])
    connection = mysql.connector.connect(
        host=config['host'], port=config['port'], user=config['user'],
        password=config['password'], database=config['database'], connection_timeout=8,
        use_pure=True,
    )
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute('SELECT DATABASE() AS db, CURRENT_USER() AS usuario')
            about = cursor.fetchone()
            result = {}
            columns = {}
            for table in TABLES:
                cursor.execute('SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS '
                               'WHERE TABLE_SCHEMA = %s AND LOWER(TABLE_NAME) = %s',
                               (config['database'], table.lower()))
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


def normalize(raw):
    """Preserva a cardinalidade original e cria chaves auxiliares para filtros."""
    d = {k: v.copy() for k,v in raw.items()}
    for name in ('empresas', 'clientes', 'projetos', 'membros', 'sprints', 'tarefas'):
        if 'id' in d[name]:
            d[name]['id'] = pd.to_numeric(d[name]['id'], errors='coerce').astype('Int64')
    for name, col in [('projetos','id_empresa'),('membros','id_empresa'),('clientes','id_empresa'),
                      ('sprints','id_projeto'),('tarefas','id_projeto'),('tarefas','id_sprint'),
                      ('demanda','id_projeto'),('demanda','id_cliente')]:
        if col in d[name]:
            d[name][col] = pd.to_numeric(d[name][col], errors='coerce').astype('Int64')
    for name in ('tarefas', 'sprints'):
        for col in (('data_cria','data_fin') if name == 'tarefas' else ('data_in','data_fin')):
            d[name][col] = pd.to_datetime(d[name][col], errors='coerce')
    if 'isDone' in d['sprints']:
        d['sprints']['isDone'] = pd.to_numeric(d['sprints']['isDone'], errors='coerce')
    for c in ('nome','rep'):
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
        total_tarefas=('id','count'),
        concluidas=('estado',lambda x: int((x == 'concluida').sum())),
        em_andamento=('estado',lambda x: int((x == 'em_andamento').sum())),
        nao_iniciadas=('estado',lambda x: int((x == 'nao_iniciada').sum())),
    ).reset_index()
    sprint_stats = sprints.groupby('id_projeto', dropna=False).agg(
        total_sprints=('id','count'), sprints_concluidas=('isDone', lambda x: int((x == 1).sum()))
    ).reset_index()
    client_stats = demands.groupby('id_projeto').agg(clientes=('id_cliente','nunique')).reset_index()
    summary = projects.merge(d['empresas'][['id','nome']].rename(columns={'id':'id_empresa','nome':'empresa'}),
                             on='id_empresa', how='left')
    summary = summary.merge(totals, left_on='id', right_on='id_projeto', how='left').drop(columns=['id_projeto'])
    summary = summary.merge(sprint_stats, left_on='id', right_on='id_projeto', how='left').drop(columns=['id_projeto'])
    summary = summary.merge(client_stats, left_on='id', right_on='id_projeto', how='left').drop(columns=['id_projeto'])
    for c in ['total_tarefas','concluidas','em_andamento','nao_iniciadas','total_sprints','sprints_concluidas','clientes']:
        summary[c] = summary[c].fillna(0).astype(int)
    summary['taxa_conclusao'] = 100 * summary['concluidas'].div(summary['total_tarefas'].where(summary['total_tarefas'].gt(0)))
    return {'projects': projects, 'companies': companies, 'members': members,
            'sprints': sprints, 'tasks': tasks, 'tasks_all': tasks_all,
            'demands':demands, 'clients':clients, 'summary':summary}


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
    t, s, p = d['tarefas'],d['sprints'],d['projetos']
    sprint_map = s[['id','id_projeto']].rename(columns={'id':'id_sprint', 'id_projeto':'sprint_project'})
    check = t[t['id_sprint'].notna()].merge(sprint_map, on='id_sprint', how='left', indicator=True)
    mismatches = int((check['sprint_project'].notna() & (check['id_projeto'] != check['sprint_project'])).sum())
    checks = [
        ('Projetos sem empresa válida', int((~p['id_empresa'].isin(d['empresas']['id'])).sum())),
        ('Tarefas sem sprint', int(t['id_sprint'].isna().sum())),
        ('Tarefas vinculadas a sprint de outro projeto', mismatches),
        ('Tarefas com referência a sprint inexistente', int(check['_merge'].eq('left_only').sum())),
        ('Tarefas com fim anterior à criação', int(t['data_fin'].lt(t['data_cria']).sum())),
        ('Tarefas sem estado reconhecido', int((~t['estado'].isin(['concluida', 'em_andamento', 'nao_iniciada'])).sum())),
        ('Tarefas concluídas sem data de finalização',int(((t['estado']=='concluida') & t['data_fin'].isna()).sum())),
        ('Tarefas não concluídas com data de finalização',int(((t['estado']!='concluida') & t['data_fin'].notna()).sum())),
        ('Sprints sem data inicial ou final',int((s['data_in'].isna() | s['data_fin'].isna()).sum())),
        ('Sprints com fim anterior ao início',int(((s['data_fin'] < s['data_in']) & s['data_fin'].notna() & s['data_in'].notna()).sum())),
        ('Projetos sem tarefas cadastradas',int((~p['id'].isin(t['id_projeto'])).sum())),
        ('Clientes sem demanda associada',int((~d['clientes']['id'].isin(d['demanda']['id_cliente'])).sum())),
    ]
    if 'id_empresa' in d['clientes']:
        contracts = d['clientes'].set_index('id')['id_empresa']
        owners = d['demanda']['id_projeto'].map(p.set_index('id')['id_empresa'])
        contracted = d['demanda']['id_cliente'].map(contracts)
        conflicts = owners.notna() & contracted.notna() & owners.ne(contracted)
        checks.append(('Demandas fora da empresa cadastrada para o cliente', int(conflicts.sum())))
    return checks

#====================================
#Funções de inserção e ativação
#===================================

def execute_command(config, query, params=None):
    """Executa comandos INSERT, UPDATE e DELETE"""
    import mysql.connector
    db = validate_name(config['database'])
    connection = mysql.connector.connect(
        host=config['host'], port=config['port'], user=config['user'],
        password=config['password'], database=config['database'], connection_timeout=8,
        use_pure=True,
    )
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(query, params or ())
            connection.commit()
            return True

        except Exception as e:
            return print("Erro")
        finally:
            cursor.close()
    finally:
        connection.close()

# ==========================================
# FUNÇÕES DE INSERÇÃO E ATUALIZAÇÃO
# ==========================================
@app.post('/')
def inserir_nova_empresa(config, id_empresa, nome, rep):
    query = "INSERT INTO empresas (id, nome, rep) VALUES (%s, %s, %s);"
    return execute_command(config, query, (id_empresa, nome, rep))

def inserir_novo_membro(config, id_membro, id_empresa, nome, email, cargo):
    query = "INSERT INTO membros (id, id_empresa, nome, email, cargo) VALUES (%s, %s, %s, %s, %s);"
    return execute_command(config, query, (id_membro, id_empresa, nome, email, cargo))

def inserir_novo_cliente(config, nome, email, id_empresa):
    query = "INSERT INTO clientes (nome, email, id_empresa) VALUES (%s, %s, %s);"
    return execute_command(config, query, (nome, email, id_empresa))

def inserir_novo_projeto(config, id_projeto, id_empresa, nome, descricao, id_cliente=None):
    query_projeto = "INSERT INTO projetos (id, id_empresa, nome, descricao) VALUES (%s, %s, %s, %s);"
    sucesso = execute_command(config, query_projeto, (id_projeto, id_empresa, nome, descricao))
    if sucesso and id_cliente:
        query_demanda = "INSERT INTO demanda (id_projeto, id_cliente) VALUES (%s, %s);"
        execute_command(config, query_demanda, (id_projeto, id_cliente))
    return sucesso

def inserir_nova_sprint(config, id_projeto, is_done, data_in, data_fin):
    query = "INSERT INTO sprints (id_projeto, isDone, data_in, data_fin) VALUES (%s, %s, %s, %s);"
    return execute_command(config, query, (id_projeto, is_done, data_in, data_fin))

def inserir_nova_tarefa(config, id_projeto, descricao, estado='nao_iniciada', id_sprint=None, data_cria=None, data_fin=None):
    query = """
        INSERT INTO tarefas (id_projeto, id_sprint, estado, descricao, data_cria, data_fin) 
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    return execute_command(config, query, (id_projeto, id_sprint, estado, descricao, data_cria, data_fin))


#=================================
#Funções de atualizção
#=================================


def atualizar_estado_tarefa(config, id_tarefa, novo_estado):
    query = "UPDATE tarefas SET estado = %s WHERE id = %s;"
    return execute_command(config, query, (novo_estado, id_tarefa))

def associar_tarefa_a_sprint(config, id_tarefa, id_sprint):
    """Vincula uarefa existente a uma sprint existente[cite: 2]."""
    query = "UPDATE tarefas SET id_sprint = %s WHERE id = %s;"
    return execute_command(config, query, (id_sprint, id_tarefa))


def vincular_projeto_cliente(config, id_projeto, id_cliente):
    """Associa um projeto existente a um cliente na tabela demanda[cite: 2]."""
    query = "INSERT INTO demanda (id_projeto, id_cliente) VALUES (%s, %s);"
    return execute_command(config, query, (id_projeto, id_cliente))




# ==========================================
# FUNÇÕES DE DELEÇÃO
# ==========================================
def deletar_empresa(config, id_empresa):
    return execute_command(config, "DELETE FROM empresas WHERE id = %s;", (id_empresa,))

def deletar_cliente(config, id_cliente):
    return execute_command(config, "DELETE FROM clientes WHERE id = %s;", (id_cliente,))

def deletar_membro(config, id_membro):
    return execute_command(config, "DELETE FROM membros WHERE id = %s;", (id_membro,))

def deletar_projeto(config, id_projeto):
    return execute_command(config, "DELETE FROM projetos WHERE id = %s;", (id_projeto,))

def deletar_sprint(config, id_sprint):
    return execute_command(config, "DELETE FROM sprints WHERE id = %s;", (id_sprint,))

def deletar_tarefa(config, id_tarefa):
    return execute_command(config, "DELETE FROM tarefas WHERE id = %s;", (id_tarefa,))



#===================================
#Desvincular
#===================================

def desvincular_projeto_cliente(config, id_projeto, id_cliente): #WIp
    """Remove a associação entre um projeto e um cliente na tabela 'demanda'[cite: 2]."""
    query = "DELETE FROM demanda WHERE id_projeto = %s AND id_cliente = %s;"
    return execute_command(config, query, (id_projeto, id_cliente))