"""API FastAPI do backend EJFlow integrada às funções de backend/data_access.py."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal, Optional

import numpy as np
import pandas as pd
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
from mysql.connector import Error, pooling
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

try:
    from backend import data_access as da
except ImportError:
    import data_access as da


EstadoTarefa = Literal['nao_iniciada', 'em_andamento', 'concluida']


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
    estado: Optional[str] = None
    descricao: Optional[str] = Field(default=None, max_length=1000)
    data_cria: Optional[datetime] = None
    data_fin: Optional[datetime] = None


class TarefaCreate(BaseModel):
    id_projeto: int
    descricao: str = Field(..., min_length=1, max_length=1000)
    estado: EstadoTarefa = 'nao_iniciada'
    id_sprint: Optional[int] = None
    data_cria: Optional[datetime] = None
    data_fin: Optional[datetime] = None


class TarefaEstadoUpdate(BaseModel):
    estado: EstadoTarefa


class TarefaSprintUpdate(BaseModel):
    id_sprint: Optional[int] = None


class Demanda(BaseModel):
    id_projeto: int
    id_cliente: int


class MensagemResposta(BaseModel):
    mensagem: str


class QualidadeItem(BaseModel):
    verificacao: str
    ocorrencias: int


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


# ---------------------------------------------------------------------------
# ROTAS GET — LEITURA DE ENTIDADES
# ---------------------------------------------------------------------------

@app.get('/empresas', response_model=list[Empresa], tags=['Empresas'], summary='Listar todas as empresas.')
def listar_empresas(db=Depends(get_db)):
    return da.listar_empresas(db)


@app.get('/empresas/{empresa_id}', response_model=Empresa, tags=['Empresas'], summary='Buscar dados de uma empresa.')
def obter_empresa(empresa_id: int, db=Depends(get_db)):
    empresa = da.obter_empresa(db, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Empresa {empresa_id} não encontrada.')
    return empresa


@app.get('/projetos', response_model=list[Projeto], tags=['Projetos'], summary='Listar todos os projetos.')
def listar_projetos(id_empresa: Optional[int] = None, db=Depends(get_db)):
    projetos = da.listar_projetos(db, id_empresa=id_empresa)
    demandas = da.listar_demandas(db)
    clientes_por_projeto: dict[int, list[int]] = {}
    for d in demandas:
        clientes_por_projeto.setdefault(d['id_projeto'], []).append(d['id_cliente'])
    return [{**p, 'clientes': clientes_por_projeto.get(p['id'], [])} for p in projetos]


@app.get('/projeto/{projeto_id}', response_model=Projeto, tags=['Projetos'], summary='Buscar dados de um projeto.')
def obter_projeto(projeto_id: int, db=Depends(get_db)):
    projeto = da.obter_projeto(db, projeto_id)
    if projeto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Projeto {projeto_id} não encontrado.')
    demandas = da.listar_demandas(db, id_projeto=projeto_id)
    return {**projeto, 'clientes': [d['id_cliente'] for d in demandas]}


@app.get('/clientes', response_model=list[Cliente], tags=['Clientes'], summary='Listar todos os clientes.')
def listar_clientes(db=Depends(get_db)):
    return da.listar_clientes(db)


@app.get('/cliente/{cliente_id}', response_model=Cliente, tags=['Clientes'], summary='Buscar dados de um cliente.')
def obter_cliente(cliente_id: int, db=Depends(get_db)):
    cliente = da.obter_cliente(db, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Cliente {cliente_id} não encontrado.')
    return cliente


@app.get('/membros', response_model=list[Membros], tags=['Membros'], summary='Listar todos os membros.')
def obter_membros(id_empresa: Optional[int] = None, db=Depends(get_db)):
    return da.listar_membros(db, id_empresa=id_empresa)


@app.get('/membros/{membros_id}', response_model=Membros, tags=['Membros'], summary='Buscar dados de um membro.')
def obter_membro(membros_id: int, db=Depends(get_db)):
    membro = da.obter_membro(db, membros_id)
    if membro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Membro {membros_id} não encontrado.')
    return membro


@app.get('/sprints', response_model=list[Sprint], tags=['Sprints'], summary='Listar todas as sprints.')
def listar_sprints(db=Depends(get_db)):
    return da.listar_sprints(db)


@app.get('/sprints/{projeto_id}', response_model=list[Sprint], tags=['Sprints'], summary='Buscar sprints associadas a um projeto.')
def obter_sprint(projeto_id: int, db=Depends(get_db)):
    return da.listar_sprints(db, id_projeto=projeto_id)


@app.get('/tarefas', response_model=list[Tarefas], tags=['Tarefas'], summary='Listar tarefas com filtros opcionais.')
def listar_tarefas(
    id_projeto: Optional[int] = None,
    id_sprint: Optional[int] = None,
    estado: Optional[EstadoTarefa] = None,
    db=Depends(get_db),
):
    return da.listar_tarefas(db, id_projeto=id_projeto, id_sprint=id_sprint, estado=estado)


@app.get('/tarefas/{tarefa_id}', response_model=Tarefas, tags=['Tarefas'], summary='Buscar dados de uma tarefa.')
def obter_tarefa(tarefa_id: int, db=Depends(get_db)):
    tarefa = da.obter_tarefa(db, tarefa_id)
    if tarefa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Tarefa {tarefa_id} não encontrada.')
    return tarefa


@app.get('/demandas', response_model=list[Demanda], tags=['Demandas'], summary='Listar vínculos entre projetos e clientes.')
def listar_demandas(
    id_projeto: Optional[int] = None,
    id_cliente: Optional[int] = None,
    db=Depends(get_db),
):
    return da.listar_demandas(db, id_projeto=id_projeto, id_cliente=id_cliente)


# ---------------------------------------------------------------------------
# ROTAS GET — ANALYTICS E QUALIDADE DE DADOS (fetch_all, normalize, analytics)
# ---------------------------------------------------------------------------

@app.get('/dados', tags=['Analytics'], summary='Carregar e normalizar todas as tabelas do banco.')
def obter_todos_os_dados(db=Depends(get_db)):
    raw, columns, about = da.fetch_all(db)
    normalized = da.normalize(raw)
    return {
        'about': about,
        'columns': {k: sorted(v) for k, v in columns.items()},
        'tables': {k: _df_to_records(df) for k, df in normalized.items()},
    }


@app.get('/analytics', tags=['Analytics'], summary='Calcular indicadores agregados do portfólio.')
def obter_analytics(
    company_ids: Optional[list[int]] = Query(default=None),
    project_ids: Optional[list[int]] = Query(default=None),
    task_status: Optional[list[EstadoTarefa]] = Query(default=None),
    db=Depends(get_db),
):
    raw, _, _ = da.fetch_all(db)
    normalized = da.normalize(raw)
    analytics = da.make_analytics(
        normalized,
        company_ids=company_ids,
        project_ids=project_ids,
        task_status=task_status,
    )
    return {k: _df_to_records(df) for k, df in analytics.items()}


@app.get('/analytics/sprints', tags=['Analytics'], summary='Calcular métricas de desempenho por sprint.')
def obter_analytics_sprints(
    company_ids: Optional[list[int]] = Query(default=None),
    project_ids: Optional[list[int]] = Query(default=None),
    task_status: Optional[list[EstadoTarefa]] = Query(default=None),
    db=Depends(get_db),
):
    raw, _, _ = da.fetch_all(db)
    normalized = da.normalize(raw)
    analytics = da.make_analytics(
        normalized,
        company_ids=company_ids,
        project_ids=project_ids,
        task_status=task_status,
    )
    metrics = da.sprint_analytics(analytics['sprints'], analytics['tasks'])
    return _df_to_records(metrics)


@app.get('/qualidade', response_model=list[QualidadeItem], tags=['Analytics'], summary='Executar auditoria de qualidade de dados.')
def obter_qualidade_dados(db=Depends(get_db)):
    raw, _, _ = da.fetch_all(db)
    normalized = da.normalize(raw)
    checks = da.data_quality(normalized)
    return [QualidadeItem(verificacao=nome, ocorrencias=qtd) for nome, qtd in checks]


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
def criar_empresa(payload: Empresa, db=Depends(get_db)):
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
def criar_membro(payload: Membros, db=Depends(get_db)):
    if not da.inserir_novo_membro(db, payload.id, payload.id_empresa, payload.nome, str(payload.email), payload.cargo):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível cadastrar o membro.')
    return MensagemResposta(mensagem='Membro cadastrado com sucesso.')


@app.post(
    '/clientes',
    response_model=MensagemResposta,
    status_code=status.HTTP_201_CREATED,
    tags=['Clientes'],
    summary='Cadastrar um novo cliente.',
)
def criar_cliente(payload: ClienteCreate, db=Depends(get_db)):
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
def criar_projeto(payload: ProjetoCreate, db=Depends(get_db)):
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
def criar_sprint(payload: SprintCreate, db=Depends(get_db)):
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
def criar_tarefa(payload: TarefaCreate, db=Depends(get_db)):
    if not da.inserir_nova_tarefa(
        db,
        payload.id_projeto,
        payload.descricao,
        estado=payload.estado,
        id_sprint=payload.id_sprint,
        data_cria=payload.data_cria,
        data_fin=payload.data_fin,
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
def criar_demanda(payload: Demanda, db=Depends(get_db)):
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
    '/tarefas/{tarefa_id}/estado',
    response_model=MensagemResposta,
    tags=['Tarefas'],
    summary='Atualizar o estado de uma tarefa.',
)
def atualizar_estado_tarefa(tarefa_id: int, payload: TarefaEstadoUpdate, db=Depends(get_db)):
    if da.obter_tarefa(db, tarefa_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Tarefa {tarefa_id} não encontrada.')
    if not da.atualizar_estado_tarefa(db, tarefa_id, payload.estado):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível atualizar o estado da tarefa.')
    return MensagemResposta(mensagem='Estado da tarefa atualizado com sucesso.')


@app.patch(
    '/tarefas/{tarefa_id}/sprint',
    response_model=MensagemResposta,
    tags=['Tarefas'],
    summary='Associar uma tarefa a uma sprint (ou remover da sprint enviando null).',
)
def associar_tarefa_sprint(tarefa_id: int, payload: TarefaSprintUpdate, db=Depends(get_db)):
    if da.obter_tarefa(db, tarefa_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Tarefa {tarefa_id} não encontrada.')
    if not da.associar_tarefa_a_sprint(db, tarefa_id, payload.id_sprint):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Não foi possível associar a tarefa à sprint.')
    return MensagemResposta(mensagem='Tarefa associada à sprint com sucesso.')


# ---------------------------------------------------------------------------
# ROTAS DELETE — DELEÇÃO E DESVINCULAÇÃO
# ---------------------------------------------------------------------------

@app.delete(
    '/empresas/{empresa_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    tags=['Empresas'],
    summary='Remover uma empresa.',
)
def remover_empresa(empresa_id: int, db=Depends(get_db)):
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
def remover_cliente(cliente_id: int, db=Depends(get_db)):
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
def remover_membro(membros_id: int, db=Depends(get_db)):
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
def remover_projeto(projeto_id: int, db=Depends(get_db)):
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
def remover_sprint(sprint_id: int, db=Depends(get_db)):
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
def remover_tarefa(tarefa_id: int, db=Depends(get_db)):
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
def remover_demanda(projeto_id: int, cliente_id: int, db=Depends(get_db)):
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
