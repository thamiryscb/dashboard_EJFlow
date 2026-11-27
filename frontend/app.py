"""EJFlow | Observatório de Projetos — painel acadêmico e executivo (Banco 2).
Painel interativo com operações de leitura, escrita (CRUD) e gerenciamento de vínculos via API FastAPI.
"""
from __future__ import annotations

import io
import os
import zipfile
from html import escape
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

TABLES = ('empresas', 'clientes', 'projetos', 'membros', 'demanda', 'sprints', 'tarefas')
ALL_TABLES = TABLES + ('membro_projeto', 'admins')
TABLE_COLUMNS = {
    'empresas': ['id', 'nome', 'rep'],
    'clientes': ['id', 'nome', 'email', 'id_empresa'],
    'projetos': ['id', 'id_empresa', 'nome', 'descricao'],
    'membros': ['id', 'id_empresa', 'nome', 'email', 'cargo', 'perfil'],
    'demanda': ['id_projeto', 'id_cliente'],
    'sprints': ['id', 'id_projeto', 'isDone', 'data_in', 'data_fin'],
    'tarefas': ['id', 'id_projeto', 'id_sprint', 'id_membro', 'estado', 'descricao', 'data_cria', 'data_fin'],
    'membro_projeto': ['id_projeto', 'id_membro'],
    'admins': ['id', 'nome', 'email'],
}
SUMMARY_COLUMNS = [
    'id', 'id_empresa', 'nome', 'descricao', 'empresa',
    'total_tarefas', 'concluidas', 'em_andamento', 'nao_iniciadas',
    'total_sprints', 'sprints_concluidas', 'clientes', 'taxa_conclusao',
]
SPRINT_METRICS_COLUMNS = [
    'id_sprint', 'id_projeto', 'isDone', 'data_in', 'data_fin',
    'tarefas', 'concluidas', 'pendentes', 'taxa_conclusao', 'duracao_dias',
]

st.set_page_config(
    page_title='EJFlow | Observatório de Projetos',
    page_icon='◆',
    layout='wide',
    initial_sidebar_state='expanded',
)
COLORS = {'concluida': '#2DD5A7', 'em_andamento': '#6D8DFF', 'nao_iniciada': '#F6BA64', 'nao_informado': '#94A3B8'}
PALETTE = ['#698BFF', '#32D5AB', '#F8BA70', '#BA99FF', '#78C8ED', '#FA8E9C', '#98A5C0']

if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None
st.session_state.setdefault('projeto_ativo_id', None)
st.session_state.setdefault('sprint_ativa_id', None)

st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap');
html,body,[data-testid="stApp"] {font-family:'DM Sans',sans-serif;}
[data-testid="stAppViewContainer"] {background:radial-gradient(ellipse at 80% 0%,#18264b 0%,#0c1427 37%,#090f1d 90%);color:#e9f0ff;}
[data-testid="stSidebar"] {background:#0d1729;border-right:1px solid #27344a;}
[data-testid="stSidebar"] * {color:#E5ECFA;}
.block-container {max-width:1560px;padding:2.1rem 2.2rem 4rem;}
h1,h2,h3 {font-family:Manrope,sans-serif;letter-spacing:-0.045em;color:#F4F7FF!important;}
h1 {font-weight:800!important;font-size:2.5rem!important;}
h2 {font-size:1.45rem!important;}
h3 {font-size:1.05rem!important;}
p,li,div[data-testid="stCaptionContainer"] {color:#B9C7DC;}
[data-testid="stMetric"] {background:linear-gradient(160deg,#18253d,#111d32);border:1px solid #31405b;box-shadow:0px 8px 25px #0000001a;padding:1.1rem 1.3rem;border-radius:18px;min-height:118px;}
[data-testid="stMetricValue"] {color:#F3F6FF!important;font-family:Manrope,sans-serif;font-weight:800;font-size:1.85rem!important;}
[data-testid="stMetricLabel"] {color:#AABAD1!important;font-size:.88rem;}
[data-testid="stMetricDelta"] {font-size:.78rem;}
[data-testid="stTabs"] [role="tablist"] {border-bottom:1px solid #30405a;gap:.5rem;}
[data-testid="stTabs"] button {color:#AFC4E4;font-weight:700;padding:.75rem 1.05rem;border-radius:9px 9px 0 0;}
[data-testid="stTabs"] button[aria-selected="true"] {color:#91AFFF!important;border-bottom:3px solid #7593FF;}
[data-testid="stPlotlyChart"] {background:#111c30;border:1px solid #2b3a55;border-radius:18px;padding:.4rem .8rem;overflow:hidden;}
[data-testid="stDataFrame"] {border:1px solid #2B3C55;border-radius:14px;overflow:hidden;}
[data-testid="stAlert"] {border-radius:14px;}
div.stButton>button[kind="primary"] {background:#657EFF;border:none;border-radius:12px;font-weight:700;}
.eyebrow {text-transform:uppercase;letter-spacing:.19em;color:#43E0BC;font-size:.72rem;font-weight:800;margin-bottom:4px;}
.hero {padding:1.2rem 0 1.4rem;}
.hero p {margin:.5rem 0;font-size:1rem;color:#AFC2DC;}
.pill {display:inline-block;background:#193e47;border:1px solid #235a61;color:#74F0CE;border-radius:50px;padding:5px 12px;font-size:.75rem;font-weight:700;letter-spacing:.02em;}
.insight {background:linear-gradient(120deg,#1a2843,#14243e);border:1px solid #2e4666;border-radius:15px;padding:16px 19px;min-height:118px;}
.insight strong {font-size:1rem;color:#ECF3FF;}
.insight p {color:#B9CCE7;font-size:.85rem;margin:8px 0 0;}
.info-card {background:#142136;border:1px solid #34435a;border-radius:15px;padding:18px 20px;}
.entity-card {background:linear-gradient(160deg,#18253d,#111d32);border:1px solid #31405b;border-radius:16px;padding:16px 18px;margin-bottom:10px;box-shadow:0 8px 20px #0000001f;}
.entity-card-title {font-family:Manrope,sans-serif;font-weight:800;font-size:1.05rem;color:#F3F6FF;margin-bottom:4px;}
.entity-card-meta {font-size:.82rem;color:#9FB4D1;margin-bottom:8px;}
.badge-ok {display:inline-block;background:#153f3a;border:1px solid #23685d;color:#43E0BC;border-radius:50px;padding:2px 10px;font-size:.73rem;font-weight:700;}
.badge-prog {display:inline-block;background:#1c2f59;border:1px solid #335294;color:#8EAAFF;border-radius:50px;padding:2px 10px;font-size:.73rem;font-weight:700;}
.badge-warn {display:inline-block;background:#45341b;border:1px solid #755525;color:#F6BA64;border-radius:50px;padding:2px 10px;font-size:.73rem;font-weight:700;}
.section-head {color:#D5E1F6;font-weight:800;font-size:1rem;letter-spacing:.01em;margin:18px 0 8px;}
small {color:#A3B7D0;}
</style>''', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cliente HTTP da API FastAPI
# ---------------------------------------------------------------------------

def get_api_base_url() -> str:
    """Lê a URL base da API a partir de API_BASE_URL ou st.secrets."""
    try:
        secrets = dict(st.secrets)
    except Exception:
        secrets = {}
    url = os.getenv('API_BASE_URL') or secrets.get('API_BASE_URL') or 'http://127.0.0.1:8000'
    return str(url).rstrip('/')


def _extract_error_detail(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text or f'Erro HTTP {response.status_code}'
    detail = body.get('detail')
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = '.'.join(str(x) for x in item.get('loc', []) if x != 'body')
                msg = item.get('msg', '')
                parts.append(f'{loc}: {msg}' if loc else msg)
            else:
                parts.append(str(item))
        return '; '.join(parts) or f'Erro HTTP {response.status_code}'
    return f'Erro HTTP {response.status_code}'


def api_request(
    method: str,
    api_url: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: list[tuple[str, Any]] | dict[str, Any] | None = None,
    timeout: int = 15,
) -> tuple[bool, Any, str | None]:
    """Executa requisição HTTP para o backend e retorna (ok, dados, erro)."""
    url = f'{api_url}{path}'
    headers: dict[str, str] = {}
    usuario_sess = st.session_state.get('usuario_logado')
    if isinstance(usuario_sess, dict) and usuario_sess.get('token') and not path.startswith('/auth/login'):
        headers['Authorization'] = f"Bearer {usuario_sess['token']}"
    try:
        response = requests.request(
            method=method,
            url=url,
            json=json_body,
            params=params,
            headers=headers or None,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return False, None, f'Falha de comunicação com a API ({url}): {exc}'

    if response.ok:
        if not response.content:
            return True, None, None
        try:
            return True, response.json(), None
        except ValueError:
            return True, response.text, None

    return False, None, _extract_error_detail(response)


def _records_to_df(records: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=columns)
    for col in columns:
        if col not in df.columns:
            df[col] = pd.Series(dtype='object')
    return df


def _coerce_table_types(table: str, df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    for col in ('id', 'id_empresa', 'id_projeto', 'id_sprint', 'id_cliente', 'id_membro'):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors='coerce').astype('Int64')
    if table == 'sprints':
        for col in ('data_in', 'data_fin'):
            if col in frame.columns:
                frame[col] = pd.to_datetime(frame[col], errors='coerce')
        if 'isDone' in frame.columns:
            frame['isDone'] = pd.to_numeric(frame['isDone'], errors='coerce')
    elif table == 'tarefas':
        for col in ('data_cria', 'data_fin'):
            if col in frame.columns:
                frame[col] = pd.to_datetime(frame[col], errors='coerce')
        if 'estado' in frame.columns:
            frame['estado'] = frame['estado'].fillna('nao_informado').astype(str)
    for col in ('nome', 'rep', 'descricao', 'cargo', 'email', 'perfil'):
        if col in frame.columns:
            frame[col] = frame[col].fillna('').astype(str)
    if 'possui_senha' in frame.columns:
        frame['possui_senha'] = frame['possui_senha'].fillna(False).astype(bool)
    return frame


@st.cache_data(ttl=60, show_spinner=False)
def load_db(api_url: str, auth_token: str = '') -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    ok, payload, err = api_request('GET', api_url, '/dados')
    if not ok or not isinstance(payload, dict):
        raise RuntimeError(err or 'Resposta inválida da API em /dados.')
    tables_raw = payload.get('tables', {})
    columns_meta = payload.get('columns', {})
    tables: dict[str, pd.DataFrame] = {}
    for table in ALL_TABLES:
        cols = columns_meta.get(table) or TABLE_COLUMNS[table]
        df = _records_to_df(tables_raw.get(table, []), list(cols))
        tables[table] = _coerce_table_types(table, df)
    return tables, payload.get('about') or {}


@st.cache_data(ttl=60, show_spinner=False)
def load_analytics(
    api_url: str,
    company_ids: tuple[int, ...],
    project_ids: tuple[int, ...],
    auth_token: str = '',
) -> dict[str, pd.DataFrame]:
    params: list[tuple[str, int]] = [('company_ids', int(c)) for c in company_ids] + [
        ('project_ids', int(p)) for p in project_ids
    ]
    ok, payload, err = api_request('GET', api_url, '/analytics', params=params)
    if not ok or not isinstance(payload, dict):
        raise RuntimeError(err or 'Resposta inválida da API em /analytics.')

    table_map = {
        'projects': 'projetos',
        'companies': 'empresas',
        'members': 'membros',
        'sprints': 'sprints',
        'tasks': 'tarefas',
        'tasks_all': 'tarefas',
        'demands': 'demanda',
        'clients': 'clientes',
    }
    result: dict[str, pd.DataFrame] = {}
    for key, table_name in table_map.items():
        df = _records_to_df(payload.get(key, []), TABLE_COLUMNS[table_name])
        result[key] = _coerce_table_types(table_name, df)

    summary = _records_to_df(payload.get('summary', []), SUMMARY_COLUMNS)
    for col in ('id', 'id_empresa'):
        summary[col] = pd.to_numeric(summary[col], errors='coerce').astype('Int64')
    for col in ('total_tarefas', 'concluidas', 'em_andamento', 'nao_iniciadas', 'total_sprints', 'sprints_concluidas', 'clientes'):
        summary[col] = pd.to_numeric(summary[col], errors='coerce').fillna(0).astype(int)
    summary['taxa_conclusao'] = pd.to_numeric(summary['taxa_conclusao'], errors='coerce')
    for col in ('nome', 'descricao', 'empresa'):
        summary[col] = summary[col].fillna('').astype(str)
    result['summary'] = summary
    return result


@st.cache_data(ttl=60, show_spinner=False)
def load_sprint_analytics(
    api_url: str,
    company_ids: tuple[int, ...],
    project_ids: tuple[int, ...],
    auth_token: str = '',
) -> pd.DataFrame:
    params: list[tuple[str, int]] = [('company_ids', int(c)) for c in company_ids] + [
        ('project_ids', int(p)) for p in project_ids
    ]
    ok, payload, err = api_request('GET', api_url, '/analytics/sprints', params=params)
    if not ok or not isinstance(payload, list):
        raise RuntimeError(err or 'Resposta inválida da API em /analytics/sprints.')

    metrics = _records_to_df(payload, SPRINT_METRICS_COLUMNS)
    for col in ('id_sprint', 'id_projeto'):
        metrics[col] = pd.to_numeric(metrics[col], errors='coerce').astype('Int64')
    for col in ('data_in', 'data_fin'):
        metrics[col] = pd.to_datetime(metrics[col], errors='coerce')
    for col in ('tarefas', 'concluidas', 'pendentes'):
        metrics[col] = pd.to_numeric(metrics[col], errors='coerce').fillna(0).astype(int)
    for col in ('isDone', 'taxa_conclusao', 'duracao_dias'):
        metrics[col] = pd.to_numeric(metrics[col], errors='coerce')
    return metrics


@st.cache_data(ttl=60, show_spinner=False)
def load_quality(api_url: str, auth_token: str = '') -> pd.DataFrame:
    ok, payload, err = api_request('GET', api_url, '/qualidade')
    if not ok or not isinstance(payload, list):
        raise RuntimeError(err or 'Resposta inválida da API em /qualidade.')
    rows = [(item['verificacao'], int(item['ocorrencias'])) for item in payload]
    return pd.DataFrame(rows, columns=['Verificação', 'Ocorrências'])


def clear_api_caches() -> None:
    load_db.clear()
    load_analytics.clear()
    load_sprint_analytics.clear()
    load_quality.clear()


# ---------------------------------------------------------------------------
# Utilitários visuais
# ---------------------------------------------------------------------------

def fmt(value, decimals=0, suffix=''):
    if value is None or pd.isna(value) or not np.isfinite(float(value)):
        return '—'
    return f'{float(value):,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.') + suffix


def draw(fig, height=350, percent=False, legend=False):
    fig.update_layout(
        height=height, margin=dict(l=15, r=19, t=24, b=30),
        paper_bgcolor='#111c30', plot_bgcolor='#111c30',
        font=dict(family='DM Sans, Arial', color='#D5E3F9', size=12),
        colorway=PALETTE, hoverlabel=dict(bgcolor='#263c61', font_color='#fff'),
        legend=dict(orientation='h', x=0, y=1.12, font=dict(size=11)), showlegend=legend,
        hovermode='closest',
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor='#3B4B62', tickfont=dict(color='#A9BBD6'))
    fig.update_yaxes(showgrid=True, gridcolor='#26354c', zeroline=False, tickfont=dict(color='#A9BBD6'))
    if percent:
        fig.update_xaxes(ticksuffix='%')
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={'displaylogo': False, 'modeBarButtonsToRemove': ['lasso2d', 'select2d']},
    )


def header(title, subtitle=None):
    st.markdown(f'<div class="section-head">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)


def insight(title, description):
    st.markdown(f'<div class="insight"><strong>{title}</strong><p>{description}</p></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Página de login inicial
# ---------------------------------------------------------------------------

def _classificar_situacao_qualitativa(taxa: Any) -> str:
    if taxa is None or pd.isna(taxa):
        return 'Sem atividades registradas'
    valor = float(taxa)
    if valor >= 100:
        return 'Concluído'
    if valor >= 70:
        return 'Em reta final'
    if valor >= 30:
        return 'Em andamento'
    return 'Fase inicial'


def _fazer_logout() -> None:
    st.session_state['usuario_logado'] = None
    st.session_state['projeto_ativo_id'] = None
    st.session_state['sprint_ativa_id'] = None
    clear_api_caches()
    st.rerun()


def _formatar_data_curta(val: Any) -> str:
    if val is None or pd.isna(val):
        return '—'
    try:
        return pd.Timestamp(val).strftime('%d/%m/%Y')
    except Exception:
        return str(val)


def _badge_situacao(texto: str, *, concluido: bool = False, atencao: bool = False) -> str:
    cls = 'badge-ok' if concluido else ('badge-warn' if atencao else 'badge-prog')
    return f'<span class="{cls}">{escape(texto)}</span>'


def _progresso_normalizado(taxa: Any) -> float:
    if taxa is None or pd.isna(taxa):
        return 0.0
    return min(1.0, max(0.0, float(taxa) / 100.0))


def _render_barra_abas(itens: list[tuple[Any, str]], ativo: Any, key_prefix: str, on_select) -> None:
    """Renderiza uma barra de abas clicáveis em linhas de até 5 colunas."""
    for start in range(0, len(itens), 5):
        lote = itens[start:start + 5]
        cols = st.columns(len(lote))
        for idx, (col, (valor, rotulo)) in enumerate(zip(cols, lote)):
            with col:
                btn_type = 'primary' if valor == ativo else 'secondary'
                if st.button(rotulo, key=f'{key_prefix}_{start + idx}_{valor}', type=btn_type, use_container_width=True):
                    on_select(valor)
                    st.rerun()


def _render_form_estado_tarefa_membro(tarefas_df: pd.DataFrame, form_key: str) -> None:
    """Permite ao perfil membro atualizar o estado das suas tarefas no contexto atual."""
    if tarefas_df.empty:
        st.info('Você não possui tarefas atribuídas neste recorte.')
        return
    estados_validos = ['nao_iniciada', 'em_andamento', 'concluida']
    with st.form(form_key):
        tarefa_id_m = st.selectbox(
            'Selecione a tarefa',
            options=tarefas_df['id'].tolist(),
            format_func=lambda x: (
                f"[{x}] {tarefas_df.loc[tarefas_df['id'] == x, 'descricao'].values[0][:50]} "
                f"(atual: {tarefas_df.loc[tarefas_df['id'] == x, 'estado'].values[0]})"
            ),
        )
        estado_atual = str(tarefas_df.loc[tarefas_df['id'] == tarefa_id_m, 'estado'].values[0])
        idx_estado = estados_validos.index(estado_atual) if estado_atual in estados_validos else 0
        novo_estado_m = st.selectbox('Novo Estado', estados_validos, index=idx_estado)
        if st.form_submit_button('Atualizar Estado', type='primary'):
            ok, _, err = api_request(
                'PATCH',
                API_URL,
                f'/tarefas/{int(tarefa_id_m)}/estado',
                json_body={'estado': novo_estado_m},
            )
            if ok:
                st.success('Estado da tarefa atualizado com sucesso!')
                clear_api_caches()
                st.rerun()
            else:
                st.error(f'Erro ao atualizar estado da tarefa: {err}')


def _render_secao_sprints_do_projeto(
    proj_id: int,
    proj_nome: str,
    tipo_perfil: str,
    sprint_metrics: pd.DataFrame,
    tasks: pd.DataFrame,
    membros_df: pd.DataFrame,
) -> None:
    """Renderiza a barra de abas, cards clicáveis e aba própria para cada sprint de um projeto."""
    proj_sprints = sprint_metrics[sprint_metrics['id_projeto'] == proj_id].sort_values('id_sprint').copy()
    proj_tasks = tasks[tasks['id_projeto'] == proj_id].copy()
    proj_backlog = proj_tasks[proj_tasks['id_sprint'].isna()].copy()
    sprint_ids_validos = [int(r.id_sprint) for r in proj_sprints.itertuples()]

    ativo = st.session_state.get('sprint_ativa_id')
    if ativo is not None:
        valido_backlog = ativo == 'backlog' and tipo_perfil != 'cliente' and not proj_backlog.empty
        valido_sprint = isinstance(ativo, int) and ativo in sprint_ids_validos
        if not (valido_backlog or valido_sprint):
            st.session_state['sprint_ativa_id'] = None
            ativo = None

    header(f'Sprints de {escape(proj_nome)}', 'Selecione uma sprint pela barra de abas ou clique em um card')

    abas_sprint: list[tuple[Any, str]] = [(None, '🏃 Todas as Sprints')] + [
        (int(r.id_sprint), f'🏃 Sprint #{int(r.id_sprint)}') for r in proj_sprints.itertuples()
    ]
    if tipo_perfil != 'cliente' and not proj_backlog.empty:
        abas_sprint.append(('backlog', f'📥 Backlog ({len(proj_backlog)})'))

    def _selecionar_sprint(val: Any) -> None:
        st.session_state['sprint_ativa_id'] = val

    _render_barra_abas(abas_sprint, ativo, f'sprint_tab_{proj_id}', _selecionar_sprint)
    st.write('')

    if ativo is None:
        if proj_sprints.empty and (tipo_perfil == 'cliente' or proj_backlog.empty):
            st.info('Nenhuma sprint cadastrada para este projeto.')
            return

        if not proj_sprints.empty:
            sprints_rows = list(proj_sprints.itertuples())
            for start in range(0, len(sprints_rows), 3):
                lote = sprints_rows[start:start + 3]
                cols = st.columns(3)
                for col, sr in zip(cols, lote):
                    sid = int(sr.id_sprint)
                    concluida_flag = pd.notna(sr.isDone) and int(sr.isDone) == 1
                    status_txt = 'Finalizada' if concluida_flag else 'Em andamento'
                    periodo = f'{_formatar_data_curta(sr.data_in)} → {_formatar_data_curta(sr.data_fin)}'
                    dur_txt = fmt(sr.duracao_dias, 0, ' dias') if pd.notna(sr.duracao_dias) else '—'
                    taxa_val = sr.taxa_conclusao

                    if tipo_perfil == 'cliente':
                        situacao = _classificar_situacao_qualitativa(taxa_val)
                        resumo_html = (
                            f'Situação: <strong>{escape(situacao)}</strong> · '
                            f'Progresso: <strong>{fmt(taxa_val, 1, "%")}</strong>'
                        )
                    else:
                        resumo_html = (
                            f'Tarefas: <strong>{int(sr.tarefas)}</strong> · '
                            f'Concluídas: <strong>{int(sr.concluidas)}</strong> · '
                            f'Pendentes: <strong>{int(sr.pendentes)}</strong>'
                        )

                    with col:
                        st.markdown(
                            f'<div class="entity-card">'
                            f'<div class="entity-card-title">Sprint #{sid} {_badge_situacao(status_txt, concluido=concluida_flag)}</div>'
                            f'<div class="entity-card-meta">📅 {periodo} · ⏱ {dur_txt}</div>'
                            f'<div class="entity-card-meta">{resumo_html}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.progress(_progresso_normalizado(taxa_val))
                        if st.button('Abrir Sprint →', key=f'card_sprint_{proj_id}_{sid}', use_container_width=True):
                            st.session_state['sprint_ativa_id'] = sid
                            st.rerun()

        if tipo_perfil != 'cliente' and not proj_backlog.empty:
            st.write('')
            c_bl, _ = st.columns([1, 2])
            with c_bl:
                pendentes_bl = int((proj_backlog['estado'] != 'concluida').sum())
                st.markdown(
                    f'<div class="entity-card">'
                    f'<div class="entity-card-title">📥 Backlog fora de sprint {_badge_situacao("Sem sprint", atencao=pendentes_bl > 0)}</div>'
                    f'<div class="entity-card-meta">Tarefas no backlog: <strong>{len(proj_backlog)}</strong> · Pendentes: <strong>{pendentes_bl}</strong></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button('Abrir Backlog →', key=f'card_sprint_{proj_id}_backlog', use_container_width=True):
                    st.session_state['sprint_ativa_id'] = 'backlog'
                    st.rerun()
        return

    if st.button('← Voltar para Sprints', key=f'btn_voltar_sprints_{proj_id}'):
        st.session_state['sprint_ativa_id'] = None
        st.rerun()

    member_names = membros_df.set_index('id')['nome'] if not membros_df.empty else pd.Series(dtype=str)

    if ativo == 'backlog':
        st.markdown(f'<div class="info-card"><strong style="color:#EFF5FF;font-size:1.05rem">📥 Backlog de {escape(proj_nome)}</strong><p style="margin:6px 0 0;color:#BDCCE0">Tarefas ainda não associadas a nenhuma sprint.</p></div>', unsafe_allow_html=True)
        bl_table = proj_backlog.assign(
            responsavel=lambda f: f['id_membro'].map(member_names).fillna('Não atribuído') if 'id_membro' in f.columns else 'Não atribuído'
        )[['id', 'responsavel', 'estado', 'descricao', 'data_cria', 'data_fin']].rename(columns={
            'id': 'ID', 'responsavel': 'Responsável', 'estado': 'Estado',
            'descricao': 'Descrição', 'data_cria': 'Criada em', 'data_fin': 'Finalizada em',
        })
        st.dataframe(bl_table, hide_index=True, use_container_width=True)
        if tipo_perfil == 'membro':
            header('Atualizar estado de tarefa no backlog')
            _render_form_estado_tarefa_membro(proj_backlog, f'form_membro_sprint_estado_{proj_id}_backlog')
        return

    # Aba própria da sprint selecionada
    sr = proj_sprints[proj_sprints['id_sprint'] == ativo].iloc[0]
    sprint_tasks = proj_tasks[proj_tasks['id_sprint'] == ativo].copy()
    concluida_flag = pd.notna(sr['isDone']) and int(sr['isDone']) == 1
    status_txt = 'Finalizada' if concluida_flag else 'Em andamento'
    periodo = f"{_formatar_data_curta(sr['data_in'])} → {_formatar_data_curta(sr['data_fin'])}"
    dur_txt = fmt(sr['duracao_dias'], 0, ' dias') if pd.notna(sr['duracao_dias']) else '—'

    st.markdown(
        f'<div class="info-card">'
        f'<strong style="color:#EFF5FF;font-size:1.1rem">🏃 Sprint #{int(ativo)} · {escape(proj_nome)}</strong> '
        f'{_badge_situacao(status_txt, concluido=concluida_flag)}'
        f'<p style="margin:7px 0 0;color:#BDCCE0">Período: {periodo} · Duração planejada: {dur_txt}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if tipo_perfil == 'cliente':
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Situação', _classificar_situacao_qualitativa(sr['taxa_conclusao']))
        c2.metric('Progresso', fmt(sr['taxa_conclusao'], 1, '%'))
        c3.metric('Status da Sprint', status_txt)
        c4.metric('Duração', dur_txt)
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Tarefas na Sprint', fmt(sr['tarefas']))
        c2.metric('Concluídas', fmt(sr['concluidas']))
        c3.metric('Pendentes', fmt(sr['pendentes']))
        c4.metric('Conclusão', fmt(sr['taxa_conclusao'], 1, '%'))

    status_sp = sprint_tasks.groupby('estado').size().reset_index(name='quantidade')
    labels = {'concluida': 'Concluída', 'em_andamento': 'Em andamento', 'nao_iniciada': 'Não iniciada', 'nao_informado': 'Não informado'}
    if not status_sp.empty:
        status_sp['label'] = status_sp['estado'].map(labels).fillna(status_sp['estado'])
        if tipo_perfil == 'cliente':
            header('Distribuição qualitativa da sprint', 'Proporção dos estados das atividades nesta sprint')
            fig = px.pie(status_sp, names='label', values='quantidade', hole=.62, color='estado', color_discrete_map=COLORS)
            fig.update_traces(textinfo='percent+label')
            draw(fig, height=300)
        else:
            header('Situação das tarefas na sprint')
            fig = px.bar(status_sp, x='quantidade', y='label', orientation='h', text='quantidade', color='estado', color_discrete_map=COLORS)
            fig.update_traces(textposition='outside', showlegend=False)
            fig.update_xaxes(range=[0, max(2, status_sp['quantidade'].max() * 1.18)])
            draw(fig, height=260)

    if tipo_perfil != 'cliente':
        header('Tarefas desta sprint')
        if sprint_tasks.empty:
            st.info('Nenhuma tarefa associada a esta sprint.')
        else:
            st_table = sprint_tasks.assign(
                responsavel=lambda f: f['id_membro'].map(member_names).fillna('Não atribuído') if 'id_membro' in f.columns else 'Não atribuído'
            )[['id', 'responsavel', 'estado', 'descricao', 'data_cria', 'data_fin']].rename(columns={
                'id': 'ID', 'responsavel': 'Responsável', 'estado': 'Estado',
                'descricao': 'Descrição', 'data_cria': 'Criada em', 'data_fin': 'Finalizada em',
            })
            st.dataframe(st_table, hide_index=True, use_container_width=True)
            if tipo_perfil == 'membro':
                header('Atualizar estado de tarefa nesta sprint')
                _render_form_estado_tarefa_membro(sprint_tasks, f'form_membro_sprint_estado_{proj_id}_{int(ativo)}')


def render_login_page(api_url: str) -> None:
    """Exibe a tela inicial de login obrigatório antes de liberar o dashboard."""
    st.markdown(
        '''<style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"] {display: none !important;}
        .block-container {max-width: 1120px; padding-top: 4rem;}
        [data-testid="stForm"] {
            background: linear-gradient(160deg, #18253d, #111d32);
            border: 1px solid #31405b;
            border-radius: 18px;
            padding: 1.8rem 1.8rem 1.4rem;
            box-shadow: 0 16px 40px #00000033;
        }
        </style>''',
        unsafe_allow_html=True,
    )
    _, col_center, _ = st.columns([1.2, 1.6, 1.2])
    with col_center:
        st.markdown('<div class="eyebrow">EJFLOW · OBSERVATÓRIO DE PROJETOS</div>', unsafe_allow_html=True)
        st.title('◆ Acesso ao Sistema')
        st.caption('Entre com seu e-mail e senha para acessar o dashboard e as demais funcionalidades.')
        with st.form('form_login_inicial'):
            email_input = st.text_input('E-mail', placeholder='ex: joao.pedro@techsolutions.com')
            senha_input = st.text_input('Senha', type='password', placeholder='Digite sua senha')
            submitted = st.form_submit_button('🔐 Entrar', type='primary', use_container_width=True)
            if submitted:
                if not email_input.strip() or not senha_input:
                    st.error('Informe e-mail e senha para continuar.')
                else:
                    ok, user, err = api_request(
                        'POST',
                        api_url,
                        '/auth/login',
                        json_body={'email': email_input.strip(), 'senha': senha_input},
                    )
                    if ok and isinstance(user, dict):
                        st.session_state['usuario_logado'] = user
                        clear_api_caches()
                        st.rerun()
                    else:
                        st.error(err or 'E-mail ou senha inválidos.')
        st.caption(f'Acesso restrito a membros e clientes cadastrados · API: `{api_url}`')


# ---------------------------------------------------------------------------
# Conexão inicial e barra lateral
# ---------------------------------------------------------------------------

API_URL = get_api_base_url()

usuario = st.session_state['usuario_logado']
if usuario is None:
    render_login_page(API_URL)
    st.stop()

auth_token = str(usuario.get('token') or '')
tipo_perfil = usuario.get('tipo', 'membro')
PERFIL_LABELS = {
    'admin': 'Administrador',
    'chefe': 'Chefe',
    'membro': 'Membro',
    'cliente': 'Cliente',
}
perfil_label = PERFIL_LABELS.get(tipo_perfil, 'Usuário')

with st.sidebar:
    st.markdown('## ◆ EJFlow')
    st.caption('OBSERVATÓRIO · GESTÃO DE PROJETOS')
    st.markdown(f"**{escape(str(usuario['nome']))}** · `{perfil_label}`")
    if st.button('Sair', key='sidebar_sair', use_container_width=True):
        _fazer_logout()
    st.divider()
    st.markdown('**FONTE DE DADOS**')
    st.caption(f'API FastAPI · `{API_URL}`')
    st.caption('Leitura e Escrita • Dados atualizados via backend')
    if st.button('↻  Atualizar dados', use_container_width=True, type='primary'):
        clear_api_caches()
        st.rerun()

try:
    all_data, db_about = load_db(API_URL, auth_token)
except Exception as exc:
    st.markdown('<div class="eyebrow">EJFlow / CONEXÃO</div>', unsafe_allow_html=True)
    st.title('API do EJFlow indisponível')
    st.error('Não foi possível carregar os dados pela API. O painel não utiliza dados simulados.')
    st.info(
        f'Verifique se o backend FastAPI está em execução em `{API_URL}` '
        '(configurável via variável de ambiente `API_BASE_URL`) e conectado ao MySQL.'
    )
    st.code('uvicorn backend.api:app --reload', language='bash')
    with st.expander('Detalhes técnicos da falha'):
        st.caption(str(exc))
    st.stop()

db_name = db_about.get('db') or 'MySQL'

with st.sidebar:
    st.caption(f'Banco ativo · `{db_name}`')
    st.divider()
    st.markdown('**FILTROS GLOBAIS**')
    e = all_data['empresas']
    p = all_data['projetos']
    companies_map = {int(r.id): f'{r.nome} · #{int(r.id)}' for r in e.itertuples()}
    if tipo_perfil in ('membro', 'chefe') and usuario.get('id_empresa') is not None:
        emp_fixa = int(usuario['id_empresa'])
        company_ids = [emp_fixa] if emp_fixa in companies_map or not companies_map else list(companies_map)
        emp_label = companies_map.get(emp_fixa, f'Empresa #{emp_fixa}')
        st.caption(f'Empresa vinculada · **{escape(emp_label)}**')
    elif tipo_perfil == 'cliente':
        company_ids = list(companies_map)
    else:
        company_ids = st.multiselect(
            'Empresas',
            options=list(companies_map),
            default=list(companies_map),
            format_func=lambda x: companies_map[x],
        )
    available = p[p['id_empresa'].isin(company_ids)]
    projects_map = {int(r.id): f'{r.nome} · #{int(r.id)}' for r in available.itertuples()}
    project_ids = st.multiselect(
        'Projetos',
        options=list(projects_map),
        default=list(projects_map),
        format_func=lambda x: projects_map[x],
    )
    st.caption('Filtros aplicam-se a todas as abas do seu escopo.')
    st.divider()
    st.caption('As informações são consultadas pela API REST do EJFlow.')

if not company_ids or not project_ids:
    if tipo_perfil in ('membro', 'cliente') and all_data['projetos'].empty:
        st.info('Nenhum projeto está associado ao seu usuário no momento.')
    else:
        st.warning('Não há projetos nesse recorte. Selecione outra empresa ou projeto na barra lateral.')
    st.stop()

try:
    m = load_analytics(API_URL, tuple(company_ids), tuple(project_ids), auth_token)
    sprint_metrics = load_sprint_analytics(API_URL, tuple(company_ids), tuple(project_ids), auth_token)
    quality_df = load_quality(API_URL, auth_token)
except Exception as exc:
    st.error(f'Erro ao consultar indicadores na API: {exc}')
    st.stop()

projects = m['projects']
tasks = m['tasks']
sprints = m['sprints']
summary = m['summary']
demands = m['demands']

if projects.empty:
    st.warning('Não há projetos nesse recorte. Selecione outra empresa ou projeto na barra lateral.')
    st.stop()

backlog = tasks[tasks['id_sprint'].isna() & tasks['estado'].ne('concluida')]
project_names = projects.set_index('id')['nome']

col_hero, col_auth = st.columns([4, 1.3], vertical_alignment='top')
with col_hero:
    st.markdown(
        '<div class="hero"><div class="eyebrow">SISTEMAS DE INFORMAÇÃO · BUSINESS INTELLIGENCE</div>'
        '<h1>Observatório de Projetos <span style="color:#8EAAFF">↗</span></h1>'
        '<p>Visão gerencial, acadêmica e interativa de projetos, sprints, tarefas, clientes e equipes.</p>'
        '<span class="pill">● Dados consultados via API FastAPI</span></div>',
        unsafe_allow_html=True,
    )

with col_auth:
    st.write('')
    st.markdown(
        f"<div style='text-align:right; margin-bottom:6px;'>"
        f"<strong style='color:#ECF3FF;'>{escape(str(usuario['nome']))}</strong><br>"
        f"<span class='pill'>{perfil_label}</span></div>",
        unsafe_allow_html=True,
    )
    if st.button('Sair', key='hero_sair', use_container_width=True):
        _fazer_logout()

completed = int((tasks['estado'] == 'concluida').sum())
rate = (100 * completed / len(tasks)) if len(tasks) else np.nan

if tipo_perfil == 'cliente':
    k1, k2, k3, k4 = st.columns(4)
    qualidade_geral = 'Adequada' if (quality_df['Ocorrências'] == 0).all() else 'Com pontos de atenção'
    k1.metric('Projetos Associados', fmt(len(projects)))
    k2.metric('Situação Geral', _classificar_situacao_qualitativa(rate))
    k3.metric('Progresso Médio', fmt(rate, 1, '%'))
    k4.metric('Qualidade dos Projetos', qualidade_geral)
    st.caption('Indicadores qualitativos calculados exclusivamente para os projetos associados à sua conta.')
elif tipo_perfil == 'membro':
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric('Meus Projetos', fmt(len(projects)))
    k2.metric('Sprints', fmt(len(sprints)))
    k3.metric('Minhas Tarefas', fmt(len(tasks)))
    k4.metric('Concluídas', fmt(completed))
    k5.metric('Conclusão', fmt(rate, 1, '%'))
    emp_nome_m = m['companies']['nome'].iloc[0] if not m['companies'].empty else f"Empresa #{usuario.get('id_empresa', '')}"
    st.caption(f'Empresa: **{escape(str(emp_nome_m))}** · Visão restrita à sua empresa, projetos associados e tarefas atribuídas.')
else:
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric('Projetos', fmt(len(projects)))
    k2.metric('Empresas', fmt(len(m['companies'])))
    k3.metric('Sprints', fmt(len(sprints)))
    k4.metric('Tarefas', fmt(len(tasks)))
    k5.metric('Concluídas', fmt(completed))
    k6.metric('Conclusão', fmt(rate, 1, '%'))
    st.caption('Taxa de conclusão = tarefas com estado `concluida` / total de tarefas do recorte.')

if tipo_perfil == 'cliente':
    abas_permitidas = ['◈  Visão geral', '▤  Projetos', '◎  Índices qualitativos']
elif tipo_perfil == 'membro':
    abas_permitidas = ['◈  Visão geral', '▤  Projetos', '◷  Sprints & tarefas']
elif tipo_perfil == 'chefe':
    abas_permitidas = ['◈  Visão geral', '▤  Projetos', '◷  Sprints & tarefas', '♧  Clientes & equipes', '⚙  Gerenciamento']
else:
    abas_permitidas = [
        '◈  Visão geral',
        '▤  Projetos',
        '◷  Sprints & tarefas',
        '♧  Clientes & equipes',
        '📋 Tabelas do Dataset',
        '◎  Qualidade & metodologia',
        '⚙  Gerenciamento',
    ]

tabs_criadas = st.tabs(abas_permitidas)
pages = dict(zip(abas_permitidas, tabs_criadas))

if '◈  Visão geral' in pages:
    with pages['◈  Visão geral']:
        st.write('')
        if tipo_perfil == 'cliente':
            comp_sorted = summary[summary['total_tarefas'] > 0].sort_values('taxa_conclusao', ascending=False)
            lead_comp = comp_sorted.iloc[0] if len(comp_sorted) else None
            total_alerts = int(quality_df['Ocorrências'].sum()) if not quality_df.empty else 0
            cols = st.columns(3)
            with cols[0]:
                insight(
                    '📌 Situação dos projetos',
                    f'Os {len(projects)} projeto(s) vinculados apresentam situação geral: '
                    f'{_classificar_situacao_qualitativa(rate)} ({fmt(rate, 1, "%")}).',
                )
            with cols[1]:
                insight(
                    '🏁 Melhor andamento',
                    f"{escape(str(lead_comp['nome']))} está em '{_classificar_situacao_qualitativa(lead_comp['taxa_conclusao'])}' "
                    f"({fmt(lead_comp['taxa_conclusao'], 1, '%')})."
                    if lead_comp is not None else 'Sem atividades avaliadas até o momento.',
                )
            with cols[2]:
                insight(
                    '◎ Qualidade das entregas',
                    'Sem inconsistências registradas nos projetos vinculados.'
                    if total_alerts == 0
                    else f'{total_alerts} ponto(s) de atenção detectado(s) na auditoria qualitativa.',
                )
            a, b = st.columns([1.2, 1.2])
            with a:
                header('Distribuição qualitativa das entregas', 'Proporção dos estados nos seus projetos')
                status_df = tasks.groupby('estado').size().reset_index(name='quantidade')
                labels = {
                    'concluida': 'Concluída',
                    'em_andamento': 'Em andamento',
                    'nao_iniciada': 'Não iniciada',
                    'nao_informado': 'Não informado',
                }
                status_df['label'] = status_df['estado'].map(labels).fillna(status_df['estado'])
                if status_df.empty:
                    st.info('Sem atividades cadastradas nos projetos associados.')
                else:
                    fig = px.pie(status_df, names='label', values='quantidade', hole=.62, color='estado', color_discrete_map=COLORS)
                    fig.update_traces(textinfo='percent+label')
                    draw(fig, height=340)
            with b:
                header('Progresso qualitativo por projeto', 'Percentual de conclusão dos projetos associados')
                comp = summary[summary['total_tarefas'] > 0].sort_values('taxa_conclusao', ascending=True)
                if comp.empty:
                    st.info('Não há atividades para calcular percentuais.')
                else:
                    fig = px.bar(comp, x='taxa_conclusao', y='nome', orientation='h', text='taxa_conclusao', color='nome', color_discrete_sequence=PALETTE)
                    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside', showlegend=False)
                    fig.update_xaxes(range=[0, 110])
                    draw(fig, 340, percent=True)
        else:
            lead = summary.sort_values('total_tarefas', ascending=False).iloc[0] if len(summary) else None
            pct = fmt(rate, 1, '%')
            cols = st.columns(3)
            with cols[0]:
                insight('📌 Retrato das entregas', f'{completed} de {len(tasks)} tarefas cadastradas no recorte estão concluídas ({pct}).')
            with cols[1]:
                insight(
                    '🏁 Projeto com mais tarefas',
                    f"{escape(str(lead['nome']))} reúne {int(lead['total_tarefas'])} tarefa(s) no recorte."
                    if lead is not None else 'Sem projetos disponíveis.',
                )
            with cols[2]:
                insight('🔎 Backlog fora de sprint', f'{len(backlog)} tarefa(s) ainda não concluídas e sem sprint no recorte.')
            a, b = st.columns([1.45, 1])
            with a:
                header('Situação das tarefas', 'Distribuição dos estados efetivamente cadastrados')
                status_df = tasks.groupby('estado').size().reset_index(name='quantidade')
                labels = {
                    'concluida': 'Concluída',
                    'em_andamento': 'Em andamento',
                    'nao_iniciada': 'Não iniciada',
                    'nao_informado': 'Não informado',
                }
                status_df['label'] = status_df['estado'].map(labels).fillna(status_df['estado'])
                fig = px.bar(status_df, x='quantidade', y='label', orientation='h', text='quantidade', color='estado', color_discrete_map=COLORS)
                fig.update_traces(textposition='outside', showlegend=False)
                fig.update_xaxes(range=[0, max(2, status_df['quantidade'].max() * 1.18)] if len(status_df) else [0, 1])
                draw(fig, height=320)
            with b:
                if tipo_perfil == 'membro':
                    header('Conclusão por projeto', 'Percentual de tarefas com estado concluída')
                    comp = summary[summary['total_tarefas'] > 0].sort_values('taxa_conclusao', ascending=True)
                    if comp.empty:
                        st.info('Não há tarefas para calcular percentuais.')
                    else:
                        fig = px.bar(comp, x='taxa_conclusao', y='nome', orientation='h', text='taxa_conclusao', color='nome', color_discrete_sequence=PALETTE)
                        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside', showlegend=False)
                        fig.update_xaxes(range=[0, 110])
                        draw(fig, 320, percent=True)
                else:
                    header('Projetos por empresa', 'Quantidade de projetos vinculados às empresas selecionadas')
                    pc = summary.groupby('empresa', dropna=False).size().reset_index(name='projetos')
                    fig = px.pie(pc, names='empresa', values='projetos', hole=.66, color_discrete_sequence=PALETTE)
                    fig.update_traces(textinfo='value+percent', hovertemplate='%{label}: %{value} projeto(s)<extra></extra>')
                    draw(fig, height=320)
            if tipo_perfil == 'membro':
                header('Volume de trabalho por projeto', 'Contagem das suas tarefas atribuídas por projeto')
                vol = summary.sort_values('total_tarefas', ascending=True)
                fig = px.bar(vol, x='total_tarefas', y='nome', orientation='h', color='nome', text='total_tarefas', color_discrete_sequence=PALETTE)
                fig.update_traces(textposition='outside', showlegend=False)
                draw(fig, 340)
            else:
                a, b = st.columns([1.4, 1])
                with a:
                    header('Volume de trabalho por projeto', 'Contagem de tarefas sem duplicações de JOIN com clientes ou sprints')
                    vol = summary.sort_values('total_tarefas', ascending=True)
                    fig = px.bar(vol, x='total_tarefas', y='nome', orientation='h', color='empresa', text='total_tarefas', color_discrete_sequence=PALETTE)
                    fig.update_traces(textposition='outside')
                    draw(fig, 370, legend=len(vol['empresa'].unique()) > 1)
                with b:
                    header('Conclusão por projeto', 'Percentual de tarefas com estado concluída')
                    comp = summary[summary['total_tarefas'] > 0].sort_values('taxa_conclusao', ascending=True)
                    if comp.empty:
                        st.info('Não há tarefas para calcular percentuais.')
                    else:
                        fig = px.bar(comp, x='taxa_conclusao', y='nome', orientation='h', text='taxa_conclusao', color='nome', color_discrete_sequence=PALETTE)
                        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside', showlegend=False)
                        fig.update_xaxes(range=[0, 110])
                        draw(fig, 370, percent=True)

if '▤  Projetos' in pages:
    with pages['▤  Projetos']:
        st.write('')
        if tipo_perfil != 'cliente':
            display = summary[[
                'id', 'nome', 'empresa', 'total_sprints', 'sprints_concluidas',
                'total_tarefas', 'concluidas', 'em_andamento', 'nao_iniciadas', 'clientes', 'taxa_conclusao',
            ]].rename(columns={
                'id': 'ID', 'nome': 'Projeto', 'empresa': 'Empresa', 'total_sprints': 'Sprints',
                'sprints_concluidas': 'Sprints finalizadas', 'total_tarefas': 'Tarefas', 'concluidas': 'Concluídas',
                'em_andamento': 'Em andamento', 'nao_iniciadas': 'Não iniciadas', 'clientes': 'Clientes vinculados',
                'taxa_conclusao': 'Conclusão (%)',
            })
            if tipo_perfil == 'membro':
                display = display.drop(columns=['Clientes vinculados'], errors='ignore')

        proj_ids_validos = [int(x) for x in summary['id'].tolist()]
        proj_ativo = st.session_state.get('projeto_ativo_id')
        if proj_ativo is not None and proj_ativo not in proj_ids_validos:
            st.session_state['projeto_ativo_id'] = None
            st.session_state['sprint_ativa_id'] = None
            proj_ativo = None

        abas_projetos: list[tuple[Any, str]] = [(None, '📋 Todos os Projetos')] + [
            (int(r.id), f'📂 {r.nome}') for r in summary.itertuples()
        ]

        def _selecionar_projeto(val: Any) -> None:
            st.session_state['projeto_ativo_id'] = val
            st.session_state['sprint_ativa_id'] = None

        _render_barra_abas(abas_projetos, proj_ativo, 'proj_tab', _selecionar_projeto)
        st.write('')

        if proj_ativo is None:
            if tipo_perfil == 'cliente':
                header('Projetos Associados', 'Selecione um projeto pelo card ou pela barra de abas para ver detalhes e sprints')
            else:
                header('Portfólio de Projetos', 'Selecione um projeto pelo card ou pela barra de abas para abrir sua visão detalhada e sprints')

            proj_rows = list(summary.itertuples())
            for start in range(0, len(proj_rows), 3):
                lote = proj_rows[start:start + 3]
                cols = st.columns(3)
                for col, pr in zip(cols, lote):
                    pid = int(pr.id)
                    desc_raw = str(pr.descricao or '').strip()
                    desc_curta = (desc_raw[:107] + '...') if len(desc_raw) > 110 else (desc_raw or 'Sem descrição cadastrada.')
                    taxa_val = pr.taxa_conclusao
                    situacao = _classificar_situacao_qualitativa(taxa_val)
                    concl_flag = pd.notna(taxa_val) and float(taxa_val) >= 100
                    atencao_flag = pd.isna(taxa_val) or float(taxa_val) < 30

                    if tipo_perfil == 'cliente':
                        resumo_proj = (
                            f'Progresso: <strong>{fmt(taxa_val, 1, "%")}</strong> · '
                            f'Sprints finalizadas: <strong>{int(pr.sprints_concluidas)}/{int(pr.total_sprints)}</strong>'
                        )
                    elif tipo_perfil == 'membro':
                        resumo_proj = (
                            f'Minhas tarefas: <strong>{int(pr.total_tarefas)}</strong> '
                            f'(<strong>{int(pr.concluidas)}</strong> concluídas) · '
                            f'Sprints: <strong>{int(pr.total_sprints)}</strong>'
                        )
                    else:
                        resumo_proj = (
                            f'Tarefas: <strong>{int(pr.total_tarefas)}</strong> '
                            f'(<strong>{int(pr.concluidas)}</strong> concluídas) · '
                            f'Sprints: <strong>{int(pr.sprints_concluidas)}/{int(pr.total_sprints)}</strong> · '
                            f'Clientes: <strong>{int(pr.clientes)}</strong>'
                        )

                    with col:
                        st.markdown(
                            f'<div class="entity-card">'
                            f'<div class="entity-card-title">{escape(str(pr.nome))} {_badge_situacao(situacao, concluido=concl_flag, atencao=atencao_flag)}</div>'
                            f'<div class="entity-card-meta">🏢 {escape(str(pr.empresa))}</div>'
                            f'<p style="font-size:.86rem;color:#C5D4EA;margin:0 0 10px;min-height:42px;">{escape(desc_curta)}</p>'
                            f'<div class="entity-card-meta">{resumo_proj}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.progress(_progresso_normalizado(taxa_val))
                        if st.button('Abrir projeto →', key=f'card_proj_{pid}', type='primary', use_container_width=True):
                            st.session_state['projeto_ativo_id'] = pid
                            st.session_state['sprint_ativa_id'] = None
                            st.rerun()

            with st.expander('Ver tabela comparativa de projetos'):
                if tipo_perfil == 'cliente':
                    qual_df = summary[['nome', 'empresa', 'sprints_concluidas', 'total_sprints', 'taxa_conclusao']].copy()
                    qual_df['Situação'] = qual_df['taxa_conclusao'].map(_classificar_situacao_qualitativa)
                    qual_df['Sprints finalizadas'] = qual_df['sprints_concluidas'].astype(str) + ' / ' + qual_df['total_sprints'].astype(str)
                    qual_view = qual_df[['nome', 'empresa', 'Situação', 'Sprints finalizadas', 'taxa_conclusao']].rename(
                        columns={'nome': 'Projeto', 'empresa': 'Empresa', 'taxa_conclusao': 'Progresso (%)'}
                    )
                    st.dataframe(
                        qual_view,
                        use_container_width=True,
                        hide_index=True,
                        column_config={'Progresso (%)': st.column_config.ProgressColumn('Progresso (%)', min_value=0, max_value=100, format='%.1f%%')},
                    )
                else:
                    st.dataframe(
                        display,
                        use_container_width=True,
                        hide_index=True,
                        column_config={'Conclusão (%)': st.column_config.ProgressColumn('Conclusão (%)', min_value=0, max_value=100, format='%.1f%%')},
                    )
        else:
            if st.button('← Voltar para Todos os Projetos', key='btn_voltar_projetos'):
                st.session_state['projeto_ativo_id'] = None
                st.session_state['sprint_ativa_id'] = None
                st.rerun()

            selected = summary[summary['id'] == proj_ativo].iloc[0]
            st.markdown(
                f'<div class="info-card"><strong style="color:#EFF5FF;font-size:1.15rem">{escape(str(selected["nome"]))}</strong>'
                f'<p style="margin:7px 0;color:#BDCCE0">{escape(str(selected["descricao"]))}</p>'
                f'<small>Empresa responsável: {escape(str(selected["empresa"]))}</small></div>',
                unsafe_allow_html=True,
            )

            if tipo_perfil == 'cliente':
                ca, cb, cc = st.columns(3)
                ca.metric('Situação', _classificar_situacao_qualitativa(selected['taxa_conclusao']))
                cb.metric('Progresso', fmt(selected['taxa_conclusao'], 1, '%'))
                cc.metric('Sprints finalizadas', f"{int(selected['sprints_concluidas'])} / {int(selected['total_sprints'])}")
            elif tipo_perfil == 'membro':
                ca, cb, cc = st.columns(3)
                ca.metric('Minhas tarefas no projeto', fmt(selected['total_tarefas']))
                cb.metric('Concluídas', fmt(selected['concluidas']))
                cc.metric('Sprints registradas', fmt(selected['total_sprints']))
            else:
                ca, cb, cc, cd = st.columns(4)
                ca.metric('Tarefas do projeto', fmt(selected['total_tarefas']))
                cb.metric('Concluídas', fmt(selected['concluidas']))
                cc.metric('Sprints registradas', fmt(selected['total_sprints']))
                cd.metric('Clientes relacionados', fmt(selected['clientes']))
                client_ids = demands.loc[demands['id_projeto'] == proj_ativo, 'id_cliente'].tolist()
                client_names = m['clients'][m['clients']['id'].isin(client_ids)][['id', 'nome']].rename(columns={'id': 'ID', 'nome': 'Cliente'})
                st.markdown('**Clientes associados à demanda**')
                if client_names.empty:
                    st.info('Nenhum cliente associado a esse projeto.')
                else:
                    st.dataframe(client_names, hide_index=True, use_container_width=True)

            st.divider()
            _render_secao_sprints_do_projeto(
                int(proj_ativo),
                str(selected['nome']),
                tipo_perfil,
                sprint_metrics,
                tasks,
                all_data['membros'],
            )

if '◎  Índices qualitativos' in pages and tipo_perfil == 'cliente':
    with pages['◎  Índices qualitativos']:
        st.write('')
        header('Índices Qualitativos dos Projetos', 'Auditoria de consistência restrita aos projetos vinculados à sua conta')
        checks_cli = quality_df.copy()
        checks_cli['Situação'] = checks_cli['Ocorrências'].map(lambda n: 'Adequado' if n == 0 else 'Ponto de atenção')
        st.dataframe(checks_cli[['Verificação', 'Situação', 'Ocorrências']], hide_index=True, use_container_width=True)
        st.caption('Por privacidade, apenas indicadores qualitativos dos seus projetos são exibidos neste perfil.')

if '◷  Sprints & tarefas' in pages:
    with pages['◷  Sprints & tarefas']:
        st.write('')
        a, b, c, d = st.columns(4)
        durs = sprint_metrics['duracao_dias']
        a.metric('Sprints cadastradas', fmt(len(sprints)))
        b.metric('Sprints marcadas concluídas', fmt((sprints['isDone'] == 1).sum()))
        c.metric('Duração média cadastrada', fmt(durs.dropna().mean(), 1, ' dias'))
        d.metric('Tarefas sem sprint', fmt(tasks['id_sprint'].isna().sum()))
        header('Distribuição de tarefas por sprint', 'Associação atual de tarefas; não é histórico de movimentações')
        sprint_list = sprints.merge(projects[['id', 'nome']].rename(columns={'id': 'id_projeto', 'nome': 'projeto'}), on='id_projeto', how='left')
        sprint_list['rotulo'] = sprint_list['projeto'] + ' · Sprint ' + sprint_list['id'].astype(str)
        bys = tasks.groupby(['id_projeto', 'id_sprint', 'estado']).size().reset_index(name='quantidade')
        bys = bys.merge(sprint_list[['id', 'id_projeto', 'rotulo']], left_on=['id_projeto', 'id_sprint'], right_on=['id_projeto', 'id'], how='inner')
        if bys.empty:
            st.info('Não há tarefas associadas a sprints neste recorte.')
        else:
            fig = px.bar(
                bys, x='rotulo', y='quantidade', color='estado', barmode='stack', color_discrete_map=COLORS,
                labels={'rotulo': 'Sprint', 'quantidade': 'Tarefas', 'estado': 'Estado'},
            )
            fig.update_xaxes(tickangle=-30)
            draw(fig, 380, legend=True)
        a, b = st.columns([1.2, 1])
        with a:
            header('Calendário de sprints', 'Intervalos planejados/cadastrados')
            timeline = sprint_list.dropna(subset=['data_in', 'data_fin']).copy()
            timeline = timeline[timeline['data_fin'] >= timeline['data_in']]
            if timeline.empty:
                st.info('Nenhuma sprint possui datas de início e fim válidas.')
            else:
                fig = px.timeline(
                    timeline, x_start='data_in', x_end='data_fin', y='rotulo', color='projeto',
                    hover_data=['id', 'isDone'], color_discrete_sequence=PALETTE,
                )
                fig.update_yaxes(autorange='reversed')
                draw(fig, max(330, min(620, 90 + 50 * len(timeline))), legend=True)
        with b:
            header('Estados das sprints', 'O campo `isDone` é independente do status de cada tarefa')
            states = sprints['isDone'].map({1: 'Finalizada', 0: 'Não finalizada'}).fillna('Não informado').value_counts().reset_index()
            states.columns = ['estado', 'quantidade']
            fig = px.pie(states, names='estado', values='quantidade', hole=.6, color_discrete_sequence=PALETTE)
            draw(fig, 330)
        header('Explorar tarefas', 'Os filtros abaixo valem para a tabela')
        options = sorted(tasks['estado'].unique())
        chosen = st.multiselect('Estados da tabela', options=options, default=options)
        backlog_only = st.checkbox('Mostrar apenas backlog fora de sprint')
        task_source = backlog if backlog_only else tasks
        member_names = all_data['membros'].set_index('id')['nome'] if not all_data['membros'].empty else pd.Series(dtype=str)
        dtable = task_source[task_source['estado'].isin(chosen)].assign(
            projeto=lambda frame: frame['id_projeto'].map(project_names),
            responsavel=lambda frame: frame['id_membro'].map(member_names).fillna('Não atribuído')
            if 'id_membro' in frame.columns else 'Não atribuído',
        )
        dtable = dtable[['id', 'projeto', 'id_sprint', 'responsavel', 'estado', 'descricao', 'data_cria', 'data_fin']].rename(columns={
            'id': 'ID', 'projeto': 'Projeto', 'id_sprint': 'Sprint', 'responsavel': 'Responsável',
            'estado': 'Estado', 'descricao': 'Descrição', 'data_cria': 'Criada em', 'data_fin': 'Finalizada em',
        })
        st.dataframe(dtable, hide_index=True, use_container_width=True, height=370)

        if tipo_perfil == 'membro':
            header('Atualizar estado de minha tarefa', 'Altere o andamento das tarefas atribuídas a você')
            tarefas_m = all_data['tarefas']
            if tarefas_m.empty:
                st.info('Você não possui tarefas atribuídas para atualizar.')
            else:
                estados_validos = ['nao_iniciada', 'em_andamento', 'concluida']
                with st.form('form_membro_atualizar_tarefa'):
                    tarefa_id_m = st.selectbox(
                        'Selecione a tarefa',
                        options=tarefas_m['id'].tolist(),
                        format_func=lambda x: (
                            f"[{x}] {tarefas_m.loc[tarefas_m['id'] == x, 'descricao'].values[0][:50]} "
                            f"(atual: {tarefas_m.loc[tarefas_m['id'] == x, 'estado'].values[0]})"
                        ),
                    )
                    estado_atual = str(tarefas_m.loc[tarefas_m['id'] == tarefa_id_m, 'estado'].values[0])
                    idx_estado = estados_validos.index(estado_atual) if estado_atual in estados_validos else 0
                    novo_estado_m = st.selectbox('Novo Estado', estados_validos, index=idx_estado)
                    if st.form_submit_button('Atualizar Estado', type='primary'):
                        ok, _, err = api_request(
                            'PATCH',
                            API_URL,
                            f'/tarefas/{int(tarefa_id_m)}/estado',
                            json_body={'estado': novo_estado_m},
                        )
                        if ok:
                            st.success('Estado da tarefa atualizado com sucesso!')
                            clear_api_caches()
                            st.rerun()
                        else:
                            st.error(f'Erro ao atualizar estado da tarefa: {err}')

if '♧  Clientes & equipes' in pages:
    with pages['♧  Clientes & equipes']:
        st.write('')
        aa, bb, cc, dd = st.columns(4)
        aa.metric('Empresas do recorte', fmt(len(m['companies'])))
        bb.metric('Membros das empresas', fmt(len(m['members'])))
        cc.metric('Clientes vinculados', fmt(len(m['clients'])))
        dd.metric('Relações projeto–cliente', fmt(len(demands)))
        a, b = st.columns([1.1, 1])
        with a:
            header('Membros por empresa', 'Não significa participantes de cada projeto')
            mc = m['members'].groupby('id_empresa').size().reset_index(name='membros')
            mc = mc.merge(all_data['empresas'][['id', 'nome']], left_on='id_empresa', right_on='id', how='left')
            if mc.empty:
                st.info('Sem membros cadastrados.')
            else:
                fig = px.bar(mc, x='membros', y='nome', orientation='h', color='nome', text='membros', color_discrete_sequence=PALETTE)
                fig.update_traces(textposition='outside', showlegend=False)
                draw(fig, 340)
        with b:
            header('Cargos cadastrados', 'Distribuição descritiva do cadastro de membros')
            positions = m['members'].groupby('cargo').size().reset_index(name='membros')
            if positions.empty:
                st.info('Sem cargos cadastrados.')
            else:
                fig = px.bar(positions, x='membros', y='cargo', orientation='h', text='membros', color='cargo', color_discrete_sequence=PALETTE)
                fig.update_traces(textposition='outside', showlegend=False)
                draw(fig, 340)
        header('Relacionamento entre clientes e projetos', 'JOIN: demanda → projetos → clientes')
        relations = demands.merge(projects[['id', 'nome', 'id_empresa']].rename(columns={'id': 'id_projeto', 'nome': 'projeto'}), on='id_projeto', how='left')
        relations = relations.merge(all_data['clientes'][['id', 'nome']].rename(columns={'id': 'id_cliente', 'nome': 'cliente'}), on='id_cliente', how='left')
        relations = relations.merge(all_data['empresas'][['id', 'nome']].rename(columns={'id': 'id_empresa', 'nome': 'empresa'}), on='id_empresa', how='left')
        st.dataframe(
            relations[['empresa', 'projeto', 'cliente']].rename(columns={'empresa': 'Empresa', 'projeto': 'Projeto', 'cliente': 'Cliente'}),
            hide_index=True,
            use_container_width=True,
        )

# =========================================================================
# ABA 5: TABELAS DO DATASET (VISUALIZAÇÃO COMPLETA VIA API)
# =========================================================================
if '📋 Tabelas do Dataset' in pages:
    with pages['📋 Tabelas do Dataset']:
        st.write('')
        header('Visualização do Banco de Dados', 'Exibição completa de todas as tabelas retornadas pela API, sem filtros de tela')

        tab_emp, tab_cli, tab_proj, tab_memb, tab_dem, tab_mp, tab_spr, tab_tar, tab_adm = st.tabs([
            '🏢 Empresas', '👤 Clientes', '📂 Projetos', '👥 Membros', '🔗 Demanda',
            '🤝 Membro ↔ Projeto', '🏃 Sprints', '📌 Tarefas', '🛡️ Admins',
        ])

        with tab_emp:
            st.subheader('Tabela: Empresas')
            st.dataframe(all_data['empresas'], use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['empresas'])}")

        with tab_cli:
            st.subheader('Tabela: Clientes')
            st.dataframe(all_data['clientes'].drop(columns=['senha', 'possui_senha'], errors='ignore'), use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['clientes'])}")

        with tab_proj:
            st.subheader('Tabela: Projetos')
            st.dataframe(all_data['projetos'], use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['projetos'])}")

        with tab_memb:
            st.subheader('Tabela: Membros')
            st.dataframe(all_data['membros'].drop(columns=['senha', 'possui_senha'], errors='ignore'), use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['membros'])}")

        with tab_dem:
            st.subheader('Tabela: Demanda (Projeto ↔ Cliente)')
            st.dataframe(all_data['demanda'], use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['demanda'])}")

        with tab_mp:
            st.subheader('Tabela: Membro ↔ Projeto')
            st.dataframe(all_data['membro_projeto'], use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['membro_projeto'])}")

        with tab_spr:
            st.subheader('Tabela: Sprints')
            st.dataframe(all_data['sprints'], use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['sprints'])}")

        with tab_tar:
            st.subheader('Tabela: Tarefas')
            st.dataframe(all_data['tarefas'], use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['tarefas'])}")

        with tab_adm:
            st.subheader('Tabela: Administradores')
            st.dataframe(all_data['admins'].drop(columns=['senha', 'possui_senha'], errors='ignore'), use_container_width=True, hide_index=True)
            st.caption(f"Total de registros: {len(all_data['admins'])}")

if '◎  Qualidade & metodologia' in pages:
    with pages['◎  Qualidade & metodologia']:
        st.write('')
        header('Do relatório ao painel', 'EJFlow · Gerenciador de Projetos para Empresas Juniores · UFRN')
        insight('Duas bases, dois objetivos', 'Este painel consulta a API REST do EJFlow e aplica os indicadores que suas sete tabelas permitem calcular.')
        header('Auditoria de dados', 'Verificações no banco inteiro, independentemente dos filtros laterais')
        checks = quality_df.copy()
        checks['Situação'] = checks['Ocorrências'].map(lambda n: 'Sem ocorrências' if n == 0 else 'Com ocorrências')
        st.dataframe(checks, hide_index=True, use_container_width=True)
        header('Catálogo de dados', 'Modelo relacional extraído do arquivo SQL fornecido')
        catalog = pd.DataFrame([
            ('empresas', 'Empresas e seus representantes', '1:N com projetos e membros'),
            ('clientes', 'Clientes cadastrados', 'N:N com projetos via demanda'),
            ('projetos', 'Projetos e empresa responsável', '1:N com sprints e tarefas'),
            ('membros', 'Integrantes vinculados a empresas', 'Não há vínculo direto com projetos'),
            ('demanda', 'Associação projeto–cliente', 'Chave primária composta'),
            ('sprints', 'Períodos e indicador de finalização', 'Pertencem a um projeto'),
            ('tarefas', 'Atividades e estados', 'Projeto obrigatório; sprint opcional'),
        ], columns=['Tabela', 'Descrição', 'Relação'])
        catalog['Linhas no MySQL'] = [len(all_data[k]) for k in TABLES]
        st.dataframe(catalog, hide_index=True, use_container_width=True)
        header('Exportação do recorte', 'Faça download para validação acadêmica e reprodução dos resultados')
        frames = {
            'projetos_resumo.csv': display,
            'tarefas.csv': tasks.copy(),
            'sprints.csv': sprints.copy(),
            'sprints_indicadores.csv': sprint_metrics,
            'auditoria_banco.csv': checks.copy(),
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for filename, frame in frames.items():
                z.writestr(filename, frame.to_csv(index=False).encode('utf-8-sig'))
        st.download_button(
            '↓ Baixar relatório de dados (.zip)',
            data=buffer.getvalue(),
            file_name='ejflow_analise_mysql.zip',
            mime='application/zip',
            type='primary',
        )

# =========================================================================
# ABA 7: GERENCIAMENTO (ADMIN = MANUTENÇÃO COMPLETA | CHEFE = PRÓPRIA EMPRESA)
# =========================================================================

def _submeter_api_e_recarregar(method: str, path: str, msg_sucesso: str, *, json_body: dict[str, Any] | None = None, aviso: bool = False) -> None:
    ok, _, err = api_request(method, API_URL, path, json_body=json_body)
    if ok:
        (st.warning if aviso else st.success)(msg_sucesso)
        clear_api_caches()
        st.rerun()
    else:
        st.error(f'Erro na operação: {err}')


def _render_form_projeto(empresas_df: pd.DataFrame, clientes_df: pd.DataFrame, empresa_fixa_id: int | None = None) -> None:
    with st.form('form_projeto'):
        id_proj = st.number_input('ID do Projeto', step=1)
        if empresa_fixa_id is not None:
            emp_proj = empresa_fixa_id
            emp_nome = empresas_df.loc[empresas_df['id'] == emp_proj, 'nome']
            st.caption(f"Empresa Responsável: **{emp_nome.values[0] if len(emp_nome) else emp_proj}** (ID: {emp_proj})")
        else:
            emp_proj = st.selectbox(
                'Empresa Responsável',
                options=empresas_df['id'].tolist(),
                format_func=lambda x: f"{empresas_df.loc[empresas_df['id'] == x, 'nome'].values[0]} (ID: {x})",
            )
        nome_proj = st.text_input('Nome do Projeto')
        desc_proj = st.text_area('Descrição')
        cli_proj = st.selectbox(
            'Cliente Inicial (Opcional)',
            options=[None] + clientes_df['id'].tolist(),
            format_func=lambda x: 'Nenhum' if x is None else f"{clientes_df.loc[clientes_df['id'] == x, 'nome'].values[0]} (ID: {x})",
        )
        if st.form_submit_button('Salvar Projeto', type='primary'):
            _submeter_api_e_recarregar(
                'POST',
                '/projetos',
                'Projeto cadastrado com sucesso!',
                json_body={
                    'id': int(id_proj),
                    'id_empresa': int(emp_proj),
                    'nome': nome_proj,
                    'descricao': desc_proj,
                    'id_cliente': int(cli_proj) if cli_proj is not None else None,
                },
            )


def _render_form_membro(empresas_df: pd.DataFrame, permitir_perfil: bool, empresa_fixa_id: int | None = None) -> None:
    with st.form('form_membro'):
        id_memb = st.number_input('ID do Membro', step=1)
        if empresa_fixa_id is not None:
            emp_escolhida = empresa_fixa_id
            emp_nome = empresas_df.loc[empresas_df['id'] == emp_escolhida, 'nome']
            st.caption(f"Empresa: **{emp_nome.values[0] if len(emp_nome) else emp_escolhida}** (ID: {emp_escolhida})")
        else:
            emp_escolhida = st.selectbox(
                'Empresa',
                options=empresas_df['id'].tolist(),
                format_func=lambda x: f"{empresas_df.loc[empresas_df['id'] == x, 'nome'].values[0]} (ID: {x})",
            )
        nome_memb = st.text_input('Nome do Membro')
        email_memb = st.text_input('E-mail')
        cargo_memb = st.text_input('Cargo')
        perfil_memb = st.selectbox('Perfil', ['membro', 'chefe']) if permitir_perfil else 'membro'
        senha_inicial = st.text_input('Senha Inicial (Opcional)', type='password')
        if st.form_submit_button('Salvar Membro', type='primary'):
            _submeter_api_e_recarregar(
                'POST',
                '/membros',
                'Membro cadastrado com sucesso!',
                json_body={
                    'id': int(id_memb),
                    'id_empresa': int(emp_escolhida),
                    'nome': nome_memb,
                    'email': email_memb,
                    'cargo': cargo_memb,
                    'perfil': perfil_memb,
                    'senha': senha_inicial or None,
                },
            )


def _render_form_associar_membro_projeto(projetos_df: pd.DataFrame, membros_df: pd.DataFrame) -> None:
    with st.form('form_membro_projeto'):
        if projetos_df.empty or membros_df.empty:
            st.info('É necessário possuir projetos e membros no escopo para criar a associação.')
            st.form_submit_button('Associar Membro ao Projeto', disabled=True)
            return
        p_mp = st.selectbox(
            'Projeto',
            options=projetos_df['id'].tolist(),
            format_func=lambda x: f"{projetos_df.loc[projetos_df['id'] == x, 'nome'].values[0]} (ID: {x})",
        )
        m_mp = st.selectbox(
            'Membro',
            options=membros_df['id'].tolist(),
            format_func=lambda x: f"{membros_df.loc[membros_df['id'] == x, 'nome'].values[0]} (ID: {x})",
        )
        if st.form_submit_button('Associar Membro ao Projeto', type='primary'):
            _submeter_api_e_recarregar(
                'POST',
                '/membro-projeto',
                'Membro associado ao projeto com sucesso!',
                json_body={'id_projeto': int(p_mp), 'id_membro': int(m_mp)},
            )


def _render_form_desvincular_membro_projeto(mp_df: pd.DataFrame, projetos_df: pd.DataFrame, membros_df: pd.DataFrame) -> None:
    with st.form('form_desvincular_mp'):
        st.caption('Selecione uma alocação existente em `membro_projeto` para removê-la:')
        if mp_df.empty:
            st.info('Não há associações entre membros e projetos no escopo atual.')
            st.form_submit_button('Remover Associação', disabled=True)
            return

        def _fmt_mp(r):
            p_n = projetos_df.loc[projetos_df['id'] == r.id_projeto, 'nome'].values
            m_n = membros_df.loc[membros_df['id'] == r.id_membro, 'nome'].values
            return f"Projeto: '{p_n[0] if len(p_n) else r.id_projeto}' ↔ Membro: '{m_n[0] if len(m_n) else r.id_membro}'"

        opcoes = [_fmt_mp(r) for r in mp_df.itertuples()]
        tuplas = [(int(r.id_projeto), int(r.id_membro)) for r in mp_df.itertuples()]
        idx = st.selectbox('Associação Projeto ↔ Membro', options=range(len(opcoes)), format_func=lambda i: opcoes[i])
        if st.form_submit_button('Remover Associação'):
            p_sel, m_sel = tuplas[idx]
            _submeter_api_e_recarregar('DELETE', f'/membro-projeto/{p_sel}/{m_sel}', 'Associação removida com sucesso!', aviso=True)


def _render_form_sprint(projetos_df: pd.DataFrame) -> None:
    with st.form('form_sprint'):
        if projetos_df.empty:
            st.info('Nenhum projeto disponível no escopo.')
            st.form_submit_button('Salvar Sprint', disabled=True)
            return
        proj_sprint = st.selectbox(
            'Projeto',
            options=projetos_df['id'].tolist(),
            format_func=lambda x: f"{projetos_df.loc[projetos_df['id'] == x, 'nome'].values[0]} (ID: {x})",
        )
        is_done_sprint = st.selectbox('Concluída?', [0, 1], format_func=lambda x: 'Sim' if x == 1 else 'Não')
        data_in = st.text_input('Data Início (YYYY-MM-DD HH:MM:SS)', '2026-03-01 08:00:00')
        data_fin = st.text_input('Data Fim (YYYY-MM-DD HH:MM:SS)', '2026-03-15 18:00:00')
        if st.form_submit_button('Salvar Sprint', type='primary'):
            _submeter_api_e_recarregar(
                'POST',
                '/sprints',
                'Sprint cadastrada com sucesso!',
                json_body={
                    'id_projeto': int(proj_sprint),
                    'is_done': bool(is_done_sprint),
                    'data_in': data_in.strip() or None,
                    'data_fin': data_fin.strip() or None,
                },
            )


def _render_form_tarefa(projetos_df: pd.DataFrame, sprints_df: pd.DataFrame, membros_df: pd.DataFrame) -> None:
    with st.form('form_tarefa'):
        if projetos_df.empty:
            st.info('Nenhum projeto disponível no escopo.')
            st.form_submit_button('Salvar Tarefa', disabled=True)
            return
        proj_id = st.selectbox(
            'Projeto',
            options=projetos_df['id'].tolist(),
            format_func=lambda x: f"{projetos_df.loc[projetos_df['id'] == x, 'nome'].values[0]} (ID: {x})",
        )
        sprint_id = st.selectbox(
            'Sprint (Opcional)',
            options=[None] + sprints_df['id'].tolist(),
            format_func=lambda x: 'Nenhuma (Backlog)' if x is None else f'Sprint ID {x}',
        )
        membro_id = st.selectbox(
            'Membro Responsável (Opcional)',
            options=[None] + membros_df['id'].tolist(),
            format_func=lambda x: 'Nenhum' if x is None else f"{membros_df.loc[membros_df['id'] == x, 'nome'].values[0]} (ID: {x})",
        )
        desc = st.text_area('Descrição da Tarefa')
        estado = st.selectbox('Estado', ['nao_iniciada', 'em_andamento', 'concluida'])
        if st.form_submit_button('Salvar Tarefa', type='primary'):
            _submeter_api_e_recarregar(
                'POST',
                '/tarefas',
                'Tarefa cadastrada com sucesso!',
                json_body={
                    'id_projeto': int(proj_id),
                    'descricao': desc,
                    'estado': estado,
                    'id_sprint': int(sprint_id) if sprint_id is not None else None,
                    'id_membro': int(membro_id) if membro_id is not None else None,
                },
            )


def _render_form_atualizar_estado_tarefa(tarefas_df: pd.DataFrame) -> None:
    with st.form('form_atualizar_tarefa'):
        if tarefas_df.empty:
            st.info('Nenhuma tarefa disponível no escopo.')
            st.form_submit_button('Atualizar Estado', disabled=True)
            return
        tarefa_id_up = st.selectbox(
            'Selecione a Tarefa',
            options=tarefas_df['id'].tolist(),
            format_func=lambda x: f"[{x}] {tarefas_df.loc[tarefas_df['id'] == x, 'descricao'].values[0][:50]}...",
        )
        novo_estado = st.selectbox('Novo Estado', ['nao_iniciada', 'em_andamento', 'concluida'])
        if st.form_submit_button('Atualizar Estado'):
            _submeter_api_e_recarregar(
                'PATCH',
                f'/tarefas/{int(tarefa_id_up)}/estado',
                'Estado da tarefa atualizado com sucesso!',
                json_body={'estado': novo_estado},
            )


def _render_form_associar_tarefa_sprint(tarefas_df: pd.DataFrame, sprints_df: pd.DataFrame) -> None:
    with st.form('form_associar_sprint'):
        if tarefas_df.empty or sprints_df.empty:
            st.info('É necessário possuir tarefas e sprints no escopo.')
            st.form_submit_button('Vincular a Sprint', disabled=True)
            return
        t_id = st.selectbox(
            'Selecione a Tarefa',
            options=tarefas_df['id'].tolist(),
            format_func=lambda x: f"[{x}] {tarefas_df.loc[tarefas_df['id'] == x, 'descricao'].values[0][:50]}...",
        )
        s_id = st.selectbox(
            'Selecione a Sprint de Destino',
            options=sprints_df['id'].tolist(),
            format_func=lambda x: f'Sprint ID: {x}',
        )
        if st.form_submit_button('Vincular a Sprint'):
            _submeter_api_e_recarregar(
                'PATCH',
                f'/tarefas/{int(t_id)}/sprint',
                'Tarefa associada à sprint com sucesso!',
                json_body={'id_sprint': int(s_id)},
            )


def _render_form_atribuir_tarefa_membro(tarefas_df: pd.DataFrame, membros_df: pd.DataFrame) -> None:
    with st.form('form_atribuir_tarefa_membro'):
        if tarefas_df.empty:
            st.info('Nenhuma tarefa disponível no escopo.')
            st.form_submit_button('Atribuir Tarefa', disabled=True)
            return
        t_id = st.selectbox(
            'Selecione a Tarefa',
            options=tarefas_df['id'].tolist(),
            format_func=lambda x: f"[{x}] {tarefas_df.loc[tarefas_df['id'] == x, 'descricao'].values[0][:50]}...",
        )
        m_id = st.selectbox(
            'Membro Responsável',
            options=[None] + membros_df['id'].tolist(),
            format_func=lambda x: 'Sem responsável' if x is None else f"{membros_df.loc[membros_df['id'] == x, 'nome'].values[0]} (ID: {x})",
        )
        if st.form_submit_button('Atribuir Tarefa', type='primary'):
            _submeter_api_e_recarregar(
                'PATCH',
                f'/tarefas/{int(t_id)}/membro',
                'Responsável pela tarefa atualizado com sucesso!',
                json_body={'id_membro': int(m_id) if m_id is not None else None},
            )


def _render_form_definir_senha(contas: dict[str, tuple[str, pd.DataFrame]]) -> None:
    opcoes_label = list(contas.keys())
    escolha = st.radio('Tipo de conta', opcoes_label, horizontal=True) if len(opcoes_label) > 1 else opcoes_label[0]
    chave_tipo, df_usr = contas[escolha]
    with st.form('form_definir_senha'):
        if df_usr.empty:
            st.info(f'Nenhum registro disponível em {escolha}.')
            st.form_submit_button('Salvar Senha', disabled=True)
            return
        usr_id = st.selectbox(
            f'Selecione ({escolha})',
            options=df_usr['id'].tolist(),
            format_func=lambda x: f"{df_usr.loc[df_usr['id'] == x, 'nome'].values[0]} ({df_usr.loc[df_usr['id'] == x, 'email'].values[0]})",
        )
        nova_senha = st.text_input('Nova Senha', type='password')
        confirmar_senha = st.text_input('Confirmar Nova Senha', type='password')
        if st.form_submit_button('Salvar Senha', type='primary'):
            if not nova_senha:
                st.error('A senha não pode ficar em branco.')
            elif nova_senha != confirmar_senha:
                st.error('As senhas digitadas não coincidem.')
            else:
                _submeter_api_e_recarregar(
                    'PATCH',
                    f'/auth/senhas/{chave_tipo}/{int(usr_id)}',
                    f'Senha definida com sucesso ({escolha})!',
                    json_body={'nova_senha': nova_senha},
                )


def _render_form_remover_senha(contas: dict[str, tuple[str, pd.DataFrame]], usuario_atual: dict[str, Any]) -> None:
    st.caption('Remove a senha cadastrada do usuário, impedindo o login sem excluir seu registro.')
    opcoes_label = list(contas.keys())
    escolha = (
        st.radio('Tipo de conta', opcoes_label, horizontal=True, key='radio_del_senha')
        if len(opcoes_label) > 1 else opcoes_label[0]
    )
    chave_tipo, df_usr = contas[escolha]
    with st.form('form_remover_senha'):
        if 'possui_senha' in df_usr.columns:
            df_com_senha = df_usr[df_usr['possui_senha'].fillna(False).astype(bool)]
        elif 'senha' in df_usr.columns:
            df_com_senha = df_usr[df_usr['senha'].fillna('') != '']
        else:
            df_com_senha = df_usr

        if df_com_senha.empty:
            st.info(f'Nenhuma conta de {escolha} possui senha cadastrada no momento.')
            st.form_submit_button('Remover Senha', disabled=True)
            return
        usr_del_id = st.selectbox(
            f'Selecione ({escolha})',
            options=df_com_senha['id'].tolist(),
            format_func=lambda x: f"{df_com_senha.loc[df_com_senha['id'] == x, 'nome'].values[0]} ({df_com_senha.loc[df_com_senha['id'] == x, 'email'].values[0]})",
        )
        if st.form_submit_button('Remover Senha'):
            if chave_tipo == usuario_atual.get('tipo') and int(usr_del_id) == int(usuario_atual['id']):
                st.error('Você não pode remover a senha da sua própria conta enquanto está logado.')
            else:
                _submeter_api_e_recarregar(
                    'DELETE',
                    f'/auth/senhas/{chave_tipo}/{int(usr_del_id)}',
                    'Senha removida! O usuário não poderá mais fazer login.',
                    aviso=True,
                )


if '⚙  Gerenciamento' in pages and tipo_perfil in ('admin', 'chefe'):
    with pages['⚙  Gerenciamento']:
        st.write('')
        header('Gerenciamento do Banco de Dados', 'Adicione, atualize ou remova registros e vínculos através da API FastAPI')

        if tipo_perfil == 'chefe':
            emp_chefe_id = int(usuario['id_empresa'])
            emp_chefe_nome = all_data['empresas'].loc[all_data['empresas']['id'] == emp_chefe_id, 'nome']
            nome_emp_txt = emp_chefe_nome.values[0] if len(emp_chefe_nome) else f'Empresa #{emp_chefe_id}'
            st.info(f'Perfil **Chefe** · Operações restritas à empresa **{escape(str(nome_emp_txt))}** (ID {emp_chefe_id}).')

            empresas_esc = all_data['empresas'][all_data['empresas']['id'] == emp_chefe_id]
            projetos_esc = all_data['projetos'][all_data['projetos']['id_empresa'] == emp_chefe_id]
            p_esc_ids = projetos_esc['id'].tolist()
            membros_esc = all_data['membros'][all_data['membros']['id_empresa'] == emp_chefe_id]
            membros_comuns_esc = membros_esc[membros_esc['perfil'] == 'membro'] if 'perfil' in membros_esc.columns else membros_esc
            sprints_esc = all_data['sprints'][all_data['sprints']['id_projeto'].isin(p_esc_ids)]
            tarefas_esc = all_data['tarefas'][all_data['tarefas']['id_projeto'].isin(p_esc_ids)]
            mp_esc = all_data['membro_projeto'][all_data['membro_projeto']['id_projeto'].isin(p_esc_ids)]
            clientes_esc = all_data['clientes']

            tab_create, tab_delete = st.tabs(['➕ Inserir / Atualizar Dados', '🗑️ Desvincular / Revogar'])

            with tab_create:
                acao_escolhida = st.selectbox(
                    'Selecione a operação',
                    [
                        'Adicionar Projeto à Empresa',
                        'Cadastrar Membro na Empresa',
                        'Associar Membro a Projeto',
                        'Cadastrar Sprint',
                        'Cadastrar Tarefa',
                        'Atualizar Estado de Tarefa',
                        'Associar Tarefa a Sprint',
                        'Atribuir Tarefa a Membro',
                        'Definir / Alterar Senha de Membro',
                    ],
                )
                if acao_escolhida == 'Adicionar Projeto à Empresa':
                    _render_form_projeto(empresas_esc, clientes_esc, empresa_fixa_id=emp_chefe_id)
                elif acao_escolhida == 'Cadastrar Membro na Empresa':
                    _render_form_membro(empresas_esc, permitir_perfil=False, empresa_fixa_id=emp_chefe_id)
                elif acao_escolhida == 'Associar Membro a Projeto':
                    _render_form_associar_membro_projeto(projetos_esc, membros_esc)
                elif acao_escolhida == 'Cadastrar Sprint':
                    _render_form_sprint(projetos_esc)
                elif acao_escolhida == 'Cadastrar Tarefa':
                    _render_form_tarefa(projetos_esc, sprints_esc, membros_esc)
                elif acao_escolhida == 'Atualizar Estado de Tarefa':
                    _render_form_atualizar_estado_tarefa(tarefas_esc)
                elif acao_escolhida == 'Associar Tarefa a Sprint':
                    _render_form_associar_tarefa_sprint(tarefas_esc, sprints_esc)
                elif acao_escolhida == 'Atribuir Tarefa a Membro':
                    _render_form_atribuir_tarefa_membro(tarefas_esc, membros_esc)
                elif acao_escolhida == 'Definir / Alterar Senha de Membro':
                    _render_form_definir_senha({'Membro': ('membro', membros_comuns_esc)})

            with tab_delete:
                modo_delecao = st.selectbox(
                    'Selecione a ação de remoção',
                    ['Desvincular Membro de Projeto', 'Remover Senha de Membro (Revogar Acesso)'],
                )
                if modo_delecao == 'Desvincular Membro de Projeto':
                    _render_form_desvincular_membro_projeto(mp_esc, projetos_esc, membros_esc)
                elif modo_delecao == 'Remover Senha de Membro (Revogar Acesso)':
                    _render_form_remover_senha({'Membro': ('membro', membros_comuns_esc)}, usuario)

        else:
            # Perfil ADMIN — Manutenção completa do servidor
            tab_create, tab_delete = st.tabs(['➕ Inserir / Atualizar Dados', '🗑️ Excluir / Desvincular Dados'])

            with tab_create:
                acao_escolhida = st.selectbox(
                    'Selecione a operação',
                    [
                        'Inserir Novo Registro',
                        'Alterar Perfil de Membro',
                        'Associar Membro a Projeto',
                        'Atualizar Estado de Tarefa',
                        'Associar Tarefa a Sprint',
                        'Atribuir Tarefa a Membro',
                        'Vincular Projeto a Cliente',
                        'Definir / Alterar Senha de Usuário',
                    ],
                )

                if acao_escolhida == 'Inserir Novo Registro':
                    tipo_insercao = st.selectbox(
                        'Entidade',
                        ['Empresa', 'Membro', 'Cliente', 'Projeto', 'Sprint', 'Tarefa', 'Administrador'],
                    )
                    if tipo_insercao == 'Empresa':
                        with st.form('form_empresa'):
                            id_emp = st.number_input('ID da Empresa', step=1)
                            nome_emp = st.text_input('Nome da Empresa')
                            rep_emp = st.text_input('Representante')
                            if st.form_submit_button('Salvar Empresa', type='primary'):
                                _submeter_api_e_recarregar(
                                    'POST', '/empresas', 'Empresa cadastrada com sucesso!',
                                    json_body={'id': int(id_emp), 'nome': nome_emp, 'rep': rep_emp},
                                )
                    elif tipo_insercao == 'Membro':
                        _render_form_membro(all_data['empresas'], permitir_perfil=True)
                    elif tipo_insercao == 'Cliente':
                        with st.form('form_cliente'):
                            nome_cli = st.text_input('Nome do Cliente')
                            email_cli = st.text_input('E-mail')
                            empresas_df = all_data['empresas']
                            emp_cli = st.selectbox(
                                'Empresa Vinculada',
                                options=empresas_df['id'].tolist(),
                                format_func=lambda x: f"{empresas_df.loc[empresas_df['id'] == x, 'nome'].values[0]} (ID: {x})",
                            )
                            if st.form_submit_button('Salvar Cliente', type='primary'):
                                _submeter_api_e_recarregar(
                                    'POST', '/clientes', 'Cliente cadastrado com sucesso!',
                                    json_body={'nome': nome_cli, 'email': email_cli, 'id_empresa': int(emp_cli)},
                                )
                    elif tipo_insercao == 'Projeto':
                        _render_form_projeto(all_data['empresas'], all_data['clientes'])
                    elif tipo_insercao == 'Sprint':
                        _render_form_sprint(all_data['projetos'])
                    elif tipo_insercao == 'Tarefa':
                        _render_form_tarefa(all_data['projetos'], all_data['sprints'], all_data['membros'])
                    elif tipo_insercao == 'Administrador':
                        with st.form('form_admin'):
                            nome_adm = st.text_input('Nome do Administrador')
                            email_adm = st.text_input('E-mail')
                            senha_adm = st.text_input('Senha', type='password')
                            if st.form_submit_button('Salvar Administrador', type='primary'):
                                _submeter_api_e_recarregar(
                                    'POST', '/admins', 'Administrador cadastrado com sucesso!',
                                    json_body={'nome': nome_adm, 'email': email_adm, 'senha': senha_adm},
                                )

                elif acao_escolhida == 'Alterar Perfil de Membro':
                    with st.form('form_perfil_membro'):
                        membros_df = all_data['membros']
                        if membros_df.empty:
                            st.info('Nenhum membro cadastrado.')
                            st.form_submit_button('Atualizar Perfil', disabled=True)
                        else:
                            m_sel = st.selectbox(
                                'Selecione o Membro',
                                options=membros_df['id'].tolist(),
                                format_func=lambda x: (
                                    f"{membros_df.loc[membros_df['id'] == x, 'nome'].values[0]} "
                                    f"[{membros_df.loc[membros_df['id'] == x, 'perfil'].values[0]}]"
                                ),
                            )
                            novo_perfil = st.selectbox('Novo Perfil', ['membro', 'chefe'])
                            if st.form_submit_button('Atualizar Perfil', type='primary'):
                                _submeter_api_e_recarregar(
                                    'PATCH', f'/membros/{int(m_sel)}/perfil',
                                    'Perfil do membro atualizado com sucesso!',
                                    json_body={'perfil': novo_perfil},
                                )

                elif acao_escolhida == 'Associar Membro a Projeto':
                    _render_form_associar_membro_projeto(all_data['projetos'], all_data['membros'])
                elif acao_escolhida == 'Atualizar Estado de Tarefa':
                    _render_form_atualizar_estado_tarefa(all_data['tarefas'])
                elif acao_escolhida == 'Associar Tarefa a Sprint':
                    _render_form_associar_tarefa_sprint(all_data['tarefas'], all_data['sprints'])
                elif acao_escolhida == 'Atribuir Tarefa a Membro':
                    _render_form_atribuir_tarefa_membro(all_data['tarefas'], all_data['membros'])
                elif acao_escolhida == 'Vincular Projeto a Cliente':
                    with st.form('form_vincular_demanda'):
                        projetos_df = all_data['projetos']
                        p_demanda = st.selectbox(
                            'Projeto',
                            options=projetos_df['id'].tolist(),
                            format_func=lambda x: f"{projetos_df.loc[projetos_df['id'] == x, 'nome'].values[0]} (ID: {x})",
                        )
                        clientes_df = all_data['clientes']
                        c_demanda = st.selectbox(
                            'Cliente',
                            options=clientes_df['id'].tolist(),
                            format_func=lambda x: f"{clientes_df.loc[clientes_df['id'] == x, 'nome'].values[0]} (ID: {x})",
                        )
                        if st.form_submit_button('Criar Vínculo (Demanda)', type='primary'):
                            _submeter_api_e_recarregar(
                                'POST', '/demandas', 'Projeto vinculado ao cliente com sucesso!',
                                json_body={'id_projeto': int(p_demanda), 'id_cliente': int(c_demanda)},
                            )
                elif acao_escolhida == 'Definir / Alterar Senha de Usuário':
                    _render_form_definir_senha({
                        'Admin': ('admin', all_data['admins']),
                        'Membro / Chefe': ('membro', all_data['membros']),
                        'Cliente': ('cliente', all_data['clientes']),
                    })

            with tab_delete:
                modo_delecao = st.selectbox(
                    'Selecione a ação de remoção',
                    [
                        'Excluir Registro de Tabela',
                        'Desvincular Projeto de Cliente (Tabela Demanda)',
                        'Desvincular Membro de Projeto',
                        'Remover Senha de Usuário (Revogar Acesso)',
                    ],
                )

                if modo_delecao == 'Excluir Registro de Tabela':
                    opcao_deletar = st.selectbox(
                        'Selecione a entidade para remover',
                        ['Tarefa', 'Sprint', 'Membro', 'Cliente', 'Projeto', 'Empresa', 'Administrador'],
                    )
                    if opcao_deletar == 'Tarefa':
                        with st.form('form_del_tarefa'):
                            tarefas_df = all_data['tarefas']
                            t_del = st.selectbox(
                                'Selecione a Tarefa',
                                options=tarefas_df['id'].tolist(),
                                format_func=lambda x: f"[{x}] {tarefas_df.loc[tarefas_df['id'] == x, 'descricao'].values[0][:50]}...",
                            )
                            if st.form_submit_button('Excluir Tarefa'):
                                _submeter_api_e_recarregar('DELETE', f'/tarefas/{int(t_del)}', 'Tarefa removida com sucesso!', aviso=True)
                    elif opcao_deletar == 'Sprint':
                        with st.form('form_del_sprint'):
                            sprints_df = all_data['sprints']
                            s_del = st.selectbox(
                                'Selecione a Sprint',
                                options=sprints_df['id'].tolist(),
                                format_func=lambda x: f"Sprint ID {x} (Projeto ID: {sprints_df.loc[sprints_df['id'] == x, 'id_projeto'].values[0]})",
                            )
                            if st.form_submit_button('Excluir Sprint'):
                                _submeter_api_e_recarregar('DELETE', f'/sprints/{int(s_del)}', 'Sprint removida com sucesso!', aviso=True)
                    elif opcao_deletar == 'Membro':
                        with st.form('form_del_membro'):
                            membros_df = all_data['membros']
                            m_del = st.selectbox(
                                'Selecione o Membro',
                                options=membros_df['id'].tolist(),
                                format_func=lambda x: f"{membros_df.loc[membros_df['id'] == x, 'nome'].values[0]} ({membros_df.loc[membros_df['id'] == x, 'cargo'].values[0]})",
                            )
                            if st.form_submit_button('Excluir Membro'):
                                _submeter_api_e_recarregar('DELETE', f'/membros/{int(m_del)}', 'Membro removido com sucesso!', aviso=True)
                    elif opcao_deletar == 'Cliente':
                        with st.form('form_del_cliente'):
                            clientes_df = all_data['clientes']
                            c_del = st.selectbox(
                                'Selecione o Cliente',
                                options=clientes_df['id'].tolist(),
                                format_func=lambda x: f"{clientes_df.loc[clientes_df['id'] == x, 'nome'].values[0]}",
                            )
                            if st.form_submit_button('Excluir Cliente'):
                                _submeter_api_e_recarregar('DELETE', f'/clientes/{int(c_del)}', 'Cliente removido com sucesso!', aviso=True)
                    elif opcao_deletar == 'Projeto':
                        with st.form('form_del_projeto'):
                            projetos_df = all_data['projetos']
                            p_del = st.selectbox(
                                'Selecione o Projeto',
                                options=projetos_df['id'].tolist(),
                                format_func=lambda x: f"{projetos_df.loc[projetos_df['id'] == x, 'nome'].values[0]} (ID: {x})",
                            )
                            if st.form_submit_button('Excluir Projeto'):
                                _submeter_api_e_recarregar('DELETE', f'/projetos/{int(p_del)}', 'Projeto removido com sucesso!', aviso=True)
                    elif opcao_deletar == 'Empresa':
                        with st.form('form_del_empresa'):
                            empresas_df = all_data['empresas']
                            e_del = st.selectbox(
                                'Selecione a Empresa',
                                options=empresas_df['id'].tolist(),
                                format_func=lambda x: f"{empresas_df.loc[empresas_df['id'] == x, 'nome'].values[0]} (Rep: {empresas_df.loc[empresas_df['id'] == x, 'rep'].values[0]})",
                            )
                            if st.form_submit_button('Excluir Empresa'):
                                _submeter_api_e_recarregar('DELETE', f'/empresas/{int(e_del)}', 'Empresa removida com sucesso!', aviso=True)
                    elif opcao_deletar == 'Administrador':
                        with st.form('form_del_admin'):
                            admins_df = all_data['admins']
                            a_del = st.selectbox(
                                'Selecione o Administrador',
                                options=admins_df['id'].tolist(),
                                format_func=lambda x: f"{admins_df.loc[admins_df['id'] == x, 'nome'].values[0]} ({admins_df.loc[admins_df['id'] == x, 'email'].values[0]})",
                            )
                            if st.form_submit_button('Excluir Administrador'):
                                if int(a_del) == int(usuario['id']):
                                    st.error('Você não pode excluir a sua própria conta de administrador.')
                                else:
                                    _submeter_api_e_recarregar('DELETE', f'/admins/{int(a_del)}', 'Administrador removido com sucesso!', aviso=True)

                elif modo_delecao == 'Desvincular Projeto de Cliente (Tabela Demanda)':
                    with st.form('form_desvincular_demanda'):
                        st.caption('Selecione um vínculo existente na tabela `demanda` para removê-lo:')
                        if demands.empty:
                            st.info('Não há vínculos de demanda ativos no recorte atual.')
                        else:
                            projetos_df = all_data['projetos']
                            clientes_df = all_data['clientes']

                            def formatar_demanda(r):
                                p_nome = projetos_df.loc[projetos_df['id'] == r.id_projeto, 'nome'].values
                                c_nome = clientes_df.loc[clientes_df['id'] == r.id_cliente, 'nome'].values
                                p_str = p_nome[0] if len(p_nome) > 0 else f'ID {r.id_projeto}'
                                c_str = c_nome[0] if len(c_nome) > 0 else f'ID {r.id_cliente}'
                                return f"Projeto: '{p_str}' ↔ Cliente: '{c_str}'"

                            demanda_opcoes = [formatar_demanda(r) for r in demands.itertuples()]
                            demanda_tuplas = [(int(r.id_projeto), int(r.id_cliente)) for r in demands.itertuples()]
                            escolha_idx = st.selectbox('Vínculo Projeto ↔ Cliente', options=range(len(demanda_opcoes)), format_func=lambda i: demanda_opcoes[i])
                            if st.form_submit_button('Remover Vínculo'):
                                p_id_sel, c_id_sel = demanda_tuplas[escolha_idx]
                                _submeter_api_e_recarregar('DELETE', f'/demandas/{p_id_sel}/{c_id_sel}', 'Vínculo removido com sucesso!', aviso=True)

                elif modo_delecao == 'Desvincular Membro de Projeto':
                    _render_form_desvincular_membro_projeto(all_data['membro_projeto'], all_data['projetos'], all_data['membros'])

                elif modo_delecao == 'Remover Senha de Usuário (Revogar Acesso)':
                    _render_form_remover_senha(
                        {
                            'Admin': ('admin', all_data['admins']),
                            'Membro / Chefe': ('membro', all_data['membros']),
                            'Cliente': ('cliente', all_data['clientes']),
                        },
                        usuario,
                    )

st.divider()
st.caption(f'◆ EJFlow · Observatório de Projetos | API: `{API_URL}` | MySQL: `{db_name}` | painel interativo · © projeto acadêmico')
