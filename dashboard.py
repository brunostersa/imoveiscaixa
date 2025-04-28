import streamlit as st
import pandas as pd
pd.set_option("styler.render.max_elements", 60000)
import plotly.express as px
import os
import firebase_admin
from firebase_admin import credentials, db
from filtros_sidebar import renderizar_filtros
from firebase_auth import exibir_login_cadastro
from session_utils import limpar_sessao, carregar_usuario

# Função que exibe o conteúdo principal do dashboard
def mostrar_dashboard():
    hide_streamlit_style = """
        <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    # === Session
    user_email = st.session_state.get("user_email") or carregar_usuario()
    if not user_email:
        st.switch_page("login.py")  # ou outro nome da sua tela de login



    # Inicializa Firebase se necessário
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate("leiloesdevproject-firebase-adminsdk-fbsvc-fb8c7e8d47.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://leiloesdevproject-default-rtdb.firebaseio.com/'
            }, name="leiloes_app")
        except Exception as e:
            st.error(f"Erro ao inicializar o Firebase: {e}")

    
    st.title("📊 Painel de Oportunidades - Imóveis Caixa")







    # === Funções utilitárias ===
    @st.cache_data(ttl=600)
    def carregar_dados(caminho):
        if not os.path.exists(caminho):
            st.error("Arquivo de dados não encontrado.")
            st.stop()
        df = pd.read_excel(caminho, sheet_name="Imóveis Caixa")
        df["Desconto"] = pd.to_numeric(df["Desconto"], errors="coerce")
        df["Preço Venda"] = pd.to_numeric(df["Preço Venda"], errors="coerce")
        df["Preço Avaliação"] = pd.to_numeric(df["Preço Avaliação"], errors="coerce")
        df["Lucro Potencial"] = df["Preço Avaliação"] - df["Preço Venda"]
        df["Modalidade"] = df["Modo Venda"].fillna("Outros")
        for col in df.columns:
            if "data" in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df.rename(columns={col: "Data Cadastro"}, inplace=True)
                    break
                except:
                    pass
        return df

    def calcular_score(df):
        agrupado = df.groupby(["Cidade", "Tipo"])["Preço Venda"].mean().reset_index()
        agrupado.rename(columns={"Preço Venda": "Preço Médio"}, inplace=True)
        df = df.merge(agrupado, on=["Cidade", "Tipo"], how="left")

        # Normalização para garantir valores de 0 a 100
        score_bruto = (
            ((df["Desconto"] / 100).fillna(0)) * 0.4 +
            ((df["Lucro Potencial"] / df["Preço Médio"]).fillna(0)) * 0.3 +
            ((1 - (df["Preço Venda"] / df["Preço Médio"])).fillna(0)) * 0.3
        )

        score_bruto = score_bruto.clip(lower=0)
        score_min, score_max = score_bruto.min(), score_bruto.max()
        df["Score"] = ((score_bruto - score_min) / (score_max - score_min) * 100).clip(0, 100).round(2)

        return df

    # === Carregamento de dados ===
    arquivo = "smart_leiloes_imoveis_caixa.xlsx"
    df = carregar_dados(arquivo)
    df = calcular_score(df)

    # === Filtros ===
    modalidades, estados, cidades, tipos, desconto_range, financiamento, lucro, score_minimo = renderizar_filtros(df)

    # === Aplicação dos filtros ===
    if modalidades:
        df = df[df["Modalidade"].isin(modalidades)]
    if estados:
        df = df[df["Estado"].isin(estados)]
    if cidades:
        df = df[df["Cidade"].isin(cidades)]
    if tipos:
        df = df[df["Tipo"].isin(tipos)]
    df = df[(df["Desconto"] >= desconto_range[0]) & (df["Desconto"] <= desconto_range[1])]
    if financiamento:
        df = df[df["Aceita Financiamento"].str.upper() == "SIM"]
    if lucro:
        df = df[df["Lucro Potencial"] > 0]
    df = df[df["Score"] >= score_minimo]

    # === KPIs ===
    st.subheader("📊 Indicadores")
    col1, col2, col3 = st.columns(3)
    col1.metric("🏠 Total de Imóveis", len(df))
    col2.metric("💲 Desconto Médio", f'{df["Desconto"].mean():.2f}%')
    financiaveis = df[df["Aceita Financiamento"].str.upper() == "SIM"]
    lucro_medio = financiaveis["Lucro Potencial"].sum() / len(financiaveis) if len(financiaveis) > 0 else 0
    col3.metric("💼 Lucro Médio (Financiáveis)", f'R$ {lucro_medio:,.2f}')

    # === Tabela Completa ===
    st.subheader("📋 Tabela Completa")
    df_fmt = df[["Cidade", "Tipo", "Modalidade", "Aceita Financiamento", "Desconto", "Preço Avaliação", "Preço Venda", "Lucro Potencial", "Score", "Site"]].copy()

    # Não formatar Score antes do Styler
    for col in ["Desconto", "Preço Avaliação", "Preço Venda", "Lucro Potencial"]:
        if "Desconto" in col:
            df_fmt[col] = df_fmt[col].map("{:.2f}%".format)
        else:
            df_fmt[col] = df_fmt[col].map("R$ {:,.2f}".format)

    # Coloração do Score com escala fixa 0–100 (verde = alto)
    styled_df = df_fmt.style.format({"Score": "{:.2f}"}).background_gradient(
        subset=["Score"], cmap="RdYlGn", vmin=0, vmax=100
    )
    st.dataframe(styled_df, use_container_width=True)

    # Exportar CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Exportar Resultados", csv, file_name="imoveis_filtrados.csv", mime="text/csv")


