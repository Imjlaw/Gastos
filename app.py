# app_gastos_sincronizado.py
import streamlit as st
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore_v1

# Configuração do Firebase
if not firebase_admin._apps:
    firebase_config = {
        "type": st.secrets["FIREBASE"]["TYPE"],
        "project_id": st.secrets["FIREBASE"]["PROJECT_ID"],
        "private_key_id": st.secrets["FIREBASE"]["PRIVATE_KEY_ID"],
        "private_key": st.secrets["FIREBASE"]["PRIVATE_KEY"].replace('\\n', '\n'),
        "client_email": st.secrets["FIREBASE"]["CLIENT_EMAIL"],
        "client_id": st.secrets["FIREBASE"]["CLIENT_ID"],
        "auth_uri": st.secrets["FIREBASE"]["AUTH_URI"],
        "token_uri": st.secrets["FIREBASE"]["TOKEN_URI"],
        "auth_provider_x509_cert_url": st.secrets["FIREBASE"]["AUTH_PROVIDER_X509_CERT_URL"],
        "client_x509_cert_url": st.secrets["FIREBASE"]["CLIENT_X509_CERT_URL"]
    }
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- Configuração de Sessão ---
if 'usuario_id' not in st.session_state:
    st.session_state.usuario_id = None
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- Estilos ---
st.set_page_config(
    page_title="Controle Financeiro Sincronizado",
    layout="centered",
    page_icon="💰",
    initial_sidebar_state="expanded"
)

# Cores para categorias
CATEGORIA_CORES = {
    "Comida": "#FF9AA2",
    "Conta": "#FFB7B2",
    "Assinatura": "#FFDAC1",
    "Móveis": "#E2F0CB",
    "Transporte": "#B5EAD7",
    "Outros": "#C7CEEA"
}

# --- Funções Firebase ---
@st.cache_data(ttl=300)
def carregar_gastos(usuario_id):
    gastos_ref = db.collection('usuarios').document(usuario_id).collection('gastos')
    docs = gastos_ref.order_by('data', direction=firestore_v1.Query.DESCENDING).stream()
    return pd.DataFrame([doc.to_dict() for doc in docs]) if docs else pd.DataFrame(columns=["data", "categoria", "valor", "descricao", "mes"])

def adicionar_gasto(usuario_id, gasto):
    db.collection('usuarios').document(usuario_id).collection('gastos').add(gasto)
    st.cache_data.clear()

def carregar_saldos(usuario_id):
    doc_ref = db.collection('usuarios').document(usuario_id).collection('config').document('saldos')
    doc = doc_ref.get()
    return doc.to_dict() or {}

def salvar_saldos(usuario_id, saldos):
    db.collection('usuarios').document(usuario_id).collection('config').document('saldos').set(saldos)
    st.cache_data.clear()

def carregar_emprestimos(usuario_id):
    docs = db.collection('usuarios').document(usuario_id).collection('emprestimos').stream()
    emprestimos = []
    for doc in docs:
        emp = doc.to_dict()
        emp['id'] = doc.id
        emprestimos.append(emp)
    return pd.DataFrame(emprestimos) if emprestimos else pd.DataFrame(columns=["data", "pessoa", "valor", "descricao", "pago", "mes"])

def adicionar_emprestimo(usuario_id, emprestimo):
    db.collection('usuarios').document(usuario_id).collection('emprestimos').add(emprestimo)
    st.cache_data.clear()

def atualizar_emprestimo(usuario_id, emp_id):
    emp_ref = db.collection('usuarios').document(usuario_id).collection('emprestimos').document(emp_id)
    emp_ref.update({'pago': True})
    st.cache_data.clear()

# --- Autenticação Persistente ---
def autenticar():
    st.sidebar.title("🔐 Gerenciar Conta")
    
    if st.session_state.autenticado:
        if st.sidebar.button("🚪 Sair", type="primary"):
            st.session_state.autenticado = False
            st.session_state.usuario_id = None
            st.rerun()
        return st.session_state.usuario_id
    
    with st.sidebar.form("login_form"):
        email = st.text_input("Email", placeholder="seu@email.com")
        senha = st.text_input("Senha", type="password")
        
        if st.form_submit_button("👉 Entrar", use_container_width=True):
            if email and senha:
                st.session_state.usuario_id = email.replace("@", "_").replace(".", "_")
                st.session_state.autenticado = True
                st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.info("✨ Use qualquer email/senha para criar uma conta")
    return None

# --- Aplicação Principal ---
usuario_id = autenticar()

if not st.session_state.autenticado:
    st.warning("Por favor, faça login para acessar o sistema")
    st.stop()

# --- Data atual ---
hoje = datetime.now()
mes_atual = hoje.strftime("%Y-%m")

# --- Carregar Dados ---
with st.spinner("Carregando seus dados..."):
    saldos = carregar_saldos(usuario_id)
    emprestimos_df = carregar_emprestimos(usuario_id)
    df_todos = carregar_gastos(usuario_id)
    df_mes = df_todos[df_todos['mes'] == mes_atual] if not df_todos.empty else pd.DataFrame(columns=["data", "categoria", "valor", "descricao", "mes"])

# --- Cálculos Financeiros ---
total_saldos = sum(float(v) for v in saldos.values())
total_gastos = df_todos["valor"].sum() if not df_todos.empty else 0.0
emprestimos_pendentes = emprestimos_df[~emprestimos_df["pago"]]["valor"].sum() if not emprestimos_df.empty else 0.0
saldo_disponivel = total_saldos - total_gastos - emprestimos_pendentes
total_gastos_mes = df_mes["valor"].sum() if not df_mes.empty else 0.0

# --- Interface ---
st.title(f"💰 Controle Financeiro")
st.caption(f"Bem-vindo, {st.session_state.usuario_id.replace('_', '@', 1).rsplit('_', 1)[0]}")

# --- Dashboard Resumo ---
col1, col2, col3 = st.columns(3)
col1.metric("Saldo Total", f"R$ {saldo_disponivel:,.2f}", 
           delta=f"R$ {total_saldos:,.2f} disponíveis")
col2.metric("Gastos Mensais", f"R$ {total_gastos_mes:,.2f}", 
           delta=f"-R$ {total_gastos:,.2f} histórico", delta_color="inverse")
col3.metric("Empréstimos", f"R$ {emprestimos_pendentes:,.2f}", 
           "pendentes" if emprestimos_pendentes > 0 else "quitados")

# --- Seção de Saldo ---
with st.expander("💳 Gerenciar Saldos Mensais", expanded=False):
    cols = st.columns(3)
    with cols[0]:
        mes_selecionado = st.selectbox("Mês", list(saldos.keys()) + [mes_atual], index=len(saldos))
    with cols[1]:
        valor_atual = saldos.get(mes_selecionado, 0.0)
        novo_saldo = st.number_input("Valor (R$)", value=float(valor_atual), step=100.0, format="%.2f")
    with cols[2]:
        st.write("⠀")
        if st.button("💾 Salvar", key="salvar_saldo"):
            saldos[mes_selecionado] = novo_saldo
            salvar_saldos(usuario_id, saldos)
            st.success(f"Saldo de {mes_selecionado} atualizado!")

# --- Seção de Gastos ---
st.subheader("📝 Novo Gasto")
with st.form("novo_gasto", clear_on_submit=True, border=True):
    cols = st.columns([1, 1, 2, 3])
    with cols[0]:
        data = st.date_input("Data", value=hoje, key="gasto_data")
    with cols[1]:
        valor = st.number_input("Valor", min_value=0.01, step=50.0, format="%.2f")
    with cols[2]:
        categoria = st.selectbox("Categoria", list(CATEGORIA_CORES.keys()), key="gasto_cat")
    with cols[3]:
        descricao = st.text_input("Descrição", placeholder="O que foi comprado?", key="gasto_desc")
    
    if st.form_submit_button("➕ Adicionar Gasto", use_container_width=True):
        novo_gasto = {
            "data": data.strftime("%d/%m/%Y"),
            "categoria": categoria,
            "valor": float(valor),
            "descricao": descricao,
            "mes": mes_atual
        }
        adicionar_gasto(usuario_id, novo_gasto)
        st.toast("✅ Gasto registrado com sucesso!")

# --- Seção de Empréstimos ---
tab_emp1, tab_emp2 = st.tabs(["📌 Novo Empréstimo", "✅ Quitar Empréstimos"])

with tab_emp1:
    with st.form("novo_emprestimo", clear_on_submit=True, border=True):
        cols = st.columns([1, 2, 1, 2])
        with cols[0]:
            data_emp = st.date_input("Data", value=hoje, key="emp_data")
        with cols[1]:
            pessoa = st.text_input("Para quem?", key="emp_pessoa")
        with cols[2]:
            valor_emp = st.number_input("Valor", min_value=0.01, step=100.0, format="%.2f", key="emp_valor")
        with cols[3]:
            desc_emp = st.text_input("Descrição", key="emp_desc")
        
        if st.form_submit_button("📌 Registrar Empréstimo", use_container_width=True):
            novo_emp = {
                "data": data_emp.strftime("%d/%m/%Y"),
                "pessoa": pessoa,
                "valor": float(valor_emp),
                "descricao": desc_emp,
                "pago": False,
                "mes": mes_atual
            }
            adicionar_emprestimo(usuario_id, novo_emp)
            st.toast("✅ Empréstimo registrado!")

with tab_emp2:
    if not emprestimos_df.empty:
        emprestimos_pendentes = emprestimos_df[~emprestimos_df["pago"]]
        
        if not emprestimos_pendentes.empty:
            for _, emp in emprestimos_pendentes.iterrows():
                with st.container(border=True):
                    cols = st.columns([3, 2, 1])
                    cols[0].markdown(
                        f"**{emp['pessoa']}**  \n"
                        f"_{emp['descricao']}_  \n"
                        f"📅 {emp['data']}"
                    )
                    cols[1].markdown(f"**R$ {emp['valor']:,.2f}**")
                    if cols[2].button("Quitar", key=f"quitar_{emp['id']}"):
                        atualizar_emprestimo(usuario_id, emp['id'])
                        st.rerun()
        else:
            st.success("🎉 Todos os empréstimos estão quitados!")
    else:
        st.info("Nenhum empréstimo pendente encontrado.")

# --- Análise de Dados ---
st.subheader("📊 Análise Financeira")
tab_anal1, tab_anal2, tab_anal3 = st.tabs(["📅 Histórico", "🍕 Categorias", "📈 Evolução"])

with tab_anal1:
    st.dataframe(
        df_todos[["data", "categoria", "valor", "descricao"]],
        column_config={
            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")
        },
        hide_index=True,
        use_container_width=True,
        height=400
    )

with tab_anal2:
    if not df_todos.empty:
        df_categorias = df_todos.groupby("categoria")["valor"].sum().reset_index()
        df_categorias = df_categorias.sort_values("valor", ascending=False)
        
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        ax1.pie(
            df_categorias["valor"],
            labels=df_categorias["categoria"],
            colors=[CATEGORIA_CORES.get(cat, "#DDDDDD") for cat in df_categorias["categoria"]],
            autopct='%1.1f%%',
            startangle=90
        )
        ax1.set_title("Distribuição por Categoria")
        st.pyplot(fig1)
    else:
        st.warning("Nenhum dado para análise")

with tab_anal3:
    if not df_todos.empty:
        df_mensal = df_todos.copy()
        df_mensal["mes_ano"] = pd.to_datetime(df_mensal["data"], dayfirst=True).dt.to_period("M").astype(str)
        df_evolucao = df_mensal.groupby("mes_ano")["valor"].sum().reset_index()
        
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        ax2.plot(
            df_evolucao["mes_ano"],
            df_evolucao["valor"],
            marker="o",
            linestyle="-",
            color="#4CAF50"
        )
        ax2.set_title("Evolução Mensal de Gastos")
        ax2.set_ylabel("Valor (R$)")
        plt.xticks(rotation=45)
        st.pyplot(fig2)
    else:
        st.warning("Nenhum dado para análise")

# --- Rodapé ---
st.markdown("---")
st.caption("🔗 Acesse de qualquer dispositivo - seus dados estão sempre sincronizados")
st.caption("🔄 Atualização automática - não precisa recarregar a página")
