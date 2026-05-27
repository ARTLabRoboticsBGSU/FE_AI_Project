

# About this code:
# ----------------
# This code performs the following tasks:
  # 1. It creates a Streamlit app that allows users to interact with an LLM of their choosing to generate responses to their queries:  
  #   - The app allows users to select from a list of LLMs and input their queries.
  #   - The LLMs can be changed within a session. 
  #   - The app displays the conversation between the user and the LLM.
  #   - The app allows users to export the conversation to a PDF.
  # 2. Students can intereact with the app, without having to create API keys for each LLM.
  # 3. The app is designed to be used for educational purposes only.
# -----------------------------------------------------------------------------


# Import required libraries:
# --------------------------
import os # Standard Library
import sys
import traceback
from datetime import datetime

# small helper to emit debug to stderr and a log file
def _rag_debug(msg: str, exc: Exception | None = None):
  ts = datetime.utcnow().isoformat() + 'Z'
  line = f"{ts} {msg}"
  try:
    # stderr (visible in most Streamlit server logs)
    print(line, file=sys.stderr)
    if exc is not None:
      traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
    # also append to a persistent log for offline inspection
    os.makedirs('logs', exist_ok=True)
    with open(os.path.join('logs', 'rag_debug.log'), 'a', encoding='utf-8') as fh:
      fh.write(line + "\n")
      if exc is not None:
        fh.write(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
  except Exception:
    # best-effort only
    pass

# Our Own Modules
from lib import chatpdf, chatgeneration, sidebar

# Third-Party Libraries
from dotenv import load_dotenv
import streamlit as st


# -----------------------------------------------------------------------------


# Import models from config
from config import MODELS, get_page_models, get_default_model_for_page, PAGE_ICON

# Enforce no-external-HTTP policy by importing runtime guard early.
try:
  from lib import disable_http  # noqa: F401
except Exception:
  pass

# Get all models for coding companion dynamically from config
# This automatically updates when models are added/removed/renamed in config.py
models = get_page_models("coding_companion")
# Ensure a model_choice exists in session state (required by chat generation code)
if "model_choice" not in st.session_state:
  try:
    st.session_state.model_choice = get_default_model_for_page("coding_companion")
  except Exception:
    st.session_state.model_choice = models[0] if models else None
# -----------------------------------------------------------------------------


# Load Environment Variables:
# ---------------------------
load_dotenv()

openai_api_key = os.getenv('OPENAI_API_KEY')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
cohere_api_key = os.getenv('COHERE_API_KEY')
groq_api_key = os.getenv('GROQ_API_KEY')
# -----------------------------------------------------------------------------


# Constant Values:
# ----------------
TEMPERATURE = 0


SYSTEM_PROMPT = """
You are an upbeat, encouraging tutor who helps undergraduate students learn by guiding them to build their own solutions rather than providing final answers. Start by introducing yourself as their FE-AI Assistant and explain that you'll provide short, step-by-step scaffolding: leading questions, small subtasks, and targeted hints so the student can derive the final answer themselves.

Only ask one question at a time. First ask about the subject title and topic the student wants to learn. Wait for their response. After the student replies, break the problem into small steps and present one step or hint at a time. Avoid giving full end-to-end answers unless the student explicitly asks for a final solution after demonstrating their attempt. Use questions and minimal examples to check understanding before moving to the next step.

When you provide examples or code, tailor them to the student's course and level. When appropriate include short R (tidyverse-style) or Python (pandas-style) snippets to illustrate concepts, but keep code minimal and focused on the current teaching step.

When you show R code, use:
  (a) library_name::function_name() syntax (do NOT use library()); when helpful, instruct how to install packages with `if(require(pkg)==FALSE) install.packages(pkg)`.
  (b) use the native pipe `|>` as the pipe operator.

For Python examples, break chained methods into multiple lines using parentheses for readability.
"""
# Return a course-specific system prompt
def course_system_prompt(course: str) -> str:
  course = (course or '').upper()
  if course == 'ROBO':
    return SYSTEM_PROMPT + (
      "\nYou are also specialized in Robotics (ROBO). "
      "Help undergraduate students understand robotics concepts by asking guiding questions, giving short hints, and providing minimal code or pseudo-code only to illustrate the current step (e.g., control loops, sensor processing)."
    )
  elif course == 'ECE':
    return SYSTEM_PROMPT + (
      "\nYou are also specialized in Electronics and Communications (ECE). "
      "Help undergraduate students understand ECE concepts by asking guiding questions, giving short hints, and providing minimal diagrams, truth tables, or code snippets only to illustrate the current step."
    )
  else:
    return SYSTEM_PROMPT
# -----------------------------------------------------------------------------

# Initialize RAG retriever if available (lazy, optional)
try:
  from lib.rag import RAGRetriever
  if "rag_retriever" not in st.session_state:
    # default index location is data/vector_index
    try:
      st.session_state.rag_retriever = RAGRetriever()
      _rag_debug("RAG retriever initialized at page load")
    except Exception as e:
      st.session_state.rag_retriever = None
      _rag_debug("RAG retriever failed to init at page load", exc=e)
except Exception:
  st.session_state.rag_retriever = None
  _rag_debug("lib.rag import failed at page load")

# -----------------------------------------------------------------------------
# Manage page tracking and associated session state
# -----------------------------------------------------------------------------
THIS_PAGE = "coding_companion"
if "cur_page" not in st.session_state:
    st.session_state.cur_page = THIS_PAGE

if ("token_counts" not in st.session_state) or (st.session_state.cur_page != THIS_PAGE):
    st.session_state.token_counts = {model: {"input_tokens": 0, "output_tokens": 0} for model in models}

# Purge messages if coming from a different page
if (st.session_state.cur_page != THIS_PAGE) and ("messages" in st.session_state):
    del st.session_state.messages

# Initialize messages for this page
if "messages" not in st.session_state:
  # Initialize system/user messages. Use course-specific system prompt and
  # set a user intro that reflects the selected course when available.
  init_course = st.session_state.get('course') or 'Business Analytics'
  st.session_state.messages = [{
    "role": "system",
    "content": course_system_prompt(st.session_state.get('course'))
  }, {
    "role": "user",
    "content": f"Hi, I am an undergraduate student studying {init_course}."
  }]

st.session_state.cur_page = THIS_PAGE
# -----------------------------------------------------------------------------

# The Streamlit Interface:
# ------------------------

# Streamlit Title:
# ----------------
st.set_page_config(page_title = "FE-AI Coding Companion", layout = "centered", page_icon=PAGE_ICON)

# Import theme colors
from config import THEME_COLORS
from lib.ui import apply_theme_css

# Apply compact output styles for a simpler prompt/output appearance
apply_theme_css(include_code_styles=True)
st.markdown(f'<h2 align=center>FE-AI </h2><h5 style="color: {THEME_COLORS["primary"]};" align=center>Falcon Engineering AI Tutor</h5>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Render the sidebar
# -----------------------------------------------------------------------------
sidebar.render_sidebar()
# -----------------------------------------------------------------------------

# Course selection: use a radio so the active course is visibly highlighted.
if 'selected_course_tab' not in st.session_state:
  st.session_state['selected_course_tab'] = st.session_state.get('course', 'ECE') or 'ECE'

# Include SYE as a supported course option and compute index robustly
course_options = ['ECE', 'ROBO', 'SYE']
try:
  idx = course_options.index(st.session_state['selected_course_tab']) if st.session_state.get('selected_course_tab') in course_options else 0
except Exception:
  idx = 0
selected_course = st.radio('Choose your course: ', options=course_options, index=idx, horizontal=True)
st.session_state['selected_course_tab'] = selected_course

# Update the system prompt in session messages to match the selected course
try:
  if 'messages' in st.session_state and isinstance(st.session_state['messages'], list) and len(st.session_state['messages']) > 0:
    st.session_state['messages'][0]['content'] = course_system_prompt(selected_course)
    # Update the stored user intro to match the selected course
    try:
      st.session_state['messages'][1]['content'] = f"Hi, I am an undergraduate student studying {selected_course}."
    except Exception:
      pass
except Exception:
  pass

# Initialize or re-init RAG retriever for the selected course index dir
try:
  from lib.rag import RAGRetriever
  desired_idx = os.path.join('data', 'vector_index', selected_course)
  cur = st.session_state.get('rag_retriever')
  need_init = False
  if cur is None:
    need_init = True
  else:
    try:
      if getattr(cur, 'index_dir', None) != desired_idx:
        need_init = True
    except Exception:
      need_init = True

  if need_init:
    try:
      st.session_state.rag_retriever = RAGRetriever(index_dir=desired_idx)
      _rag_debug(f"RAG retriever initialized for course {selected_course} at {desired_idx}")
    except Exception as e:
      st.session_state.rag_retriever = None
      _rag_debug(f"RAG retriever failed to init for course {selected_course}", exc=e)
except Exception:
  # If rag import fails, keep previous behavior
  pass
    

# Main Window: Where the Chat is Invoked, Displayed, and Stored:
# --------------------------------------------------------------
for message in st.session_state.messages[2:]:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

# Display chatbox input & process user input (simpler placeholder)
if prompt := st.chat_input("Ask a question..."):
  # Store the user's prompt to memory
  st.session_state.messages.append({"role": "user", "content": prompt})
  # Display the user's prompt to the chat window
  st.chat_message("user").markdown(prompt)
  # Stream response from the LLM
  with st.chat_message("assistant"):
    
    # initializing the response objects
    message_placeholder = st.empty()
    full_response = ""
    input_token_count = 0
    output_token_count = 0
    
    # generating the response
    # Attempt RAG retrieval and prepend as a system message when available
    messages_for_model = [ {"role": m["role"], "content": m["content"]} for m in st.session_state.messages ]
    try:
      retr = st.session_state.get('rag_retriever')
      # If retriever wasn't initialized at page load, try to create it now
      if retr is None:
        try:
          from lib.rag import RAGRetriever
          idx = os.path.join('data', 'vector_index', selected_course)
          retr = RAGRetriever(index_dir=idx)
          st.session_state.rag_retriever = retr
          _rag_debug(f"RAG retriever lazily initialized at prompt time for course {selected_course}")
        except Exception as e:
          retr = None
          _rag_debug("RAG lazy init failed at prompt time", exc=e)

      if retr is not None:
        try:
          _rag_debug(f"Starting retrieval for query={prompt!r} (k=1)")
          docs = retr.retrieve(prompt, k=1)
          _rag_debug(f"Retrieval finished, got {len(docs) if docs is not None else 0} docs; mode={getattr(retr, '_mode', None)}")
        except Exception as e:
          docs = None
          _rag_debug("Exception during RAG.retrieve()", exc=e)
        if docs:
          # Emit a terminal debug message so server logs show RAG activity
          try:
            model_used = st.session_state.get('model_choice')
            mode = getattr(retr, '_mode', None)
            _rag_debug(f"[RAG DEBUG] mode={mode} retrieved={len(docs)} query={prompt!r} model={model_used}")
          except Exception as e:
            _rag_debug("Failed to write RAG DEBUG line", exc=e)
          # Compute similarity percentages and filter out low-similarity results
          try:
            # Extract numeric scores when available
            numeric_scores = [d.get('score') for d in docs if isinstance(d.get('score'), (int, float))]
            filtered_docs = []
            if numeric_scores:
              s_min = min(numeric_scores)
              s_max = max(numeric_scores)
              # Heuristic: if scores are in [0,1], treat them as similarity (higher better)
              is_similarity = (s_min >= 0.0 and s_max <= 1.0)
              for d in docs:
                sc = d.get('score')
                if isinstance(sc, (int, float)):
                  if is_similarity:
                    sim_pct = float(sc) * 100.0
                  else:
                    # treat as distance: lower is better -> invert via min-max
                    if s_max - s_min > 1e-12:
                      sim_pct = (s_max - float(sc)) / (s_max - s_min) * 100.0
                    else:
                      sim_pct = 100.0
                  # Attach computed similarity for debugging/UI
                  d['_sim_pct'] = sim_pct
                  if sim_pct >= 90.0:
                    filtered_docs.append(d)
                else:
                  # No numeric score: keep by default
                  d['_sim_pct'] = None
                  filtered_docs.append(d)
            else:
              # No numeric scores available (e.g., LangChain returned None); keep all
              filtered_docs = docs.copy()
            # Replace docs with filtered set
            docs = filtered_docs
            _rag_debug(f"RAG filtering applied, kept {len(docs)} docs after similarity thresholding")
          except Exception as e:
            _rag_debug("Error during RAG similarity filtering", exc=e)
          # Helper: produce a cleaned snippet ending on a sentence boundary
          def _clean_snippet(text: str, max_len: int = 400) -> str:
            if not text:
              return ''
            t = ' '.join(text.split())
            if len(t) <= max_len:
              # try to end at sentence boundary
              m = max((t.rfind(p) for p in '.!?'), default=-1)
              if m > max_len // 2:
                return t[:m+1]
              return t
            # truncate then backtrack to last sentence end
            s = t[:max_len]
            last = max(s.rfind('.'), s.rfind('!'), s.rfind('?'))
            if last > int(max_len * 0.4):
              return s[:last+1]
            # otherwise return safe truncated chunk without mid-word cut
            return s.rsplit(' ', 1)[0] + '...'

          # Concatenate short, cleaned snippets into a system message
          snippets = []
          for d in docs:
            # support both LangChain Document objects and native dict results
            if isinstance(d, dict):
              txt = d.get("text", "").strip()
            else:
              txt = (getattr(d, 'page_content', str(d)) or "").strip()
            clean = _clean_snippet(txt, max_len=400)
            if clean:
              snippets.append(clean)
          # Keep only the single best snippet (top-1) to avoid mixing multiple
          # contexts; prefer the first retrieved result which is the closest match.
          if snippets:
            primary = snippets[0]
            rag_msg = {
              "role": "system",
              "content": "Relevant course material (short excerpt):\n\n" + primary
            }
            # Insert rag message after the original system prompt
            if messages_for_model and messages_for_model[0].get('role') == 'system':
              messages_for_model.insert(1, rag_msg)
            else:
              messages_for_model.insert(0, rag_msg)
            # Save retrieved docs for UI debugging display
            st.session_state['_last_rag_docs'] = docs
    except Exception:
      # If retrieval fails, proceed without RAG
      pass

    outputs = chatgeneration.generate_chat_completion(
      model = st.session_state.model_choice,
      messages = messages_for_model,
      temp = TEMPERATURE,
      max_num_tokens = 1000
    )
    
    # extracting the response, input tokens, and output tokens
    response, input_tokens, output_tokens = outputs
    full_response += response
    message_placeholder.markdown(full_response)

    # Show retrieved snippets in the sidebar for verification (debug only)
    try:
        if st.session_state.get('_last_rag_docs'):
            with st.sidebar.expander('RAG: Retrieved snippets (debug)', expanded=False):
                for i, d in enumerate(st.session_state.get('_last_rag_docs')):
                    try:
                        # d may be a dict from native retriever or a LangChain Document
                        if isinstance(d, dict):
                            txt = d.get('text','')
                        else:
                            txt = getattr(d, 'page_content', str(d))
                        # display a cleaned preview without showing internal scores or incomplete fragments
                        def _clean_preview(t: str, max_len: int = 400) -> str:
                            if not t:
                                return ''
                            s = ' '.join(t.split())
                            if len(s) <= max_len:
                                # prefer ending at sentence boundary
                                last = max(s.rfind('.'), s.rfind('!'), s.rfind('?'))
                                if last > int(len(s) * 0.4):
                                    return s[:last+1]
                                return s
                            chunk = s[:max_len]
                            last = max(chunk.rfind('.'), chunk.rfind('!'), chunk.rfind('?'))
                            if last > int(max_len * 0.4):
                                return chunk[:last+1]
                            return chunk.rsplit(' ', 1)[0] + '...'

                        preview = _clean_preview(txt, max_len=400)
                        st.markdown(f"**#{i+1}**")
                        st.write(preview)
                    except Exception:
                        continue
    except Exception:
      pass
    
    # Ensure the token_counts has an entry for the selected model, then update
    if input_tokens is not None and output_tokens is not None:
      mc = st.session_state.model_choice
      if mc not in st.session_state.token_counts:
        st.session_state.token_counts[mc] = {"input_tokens": 0, "output_tokens": 0}
      st.session_state.token_counts[mc]['input_tokens'] += input_tokens
      st.session_state.token_counts[mc]['output_tokens'] += output_tokens
  
  # Store the full response from the LLM in memory
  st.session_state.messages.append({"role": "assistant", "content": full_response})

# Generating the PDF from the Chat:
# ---------------------------------
with st.expander("Export Chat to PDF"):
  row = st.columns([2, 2])
  user_name = row[0].text_input("Enter your name:")
  user_course = row[1].text_input("Enter your course name:")
  if user_name != "" and user_course != "":
    pdf_output_path = chatpdf.create_pdf(chat_messages=st.session_state.messages, models = models, token_counts = st.session_state.token_counts, user_name=user_name, user_course=user_course)

    with open(pdf_output_path, "rb") as file:
      st.download_button(label="Download PDF", data=file, file_name=f"{user_course}_{user_name}_FE-AI.pdf", mime="application/pdf", width="stretch")


# -----------------------------------------------------------------------------
