import streamlit as st
from lib.rag import RAGRetriever
from lib.enhanced_usage_logger import log_enhanced_usage
from lib.chatgeneration import generate_chat_completion
from lib.ui import apply_theme_css, render_topbar_auth_links

st.set_page_config(page_title="RAG — Chat", layout="wide")

# Apply shared theme and render topbar auth links (login/logout)
apply_theme_css()
render_topbar_auth_links()

# Track current page for logging/session behavior
st.session_state.cur_page = 'rag_chat'


@st.cache_resource
def get_retriever():
    return RAGRetriever()


def _init_state():
    if 'chat' not in st.session_state:
        st.session_state.chat = []


_init_state()

retriever = get_retriever()

st.sidebar.title("RAG Demo")
st.sidebar.write("This demo queries the local vector index and shows results in a chat layout.")
st.sidebar.write("Index: data/vector_index")

st.title("RAG Chat")


def render_chat():
    for msg in st.session_state.chat:
        role = msg.get('role')
        text = msg.get('text')
        if role == 'user':
            st.markdown(f"**You:** {text}")
        else:
            st.markdown(f"**Assistant:** {text}")


with st.form('input_form', clear_on_submit=True):
    user_input = st.text_input('Message', placeholder='Ask about the documents...')
    send = st.form_submit_button('Send')

if send:
    if not user_input:
        st.info('Please enter a message.')
    else:
        # append user message
        st.session_state.chat.append({'role': 'user', 'text': user_input})
        try:
            with st.spinner('Retrieving relevant documents...'):
                # fixed top-k (no user control)
                results = retriever.retrieve(user_input, k=3)

            if not results:
                assistant_text = 'I could not find relevant documents.'
            else:
                # Build context from retrieved snippets
                snippets = [r.get('text', '').strip() for r in results]
                context_text = "\n\n---\n\n".join(snippets)

                # Prepare messages for LLM: system instructs use of provided sources
                system_msg = {
                    'role': 'system',
                    'content': (
                        'You are a helpful assistant. Use the provided SOURCE texts to answer the user. '
                        'If the answer is not contained in the sources, say your source is not up-to-date for curent questions, but still generates the answer'
                        'Cite the sources in your answer as Source 1, Source 2, etc.'
                    )
                }
                sources_msg = {'role': 'system', 'content': f"SOURCES:\n\n{context_text}"}
                user_msg = {'role': 'user', 'content': user_input}

                # Call the local Ollama model via the centralized generator helper
                try:
                    llm_model = 'llama3.2:3b'
                    llm_response, in_toks, out_toks = generate_chat_completion(
                        model=llm_model,
                        messages=[system_msg, sources_msg, user_msg],
                        temp=0.0,
                        max_num_tokens=512
                    )
                    assistant_text = llm_response
                except Exception:
                    # Fallback: show raw snippets
                    parts = []
                    for i, s in enumerate(snippets, start=1):
                        parts.append(f"Source {i}: {s}")
                    assistant_text = "\n\n".join(parts)

            st.session_state.chat.append({'role': 'assistant', 'text': assistant_text})

            # Log the interaction (privacy-limited previews are handled in logger)
            try:
                log_enhanced_usage(
                    page="rag_chat",
                    model_used="local_rag",
                    prompt=user_input,
                    response=assistant_text,
                    input_tokens=None,
                    output_tokens=None,
                    additional_metadata={"retrieval_mode": getattr(retriever, '_mode', None)}
                )
            except Exception:
                # Don't let logging failures break the UI
                pass

        except Exception as e:
            err_text = f'Error during retrieval: {e}'
            st.session_state.chat.append({'role': 'assistant', 'text': err_text})
            try:
                log_enhanced_usage(
                    page="rag_chat",
                    model_used="local_rag",
                    prompt=user_input,
                    response=err_text,
                    additional_metadata={"retrieval_mode": getattr(retriever, '_mode', None), "error": str(e)}
                )
            except Exception:
                pass

render_chat()

