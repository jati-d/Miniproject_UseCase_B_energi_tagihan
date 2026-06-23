

# =========================
# IMPORT
# =========================
import os
import re
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
from groq import Groq
import streamlit as st

# =========================
# DATABASE ENGINE (STREAMLIT SECRETS ONLY)
# =========================
POSTGRES_PASSWORD = st.secrets["POSTGRES_PASSWORD"]
POSTGRES_DB = st.secrets["POSTGRES_DB"]
POSTGRES_USER = st.secrets["POSTGRES_USER"]
POSTGRES_HOST = st.secrets.get("POSTGRES_HOST", "localhost")

engine = create_engine(
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:5432/{POSTGRES_DB}"
)

# test koneksi (optional)
with engine.connect() as conn:
    print(conn.execute(text("SELECT version();")).scalar())

# =========================
# GROQ SETUP
# =========================
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

client = Groq(api_key=GROQ_API_KEY)

# =========================
# LLM WRAPPER
# =========================
class GroqLLM:
    def __init__(self, client, model):
        self.client = client
        self.model = model

    def invoke(self, prompt):
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                max_tokens=1500,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return resp.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}")

# =========================
# MODEL INIT
# =========================
GROQ_MODEL = "llama-3.3-70b-versatile"
llm = GroqLLM(client, GROQ_MODEL)

# =========================
# SCHEMA (WAJIB ADA)
# =========================
SCHEMA_STR = """
Table: usage
- cust_id
- bulan (YYYY-MM)
- kwh
- tagihan
- status_bayar
"""

# =========================
# PROMPT BUILDER
# =========================
def build_prompt(question: str) -> str:
    return f"""
Anda adalah SQL expert PostgreSQL.

Gunakan skema berikut:

{SCHEMA_STR}

ATURAN KETAT:
- hanya gunakan tabel & kolom di schema
- tidak boleh mengarang kolom
- hanya SELECT atau WITH
- hanya 1 query
- tanpa penjelasan
- tanpa markdown

PERTANYAAN:
{question}

SQL:
"""

# =========================
# AMBIL SQL
# =========================
def ambil_sql(resp):
    teks = str(resp)

    # hapus markdown
    teks = re.sub(r"```sql|```", "", teks, flags=re.I)

    # ambil SELECT/WITH sampai akhir
    match = re.search(r"(select|with)[\s\S]*", teks, re.I)

    if not match:
        raise ValueError("SQL tidak ditemukan")

    return match.group(0).strip().rstrip(";")

# =========================
# VALIDASI SQL
# =========================
def validate_sql(sql: str) -> bool:
    sql_lower = sql.lower()

    if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
        return False

    forbidden = [
        "drop", "delete", "update", "insert",
        "alter", "truncate", "create"
    ]

    if any(word in sql_lower for word in forbidden):
        return False

    # anti multi statement
    if ";" in sql.strip().rstrip(";"):
        return False

    return True

# =========================
# FORMAT OUTPUT
# =========================
def pilih_format(question, df=None):
    q = question.lower()

    if any(k in q for k in ["chart", "grafik", "visual"]):
        return "chart"

    if any(k in q for k in ["json", "api"]):
        return "json"

    if any(k in q for k in ["insight", "analisis", "kenapa"]):
        return "narasi"

    return "tabel"

# =========================
# VISUALISASI (STREAMLIT FRIENDLY)
# =========================
def render_chart(df):
    num_cols = df.select_dtypes(include="number").columns

    if len(num_cols) == 0:
        return df

    x = df.columns[0]
    y = num_cols[0]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df[x].astype(str), df[y])
    ax.set_title(f"{y} by {x}")
    plt.xticks(rotation=45)

    return fig

# =========================
# MAIN FUNCTION
# =========================
def ask_db(question):
    try:
        # 1. prompt → LLM
        prompt = build_prompt(question)
        resp = llm.invoke(prompt)

        # 2. ambil SQL
        sql = ambil_sql(resp)

        # 3. validasi
        if not validate_sql(sql):
            raise ValueError(f"SQL tidak aman:\n{sql}")

        # 4. execute
        df = pd.read_sql(sql, engine)

        # 5. format output
        mode = pilih_format(question, df)

        if mode == "json":
            return df.to_dict(orient="records")

        elif mode == "chart":
            return render_chart(df)

        elif mode == "narasi":
            insight_prompt = f"""
Pertanyaan:
{question}

Data:
{df.head(20).to_markdown(index=False)}

Berikan insight singkat.
"""
            return llm.invoke(insight_prompt)

        return df

    except Exception as e:
        return {"error": str(e)}
