import streamlit as st
from guardrails_logic import MedAssistGuardrails
from workflow import MedAssistWorkflow
from logger_metrics import SecurityLogger
from llm_service import LLMService

# Configuração da Página
st.set_page_config(page_title="MedAssist Guardrail MVP", layout="wide")


class MedAssistApp:
    def __init__(self):
        self.workflow = MedAssistWorkflow()
        try:
            self.llm = LLMService()
        except Exception as e:
            st.error(f"Erro ao inicializar serviço de IA: {e}")
            self.llm = None

    def render_sidebar(self):
        st.sidebar.title("🛡️ Painel de Controle")
        metrics = SecurityLogger.get_metrics()
        st.sidebar.metric("Bloqueios de Segurança", metrics["Bloqueios"])
        st.sidebar.metric("Intervenções HITL", metrics["Aprovações HITL"])

        if st.sidebar.button("Limpar Logs"):
            import os
            if os.path.exists("security_logs.csv"):
                os.remove("security_logs.csv")
            st.sidebar.success("Logs limpos!")
            st.rerun()

    def handle_chat(self, prompt):
        # 1. Input Guardrail
        is_safe, input_result = MedAssistGuardrails.validate_input(prompt)
        if not is_safe:
            SecurityLogger.log_event(
                "Input Guardrail", "Detecção de PII ou linguagem inadequada", "blocked")
            return input_result

        # 2. Workflow & HITL Check
        result = self.workflow.run(prompt)

        if result['status'] == "pending_approval":
            st.session_state.hitl_pending = True
            st.session_state.pending_prompt = prompt
            return None

        return self.get_ai_response(prompt)

    def get_ai_response(self, prompt):
        if not self.llm:
            return "Serviço de IA indisponível. Verifique a chave de API no arquivo .env."

        # Chamada real ao LLM
        ai_response = self.llm.get_response(prompt)

        # 3. Output Guardrail
        is_safe, output_result = MedAssistGuardrails.validate_output(
            ai_response)
        if not is_safe:
            SecurityLogger.log_event(
                "Output Guardrail", "Tentativa de diagnóstico direto pela IA", "blocked", ai_response=ai_response)
            return output_result

        return ai_response

    def run(self):
        st.title("🏥 MedAssist Guardrail")
        st.markdown("---")

        self.render_sidebar()

        # Chat
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "hitl_pending" not in st.session_state:
            st.session_state.hitl_pending = False
        if "pending_prompt" not in st.session_state:
            st.session_state.pending_prompt = ""

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Interface HITL ou Input Normal
        if st.session_state.hitl_pending:
            st.warning("⚠️ CASO DE ALTO RISCO DETECTADO. Aguardando aprovação humana...")
            st.info(f"Mensagem retida: '{st.session_state.pending_prompt}'")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Aprovar Envio para IA"):
                    SecurityLogger.log_event(
                        "HITL", "Emergência aprovada pelo operador", "hitl_approved")
                    st.session_state.hitl_pending = False
                    with st.spinner("Processando..."):
                        response = self.get_ai_response(
                            st.session_state.pending_prompt)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response})
                    st.session_state.pending_prompt = ""
                    st.rerun()
            with col2:
                if st.button("Bloquear e Encaminhar"):
                    SecurityLogger.log_event(
                        "HITL", "Emergência bloqueada/encaminhada", "blocked")
                    st.session_state.hitl_pending = False
                    response = "Encaminhando você para o atendimento humano imediato. Por favor, ligue para o 192."
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response})
                    st.session_state.pending_prompt = ""
                    st.rerun()
        else:
            if prompt := st.chat_input("Descreva seus sintomas..."):
                st.session_state.messages.append(
                    {"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    response = self.handle_chat(prompt)
                    if response is not None:
                        st.markdown(response)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response})
                    else:
                        st.rerun()

        # Exibição de Logs
        st.markdown("---")
        st.subheader("📋 Logs de Segurança em Tempo Real")
        st.dataframe(SecurityLogger.get_logs(), use_container_width=True)


if __name__ == "__main__":
    app = MedAssistApp()
    app.run()
