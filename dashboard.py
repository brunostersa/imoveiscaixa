
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

st.set_page_config(page_title="Imóveis Caixa", layout="wide")
st.title("📊 Painel de Oportunidades - Imóveis Caixa")

@st.cache_data
def carregar_dados(caminho):
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
    df["Score"] = (
        (df["Desconto"] / 100) * 40 +
        (df["Lucro Potencial"] / df["Preço Médio"]) * 30 +
        (1 - (df["Preço Venda"] / df["Preço Médio"])) * 30
    ).clip(lower=0, upper=100)
    def classificar(score):
        if score > 75:
            return "🟢 Excelente"
        elif score > 50:
            return "🟡 Médio"
        else:
            return "🔴 Ruim"
    df["Classificação"] = df["Score"].apply(classificar)
    return df

def carregar_perfis():
    if os.path.exists("filtros_perfis.json"):
        with open("filtros_perfis.json", "r") as f:
            return json.load(f)
    return {}

def salvar_perfil(nome, dados):
    perfis = carregar_perfis()
    perfis[nome] = dados
    with open("filtros_perfis.json", "w") as f:
        json.dump(perfis, f)

def excluir_perfil(nome):
    perfis = carregar_perfis()
    if nome in perfis:
        del perfis[nome]
        with open("filtros_perfis.json", "w") as f:
            json.dump(perfis, f)

arquivo = "smart_leiloes_imoveis_caixa.xlsx"
df = carregar_dados(arquivo)
df = calcular_score(df)

# === Sidebar
with st.sidebar:
    st.header("🔍 Filtros")

    if st.button("🧹 Limpar Filtros"):
        st.session_state.clear()
        st.cache_data.clear()
        st.experimental_rerun()

    # Carregar perfis
    perfis = carregar_perfis()
    nomes_perfis = list(perfis.keys())
    perfil_escolhido = st.selectbox("🎯 Carregar Perfil", [""] + nomes_perfis)
    if perfil_escolhido:
        filtros = perfis[perfil_escolhido]
    else:
        filtros = {}

    # Filtros com fallback por sessão
    modalidades = st.multiselect("Modalidade de Venda", sorted(df["Modalidade"].dropna().unique()),
                                 default=filtros.get("modalidades", []))
    if modalidades:
        df = df[df["Modalidade"].isin(modalidades)]

    estados = st.multiselect("Estado", sorted(df["Estado"].dropna().unique()),
                             default=filtros.get("estados", []))
    if estados:
        df = df[df["Estado"].isin(estados)]

    cidades = st.multiselect("Cidade", sorted(df["Cidade"].dropna().unique()),
                             default=filtros.get("cidades", []))
    if cidades:
        df = df[df["Cidade"].isin(cidades)]

    tipos = st.multiselect("Tipo de Imóvel", sorted(df["Tipo"].dropna().unique()),
                           default=filtros.get("tipos", []))
    if tipos:
        df = df[df["Tipo"].isin(tipos)]

    min_d, max_d = st.slider("Intervalo de Desconto (%)",
                             float(df["Desconto"].min()), float(df["Desconto"].max()),
                             (filtros.get("desconto_min", float(df["Desconto"].min())),
                              filtros.get("desconto_max", float(df["Desconto"].max()))))
    df = df[(df["Desconto"] >= min_d) & (df["Desconto"] <= max_d)]

    financiamento = st.checkbox("Apenas imóveis que aceitam financiamento", value=filtros.get("financiamento", False))
    lucro = st.checkbox("Apenas imóveis com decréscimo no preço", value=filtros.get("lucro", False))

    if financiamento:
        df = df[df["Aceita Financiamento"].str.upper() == "SIM"]
    if lucro:
        df = df[df["Lucro Potencial"] > 0]

    st.markdown("---")
    with st.form("salvar_perfil_form"):
        nome_perfil = st.text_input("💾 Nome do novo perfil")
        salvar = st.form_submit_button("Salvar Perfil")
        if salvar and nome_perfil:
            salvar_perfil(nome_perfil, {
                "modalidades": modalidades,
                "estados": estados,
                "cidades": cidades,
                "tipos": tipos,
                "desconto_min": min_d,
                "desconto_max": max_d,
                "financiamento": financiamento,
                "lucro": lucro
            })
            st.success("Perfil salvo com sucesso!")

    if perfil_escolhido:
        if st.button("🗑 Excluir Perfil Selecionado"):
            excluir_perfil(perfil_escolhido)
            st.experimental_rerun()

# === KPIs
col1, col2, col3 = st.columns(3)
col1.metric("🏠 Imóveis", len(df))
col2.metric("💲 Desconto Médio", f'{df["Desconto"].mean():.2f}%')
financiaveis = df[df["Aceita Financiamento"].str.upper() == "SIM"]
lucro_medio_fina = financiaveis["Lucro Potencial"].sum() / len(financiaveis) if len(financiaveis) > 0 else 0
col3.metric("💼 Lucro Médio (Financiáveis)", f'R$ {lucro_medio_fina:,.2f}')

# === Score
st.subheader("🧠 Score Visual por Classificação")
score_dist = df["Classificação"].value_counts().reset_index()
score_dist.columns = ["Classificação", "Qtd"]
fig_score = px.bar(score_dist, x="Classificação", y="Qtd", color="Classificação", color_discrete_map={
    "🟢 Excelente": "green",
    "🟡 Médio": "orange",
    "🔴 Ruim": "red"
})
st.plotly_chart(fig_score, use_container_width=True)

# === Evolução
if "Data Cadastro" in df.columns:
    st.subheader("📆 Evolução de imóveis por data")
    df_time = df.dropna(subset=["Data Cadastro"])
    df_time = df_time.groupby(df_time["Data Cadastro"].dt.to_period("M")).size().reset_index(name="Qtd")
    df_time["Data Cadastro"] = df_time["Data Cadastro"].dt.to_timestamp()
    fig_evo = px.line(df_time, x="Data Cadastro", y="Qtd", title="Imóveis cadastrados por mês")
    st.plotly_chart(fig_evo, use_container_width=True)

# === Tabelas
st.subheader("🚀 Top 10 Descontos")
top10 = df.sort_values("Desconto", ascending=False).head(10)
top10["Ver Imóvel"] = top10["Site"].apply(lambda url: f"{url}" if pd.notna(url) else "")
top10_fmt = top10[["Cidade", "Tipo", "Desconto", "Lucro Potencial", "Classificação", "Ver Imóvel"]].copy()
top10_fmt["Desconto"] = top10_fmt["Desconto"].map("{:.2f}%".format)
top10_fmt["Lucro Potencial"] = top10_fmt["Lucro Potencial"].map("R$ {:,.2f}".format)
st.dataframe(top10_fmt, use_container_width=True)

st.subheader("📋 Tabela Completa")
df_fmt = df[["Cidade", "Tipo", "Modalidade", "Aceita Financiamento", "Desconto", "Preço Avaliação", "Preço Venda", "Lucro Potencial", "Classificação", "Site"]].copy()
df_fmt["Desconto"] = df_fmt["Desconto"].map("{:.2f}%".format)
df_fmt["Preço Avaliação"] = df_fmt["Preço Avaliação"].map("R$ {:,.2f}".format)
df_fmt["Preço Venda"] = df_fmt["Preço Venda"].map("R$ {:,.2f}".format)
df_fmt["Lucro Potencial"] = df_fmt["Lucro Potencial"].map("R$ {:,.2f}".format)
st.dataframe(df_fmt, use_container_width=True)
