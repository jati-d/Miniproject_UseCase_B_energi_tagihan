
import streamlit as st
import pandas as pd
from core import ask_db

# =========================
# STREAMLIT UI
# =========================

st.title("Conversational Analytics")
st.caption("PLN HC Analytics")

# =========================
# SESSION STATE
# =========================
if "messages" not in st.session_state:
    st.session_state.messages = []

# =========================
# SHOW CHAT HISTORY
# =========================
for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        if msg["type"] == "text":
            st.write(msg["content"])

        elif msg["type"] == "table":
            st.dataframe(msg["content"], use_container_width=True)

# =========================
# USER INPUT
# =========================
question = st.chat_input("Tanyakan sesuatu tentang data...")

if question:

    # save user message
    st.session_state.messages.append({
        "role": "user",
        "type": "text",
        "content": question
    })

    with st.chat_message("user"):
        st.write(question)

    # assistant response
    with st.chat_message("assistant"):

        with st.spinner("Menganalisis data..."):

            result = ask_db(question)

            # =========================
            # IF RESULT IS DATAFRAME
            # =========================
            if isinstance(result, pd.DataFrame):

                st.dataframe(result, use_container_width=True)

                st.session_state.messages.append({
                    "role": "assistant",
                    "type": "table",
                    "content": result
                })

                # auto chart
                numeric_cols = result.select_dtypes(include="number").columns

                if len(numeric_cols) > 0:
                    st.bar_chart(result[numeric_cols])

            # =========================
            # TEXT / ERROR OUTPUT
            # =========================
            else:

                st.write(result)

                st.session_state.messages.append({
                    "role": "assistant",
                    "type": "text",
                    "content": str(result)
                })
