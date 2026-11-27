"""API FastAPI do backend EJFlow integrada às funções de backend/data_access.py."""
from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from datetime import datetime
import hashlib
import hmac
import json
import os
import time
from typing import Any, Literal, Optional

import numpy as np
import pandas as pd
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from mysql.connector import Error, pooling
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

try:
    from backend import data_access as da
except ImportError:
    import data_access as da


EstadoTarefa = Literal['nao_iniciada', 'em_andamento', 'concluida']
TipoUsuario = Literal['admin', 'chefe', 'membro', 'cliente']
PerfilMembro = Literal['membro', 'chefe']

AUTH_SECRET = os.getenv('AUTH_SECRET', 'ejflow-secret-key-local')
TOKEN_TTL_SECONDS = 86400


# ---------------------------------------------------------------------------
# Modelos (Schemas Pydantic)
# ---------------------------------------------------------------------------

class Empresa(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    nome: str = Field(..., min_length=1, max_length=255)
    rep: str = Field(
        ...,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices('rep', 'responsavel'),
    )


class Projeto(BaseModel):
    id: int
    id_empresa: int
    nome: str = Field(..., min_length=1, max_length=255)
    descricao: Optional[str] = Field(default=None, max_length=1000)
    clientes: list[int] = Field(default_factory=list)


class ProjetoCreate(BaseModel):
    id: int
    id_empresa: int
    nome: str = Field(..., min_length=1, max_length=255)
    descricao: str = Field(..., min_length=1, max_length=1000)
    id_cliente: Optional[int] = None


class Membros(BaseModel):
    id: int
    id_empresa: int
    nome: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    cargo: str = Field(..., min_length=1, max_length=100)
    perfil: str = 'membro'


class MembroCreate(BaseModel):
    id: int
    id_empresa: int
    nome: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    cargo: str = Field(..., min_length=1, max_length=100)
    perfil: PerfilMembro = 'membro'
    senha: Optional[str] = None


class MembroPerfilUpdate(BaseModel):
    perfil: PerfilMembro


class Cliente(BaseModel):
    id: int
    nome: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    id_empresa: Optional[int] = None


class ClienteCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    id_empresa: int


class Sprint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    id_projeto: int
    isDone: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices('isDone', 'is_done', 'concluida'),
    )
    data_in: Optional[datetime] = None
    data_fin: Optional[datetime] = None


class SprintCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id_projeto: int
    is_done: bool = Field(
        default=False,
        validation_alias=AliasChoices('is_done', 'isDone', 'concluida'),
    )
    data_in: Optional[datetime] = None
    data_fin: Optional[datetime] = None


class Tarefas(BaseModel):
    id: int
    id_projeto: int
    id_sprint: Optional[int] = None
    id_membro: Optional[int] = None
    estado: Optional[str] = None
    descricao: Optional[str] = Field(default=None, max_length=1000)
    data_cria: Optional[datetime] = None
    data_fin: Optional[datetime] = None


class TarefaCreate(BaseModel):
    id_projeto: int
    descricao: str = Field(..., min_length=1, max_length=1000)
    estado: EstadoTarefa = 'nao_iniciada'
    id_sprint: Optional[int] = None
    id_membro: Optional[int] = None
    data_cria: Optional[datetime] = None
    data_fin: Optional[datetime] = None


class TarefaEstadoUpdate(BaseModel):
    estado: EstadoTarefa


class TarefaSprintUpdate(BaseModel):
    id_sprint: Optional[int] = None


class TarefaMembroUpdate(BaseModel):
    id_membro: Optional[int] = None


class Demanda(BaseModel):
    id_projeto: int
    id_cliente: int


class MembroProjeto(BaseModel):
    id_projeto: int
    id_membro: int


class AdminOut(BaseModel):
    id: int
    nome: str
    email: str


class AdminCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    senha: str = Field(..., min_length=1, max_length=255)


class MensagemResposta(BaseModel):
    mensagem: str


class QualidadeItem(BaseModel):
    verificacao: str
    ocorrencias: int


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    senha: str = Field(..., min_length=1, max_length=255)


class UsuarioAutenticado(BaseModel):
    id: int
    nome: str
    email: str
    tipo: TipoUsuario
    id_empresa: Optional[int] = None
    cargo: Optional[str] = None
    perfil: Optional[str] = None
    token: str


class DefinirSenhaRequest(BaseModel):
    nova_senha: str = Field(..., min_length=1, max_length=255)


# ---------------------------------------------------------------------------
# Utilitários de serialização e conexão
# ---------------------------------------------------------------------------

def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        scalar = value.item()
        if isinstance(scalar, float) and (np.isnan(scalar) or np.isinf(scalar)):
            return None
        return scalar
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records = df.to_dict(orient='records')
    return [{k: _serialize_value(v) for k, v in row.items()} for row in records]


def _sanitize_user_dataframe(df: pd.DataFrame, include_flag: bool = True) -> pd.DataFrame:
    """Remove a coluna de hash de senha antes de expor tabelas pela API."""
    frame = df.copy()
    if 'senha' in frame.columns:
        if include_flag:
            frame['possui_senha'] = frame['senha'].fillna('').astype(str).str.strip().ne('')
        frame = frame.drop(columns=['senha'])
    return frame


def db_configs() -> dict[str, Any]:
    """Lê as configurações do MySQL via data_access.settings()."""
    return da.settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = db_configs()
    try:
        app.state.db_pool = pooling.MySQLConnectionPool(
            pool_name='fastapi_pool',
            pool_size=5,
            use_pure=True,
            **config,
        )
        print('Pool de conexões MySQL iniciado com sucesso!')
        try:
            migrated = da.garantir_colunas_senha(app.state.db_pool)
            migradas = [t for t, mudou in migrated.items() if mudou]
            if migradas:
                print(f"Coluna 'senha' criada automaticamente em: {', '.join(migradas)}")
        except Exception as exc:
            print(f"Aviso: não foi possível verificar/migrar coluna 'senha': {exc}")
    except Error as e:
        print(f'Erro ao conectar ao MySQL: {e}')
        raise e

    yield

    app.state.db_pool = None


def get_db():
    pool = getattr(app.state, 'db_pool', None)
    return pool if pool is not None else db_configs()


# ---------------------------------------------------------------------------
# Definição da API
# ---------------------------------------------------------------------------

app = FastAPI(
    title='EJFlow Backend',
    description='API REST do EJFlow com operações CRUD, analytics e auditoria de dados.',
    version='1.0.0',
    lifespan=lifespan,
)

cors_origins = [
    origin.strip()
    for origin in os.getenv('CORS_ORIGINS', 'http://localhost:8503,http://127.0.0.1:8503').split(',')
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['*'],
)


@app.get('/health', tags=['Sistema'], summary='Verificação de saúde da API.')
def healthcheck():
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# AUTENTICAÇÃO, TOKENS HMAC E AUTORIZAÇÃO POR PERFIL
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(text: str) -> bytes:
    padding = '=' * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _criar_token(usuario: dict[str, Any]) -> str:
    payload = {
        'id': int(usuario['id']),
        'tipo': usuario['tipo'],
        'id_empresa': int(usuario['id_empresa']) if usuario.get('id_empresa') is not None else None,
        'nome': usuario.get('nome', ''),
        'email': usuario.get('email', ''),
        'exp': int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    sig = _b64url_encode(hmac.new(AUTH_SECRET.encode('utf-8'), body.encode('ascii'), hashlib.sha256).digest())
    return f'{body}.{sig}'


def _decodificar_token(token: str) -> dict[str, Any]:
    try:
        body, sig = token.split('.', 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token inválido.') from exc
    expected = _b64url_encode(hmac.new(AUTH_SECRET.encode('utf-8'), body.encode('ascii'), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Assinatura de token inválida.')
    try:
        payload = json.loads(_b64url_decode(body).decode('utf-8'))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token malformado.') from exc
    if int(payload.get('exp', 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Sessão expirada. Faça login novamente.')
    return payload


def get_optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict[str, Any]]:
    if not authorization:
        return None
    if not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Cabeçalho Authorization inválido.')
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token ausente.')
    return _decodificar_token(token)


def require_roles(*roles: str):
    def _dep(user: Optional[dict[str, Any]] = Depends(get_optional_user)) -> dict[str, Any]:
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Autenticação obrigatória.')
        if user.get('tipo') not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Permissão insuficiente para esta operação.')
        return user
    return _dep


def _assert_chefe_empresa(user: dict[str, Any], id_empresa: int) -> None:
    if user.get('tipo') == 'chefe' and int(id_empresa) != int(user.get('id_empresa') or -1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='O perfil chefe só pode gerenciar recursos da própria empresa.',
        )


def _assert_chefe_projeto(db: Any, user: dict[str, Any], id_projeto: int) -> dict[str, Any]:
    projeto = da.obter_projeto(db, id_projeto)
    if projeto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Projeto {id_projeto} não encontrado.')
    _assert_chefe_empresa(user, projeto['id_empresa'])
    return projeto


def _assert_chefe_membro(db: Any, user: dict[str, Any], id_membro: int) -> dict[str, Any]:
    membro = da.obter_membro(db, id_membro)
    if membro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Membro {id_membro} não encontrado.')
    _assert_chefe_empresa(user, membro['id_empresa'])
    return membro


def _validar_mesma_empresa(db: Any, id_projeto: int, id_membro: int) -> None:
    projeto = da.obter_projeto(db, id_projeto)
    if projeto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Projeto {id_projeto} não encontrado.')
    membro = da.obter_membro(db, id_membro)
    if membro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Membro {id_membro} não encontrado.')
    if int(projeto['id_empresa']) != int(membro['id_empresa']):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='O membro e o projeto devem pertencer à mesma empresa.',
        )


def _escopo_usuario(db: Any, user: dict[str, Any]) -> dict[str, set[int]]:
    tipo = user.get('tipo')
    uid = int(user['id'])
    if tipo == 'membro':
        emp_id = int(user.get('id_empresa') or -1)
        projetos_emp = {int(p['id']) for p in da.listar_projetos(db, id_empresa=emp_id)}
        mp_proj = {
            int(r['id_projeto'])
            for r in da.listar_membro_projeto(db, id_membro=uid)
            if int(r['id_projeto']) in projetos_emp
        }
        tasks_m = [
            t for t in da.listar_tarefas(db)
            if t.get('id_membro') is not None and int(t['id_membro']) == uid and int(t['id_projeto']) in projetos_emp
        ]
        task_proj = {int(t['id_projeto']) for t in tasks_m}
        return {
            'company_ids': {emp_id} if emp_id >= 0 else set(),
            'project_ids': mp_proj | task_proj,
            'task_ids': {int(t['id']) for t in tasks_m},
        }
    if tipo == 'chefe':
        emp_id = int(user.get('id_empresa') or -1)
        projetos_emp = {int(p['id']) for p in da.listar_projetos(db, id_empresa=emp_id)}
        return {'company_ids': {emp_id} if emp_id >= 0 else set(), 'project_ids': projetos_emp, 'task_ids': set()}
    if tipo == 'cliente':
        demandas = da.listar_demandas(db, id_cliente=uid)
        p_ids = {int(d['id_projeto']) for d in demandas}
        c_ids = {int(p['id_empresa']) for p in da.listar_projetos(db) if int(p['id']) in p_ids}
        return {'company_ids': c_ids, 'project_ids': p_ids, 'task_ids': set()}
    return {'company_ids': set(), 'project_ids': set(), 'task_ids': set()}


def _verificar_usuario_existente(db: Any, tipo_usuario: TipoUsuario, usuario_id: int) -> dict[str, Any]:
    if tipo_usuario == 'admin':
        registro = da.obter_admin(db, usuario_id)
        label = 'Administrador'
    elif tipo_usuario in ('membro', 'chefe'):
        registro = da.obter_membro(db, usuario_id)
        label = 'Membro'
    else:
        registro = da.obter_cliente(db, usuario_id)
        label = 'Cliente'
    if registro is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'{label} {usuario_id} não encontrado.',
        )
    return registro


@app.post(
    '/auth/login',
    response_model=UsuarioAutenticado,
    tags=['Autenticação'],
    summary='Autenticar usuário (admin, chefe, membro ou cliente).',
)
def login_usuario(payload: LoginRequest, db=Depends(get_db)):
    usuario = da.autenticar_usuario(db, payload.email, payload.senha)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='E-mail ou senha inválidos.',
        )
    return {**usuario, 'token': _criar_token(usuario)}


@app.patch(
    '/auth/senhas/{tipo_usuario}/{usuario_id}',
    response_model=MensagemResposta,
    tags=['Autenticação'],
    summary='Definir ou alterar a senha de um usuário.',
)
def definir_senha(
    tipo_usuario: TipoUsuario,
    usuario_id: int,
    payload: DefinirSenhaRequest,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    registro = _verificar_usuario_existente(db, tipo_usuario, usuario_id)
    if user.get('tipo') == 'chefe':
        if tipo_usuario != 'membro' or (registro.get('perfil') or 'membro') != 'membro':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='O chefe só pode definir senhas de membros da sua empresa.',
            )
        _assert_chefe_empresa(user, registro['id_empresa'])
    if not da.definir_senha_usuario(db, tipo_usuario, usuario_id, payload.nova_senha):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Não foi possível salvar a senha no banco de dados.',
        )
    return MensagemResposta(mensagem=f'Senha definida com sucesso para o {tipo_usuario}.')


@app.delete(
    '/auth/senhas/{tipo_usuario}/{usuario_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Autenticação'],
    summary='Remover a senha de um usuário (revogar acesso).',
)
def revogar_senha(
    tipo_usuario: TipoUsuario,
    usuario_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    registro = _verificar_usuario_existente(db, tipo_usuario, usuario_id)
    if user.get('tipo') == 'chefe':
        if tipo_usuario != 'membro' or (registro.get('perfil') or 'membro') != 'membro':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='O chefe só pode revogar senhas de membros da sua empresa.',
            )
        _assert_chefe_empresa(user, registro['id_empresa'])
    if not da.remover_senha_usuario(db, tipo_usuario, usuario_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Não foi possível remover a senha do usuário.',
        )


# ---------------------------------------------------------------------------
# ROTAS GET — LEITURA DE ENTIDADES
# ---------------------------------------------------------------------------

@app.get('/empresas', response_model=list[Empresa], tags=['Empresas'], summary='Listar todas as empresas.')
def listar_empresas(
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    empresas = da.listar_empresas(db)
    if user and user.get('tipo') != 'admin':
        c_ids = _escopo_usuario(db, user)['company_ids']
        empresas = [e for e in empresas if int(e['id']) in c_ids]
    return empresas


@app.get('/empresas/{empresa_id}', response_model=Empresa, tags=['Empresas'], summary='Buscar dados de uma empresa.')
def obter_empresa(
    empresa_id: int,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') != 'admin':
        if int(empresa_id) not in _escopo_usuario(db, user)['company_ids']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado a esta empresa.')
    empresa = da.obter_empresa(db, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Empresa {empresa_id} não encontrada.')
    return empresa


@app.get('/projetos', response_model=list[Projeto], tags=['Projetos'], summary='Listar todos os projetos.')
def listar_projetos(
    id_empresa: Optional[int] = None,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    projetos = da.listar_projetos(db, id_empresa=id_empresa)
    tipo = user.get('tipo') if user else None
    if user and tipo != 'admin':
        escopo = _escopo_usuario(db, user)
        projetos = [p for p in projetos if int(p['id']) in escopo['project_ids']]
    if tipo == 'membro':
        return [{**p, 'clientes': []} for p in projetos]
    demandas = da.listar_demandas(db)
    if tipo == 'cliente':
        demandas = [d for d in demandas if int(d['id_cliente']) == int(user['id'])]
    clientes_por_projeto: dict[int, list[int]] = {}
    for d in demandas:
        clientes_por_projeto.setdefault(d['id_projeto'], []).append(d['id_cliente'])
    return [{**p, 'clientes': clientes_por_projeto.get(p['id'], [])} for p in projetos]


@app.get('/projeto/{projeto_id}', response_model=Projeto, tags=['Projetos'], summary='Buscar dados de um projeto.')
def obter_projeto(
    projeto_id: int,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    tipo = user.get('tipo') if user else None
    if user and tipo != 'admin':
        if int(projeto_id) not in _escopo_usuario(db, user)['project_ids']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado a este projeto.')
    projeto = da.obter_projeto(db, projeto_id)
    if projeto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Projeto {projeto_id} não encontrado.')
    if tipo == 'membro':
        return {**projeto, 'clientes': []}
    demandas = da.listar_demandas(db, id_projeto=projeto_id)
    if tipo == 'cliente':
        demandas = [d for d in demandas if int(d['id_cliente']) == int(user['id'])]
    return {**projeto, 'clientes': [d['id_cliente'] for d in demandas]}


@app.get('/clientes', response_model=list[Cliente], tags=['Clientes'], summary='Listar todos os clientes.')
def listar_clientes(
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') == 'membro':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Membros não possuem acesso à lista de clientes.')
    clientes = da.listar_clientes(db)
    if user and user.get('tipo') == 'cliente':
        return [c for c in clientes if int(c['id']) == int(user['id'])]
    if user and user.get('tipo') == 'chefe':
        emp_id = int(user.get('id_empresa') or -1)
        p_ids = _escopo_usuario(db, user)['project_ids']
        cli_dem = {int(d['id_cliente']) for d in da.listar_demandas(db) if int(d['id_projeto']) in p_ids}
        return [c for c in clientes if c.get('id_empresa') == emp_id or int(c['id']) in cli_dem]
    return clientes


@app.get('/cliente/{cliente_id}', response_model=Cliente, tags=['Clientes'], summary='Buscar dados de um cliente.')
def obter_cliente(
    cliente_id: int,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') == 'membro':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Membros não possuem acesso a dados de clientes.')
    if user and user.get('tipo') == 'cliente' and int(cliente_id) != int(user['id']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado a este cliente.')
    cliente = da.obter_cliente(db, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Cliente {cliente_id} não encontrado.')
    if user and user.get('tipo') == 'chefe':
        emp_id = int(user.get('id_empresa') or -1)
        p_ids = _escopo_usuario(db, user)['project_ids']
        cli_dem = {int(d['id_cliente']) for d in da.listar_demandas(db) if int(d['id_projeto']) in p_ids}
        if cliente.get('id_empresa') != emp_id and int(cliente['id']) not in cli_dem:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado a este cliente.')
    return cliente


@app.get('/membros', response_model=list[Membros], tags=['Membros'], summary='Listar todos os membros.')
def obter_membros(
    id_empresa: Optional[int] = None,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') == 'cliente':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Clientes não possuem acesso à lista de membros.')
    membros = da.listar_membros(db, id_empresa=id_empresa)
    if user and user.get('tipo') == 'membro':
        return [m for m in membros if int(m['id']) == int(user['id']) and int(m['id_empresa']) == int(user.get('id_empresa') or -1)]
    if user and user.get('tipo') == 'chefe':
        emp_id = int(user.get('id_empresa') or -1)
        return [m for m in membros if int(m['id_empresa']) == emp_id]
    return membros


@app.get('/membros/{membros_id}', response_model=Membros, tags=['Membros'], summary='Buscar dados de um membro.')
def obter_membro(
    membros_id: int,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') == 'cliente':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Clientes não possuem acesso a dados de membros.')
    if user and user.get('tipo') == 'membro' and int(membros_id) != int(user['id']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado a outros membros.')
    membro = da.obter_membro(db, membros_id)
    if membro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Membro {membros_id} não encontrado.')
    if user and user.get('tipo') in ('chefe', 'membro') and int(membro['id_empresa']) != int(user.get('id_empresa') or -1):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado a este membro.')
    return membro


@app.get('/sprints', response_model=list[Sprint], tags=['Sprints'], summary='Listar todas as sprints.')
def listar_sprints(
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    sprints = da.listar_sprints(db)
    if user and user.get('tipo') != 'admin':
        p_ids = _escopo_usuario(db, user)['project_ids']
        sprints = [s for s in sprints if int(s['id_projeto']) in p_ids]
    return sprints


@app.get('/sprints/{projeto_id}', response_model=list[Sprint], tags=['Sprints'], summary='Buscar sprints associadas a um projeto.')
def obter_sprint(
    projeto_id: int,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') != 'admin':
        if int(projeto_id) not in _escopo_usuario(db, user)['project_ids']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado às sprints deste projeto.')
    return da.listar_sprints(db, id_projeto=projeto_id)


@app.get('/tarefas', response_model=list[Tarefas], tags=['Tarefas'], summary='Listar tarefas com filtros opcionais.')
def listar_tarefas(
    id_projeto: Optional[int] = None,
    id_sprint: Optional[int] = None,
    estado: Optional[EstadoTarefa] = None,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') == 'cliente':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Clientes possuem acesso apenas a índices qualitativos.')
    tarefas = da.listar_tarefas(db, id_projeto=id_projeto, id_sprint=id_sprint, estado=estado)
    if user and user.get('tipo') == 'membro':
        t_ids = _escopo_usuario(db, user)['task_ids']
        return [t for t in tarefas if int(t['id']) in t_ids]
    if user and user.get('tipo') == 'chefe':
        p_ids = _escopo_usuario(db, user)['project_ids']
        return [t for t in tarefas if int(t['id_projeto']) in p_ids]
    return tarefas


@app.get('/tarefas/{tarefa_id}', response_model=Tarefas, tags=['Tarefas'], summary='Buscar dados de uma tarefa.')
def obter_tarefa(
    tarefa_id: int,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') == 'cliente':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Clientes possuem acesso apenas a índices qualitativos.')
    tarefa = da.obter_tarefa(db, tarefa_id)
    if tarefa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Tarefa {tarefa_id} não encontrada.')
    if user and user.get('tipo') == 'membro':
        if int(tarefa['id']) not in _escopo_usuario(db, user)['task_ids']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado a esta tarefa.')
    elif user and user.get('tipo') == 'chefe':
        if int(tarefa['id_projeto']) not in _escopo_usuario(db, user)['project_ids']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso negado a esta tarefa.')
    return tarefa


@app.get('/demandas', response_model=list[Demanda], tags=['Demandas'], summary='Listar vínculos entre projetos e clientes.')
def listar_demandas(
    id_projeto: Optional[int] = None,
    id_cliente: Optional[int] = None,
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    if user and user.get('tipo') == 'membro':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Membros não possuem acesso à tabela de demandas.')
    demandas = da.listar_demandas(db, id_projeto=id_projeto, id_cliente=id_cliente)
    if user and user.get('tipo') == 'cliente':
        return [d for d in demandas if int(d['id_cliente']) == int(user['id'])]
    if user and user.get('tipo') == 'chefe':
        p_ids = _escopo_usuario(db, user)['project_ids']
        return [d for d in demandas if int(d['id_projeto']) in p_ids]
    return demandas


# ---------------------------------------------------------------------------
# ROTAS GET — ANALYTICS E QUALIDADE DE DADOS (fetch_all, normalize, analytics)
# ---------------------------------------------------------------------------

@app.get('/dados', tags=['Analytics'], summary='Carregar e normalizar as tabelas do banco no escopo do usuário.')
def obter_todos_os_dados(
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    raw, columns, about = da.fetch_all(db)
    normalized = da.filtrar_dados_por_usuario(da.normalize(raw), user)
    sanitized_columns = {k: set(v) for k, v in columns.items()}
    for table_name in ('clientes', 'membros', 'admins'):
        if table_name in normalized and 'senha' in normalized[table_name].columns:
            normalized[table_name] = _sanitize_user_dataframe(normalized[table_name], include_flag=True)
            sanitized_columns.setdefault(table_name, set()).discard('senha')
            sanitized_columns[table_name].add('possui_senha')
    return {
        'about': about,
        'columns': {k: sorted(v) for k, v in sanitized_columns.items()},
        'tables': {k: _df_to_records(df) for k, df in normalized.items()},
    }


@app.get('/analytics', tags=['Analytics'], summary='Calcular indicadores agregados do portfólio.')
def obter_analytics(
    company_ids: Optional[list[int]] = Query(default=None),
    project_ids: Optional[list[int]] = Query(default=None),
    task_status: Optional[list[EstadoTarefa]] = Query(default=None),
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    raw, _, _ = da.fetch_all(db)
    normalized = da.filtrar_dados_por_usuario(da.normalize(raw), user)
    analytics = da.make_analytics(
        normalized,
        company_ids=company_ids,
        project_ids=project_ids,
        task_status=task_status,
    )
    for key in ('clients', 'members'):
        analytics[key] = _sanitize_user_dataframe(analytics[key], include_flag=False)
    return {k: _df_to_records(df) for k, df in analytics.items()}


@app.get('/analytics/sprints', tags=['Analytics'], summary='Calcular métricas de desempenho por sprint.')
def obter_analytics_sprints(
    company_ids: Optional[list[int]] = Query(default=None),
    project_ids: Optional[list[int]] = Query(default=None),
    task_status: Optional[list[EstadoTarefa]] = Query(default=None),
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    raw, _, _ = da.fetch_all(db)
    normalized = da.filtrar_dados_por_usuario(da.normalize(raw), user)
    analytics = da.make_analytics(
        normalized,
        company_ids=company_ids,
        project_ids=project_ids,
        task_status=task_status,
    )
    metrics = da.sprint_analytics(analytics['sprints'], analytics['tasks'])
    return _df_to_records(metrics)


@app.get('/qualidade', response_model=list[QualidadeItem], tags=['Analytics'], summary='Executar auditoria de qualidade de dados.')
def obter_qualidade_dados(
    db=Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_optional_user),
):
    raw, _, _ = da.fetch_all(db)
    normalized = da.filtrar_dados_por_usuario(da.normalize(raw), user)
    checks = da.qualidade_cliente(normalized) if user and user.get('tipo') == 'cliente' else da.data_quality(normalized)
    return [QualidadeItem(verificacao=nome, ocorrencias=qtd) for nome, qtd in checks]


# ---------------------------------------------------------------------------
# ROTAS DE ADMINS E ALOCAÇÃO MEMBRO ↔ PROJETO
# ---------------------------------------------------------------------------

@app.get('/admins', response_model=list[AdminOut], tags=['Admins'], summary='Listar administradores do servidor.')
def listar_admins(
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    return da.listar_admins(db)


@app.post(
    '/admins',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Admins'],
    summary='Cadastrar um novo administrador.',
)
def criar_admin(
    payload: AdminCreate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if not da.inserir_novo_admin(db, payload.nome, str(payload.email), payload.senha):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível cadastrar o administrador.')
    return MensagemResposta(mensagem='Administrador cadastrado com sucesso.')


@app.delete(
    '/admins/{admin_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Admins'],
    summary='Remover um administrador.',
)
def remover_admin(
    admin_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if int(admin_id) == int(user['id']):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Você não pode remover a sua própria conta de administrador.')
    if da.obter_admin(db, admin_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Administrador {admin_id} não encontrado.')
    if not da.deletar_admin(db, admin_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível remover o administrador.')


@app.get('/membro-projeto', response_model=list[MembroProjeto], tags=['Membros'], summary='Listar alocações entre membros e projetos.')
def listar_membro_projeto(
    id_projeto: Optional[int] = None,
    id_membro: Optional[int] = None,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    rows = da.listar_membro_projeto(db, id_projeto=id_projeto, id_membro=id_membro)
    if user.get('tipo') == 'chefe':
        projetos_emp = {p['id'] for p in da.listar_projetos(db, id_empresa=user.get('id_empresa'))}
        rows = [r for r in rows if r['id_projeto'] in projetos_emp]
    return rows


@app.post(
    '/membro-projeto',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Membros'],
    summary='Associar um membro a um projeto.',
)
def criar_membro_projeto(
    payload: MembroProjeto,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    _assert_chefe_projeto(db, user, payload.id_projeto)
    _assert_chefe_membro(db, user, payload.id_membro)
    _validar_mesma_empresa(db, payload.id_projeto, payload.id_membro)
    if not da.vincular_membro_projeto(db, payload.id_projeto, payload.id_membro):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Não foi possível associar o membro ao projeto (o vínculo já pode existir).',
        )
    return MensagemResposta(mensagem='Membro associado ao projeto com sucesso.')


@app.delete(
    '/membro-projeto/{projeto_id}/{membro_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Membros'],
    summary='Desvincular um membro de um projeto.',
)
def remover_membro_projeto(
    projeto_id: int,
    membro_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    _assert_chefe_projeto(db, user, projeto_id)
    _assert_chefe_membro(db, user, membro_id)
    if not da.listar_membro_projeto(db, id_projeto=projeto_id, id_membro=membro_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Vínculo entre projeto {projeto_id} e membro {membro_id} não encontrado.',
        )
    if not da.desvincular_membro_projeto(db, projeto_id, membro_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível desvincular o membro do projeto.')


# ---------------------------------------------------------------------------
# ROTAS POST — INSERÇÃO E VÍNCULOS
# ---------------------------------------------------------------------------

@app.post(
    '/empresas',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Empresas'],
    summary='Cadastrar uma nova empresa.',
)
def criar_empresa(
    payload: Empresa,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if not da.inserir_nova_empresa(db, payload.id, payload.nome, payload.rep):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível cadastrar a empresa.')
    return MensagemResposta(mensagem='Empresa cadastrada com sucesso.')


@app.post(
    '/membros',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Membros'],
    summary='Cadastrar um novo membro.',
)
def criar_membro(
    payload: MembroCreate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    _assert_chefe_empresa(user, payload.id_empresa)
    if user.get('tipo') == 'chefe' and payload.perfil != 'membro':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='O chefe só pode cadastrar colaboradores com perfil membro.',
        )
    if not da.inserir_novo_membro(
        db,
        payload.id,
        payload.id_empresa,
        payload.nome,
        str(payload.email),
        payload.cargo,
        perfil=payload.perfil,
        senha=payload.senha,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível cadastrar o membro.')
    return MensagemResposta(mensagem='Membro cadastrado com sucesso.')


@app.post(
    '/clientes',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Clientes'],
    summary='Cadastrar um novo cliente.',
)
def criar_cliente(
    payload: ClienteCreate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if not da.inserir_novo_cliente(db, payload.nome, str(payload.email), payload.id_empresa):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível cadastrar o cliente.')
    return MensagemResposta(mensagem='Cliente cadastrado com sucesso.')


@app.post(
    '/projetos',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Projetos'],
    summary='Cadastrar um novo projeto (opcionalmente vinculado a um cliente).',
)
def criar_projeto(
    payload: ProjetoCreate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    _assert_chefe_empresa(user, payload.id_empresa)
    if not da.inserir_novo_projeto(
        db,
        payload.id,
        payload.id_empresa,
        payload.nome,
        payload.descricao,
        payload.id_cliente,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível cadastrar o projeto.')
    return MensagemResposta(mensagem='Projeto cadastrado com sucesso.')


@app.post(
    '/sprints',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Sprints'],
    summary='Cadastrar uma nova sprint.',
)
def criar_sprint(
    payload: SprintCreate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    _assert_chefe_projeto(db, user, payload.id_projeto)
    if not da.inserir_nova_sprint(
        db,
        payload.id_projeto,
        int(payload.is_done),
        payload.data_in,
        payload.data_fin,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível cadastrar a sprint.')
    return MensagemResposta(mensagem='Sprint cadastrada com sucesso.')


@app.post(
    '/tarefas',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Tarefas'],
    summary='Cadastrar uma nova tarefa.',
)
def criar_tarefa(
    payload: TarefaCreate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    _assert_chefe_projeto(db, user, payload.id_projeto)
    if payload.id_membro is not None:
        _assert_chefe_membro(db, user, payload.id_membro)
        _validar_mesma_empresa(db, payload.id_projeto, payload.id_membro)
    if not da.inserir_nova_tarefa(
        db,
        payload.id_projeto,
        payload.descricao,
        estado=payload.estado,
        id_sprint=payload.id_sprint,
        data_cria=payload.data_cria,
        data_fin=payload.data_fin,
        id_membro=payload.id_membro,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível cadastrar a tarefa.')
    return MensagemResposta(mensagem='Tarefa cadastrada com sucesso.')


@app.post(
    '/demandas',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Demandas'],
    summary='Vincular um projeto a um cliente na tabela demanda.',
)
def criar_demanda(
    payload: Demanda,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if not da.vincular_projeto_cliente(db, payload.id_projeto, payload.id_cliente):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Não foi possível vincular o projeto ao cliente (verifique se o vínculo já existe).',
        )
    return MensagemResposta(mensagem='Projeto vinculado ao cliente com sucesso.')


# ---------------------------------------------------------------------------
# ROTAS PATCH — ATUALIZAÇÃO
# ---------------------------------------------------------------------------

@app.patch(
    '/membros/{membro_id}/perfil',
    response_model=MensagemResposta,
    tags=['Membros'],
    summary='Promover ou alterar perfil de um membro (membro ou chefe).',
)
def atualizar_perfil_membro(
    membro_id: int,
    payload: MembroPerfilUpdate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if da.obter_membro(db, membro_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Membro {membro_id} não encontrado.')
    if not da.atualizar_perfil_membro(db, membro_id, payload.perfil):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível atualizar o perfil do membro.')
    return MensagemResposta(mensagem='Perfil do membro atualizado com sucesso.')


@app.patch(
    '/tarefas/{tarefa_id}/estado',
    response_model=MensagemResposta,
    tags=['Tarefas'],
    summary='Atualizar o estado de uma tarefa.',
)
def atualizar_estado_tarefa(
    tarefa_id: int,
    payload: TarefaEstadoUpdate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe', 'membro')),
):
    tarefa = da.obter_tarefa(db, tarefa_id)
    if tarefa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Tarefa {tarefa_id} não encontrada.')
    if user.get('tipo') == 'membro':
        if int(tarefa_id) not in _escopo_usuario(db, user)['task_ids']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Você só pode alterar o estado de tarefas atribuídas a você.',
            )
    else:
        _assert_chefe_projeto(db, user, tarefa['id_projeto'])
    if not da.atualizar_estado_tarefa(db, tarefa_id, payload.estado):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível atualizar o estado da tarefa.')
    return MensagemResposta(mensagem='Estado da tarefa atualizado com sucesso.')


@app.patch(
    '/tarefas/{tarefa_id}/sprint',
    response_model=MensagemResposta,
    tags=['Tarefas'],
    summary='Associar uma tarefa a uma sprint (ou remover da sprint enviando null).',
)
def associar_tarefa_sprint(
    tarefa_id: int,
    payload: TarefaSprintUpdate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    tarefa = da.obter_tarefa(db, tarefa_id)
    if tarefa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Tarefa {tarefa_id} não encontrada.')
    _assert_chefe_projeto(db, user, tarefa['id_projeto'])
    if not da.associar_tarefa_a_sprint(db, tarefa_id, payload.id_sprint):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível associar a tarefa à sprint.')
    return MensagemResposta(mensagem='Tarefa associada à sprint com sucesso.')


@app.patch(
    '/tarefas/{tarefa_id}/membro',
    response_model=MensagemResposta,
    tags=['Tarefas'],
    summary='Atribuir uma tarefa a um membro (ou remover atribuição enviando null).',
)
def associar_tarefa_membro(
    tarefa_id: int,
    payload: TarefaMembroUpdate,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin', 'chefe')),
):
    tarefa = da.obter_tarefa(db, tarefa_id)
    if tarefa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Tarefa {tarefa_id} não encontrada.')
    _assert_chefe_projeto(db, user, tarefa['id_projeto'])
    if payload.id_membro is not None:
        _assert_chefe_membro(db, user, payload.id_membro)
        _validar_mesma_empresa(db, tarefa['id_projeto'], payload.id_membro)
    if not da.associar_tarefa_a_membro(db, tarefa_id, payload.id_membro):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível atribuir a tarefa ao membro.')
    return MensagemResposta(mensagem='Tarefa atribuída ao membro com sucesso.')


# ---------------------------------------------------------------------------
# ROTAS DELETE — DELEÇÃO E DESVINCULAÇÃO
# ---------------------------------------------------------------------------

@app.delete(
    '/empresas/{empresa_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Empresas'],
    summary='Remover uma empresa.',
)
def remover_empresa(
    empresa_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if da.obter_empresa(db, empresa_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Empresa {empresa_id} não encontrada.')
    if not da.deletar_empresa(db, empresa_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Não foi possível remover a empresa. Verifique se existem registros vinculados.',
        )


@app.delete(
    '/clientes/{cliente_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Clientes'],
    summary='Remover um cliente.',
)
def remover_cliente(
    cliente_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if da.obter_cliente(db, cliente_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Cliente {cliente_id} não encontrado.')
    if not da.deletar_cliente(db, cliente_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível remover o cliente.')


@app.delete(
    '/membros/{membros_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Membros'],
    summary='Remover um membro.',
)
def remover_membro(
    membros_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if da.obter_membro(db, membros_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Membro {membros_id} não encontrado.')
    if not da.deletar_membro(db, membros_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível remover o membro.')


@app.delete(
    '/projetos/{projeto_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Projetos'],
    summary='Remover um projeto.',
)
def remover_projeto(
    projeto_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if da.obter_projeto(db, projeto_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Projeto {projeto_id} não encontrado.')
    if not da.deletar_projeto(db, projeto_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Não foi possível remover o projeto. Verifique se existem registros vinculados.',
        )


@app.delete(
    '/sprints/{sprint_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Sprints'],
    summary='Remover uma sprint.',
)
def remover_sprint(
    sprint_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if da.obter_sprint(db, sprint_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Sprint {sprint_id} não encontrada.')
    if not da.deletar_sprint(db, sprint_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Não foi possível remover a sprint. Verifique se existem tarefas vinculadas.',
        )


@app.delete(
    '/tarefas/{tarefa_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Tarefas'],
    summary='Remover uma tarefa.',
)
def remover_tarefa(
    tarefa_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if da.obter_tarefa(db, tarefa_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Tarefa {tarefa_id} não encontrada.')
    if not da.deletar_tarefa(db, tarefa_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível remover a tarefa.')


@app.delete(
    '/demandas/{projeto_id}/{cliente_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Demandas'],
    summary='Desvincular um projeto de um cliente na tabela demanda.',
)
def remover_demanda(
    projeto_id: int,
    cliente_id: int,
    db=Depends(get_db),
    user: dict[str, Any] = Depends(require_roles('admin')),
):
    if not da.listar_demandas(db, id_projeto=projeto_id, id_cliente=cliente_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Vínculo entre projeto {projeto_id} e cliente {cliente_id} não encontrado.',
        )
    if not da.desvincular_projeto_cliente(db, projeto_id, cliente_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível desvincular projeto e cliente.')


if __name__ == '__main__':
    target = f'{__package__}.api:app' if __package__ else 'api:app'
    uvicorn.run(target, host='0.0.0.0', port=8000, reload=True)
