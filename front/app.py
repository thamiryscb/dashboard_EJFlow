"""EJFlow | Observatório de Projetos — painel acadêmico e executivo (Banco 2).
Painel interativo com operações de leitura, escrita (CRUD) e gerenciamento de vínculos via MySQL.
"""
from __future__ import annotations
import io
import zipfile
from html import escape
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from data_access import settings, fetch_all, normalize, make_analytics, sprint_analytics, data_quality, TABLES

from data_access import (
    inserir_nova_empresa, inserir_novo_membro, inserir_novo_cliente, inserir_novo_projeto, 
    inserir_nova_sprint, inserir_nova_tarefa, atualizar_estado_tarefa,
    associar_tarefa_a_sprint, vincular_projeto_cliente, desvincular_projeto_cliente,
    deletar_empresa, deletar_cliente, deletar_membro, deletar_projeto, deletar_sprint, deletar_tarefa
)

st.set_page_config(page_title='EJFlow | Observatório de Projetos', page_icon='◆', layout='wide', initial_sidebar_state='expanded')
COLORS = {'concluida':'#2DD5A7','em_andamento':'#6D8DFF','nao_iniciada':'#F6BA64','nao_informado':'#94A3B8'}
PALETTE = ['#698BFF','#32D5AB','#F8BA70','#BA99FF','#78C8ED','#FA8E9C','#98A5C0']

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
.section-head {color:#D5E1F6;font-weight:800;font-size:1rem;letter-spacing:.01em;margin:18px 0 8px;}
small {color:#A3B7D0;}
</style>''', unsafe_allow_html=True)


def fmt(value, decimals=0, suffix=''):
    if value is None or pd.isna(value) or not np.isfinite(float(value)):
        return '—'
    return f'{float(value):,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.') + suffix


def draw(fig, height=350, percent=False, legend=False):
    fig.update_layout(
        height=height, margin=dict(l=15,r=19,t=24,b=30),
        paper_bgcolor='#111c30',plot_bgcolor='#111c30',
        font=dict(family='DM Sans, Arial', color='#D5E3F9',size=12),
        colorway=PALETTE,hoverlabel=dict(bgcolor='#263c61',font_color='#fff'),
        legend=dict(orientation='h',x=0,y=1.12,font=dict(size=11)),showlegend=legend,
        hovermode='closest',
    )
    fig.update_xaxes(showgrid=False,zeroline=False,linecolor='#3B4B62',tickfont=dict(color='#A9BBD6'))
    fig.update_yaxes(showgrid=True,gridcolor='#26354c',zeroline=False,tickfont=dict(color='#A9BBD6'))
    if percent:
        fig.update_xaxes(ticksuffix='%')
    st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False, 'modeBarButtonsToRemove':['lasso2d','select2d']})


def header(title, subtitle=None):
    st.markdown(f'<div class="section-head">{title}</div>',unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)


def insight(title, description):
    st.markdown(f'<div class="insight"><strong>{title}</strong><p>{description}</p></div>',unsafe_allow_html=True)

@st.cache_data(ttl=60,show_spinner=False)
def load_db(host,port,user,password,database):
    return normalize(fetch_all({'host':host,'port':port,'user':user,'password':password,'database':database})[0])

config=settings()
with st.sidebar:
    st.markdown('## ◆ EJFlow')
    st.caption('OBSERVATÓRIO · GESTÃO DE PROJETOS')
    st.divider()
    st.markdown('**FONTE DE DADOS**')
    st.caption(f"MySQL · `{config['database']}`")
    st.caption('Leitura e Escrita • Dados atualizados da base')
    if st.button('↻  Atualizar dados',use_container_width=True,type='primary'):
        load_db.clear()
        st.rerun()

try:
    all_data=load_db(config['host'], config['port'],config['user'],config['password'],config['database'])
except Exception as exc:
    st.markdown('<div class="eyebrow">EJFlow / CONEXÃO</div>',unsafe_allow_html=True)
    st.title('Conexão MySQL indisponível')
    st.error('Não foi possível carregar as tabelas do banco. O painel não utiliza dados simulados.')
    st.info('Confira o arquivo `.streamlit/secrets.toml`, o nome do schema e a existência das 7 tabelas especificadas no SQL anexado.')
    st.code('py diagnostico_mysql.py',language='powershell')
    with st.expander('Diagnóstico técnico (somente administrador local)'):
        st.caption('Execute o diagnóstico no terminal para obter detalhes sem revelar credenciais na página pública.')
        st.caption('Se necessário, consulte o README. Esta página não exibe senhas ou mensagens completas do driver.')
    st.stop()

with st.sidebar:
    st.divider()
    st.markdown('**FILTROS GLOBAIS**')
    e=all_data['empresas']; p=all_data['projetos']; t=all_data['tarefas']
    companies_map={int(r.id):f'{r.nome} · #{int(r.id)}' for r in e.itertuples()}
    company_ids=st.multiselect('Empresas',options=list(companies_map),default=list(companies_map),format_func=lambda x:companies_map[x])
    available=p[p['id_empresa'].isin(company_ids)]
    projects_map={int(r.id):f'{r.nome} · #{int(r.id)}' for r in available.itertuples()}
    project_ids=st.multiselect('Projetos',options=list(projects_map),default=list(projects_map),format_func=lambda x:projects_map[x])
    st.caption('Filtros de empresa e projeto aplicam-se a todas as abas.')
    st.divider()
    st.caption('As informações são consultadas diretamente no Banco 2.')

m=make_analytics(all_data,company_ids=company_ids,project_ids=project_ids)
projects=m['projects']; tasks=m['tasks']; sprints=m['sprints']; summary=m['summary']; demands=m['demands']
if projects.empty:
    st.warning('Não há projetos nesse recorte. Selecione outra empresa ou projeto na barra lateral.')
    st.stop()

sprint_metrics = sprint_analytics(sprints, tasks)
backlog = tasks[tasks['id_sprint'].isna() & tasks['estado'].ne('concluida')]
project_names = projects.set_index('id')['nome']

st.markdown('<div class="hero"><div class="eyebrow">SISTEMAS DE INFORMAÇÃO · BUSINESS INTELLIGENCE</div><h1>Observatório de Projetos <span style="color:#8EAAFF">↗</span></h1><p>Visão gerencial, acadêmica e interativa de projetos, sprints, tarefas, clientes e equipes.</p><span class="pill">● Dados consultados diretamente do MySQL</span></div>',unsafe_allow_html=True)

k1,k2,k3,k4,k5,k6=st.columns(6)
completed=int((tasks['estado']=='concluida').sum())
rate=(100*completed/len(tasks)) if len(tasks) else np.nan
k1.metric('Projetos',fmt(len(projects)))
k2.metric('Empresas',fmt(len(m['companies'])))
k3.metric('Sprints',fmt(len(sprints)))
k4.metric('Tarefas',fmt(len(tasks)))
k5.metric('Concluídas',fmt(completed))
k6.metric('Conclusão',fmt(rate,1,'%'))
st.caption('Taxa de conclusão = tarefas com estado `concluida` / total de tarefas do recorte.')

pages=st.tabs(['◈  Visão geral','▤  Projetos','◷  Sprints & tarefas','♧  Clientes & equipes','📋 Tabelas do Dataset','◎  Qualidade & metodologia','⚙  Gerenciamento'])

with pages[0]:
    st.write('')
    lead=summary.sort_values('total_tarefas',ascending=False).iloc[0] if len(summary) else None
    pct=fmt(rate,1,'%')
    cols=st.columns(3)
    with cols[0]:
        insight('📌 Retrato das entregas',f'{completed} de {len(tasks)} tarefas cadastradas no recorte estão concluídas ({pct}).')
    with cols[1]:
        insight('🏁 Projeto com mais tarefas', f"{escape(str(lead['nome']))} reúne {int(lead['total_tarefas'])} tarefa(s) no recorte." if lead is not None else 'Sem projetos disponíveis.')
    with cols[2]:
        insight('🔎 Backlog fora de sprint',f'{len(backlog)} tarefa(s) ainda não concluídas e sem sprint no recorte.')
    a,b=st.columns([1.45,1])
    with a:
        header('Situação das tarefas','Distribuição dos estados efetivamente cadastrados')
        status=tasks.groupby('estado').size().reset_index(name='quantidade')
        labels={'concluida':'Concluída','em_andamento':'Em andamento','nao_iniciada':'Não iniciada','nao_informado':'Não informado'}
        status['label']=status['estado'].map(labels).fillna(status['estado'])
        fig=px.bar(status,x='quantidade',y='label',orientation='h',text='quantidade',color='estado',color_discrete_map=COLORS)
        fig.update_traces(textposition='outside',showlegend=False)
        fig.update_xaxes(range=[0,max(2, status['quantidade'].max()*1.18)] if len(status) else [0,1])
        draw(fig,height=320)
    with b:
        header('Projetos por empresa','Quantidade de projetos vinculados às empresas selecionadas')
        pc=summary.groupby('empresa',dropna=False).size().reset_index(name='projetos')
        fig=px.pie(pc,names='empresa',values='projetos',hole=.66,color_discrete_sequence=PALETTE)
        fig.update_traces(textinfo='value+percent',hovertemplate='%{label}: %{value} projeto(s)<extra></extra>')
        draw(fig,height=320)
    a,b=st.columns([1.4,1])
    with a:
        header('Volume de trabalho por projeto','Contagem de tarefas sem duplicações de JOIN com clientes ou sprints')
        vol=summary.sort_values('total_tarefas',ascending=True)
        fig=px.bar(vol,x='total_tarefas',y='nome',orientation='h',color='empresa',text='total_tarefas',color_discrete_sequence=PALETTE)
        fig.update_traces(textposition='outside')
        draw(fig,370,legend=len(vol['empresa'].unique())>1)
    with b:
        header('Conclusão por projeto','Percentual de tarefas com estado concluída')
        comp=summary[summary['total_tarefas']>0].sort_values('taxa_conclusao',ascending=True)
        if comp.empty:
            st.info('Não há tarefas para calcular percentuais.')
        else:
            fig=px.bar(comp,x='taxa_conclusao',y='nome',orientation='h',text='taxa_conclusao',color='nome',color_discrete_sequence=PALETTE)
            fig.update_traces(texttemplate='%{text:.1f}%',textposition='outside',showlegend=False)
            fig.update_xaxes(range=[0,110]);draw(fig,370,percent=True)

with pages[1]:
    st.write('')
    header('Portfólio completo','Indicadores por projeto sem combinar métricas em um índice arbitrário')
    display=summary[['id','nome','empresa','total_sprints','sprints_concluidas','total_tarefas','concluidas','em_andamento','nao_iniciadas','clientes','taxa_conclusao']].rename(columns={
        'id':'ID','nome':'Projeto','empresa':'Empresa','total_sprints':'Sprints',
        'sprints_concluidas':'Sprints finalizadas','total_tarefas':'Tarefas','concluidas':'Concluídas',
        'em_andamento':'Em andamento','nao_iniciadas':'Não iniciadas','clientes':'Clientes vinculados',
        'taxa_conclusao':'Conclusão (%)'})
    st.dataframe(display,use_container_width=True,hide_index=True,
                 column_config={'Conclusão (%)':st.column_config.ProgressColumn('Conclusão (%)',min_value=0,max_value=100,format='%.1f%%')})
    header('Análise detalhada','Selecione um projeto para investigar suas demandas, sprints e tarefas')
    project_id=st.selectbox('Projeto em destaque',options=summary['id'].tolist(),format_func=lambda x:next(f"{r.nome} — {r.empresa}" for r in summary.itertuples() if r.id==x))
    selected=summary[summary['id']==project_id].iloc[0]
    st.markdown(f'<div class="info-card"><strong style="color:#EFF5FF;font-size:1.1rem">{escape(str(selected["nome"]))}</strong><p style="margin:7px 0;color:#BDCCE0">{escape(str(selected["descricao"]))}</p><small>Empresa responsável: {escape(str(selected["empresa"]))}</small></div>',unsafe_allow_html=True)
    ca,cb,cc,cd=st.columns(4)
    ca.metric('Tarefas do projeto',fmt(selected['total_tarefas']))
    cb.metric('Concluídas',fmt(selected['concluidas']))
    cc.metric('Sprints registradas',fmt(selected['total_sprints']))
    cd.metric('Clientes relacionados',fmt(selected['clientes']))
    client_ids=demands.loc[demands['id_projeto']==project_id,'id_cliente'].tolist()
    client_names=m['clients'][m['clients']['id'].isin(client_ids)][['id','nome']].rename(columns={'id':'ID','nome':'Cliente'})
    st.markdown('**Clientes associados à demanda**')
    if client_names.empty: st.info('Nenhum cliente associado a esse projeto.')
    else: st.dataframe(client_names,hide_index=True,use_container_width=True)

with pages[2]:
    st.write('')
    a,b,c,d=st.columns(4)
    durs=sprint_metrics['duracao_dias']
    a.metric('Sprints cadastradas',fmt(len(sprints)))
    b.metric('Sprints marcadas concluídas',fmt((sprints['isDone']==1).sum()))
    c.metric('Duração média cadastrada',fmt(durs.dropna().mean(),1,' dias'))
    d.metric('Tarefas sem sprint',fmt(tasks['id_sprint'].isna().sum()))
    header('Distribuição de tarefas por sprint','Associação atual de tarefas; não é histórico de movimentações')
    sprint_list=sprints.merge(projects[['id','nome']].rename(columns={'id':'id_projeto','nome':'projeto'}),on='id_projeto',how='left')
    sprint_list['rotulo']=sprint_list['projeto']+' · Sprint '+sprint_list['id'].astype(str)
    bys=tasks.groupby(['id_projeto','id_sprint','estado']).size().reset_index(name='quantidade')
    bys=bys.merge(sprint_list[['id','id_projeto','rotulo']],left_on=['id_projeto','id_sprint'],right_on=['id_projeto','id'],how='inner')
    if bys.empty:
        st.info('Não há tarefas associadas a sprints neste recorte.')
    else:
        fig=px.bar(bys,x='rotulo',y='quantidade',color='estado',barmode='stack',color_discrete_map=COLORS,
                   labels={'rotulo':'Sprint','quantidade':'Tarefas','estado':'Estado'})
        fig.update_xaxes(tickangle=-30)
        draw(fig,380,legend=True)
    a,b=st.columns([1.2,1])
    with a:
        header('Calendário de sprints','Intervalos planejados/cadastrados')
        timeline=sprint_list.dropna(subset=['data_in','data_fin']).copy()
        timeline=timeline[timeline['data_fin']>=timeline['data_in']]
        if timeline.empty: st.info('Nenhuma sprint possui datas de início e fim válidas.')
        else:
            fig=px.timeline(timeline,x_start='data_in',x_end='data_fin',y='rotulo',color='projeto',
                            hover_data=['id','isDone'],color_discrete_sequence=PALETTE)
            fig.update_yaxes(autorange='reversed')
            draw(fig,max(330,min(620,90+50*len(timeline))),legend=True)
    with b:
        header('Estados das sprints','O campo `isDone` é independente do status de cada tarefa')
        states=sprints['isDone'].map({1:'Finalizada',0:'Não finalizada'}).fillna('Não informado').value_counts().reset_index()
        states.columns=['estado','quantidade']
        fig=px.pie(states,names='estado',values='quantidade',hole=.6,color_discrete_sequence=PALETTE)
        draw(fig,330)
    header('Explorar tarefas','Os filtros abaixo valem para a tabela')
    options=sorted(tasks['estado'].unique())
    chosen=st.multiselect('Estados da tabela',options=options,default=options)
    backlog_only = st.checkbox('Mostrar apenas backlog fora de sprint')
    task_source = backlog if backlog_only else tasks
    dtable=task_source[task_source['estado'].isin(chosen)].assign(projeto=lambda frame: frame['id_projeto'].map(project_names))
    dtable=dtable[['id','projeto','id_sprint','estado','descricao','data_cria','data_fin']].rename(columns={
        'id':'ID','projeto':'Projeto','id_sprint':'Sprint','estado':'Estado','descricao':'Descrição',
        'data_cria':'Criada em','data_fin':'Finalizada em'})
    st.dataframe(dtable,hide_index=True,use_container_width=True,height=370)

with pages[3]:
    st.write('')
    aa,bb,cc,dd=st.columns(4)
    aa.metric('Empresas do recorte',fmt(len(m['companies'])))
    bb.metric('Membros das empresas',fmt(len(m['members'])))
    cc.metric('Clientes vinculados',fmt(len(m['clients'])))
    dd.metric('Relações projeto–cliente',fmt(len(demands)))
    a,b=st.columns([1.1,1])
    with a:
        header('Membros por empresa','Não significa participantes de cada projeto')
        mc=m['members'].groupby('id_empresa').size().reset_index(name='membros')
        mc=mc.merge(all_data['empresas'][['id','nome']],left_on='id_empresa',right_on='id',how='left')
        if mc.empty: st.info('Sem membros cadastrados.')
        else:
            fig=px.bar(mc,x='membros',y='nome',orientation='h',color='nome',text='membros',color_discrete_sequence=PALETTE)
            fig.update_traces(textposition='outside',showlegend=False);draw(fig,340)
    with b:
        header('Cargos cadastrados','Distribuição descritiva do cadastro de membros')
        positions=m['members'].groupby('cargo').size().reset_index(name='membros')
        if positions.empty: st.info('Sem cargos cadastrados.')
        else:
            fig=px.bar(positions,x='membros',y='cargo',orientation='h',text='membros',color='cargo',color_discrete_sequence=PALETTE)
            fig.update_traces(textposition='outside',showlegend=False);draw(fig,340)
    header('Relacionamento entre clientes e projetos','JOIN: demanda → projetos → clientes')
    relations=demands.merge(projects[['id','nome','id_empresa']].rename(columns={'id':'id_projeto','nome':'projeto'}),on='id_projeto',how='left')
    relations=relations.merge(all_data['clientes'][['id','nome']].rename(columns={'id':'id_cliente','nome':'cliente'}),on='id_cliente',how='left')
    relations=relations.merge(all_data['empresas'][['id','nome']].rename(columns={'id':'id_empresa','nome':'empresa'}),on='id_empresa',how='left')
    st.dataframe(relations[['empresa','projeto','cliente']].rename(columns={'empresa':'Empresa','projeto':'Projeto','cliente':'Cliente'}),hide_index=True,use_container_width=True)

# =========================================================================
# ABA 5: TABELAS DO DATASET (VISUALIZAÇÃO COMPLETA BRUTA DO MYSQL)
# =========================================================================
with pages[4]:
    st.write('')
    header('Visualização do Banco de Dados', 'Exibição completa de todas as tabelas cadastradas no MySQL, sem filtros de tela')
    
    tab_emp, tab_cli, tab_proj, tab_memb, tab_dem, tab_spr, tab_tar = st.tabs([
        '🏢 Empresas', '👤 Clientes', '📂 Projetos', '👥 Membros', '🔗 Demanda', '🏃 Sprints', '📌 Tarefas'
    ])
    
    with tab_emp:
        st.subheader('Tabela: Empresas')
        st.dataframe(all_data['empresas'], use_container_width=True, hide_index=True)
        st.caption(f"Total de registros: {len(all_data['empresas'])}")
        
    with tab_cli:
        st.subheader('Tabela: Clientes')
        st.dataframe(all_data['clientes'], use_container_width=True, hide_index=True)
        st.caption(f"Total de registros: {len(all_data['clientes'])}")
        
    with tab_proj:
        st.subheader('Tabela: Projetos')
        st.dataframe(all_data['projetos'], use_container_width=True, hide_index=True)
        st.caption(f"Total de registros: {len(all_data['projetos'])}")
        
    with tab_memb:
        st.subheader('Tabela: Membros')
        st.dataframe(all_data['membros'], use_container_width=True, hide_index=True)
        st.caption(f"Total de registros: {len(all_data['membros'])}")
        
    with tab_dem:
        st.subheader('Tabela: Demanda (Projeto ↔ Cliente)')
        st.dataframe(all_data['demanda'], use_container_width=True, hide_index=True)
        st.caption(f"Total de registros: {len(all_data['demanda'])}")
        
    with tab_spr:
        st.subheader('Tabela: Sprints')
        st.dataframe(all_data['sprints'], use_container_width=True, hide_index=True)
        st.caption(f"Total de registros: {len(all_data['sprints'])}")
        
    with tab_tar:
        st.subheader('Tabela: Tarefas')
        st.dataframe(all_data['tarefas'], use_container_width=True, hide_index=True)
        st.caption(f"Total de registros: {len(all_data['tarefas'])}")

with pages[5]:
    st.write('')
    header('Do relatório ao painel','EJFlow · Gerenciador de Projetos para Empresas Juniores · UFRN')
    insight('Duas bases, dois objetivos', 'Este painel consulta o banco operacional do EJFlow e aplica os indicadores que suas sete tabelas permitem calcular.')
    header('Auditoria de dados','Verificações no banco inteiro, independentemente dos filtros laterais')
    checks=pd.DataFrame(data_quality(all_data),columns=['Verificação','Ocorrências'])
    checks['Situação']=checks['Ocorrências'].map(lambda n:'Sem ocorrências' if n==0 else 'Com ocorrências')
    st.dataframe(checks,hide_index=True,use_container_width=True)
    header('Catálogo de dados','Modelo relacional extraído do arquivo SQL fornecido')
    catalog=pd.DataFrame([
        ('empresas','Empresas e seus representantes','1:N com projetos e membros'),
        ('clientes','Clientes cadastrados','N:N com projetos via demanda'),
        ('projetos','Projetos e empresa responsável','1:N com sprints e tarefas'),
        ('membros','Integrantes vinculados a empresas','Não há vínculo direto com projetos'),
        ('demanda','Associação projeto–cliente','Chave primária composta'),
        ('sprints','Períodos e indicador de finalização','Pertencem a um projeto'),
        ('tarefas','Atividades e estados','Projeto obrigatório; sprint opcional'),
    ],columns=['Tabela','Descrição','Relação'])
    catalog['Linhas no MySQL']=[len(all_data[k]) for k in TABLES]
    st.dataframe(catalog,hide_index=True,use_container_width=True)
    header('Exportação do recorte','Faça download para validação acadêmica e reprodução dos resultados')
    frames={'projetos_resumo.csv':display,'tarefas.csv':tasks.copy(),
            'sprints.csv':sprints.copy(),'sprints_indicadores.csv':sprint_metrics,
            'auditoria_banco.csv':checks.copy()}
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for filename,frame in frames.items():
            z.writestr(filename,frame.to_csv(index=False).encode('utf-8-sig'))
    st.download_button('↓ Baixar relatório de dados (.zip)',data=buffer.getvalue(),file_name='ejflow_analise_mysql.zip',mime='application/zip',type='primary')

# =========================================================================
# ABA 7: GERENCIAMENTO (INSERÇÃO, ATUALIZAÇÃO E EXCLUSÃO / DESVINCULAÇÃO)
# =========================================================================

with pages[6]:
    st.write('')
    header('Gerenciamento do Banco de Dados', 'Adicione, atualize ou remova registros e vínculos diretamente no MySQL')

    tab_create, tab_delete = st.tabs(['➕ Inserir / Atualizar Dados', '🗑️ Excluir / Desvincular Dados'])

    # --- ABA DE INSERÇÃO E ATUALIZAÇÃO ---
    with tab_create:
        acao_escolhida = st.selectbox(
            'Selecione a operação', 
            ['Inserir Novo Registro', 'Atualizar Estado de Tarefa', 'Associar Tarefa a Sprint', 'Vincular Projeto a Cliente']
        )

        if acao_escolhida == 'Inserir Novo Registro':
            tipo_insercao = st.selectbox('Entidade', ['Empresa', 'Membro', 'Cliente', 'Projeto', 'Sprint', 'Tarefa'])

            if tipo_insercao == 'Empresa':
                with st.form('form_empresa'):
                    id_emp = st.number_input('ID da Empresa', step=1)
                    nome_emp = st.text_input('Nome da Empresa')
                    rep_emp = st.text_input('Representante')
                    if st.form_submit_button('Salvar Empresa'):
                        if inserir_nova_empresa(config, id_emp, nome_emp, rep_emp):
                            st.success('Empresa cadastrada com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao cadastrar empresa.')

            elif tipo_insercao == 'Membro':
                with st.form('form_membro'):
                    id_memb = st.number_input('ID do Membro', step=1)
                    
                    # Exibe o nome da empresa em vez do ID
                    empresas_df = all_data['empresas']
                    emp_escolhida = st.selectbox(
                        'Empresa', 
                        options=empresas_df['id'].tolist(), 
                        format_func=lambda x: f"{empresas_df.loc[empresas_df['id']==x, 'nome'].values[0]} (ID: {x})"
                    )
                    
                    nome_memb = st.text_input('Nome do Membro')
                    email_memb = st.text_input('E-mail')
                    cargo_memb = st.text_input('Cargo')
                    if st.form_submit_button('Salvar Membro'):
                        if inserir_novo_membro(config, id_memb, emp_escolhida, nome_memb, email_memb, cargo_memb):
                            st.success('Membro cadastrado com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao cadastrar membro.')

            elif tipo_insercao == 'Cliente':
                with st.form('form_cliente'):
                    nome_cli = st.text_input('Nome do Cliente')
                    email_cli = st.text_input('E-mail')
                    
                    # Exibe o nome da empresa em vez do ID
                    empresas_df = all_data['empresas']
                    emp_cli = st.selectbox(
                        'Empresa Vinculada', 
                        options=empresas_df['id'].tolist(), 
                        format_func=lambda x: f"{empresas_df.loc[empresas_df['id']==x, 'nome'].values[0]} (ID: {x})"
                    )
                    
                    if st.form_submit_button('Salvar Cliente'):
                        if inserir_novo_cliente(config, nome_cli, email_cli, emp_cli):
                            st.success('Cliente cadastrado com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao cadastrar cliente.')

            elif tipo_insercao == 'Projeto':
                with st.form('form_projeto'):
                    id_proj = st.number_input('ID do Projeto', step=1)
                    
                    # Exibe o nome da empresa responsável em vez do ID
                    empresas_df = all_data['empresas']
                    emp_proj = st.selectbox(
                        'Empresa Responsável', 
                        options=empresas_df['id'].tolist(),
                        format_func=lambda x: f"{empresas_df.loc[empresas_df['id']==x, 'nome'].values[0]} (ID: {x})"
                    )
                    
                    nome_proj = st.text_input('Nome do Projeto')
                    desc_proj = st.text_area('Descrição')
                    
                    # Exibe o nome do cliente em vez do ID
                    clientes_df = all_data['clientes']
                    cli_proj = st.selectbox(
                        'Cliente Inicial (Opcional)', 
                        options=[None] + clientes_df['id'].tolist(),
                        format_func=lambda x: 'Nenhum' if x is None else f"{clientes_df.loc[clientes_df['id']==x, 'nome'].values[0]} (ID: {x})"
                    )
                    
                    if st.form_submit_button('Salvar Projeto'):
                        if inserir_novo_projeto(config, id_proj, emp_proj, nome_proj, desc_proj, cli_proj if cli_proj else None):
                            st.success('Projeto cadastrado com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao cadastrar projeto.')

            elif tipo_insercao == 'Sprint':
                with st.form('form_sprint'):
                    # Exibe o nome do projeto ao qual a sprint pertence
                    proj_sprint = st.selectbox(
                        'Projeto', 
                        options=projects['id'].tolist(), 
                        format_func=lambda x: f"{project_names.get(x)} (ID: {x})"
                    )
                    
                    is_done_sprint = st.selectbox('Concluída?', [0, 1], format_func=lambda x: 'Sim' if x==1 else 'Não')
                    data_in = st.text_input('Data Início (YYYY-MM-DD HH:MM:SS)', '2026-03-01 08:00:00')
                    data_fin = st.text_input('Data Fim (YYYY-MM-DD HH:MM:SS)', '2026-03-15 18:00:00')
                    if st.form_submit_button('Salvar Sprint'):
                        if inserir_nova_sprint(config, proj_sprint, is_done_sprint, data_in, data_fin):
                            st.success('Sprint cadastrada com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao cadastrar sprint.')

            elif tipo_insercao == 'Tarefa':
                with st.form('form_tarefa'):
                    # Exibe o nome do projeto em vez do ID puro
                    proj_id = st.selectbox(
                        'Projeto', 
                        options=projects['id'].tolist(), 
                        format_func=lambda x: f"{project_names.get(x)} (ID: {x})"
                    )
                    
                    # Exibe detalhes da sprint (ID e projeto) se houver
                    sprints_df = all_data['sprints']
                    sprint_id = st.selectbox(
                        'Sprint (Opcional)', 
                        options=[None] + sprints_df['id'].tolist(),
                        format_func=lambda x: 'Nenhuma (Backlog)' if x is None else f"Sprint ID {x}"
                    )
                    
                    desc = st.text_area('Descrição da Tarefa')
                    estado = st.selectbox('Estado', ['nao_iniciada', 'em_andamento', 'concluida'])
                    if st.form_submit_button('Salvar Tarefa'):
                        if inserir_nova_tarefa(config, id_projeto=proj_id, descricao=desc, estado=estado, id_sprint=sprint_id if sprint_id else None):
                            st.success('Tarefa cadastrada com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao cadastrar tarefa.')

        elif acao_escolhida == 'Atualizar Estado de Tarefa':
            with st.form('form_atualizar_tarefa'):
                tarefas_df = all_data['tarefas']
                tarefa_id_up = st.selectbox(
                    'Selecione a Tarefa', 
                    options=tarefas_df['id'].tolist(), 
                    format_func=lambda x: f"[{x}] {tarefas_df.loc[tarefas_df['id']==x, 'descricao'].values[0][:50]}..."
                )
                novo_estado = st.selectbox('Novo Estado', ['nao_iniciada', 'em_andamento', 'concluida'])
                if st.form_submit_button('Atualizar Estado'):
                    if atualizar_estado_tarefa(config, tarefa_id_up, novo_estado):
                        st.success('Estado da tarefa atualizado com sucesso!')
                        load_db.clear()
                        st.rerun()
                    else:
                        st.error('Erro ao atualizar estado da tarefa.')

        elif acao_escolhida == 'Associar Tarefa a Sprint':
            with st.form('form_associar_sprint'):
                tarefas_df = all_data['tarefas']
                t_id = st.selectbox(
                    'Selecione a Tarefa', 
                    options=tarefas_df['id'].tolist(), 
                    format_func=lambda x: f"[{x}] {tarefas_df.loc[tarefas_df['id']==x, 'descricao'].values[0][:50]}..."
                )
                s_id = st.selectbox('Selecione a Sprint de Destino', options=all_data['sprints']['id'].tolist(), format_func=lambda x: f"Sprint ID: {x}")
                if st.form_submit_button('Vincular a Sprint'):
                    if associar_tarefa_a_sprint(config, t_id, s_id):
                        st.success('Tarefa associada à sprint com sucesso!')
                        load_db.clear()
                        st.rerun()
                    else:
                        st.error('Erro ao associar tarefa à sprint.')

        elif acao_escolhida == 'Vincular Projeto a Cliente':
            with st.form('form_vincular_demanda'):
                projetos_df = all_data['projetos']
                p_demanda = st.selectbox(
                    'Projeto', 
                    options=projetos_df['id'].tolist(), 
                    format_func=lambda x: f"{projetos_df.loc[projetos_df['id']==x, 'nome'].values[0]} (ID: {x})"
                )
                
                clientes_df = all_data['clientes']
                c_demanda = st.selectbox(
                    'Cliente', 
                    options=clientes_df['id'].tolist(), 
                    format_func=lambda x: f"{clientes_df.loc[clientes_df['id']==x, 'nome'].values[0]} (ID: {x})"
                )
                
                if st.form_submit_button('Criar Vínculo (Demanda)'):
                    if vincular_projeto_cliente(config, p_demanda, c_demanda):
                        st.success('Projeto vinculado ao cliente com sucesso!')
                        load_db.clear()
                        st.rerun()
                    else:
                        st.error('Erro ao vincular projeto e cliente (o vínculo já pode existir).')

    # --- ABA DE DELEÇÃO E DESVINCULAÇÃO ---
    with tab_delete:
        modo_delecao = st.selectbox(
            'Selecione a ação de remoção', 
            ['Excluir Registro de Tabela', 'Desvincular Projeto de Cliente (Tabela Demanda)']
        )

        if modo_delecao == 'Excluir Registro de Tabela':
            opcao_deletar = st.selectbox('Selecione a entidade para remover', ['Tarefa', 'Sprint', 'Membro', 'Cliente', 'Projeto', 'Empresa'])

            if opcao_deletar == 'Tarefa':
                with st.form('form_del_tarefa'):
                    tarefas_df = all_data['tarefas']
                    tarefa_del_id = st.selectbox(
                        'Selecione a Tarefa', 
                        options=tarefas_df['id'].tolist(), 
                        format_func=lambda x: f"[{x}] {tarefas_df.loc[tarefas_df['id']==x, 'descricao'].values[0][:50]}..."
                    )
                    if st.form_submit_button('Excluir Tarefa'):
                        if deletar_tarefa(config, tarefa_del_id):
                            st.warning('Tarefa removida com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao remover tarefa.')

            elif opcao_deletar == 'Sprint':
                with st.form('form_del_sprint'):
                    sprints_df = all_data['sprints']
                    sprint_del_id = st.selectbox(
                        'Selecione a Sprint', 
                        options=sprints_df['id'].tolist(), 
                        format_func=lambda x: f"Sprint ID {x} (Projeto ID: {sprints_df.loc[sprints_df['id']==x, 'id_projeto'].values[0]})"
                    )
                    if st.form_submit_button('Excluir Sprint'):
                        if deletar_sprint(config, sprint_del_id):
                            st.warning('Sprint removida com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao remover sprint.')

            elif opcao_deletar == 'Membro':
                with st.form('form_del_membro'):
                    membros_df = all_data['membros']
                    membro_del_id = st.selectbox(
                        'Selecione o Membro', 
                        options=membros_df['id'].tolist(), 
                        format_func=lambda x: f"{membros_df.loc[membros_df['id']==x, 'nome'].values[0]} ({membros_df.loc[membros_df['id']==x, 'cargo'].values[0]})"
                    )
                    if st.form_submit_button('Excluir Membro'):
                        if deletar_membro(config, membro_del_id):
                            st.warning('Membro removido com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao remover membro.')

            elif opcao_deletar == 'Cliente':
                with st.form('form_del_cliente'):
                    clientes_df = all_data['clientes']
                    cliente_del_id = st.selectbox(
                        'Selecione o Cliente', 
                        options=clientes_df['id'].tolist(), 
                        format_func=lambda x: f"{clientes_df.loc[clientes_df['id']==x, 'nome'].values[0]}"
                    )
                    if st.form_submit_button('Excluir Cliente'):
                        if deletar_cliente(config, cliente_del_id):
                            st.warning('Cliente removido com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao remover cliente.')

            elif opcao_deletar == 'Projeto':
                with st.form('form_del_projeto'):
                    projetos_df = all_data['projetos']
                    proj_del_id = st.selectbox(
                        'Selecione o Projeto', 
                        options=projetos_df['id'].tolist(), 
                        format_func=lambda x: f"{projetos_df.loc[projetos_df['id']==x, 'nome'].values[0]} (ID: {x})"
                    )
                    if st.form_submit_button('Excluir Projeto'):
                        if deletar_projeto(config, proj_del_id):
                            st.warning('Projeto removido com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao remover projeto.')

            elif opcao_deletar == 'Empresa':
                with st.form('form_del_empresa'):
                    empresas_df = all_data['empresas']
                    empresa_del_id = st.selectbox(
                        'Selecione a Empresa', 
                        options=empresas_df['id'].tolist(), 
                        format_func=lambda x: f"{empresas_df.loc[empresas_df['id']==x, 'nome'].values[0]} (Rep: {empresas_df.loc[empresas_df['id']==x, 'rep'].values[0]})"
                    )
                    if st.form_submit_button('Excluir Empresa'):
                        if deletar_empresa(config, empresa_del_id):
                            st.warning('Empresa removida com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao remover empresa. Verifique se existem registros vinculados.')

        elif modo_delecao == 'Desvincular Projeto de Cliente (Tabela Demanda)':
            with st.form('form_desvincular_demanda'):
                st.caption('Selecione um vínculo existente na tabela `demanda` para removê-lo:')
                if demands.empty:
                    st.info('Não há vínculos de demanda ativos no recorte atual.')
                else:
                    # Mapeia os IDs para nomes legíveis de Projeto e Cliente
                    projetos_df = all_data['projetos']
                    clientes_df = all_data['clientes']
                    
                    def formatar_demanda(r):
                        p_nome = projetos_df.loc[projetos_df['id'] == r.id_projeto, 'nome'].values
                        c_nome = clientes_df.loc[clientes_df['id'] == r.id_cliente, 'nome'].values
                        p_str = p_nome[0] if len(p_nome) > 0 else f"ID {r.id_projeto}"
                        c_str = c_nome[0] if len(c_nome) > 0 else f"ID {r.id_cliente}"
                        return f"Projeto: '{p_str}' ↔ Cliente: '{c_str}'"

                    demanda_opcoes = [formatar_demanda(r) for r in demands.itertuples()]
                    demanda_tuplas = [(r.id_projeto, r.id_cliente) for r in demands.itertuples()]
                    
                    escolha_idx = st.selectbox(
                        'Vínculo Projeto ↔ Cliente', 
                        options=range(len(demanda_opcoes)), 
                        format_func=lambda i: demanda_opcoes[i]
                    )
                    
                    if st.form_submit_button('Remover Vínculo'):
                        p_id_sel, c_id_sel = demanda_tuplas[escolha_idx]
                        
                        if desvincular_projeto_cliente(config, p_id_sel, c_id_sel):
                            st.warning('Vínculo removido com sucesso!')
                            load_db.clear()
                            st.rerun()
                        else:
                            st.error('Erro ao remover vínculo.')
st.divider()
st.caption(f"◆ EJFlow · Observatório de Projetos | MySQL: `{config['database']}` | painel interativo · © projeto acadêmico")