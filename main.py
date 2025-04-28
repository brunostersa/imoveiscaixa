import streamlit as st
from firebase_auth import exibir_login_cadastro
from session_utils import carregar_usuario, limpar_sessao
import dashboard

st.set_page_config(page_title="Imóveis Caixa", layout="wide")

# VERIFICA LOGIN
user = st.session_state.get("user_email") or carregar_usuario()

if not user or not st.session_state.get("logged_in"):
    exibir_login_cadastro()
    st.stop()

# INTERFACE
st.markdown(f"👋 Bem-vindo, **{user}**")
if st.button("Sair"):
    limpar_sessao()
    st.session_state.clear()
    st.rerun()

# DASHBOARD
dashboard.mostrar_dashboard()
