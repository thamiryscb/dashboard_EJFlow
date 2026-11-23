'''Somente leitura: tabelas e colunas oriundas do SQL do projeto.'''
from __future__ import annotations
import os
import re
import pandas as pd
import uvicorn

from datetime import date
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(
    title='EJFlow Backend',
    description='API com operacoes de Create, Read, Update e Delete.',
    version='1.0.0',
)

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

# ---------------------------------------------------------------------------
# Modelos (Schemas Pydantic)
# ---------------------------------------------------------------------------
class Empresa(BaseModel):
    id: int
    nome: str = Field(..., min_length=1, max_length=250)
    responsavel: str = Field(..., min_length=1, max_length=250)

class Projeto(BaseModel):
    id: int
    id_empresa: int
    id_cliente:int
    nome: str = Field(..., min_length=1, max_length=250)
    descricao: Optional[str] = Field(default=None, max_length=1000)

class Membros(BaseModel):
    id: int
    id_empresa: int
    nome: str = Field(..., min_length=1, max_length=250)
    email: EmailStr
    cargo: str = Field(...)

class Cliente(BaseModel):
    id: int
    id_empresa: int
    nome: str = Field(..., min_length=1, max_length=250)
    email: EmailStr

class Tarefas(BaseModel):
    id: int
    nome: str = Field(..., min_length=1, max_length=250)
    descricao: Optional[str] = Field(default=None, max_length=1000)
    data_in: date
    data_fin: date

class Sprint(BaseModel):
    id: int
    id_projeto: int
    concluida: bool
    data_in: date
    data_fin: date
    estado: Literal['nao_iniciada', 'em_andamento', 'concluida']


def settings():
    '''Variáveis de ambiente ou secrets.toml; nunca imprimir a senha.'''
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

# GET
@app.get('/projeto/{projeto_id}', response_model=Projeto, summary='Buscar dados de um projeto.')
async def obter_projeto(projeto_id: int):
    projeto = Projeto(id=2, id_empresa=3, id_cliente=2, nome='carla', descricao='1231')
    return projeto 

@app.get('/cliente/{cliente_id}', response_model=Cliente, summary='Buscar dados de um cliente.')
async def obter_cliente(cliente_id: int):
    cliente = Cliente(id=1, nome='zezinh', email='a.asdad@gmail.com')

    return cliente


@app.get('/membros/{membros_id}', response_model=Membros, summary='Buscar dados de uma sprint.')
async def obter_membro(membros_id: int):
    membro = Membros(id=1, id_empresa=2, nome='edu', email='a@gm.com', cargo='j') 

    return membro

@app.get('/membros', response_model=list[Membros], summary='Buscar dados de uma sprint.')
async def obter_membros():
    membros = [Membros(id=1, id_empresa=2, nome='ze', email='a@gm.com', cargo='j'), Membros(id=2, id_empresa=1, nome='chiquin', email='a@gm.com', cargo='re')]
    
    return membros

# sprints associadas a um projeto
@app.get('/sprints/{projeto_id}', response_model=list[Sprint], summary='Buscar dados de uma sprint.')
async def obter_sprint(projeto_id: int):
    sprint = [Sprint(id=6464, id_projeto=projeto_id, concluida=False, data_in=date.today(), data_fin=date.today(), estado='nao_iniciada')]
    
    return sprint

# POST

# UPDATE

# DELETE


if __name__ == '__main__':
  uvicorn.run('api:app', host='0.0.0.0', port=8000, reload=True)
