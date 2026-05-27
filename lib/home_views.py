import streamlit as st
from config import THEME_COLORS, PROJECT_ROOT


def professor_home(username: str):
    """Professor Dashboard entrypoint.

    This view refreshes the analytics scripts (short timeout), loads
    `data/topic_difficulty.json` if present, renders a difficulty heatmap,
    and shows a simple Misconception / Error Patterns bar chart.
    """
    import json
    from pathlib import Path
    import pandas as pd
    from lib import auth
    from lib.enhanced_usage_logger import load_json_log

    st.markdown(f'<h2 style="color: {THEME_COLORS["primary"]};" align=center>Instructor Dashboard</h2>', unsafe_allow_html=True)
    display = auth.get_display_name(username) or username
    st.markdown(f"**Signed in as:** {display}")

    # Narrow and center the main content container for admin pages to reduce
    # the large left/right whitespace seen in some Streamlit layouts.
    try:
                st.markdown(
                        """
                        <style>
                            /* Allow admin pages to use the full viewport width */
                            .block-container {
                                max-width: none !important;
                                padding-left: 5% !important;
                                padding-right: 5% !important;
                                margin-left: 0 !important;
                                margin-right: 0 !important;
                            }
                            /* Ensure inner content uses available width comfortably */
                            .main > div { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
                            /* Make wide charts and widgets fit better */
                            .stPlotlyChart, .streamlit-expanderHeader, .stImage { max-width: 100% !important; }
                        </style>
                        """,
                        unsafe_allow_html=True,
                )
    except Exception:
        pass

    # --- Admin summary cards: Active students, High-Risk students, Avg session time ---
    try:
        students = []
        if 'student_name' in recent.columns:
            students = recent['student_name'].dropna().unique().tolist()
        elif 'student' in recent.columns:
            students = recent['student'].dropna().unique().tolist()
        else:
            # try nested data field
            students = list({(r.get('student_name') or (r.get('data') or {}).get('student_name') or r.get('student') or 'unknown') for r in recent.to_dict(orient='records')})

        active_students = len(students)

        # average session time (minutes) per session_id
        avg_session_minutes = 0.0
        try:
            if 'timestamp' in recent.columns and 'session_id' in recent.columns:
                times = pd.to_datetime(recent['timestamp'], utc=True, errors='coerce')
                recent = recent.assign(_ts=times)
                durations = []
                for sid, g in recent.groupby('session_id'):
                    gts = g['_ts'].dropna()
                    if len(gts) >= 2:
                        dur_min = (gts.max() - gts.min()).total_seconds() / 60.0
                        durations.append(dur_min)
                if durations:
                    avg_session_minutes = sum(durations) / len(durations)
        except Exception:
            avg_session_minutes = 0.0

        # quick high-risk count using simple heuristics (same as at-risk logic)
        high_risk = 0
        try:
            student_col = None
            for c in ['student', 'student_name', 'student_id', 'studentId', 'studentName']:
                if c in recent.columns:
                    student_col = c
                    break
            if student_col is None:
                recent['student'] = recent.apply(lambda r: (r.get('student_name') or (r.get('data') or {}).get('student_name') or r.get('student') or 'unknown'), axis=1)
                student_col = 'student'

            for student, grp in recent.groupby(student_col):
                records = grp.to_dict(orient='records')
                total = len(records)
                err = sum(1 for ev in records if ((ev.get('data') or {}).get('error_tags') or ev.get('error_tags')))
                error_rate = (err / total) if total > 0 else 0.0
                if (total >= 3 and error_rate > 0.15) or (error_rate > 0.3):
                    high_risk += 1
        except Exception:
            high_risk = 0

        c1, c2, c3 = st.columns(3)
        c1.metric('Active Students', str(active_students))
        c2.metric('High-Risk Students', str(high_risk))
        avg_label = f"{avg_session_minutes:.1f} min" if avg_session_minutes > 0 else '0 min'
        c3.metric('Avg Session Time', avg_label)
    except Exception:
        pass

    # Load recent activity entries
    log_path = Path(__file__).parent.parent / 'logs' / 'activity_log.json'
    entries = load_json_log(log_path)
    if not entries:
        st.info("No activity data available yet. The dashboard will appear once interactions are logged.")
        return

    df = pd.DataFrame(entries)
    recent = df.copy()

    # --- Refresh analytics scripts with a short timeout and show output ---
    metrics_path = Path(PROJECT_ROOT) / 'data' / 'topic_difficulty.json'
    try:
        import subprocess
        scripts_dir = Path(PROJECT_ROOT) / 'scripts'
        scripts_to_run = [
            scripts_dir / 'classify_topics_ollama.py',
            scripts_dir / 'compute_counts.py',
            scripts_dir / 'compute_topic_difficulty.py',
            scripts_dir / 'compute_errors.py',
        ]
        run_outputs = []
        with st.spinner('Refreshing topic analytics (running scripts)...'):
            for sp in scripts_to_run:
                if sp.exists():
                    try:
                        res = subprocess.run(['python3', str(sp)], cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=120)
                        run_outputs.append((sp.name, res.returncode, (res.stdout or '') + (res.stderr or '')))
                    except Exception as e:
                        run_outputs.append((sp.name, -1, str(e)))
        if run_outputs:
            with st.expander('Analytics script output (latest)'):
                for name, rc, out in run_outputs:
                    st.markdown(f'**{name}** — exit {rc}')
                    st.text(out[:10000])
    except Exception:
        # non-fatal; proceed with whatever metrics are available
        pass

    # Load metrics if available
    heat_df = pd.DataFrame()
    if metrics_path.exists():
        try:
            raw = json.loads(metrics_path.read_text(encoding='utf-8'))
            rows = []
            for r in raw:
                diff = r.get('difficulty_norm') if r.get('difficulty_norm') is not None else r.get('difficulty')
                cnt = int(r.get('count') or 0)
                rows.append({
                    'topic': r.get('topic'),
                    'difficulty': float(diff) if diff is not None else 0.0,
                    'count': cnt,
                    'misconceptions': int(r.get('misconceptions') or 0),
                    'avg_attempts': float(r.get('avg_attempts') or 0.0),
                    'avg_depth': float(r.get('avg_depth') or 0.0),
                    'samples': r.get('samples') or [],
                    'domain': r.get('domain') or 'unknown',
                })
            heat_df = pd.DataFrame(rows).set_index('topic')
        except Exception:
            heat_df = pd.DataFrame()

    # Course selection (persist in session state to avoid jumpiness)
    if 'prof_selected_course' not in st.session_state:
        st.session_state['prof_selected_course'] = st.session_state.get('course', 'ECE') or 'ECE'
    # Add SYE to professor course selector and compute index safely
    prof_course_options = ['ECE', 'ROBO', 'SYE']
    try:
        p_idx = prof_course_options.index(st.session_state['prof_selected_course']) if st.session_state.get('prof_selected_course') in prof_course_options else 0
    except Exception:
        p_idx = 0
    prof_choice = st.radio('Course', options=prof_course_options, index=p_idx, horizontal=True)
    st.session_state['prof_selected_course'] = prof_choice
    selected_course = prof_choice

    # --- Top summary cards (Active / High-Risk / Avg Session Time) ---
    try:
        students = []
        if 'student_name' in recent.columns:
            students = recent['student_name'].dropna().unique().tolist()
        elif 'student' in recent.columns:
            students = recent['student'].dropna().unique().tolist()
        else:
            students = list({(r.get('student_name') or (r.get('data') or {}).get('student_name') or r.get('student') or 'unknown') for r in recent.to_dict(orient='records')})

        active_students = len(students)

        # average session time (minutes) per session_id
        avg_session_minutes = 0.0
        try:
            if 'timestamp' in recent.columns and 'session_id' in recent.columns:
                times = pd.to_datetime(recent['timestamp'], utc=True, errors='coerce')
                recent = recent.assign(_ts=times)
                durations = []
                for sid, g in recent.groupby('session_id'):
                    gts = g['_ts'].dropna()
                    if len(gts) >= 2:
                        dur_min = (gts.max() - gts.min()).total_seconds() / 60.0
                        durations.append(dur_min)
                if durations:
                    avg_session_minutes = sum(durations) / len(durations)
        except Exception:
            avg_session_minutes = 0.0

        # quick high-risk count using simple heuristics
        high_risk = 0
        try:
            student_col = None
            for c in ['student', 'student_name', 'student_id', 'studentId', 'studentName']:
                if c in recent.columns:
                    student_col = c
                    break
            if student_col is None:
                recent['student'] = recent.apply(lambda r: (r.get('student_name') or (r.get('data') or {}).get('student_name') or r.get('student') or 'unknown'), axis=1)
                student_col = 'student'

            for student, grp in recent.groupby(student_col):
                records = grp.to_dict(orient='records')
                total = len(records)
                err = sum(1 for ev in records if ((ev.get('data') or {}).get('error_tags') or ev.get('error_tags')))
                error_rate = (err / total) if total > 0 else 0.0
                if (total >= 3 and error_rate > 0.15) or (error_rate > 0.3):
                    high_risk += 1
        except Exception:
            high_risk = 0

        c1, c2, c3 = st.columns(3)
        c1.metric('Active Students', str(active_students))
        c2.metric('High-Risk Students', str(high_risk))
        avg_label = f"{avg_session_minutes:.1f} min" if avg_session_minutes > 0 else '0 min'
        c3.metric('Avg Session Time', avg_label)
    except Exception:
        # Non-fatal: if metrics cannot be computed, continue without cards
        pass

    # Render heatmap and misconception/error patterns side-by-side
    try:
        left_col, right_col = st.columns([0.8, 1.2])
    except Exception:
        left_col, right_col = st.columns(2)

    # Left: Topic Difficulty Heatmap (reduced size)
    with left_col:
        st.markdown('**Topic Difficulty Heatmap**')
        st.markdown('<p style="color:#6c757d;font-size:0.9em;margin-top:4px;">Topics with the highest student struggle levels</p>', unsafe_allow_html=True)
        try:
            import matplotlib.pyplot as plt
            if selected_course == 'ROBO':
                desired_robo_order = [
                    'Electrical/electronics Fundamentals',
                    'Sensors',
                    'Actuators',
                    'Logic & Relay-Based Control',
                    'Fluid Power Systems',
                    'Control & Automation Systems',
                    'PLC & Industrial Automation',
                    'Robotics Fundamentals',
                    'System Integration, Design, and Control',
                    'Engineering Practice & Case Studies',
                ]
                if not heat_df.empty:
                    heat_df = heat_df.reindex(desired_robo_order)
                else:
                    heat_df = pd.DataFrame(index=desired_robo_order)
            elif selected_course == 'SYE':
                desired_sye_order = [
                    'Introduction to Systems Engineering',
                    'Systems Engineering Fundamentals',
                    'Systems Development Life Cycle',
                    'Systems Integration & Design',
                    'Requirements Engineering',
                    'Systems Modeling Fundamentals',
                    'Functional & Behavioral Modeling',
                    'Decision Analysis & Optimization',
                    'Operations Research Techniques',
                    'Systems Modeling Software',
                    'Systems Analysis Methodologies',
                    'Case Studies & Group Projects',
                    'Engineering Communication',
                    'Applications of Systems Engineering',
                ]
                if not heat_df.empty:
                    heat_df = heat_df.reindex(desired_sye_order)
                else:
                    heat_df = pd.DataFrame(index=desired_sye_order)
                for col in ['difficulty', 'count', 'misconceptions', 'avg_attempts', 'avg_depth']:
                    if col not in heat_df.columns:
                        heat_df[col] = 0
                    heat_df[col] = heat_df[col].fillna(0)
            else:
                if heat_df.empty:
                    heat_df = pd.DataFrame()
                else:
                    heat_df = heat_df.sort_values('difficulty', ascending=True)

            if heat_df.empty:
                st.write('No difficulty data available to render heatmap.')
            else:
                # Further reduce vertical length: smaller multiplier with a low minimum and a capped maximum
                height = min(2.0, max(0.6, 0.12 * len(heat_df)))
                # Reduced width to make heatmap smaller when side-by-side
                fig, ax = plt.subplots(figsize=(4, height))
                data = heat_df['difficulty'].astype(float).values.reshape(-1, 1)
                im = ax.imshow(data, aspect='auto', cmap='OrRd', vmin=0, vmax=1)
                ax.set_yticks(range(len(heat_df.index)))
                import matplotlib as mpl
                # Halve the default font sizes for all heatmap labels
                try:
                    y_base = float(mpl.rcParams.get('ytick.labelsize', 10))
                except Exception:
                    y_base = 10.0
                try:
                    x_base = float(mpl.rcParams.get('xtick.labelsize', 10))
                except Exception:
                    x_base = 10.0
                try:
                    cb_base = float(mpl.rcParams.get('axes.titlesize', mpl.rcParams.get('font.size', 10)))
                except Exception:
                    cb_base = 10.0

                # Halve again: quarter of the original rcParams size, then increase y-labels by 5%
                base_quarter_y = max(2.0, y_base / 4.0)
                # increase by another 5% (apply a fourth 1.05 multiplier)
                y_fs = max(2.0, base_quarter_y * 1.05 * 1.05 * 1.05 * 1.05)
                x_fs = max(2.0, x_base / 4.0)
                cb_fs = max(3.0, cb_base / 4.0)

                ax.set_yticklabels(heat_df.index, fontsize=y_fs)
                ax.tick_params(axis='y', labelsize=y_fs)
                ax.tick_params(axis='x', labelsize=x_fs)
                ax.set_xticks([])
                cbar = fig.colorbar(im, ax=ax, orientation='vertical', fraction=0.08)
                cbar.ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
                try:
                    cbar.ax.set_title('Difficulty Level', fontsize=9, pad=8)
                except Exception:
                    cbar.set_label('Difficulty Level')
                plt.tight_layout()
                st.pyplot(fig)
        except Exception:
            try:
                st.bar_chart(heat_df['difficulty'])
            except Exception:
                st.write('No difficulty data available to render heatmap.')

    # Right: Misconception / Error patterns (topic -> subtopic breakdown)
    with right_col:
        st.markdown('**Misconception / Error Patterns**')
        st.markdown('<p style="color:#6c757d;font-size:0.9em;margin-top:4px;">Most frequent reasoning problems detected by the analytics agent</p>', unsafe_allow_html=True)

        # Topic lists per course (display labels)
        ECE_TOPICS = [
        'Electrical Fundamentals',
        'Circuit Analysis',
        'Passive Components',
        'Electromagnetism & AC Systems',
        'Electrical Machines, Relays and Switches',
        'Semiconductor Devices and applications',
        'Digital Electronics',
        'Instrumentation & Measurement',
        'Computer Engineering Basics',
        'Electronics Communication Basics',
        'Fabrication & Practical Skills',
        'Simulation & Software Tools',
    ]
        ROBO_TOPICS = [
            'Electrical/electronics Fundamentals',
            'Sensors',
            'Actuators',
            'Logic & Relay-Based Control',
            'Fluid Power Systems',
            'Control & Automation Systems',
            'PLC & Industrial Automation',
            'Robotics Fundamentals',
            'System Integration, Design, and Control',
            'Engineering Practice & Case Studies',
        ]

        # SYE (Systems Engineering) topics
        SYE_TOPICS = [
            'Introduction to Systems Engineering',
            'Systems Engineering Fundamentals',
            'Systems Development Life Cycle',
            'Systems Integration & Design',
            'Requirements Engineering',
            'Systems Modeling Fundamentals',
            'Functional & Behavioral Modeling',
            'Decision Analysis & Optimization',
            'Operations Research Techniques',
            'Systems Modeling Software',
            'Systems Analysis Methodologies',
            'Case Studies & Group Projects',
            'Engineering Communication',
            'Applications of Systems Engineering',
        ]

        # Subtopic label lists (ordered) for each topic
        ECE_SUBTOPICS = {
            'Electrical Fundamentals': [
                "Ohm’s Law", "Voltage, Current, Resistance", "Metric Units"
            ],
            'Circuit Analysis': [
                'Series Circuits', 'Parallel Circuits', 'Circuit Behavior & Analysis'
            ],
            'Passive Components': ['Resistors', 'Capacitors', 'Inductors', 'Transformers'],
            'Electromagnetism & AC Systems': ['Electromagnetic Principles', 'AC Circuits', 'Frequency & Waveforms'],
            'Electrical Machines, Relays and Switches': ['DC Motors', 'Relay Circuits and Switches'],
            'Semiconductor Devices and applications': ['Diodes', 'Rectifier Circuits', 'Transistors (BJT)', 'Switching and Amplifier circuit'],
            'Digital Electronics': ['Binary Numbers', 'Logic Gates', 'Basic Digital Logic'],
            'Instrumentation & Measurement': ['Lab Instruments', 'Measurement Techniques', 'Signal Observation'],
            'Computer Engineering Basics': ['Computer System Overview', 'CPU', 'Embedded', 'AI hardware', 'Career Paths'],
            'Electronics Communication Basics': ['Communication Types', 'Modulation/Demodulation techniques'],
            'Fabrication & Practical Skills': ['Soldering', 'Circuit Assembly', 'PCB wiring and Debugging'],
            'Simulation & Software Tools': ['Multisim', 'Circuit Simulation', 'Debugging in Simulation'],
        }
        ROBO_SUBTOPICS = {
            'Electrical/electronics Fundamentals': ['Ohm’s Law', 'Voltage, Current, Resistance', 'Electronics components'],
            'Sensors': ['Types of Sensors', 'Signal Acquisition', 'Sensor Integration'],
            'Actuators': ['Electrical Actuators', 'Mechanical Actuation', 'Actuator Selection'],
            'Logic & Relay-Based Control': ['Relay Circuits', 'Logic Circuits', 'Basic Control Logic'],
            'Fluid Power Systems': ['Hydraulic Circuits', 'Pneumatic Circuits', 'Electro-Pneumatic/hydraulic circuits'],
            'Control & Automation Systems': ['Open-loop Systems', 'Closed-loop Systems', 'Automation Architecture'],
            'PLC & Industrial Automation': ['PLC Basics', 'Ladder Logic', 'PLC Programming basics'],
            'Robotics Fundamentals': ['Robot Components', 'Robot Programming Basics', 'Industrial Robots'],
            'System Integration, Design, and Control': ['Sensor-Actuator Integration', 'System Testing', 'Troubleshooting', 'Automation Programming', 'Logic Debugging', 'Control Execution'],
            'Engineering Practice & Case Studies': ['Automation Case Study', 'Mini Project Design', 'System Evaluation'],
        }

        SYE_SUBTOPICS = {
            'Introduction to Systems Engineering': ['Systems Thinking', 'System Components', 'Engineering Systems'],
            'Systems Engineering Fundamentals': ['Interdisciplinary Design', 'System Analysis', 'Lifecycle Concepts'],
            'Systems Development Life Cycle': ['Development Phases', 'Maintenance', 'Verification & Validation'],
            'Systems Integration & Design': ['System Architecture', 'Integration', 'Interface Design'],
            'Requirements Engineering': ['Functional Requirements', 'Traceability', 'Requirement Writing'],
            'Systems Modeling Fundamentals': ['Modeling Concepts', 'Model Types', 'System Representation'],
            'Functional & Behavioral Modeling': ['DFDs', 'E-R Diagrams', 'FSMs, LDM & PDM'],
            'Decision Analysis & Optimization': ['Decision Making', 'Utility Functions', 'Linear Programming'],
            'Operations Research Techniques': ['Simplex Method', 'Optimization', 'Problem Solving'],
            'Systems Modeling Software': ['CORE', 'Rational', 'Modeling Applications'],
            'Systems Analysis Methodologies': ['Process Analysis', 'Evaluation Methods', 'Analytical Techniques'],
            'Case Studies & Group Projects': ['Team Projects', 'Case Studies', 'System Applications'],
            'Engineering Communication': ['Technical Documentation', 'Collaboration', 'Professional Practice'],
            'Applications of Systems Engineering': ['Manufacturing Systems', 'Service Systems', 'Complex Systems'],
        }

        # Build topic selector based on course
        if selected_course == 'ECE':
            topic_options = ECE_TOPICS
        elif selected_course == 'ROBO':
            topic_options = ROBO_TOPICS
        else:
            # default to SYE for any other value including 'SYE'
            topic_options = SYE_TOPICS if selected_course == 'SYE' else ECE_TOPICS

        selected_topic = st.selectbox('Select Topic', options=topic_options)

        # Determine subtopic labels for selected topic
        if selected_course == 'ECE':
            sublabels = ECE_SUBTOPICS.get(selected_topic, [])
        elif selected_course == 'ROBO':
            sublabels = ROBO_SUBTOPICS.get(selected_topic, [])
        else:
            sublabels = SYE_SUBTOPICS.get(selected_topic, []) if selected_course == 'SYE' else ECE_SUBTOPICS.get(selected_topic, [])

    # Prepare candidate items to classify: prefer analytics debug entries, else recent logs, else heat_df samples
    max_items = 60
    items = []  # list of text entries to classify
    try:
        analytics_dir = Path(__file__).parent.parent / 'data' / 'analytics'
        debug_path = analytics_dir / f'error_{selected_course}.json'
        if debug_path.exists():
            parsed = json.loads(debug_path.read_text())
            if isinstance(parsed, list):
                for obj in parsed:
                    try:
                        if (obj.get('topic') or '') == selected_topic:
                            text = (obj.get('student_prompt') or obj.get('prompt') or obj.get('sample') or '')
                            resp = (obj.get('student_response') or obj.get('response') or '')
                            # try several fields for student identity
                            student = obj.get('student') or obj.get('student_name') or obj.get('user') or (obj.get('data') or {}).get('student_name') or 'unknown'
                            items.append({'q': text, 'a': resp, 'error': bool(obj.get('misconception')), 'student': student})
                            if len(items) >= max_items:
                                break
                    except Exception:
                        continue
    except Exception:
        pass

    if not items:
        # fallback to recent logs where topic matches
        try:
            for ev in recent.to_dict(orient='records'):
                data = ev.get('data') or {}
                t = (data.get('topic') or ev.get('topic') or '')
                if t == selected_topic or (selected_course == 'ECE' and t == selected_topic):
                    q = (data.get('prompt_preview') or ev.get('prompt_preview') or '')
                    a = (data.get('response_preview') or ev.get('response_preview') or '')
                    err = bool(data.get('error_tags') or ev.get('error_tags'))
                    student = ev.get('student') or ev.get('student_name') or (data.get('student_name') if isinstance(data, dict) else None) or 'unknown'
                    items.append({'q': q, 'a': a, 'error': err, 'student': student})
                    if len(items) >= max_items:
                        break
        except Exception:
            items = items

    if not items and not heat_df.empty and selected_topic in heat_df.index:
        # use sample prompts recorded in metrics
        try:
            samples = heat_df.loc[selected_topic].get('samples') or []
            for s in samples[:max_items]:
                if isinstance(s, dict):
                    q = s.get('prompt', '')
                    a = s.get('response', '')
                    student = s.get('student') or s.get('student_name') or 'unknown'
                else:
                    q = str(s)
                    a = ''
                    student = 'unknown'
                items.append({'q': q, 'a': a, 'error': False, 'student': student})
        except Exception:
            items = items

    # Aggregation structure
    sub_counts = {lbl: 0 for lbl in sublabels} if sublabels else {}

    # Classification: try LLM if configured, otherwise heuristic keyword matching
    llm_used = False
    try:
        from lib.chatgeneration import generate_chat_completion
        model_for_classify = 'llama3.2:3b' if 'llama3.2:3b' in __import__('config').MODELS else None
    except Exception:
        generate_chat_completion = None
        model_for_classify = None

    def heuristic_classify_text(text: str, sublabels_list: list) -> str:
        t = (text or '').lower()
        # basic keyword maps per sublabel (derive from label words)
        for lbl in sublabels_list:
            key = lbl.lower()
            parts = [p.strip() for p in key.replace('/', ' ').replace('&', ' ').split() if p.strip()]
            match = any(p in t for p in parts if len(p) > 3)
            if match:
                return lbl
        return sublabels_list[0] if sublabels_list else 'Other'

    if items:
        classified = []
        if model_for_classify and generate_chat_completion:
            # Batch items into a prompt (limit tokens). Ask LLM to assign subtopic label and misconception boolean.
            try:
                system = {
                    'role': 'system',
                    'content': (
                        'You are an assistant that maps short student interactions to one of the provided subtopic labels and indicates whether the response shows a misconception. ' \
                        'Return ONLY a JSON array of objects with fields: index (1-based), subtopic (one of the provided labels), misconception (true/false).'
                    )
                }
                labels_text = '\n'.join(f'- {s}' for s in sublabels) if sublabels else ''
                user_content = 'Subtopic labels:\n' + labels_text + '\n\nNow classify the following items. For each, return index, subtopic, misconception. Items:\n\n'
                for i, it in enumerate(items, start=1):
                    user_content += f"{i}) Q: {it.get('q','')[:400]}\nA: {it.get('a','')[:400]}\n\n"
                user = {'role': 'user', 'content': user_content}
                resp_text, _, _ = generate_chat_completion(model_for_classify, [system, user], temp=0.0, max_num_tokens=1024)
                jstart = resp_text.find('[')
                jend = resp_text.rfind(']')
                if jstart != -1 and jend != -1 and jend > jstart:
                    arr_text = resp_text[jstart:jend+1]
                    parsed_arr = json.loads(arr_text)
                    for obj in parsed_arr:
                        idx = int(obj.get('index', 0)) - 1
                        sub = obj.get('subtopic')
                        mis = bool(obj.get('misconception', False))
                        if idx >= 0 and idx < len(items):
                            classified.append({'idx': idx, 'subtopic': sub, 'misconception': mis})
                    llm_used = True
            except Exception:
                classified = []

        if not classified:
            # heuristic per-item
            for i, it in enumerate(items):
                text = (it.get('q','') + ' ' + it.get('a',''))
                sub = heuristic_classify_text(text, sublabels) if sublabels else 'Other'
                mis = bool(it.get('error')) or any(k in (text or '').lower() for k in ['incorrect', 'wrong', 'mistake', 'not correct'])
                classified.append({'idx': i, 'subtopic': sub, 'misconception': mis})

        # aggregate unique students with misconceptions per subtopic
        sub_student_sets = {lbl: set() for lbl in (sublabels or [])}
        for c in classified:
            s = c.get('subtopic') or 'Other'
            if s not in sub_student_sets:
                sub_student_sets[s] = set()
            if c.get('misconception'):
                try:
                    stud = items[c.get('idx', 0)].get('student')
                except Exception:
                    stud = None
                if not stud:
                    stud = 'unknown'
                sub_student_sets[s].add(str(stud))
        # Map back to simple counts for backward compatibility
        for k, v in sub_student_sets.items():
            sub_counts[k] = len(v)

    # Render bar chart for selected topic's subtopics inside the right column
    try:
        with right_col:
            import matplotlib.pyplot as plt
            # determine total unique students from recent logs and sampled items
            try:
                all_students = set()
                for ev in recent.to_dict(orient='records'):
                    data = ev.get('data') or {}
                    stud = ev.get('student') or ev.get('student_name') or (data.get('student_name') if isinstance(data, dict) else None)
                    if stud:
                        all_students.add(str(stud))
                for it in items:
                    stud = it.get('student')
                    if stud:
                        all_students.add(str(stud))
                total_students = len(all_students)
            except Exception:
                total_students = 0

            labels = list(sublabels) if sublabels else sorted(sub_counts.keys())
            if not labels:
                with right_col:
                    st.info('No subtopic labels available for the selected topic.')
                raise Exception('No labels')

            # compute percentage of unique students per subtopic
            vals = []
            for l in labels:
                cnt = sub_counts.get(l, 0)
                pct = (cnt / total_students) * 100.0 if total_students > 0 else 0.0
                vals.append(pct)

            # Always render a chart for the selected topic. If all values are zero
            # the chart will show zero-length bars (visual placeholder) and a
            # small caption to explain the lack of recorded misconceptions.
            fig, ax = plt.subplots(figsize=(8, max(1.2, 0.35 * len(labels))))
            ax.barh(labels, vals, color=THEME_COLORS.get('primary', '#1f77b4'))
            ax.set_xlabel('Percent of Unique Students (%)')
            ax.set_xlim(0, 100)
            # use integer percent ticks
            try:
                import numpy as np
                ax.set_xticks(np.linspace(0, 100, 6))
            except Exception:
                pass
            ax.invert_yaxis()
            plt.tight_layout()
            with right_col:
                st.pyplot(fig)
                if all(v <= 0 for v in vals):
                    st.caption('No recorded misconceptions for this topic — displaying chart with zero values.')
                else:
                    if llm_used:
                        st.caption('Subtopic labels inferred by LLM for sampled interactions (may be limited by sample size).')
                    else:
                        st.caption('Subtopic labels inferred by local heuristic.')
    except Exception:
        with right_col:
            st.write('No misconception data available for this topic')

    # Render Bloom's Cognitive Depth Distribution and At-Risk Students side-by-side
    try:
        try:
            bloom_col, atrisk_col = st.columns([0.8, 1.2])
        except Exception:
            bloom_col, atrisk_col = st.columns(2)

        # Left: Bloom chart (smaller)
        with bloom_col:
            st.markdown("**Bloom's Cognitive Depth Distribution**")
            st.markdown('<p style="color:#6c757d;font-size:0.9em;margin-top:4px;">Distribution of chatbot interactions by cognitive level</p>', unsafe_allow_html=True)
            ordered_labels = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
            counts_dict = None
            try:
                analytics_file = Path(__file__).parent.parent / 'data' / 'analytics' / f'bloom_counts_{selected_course}.json'
                if analytics_file.exists():
                    with analytics_file.open('r') as fh:
                        parsed = json.load(fh)
                        counts_dict = {k: int(parsed.get(k, 0)) for k in ordered_labels}
            except Exception:
                counts_dict = None

            if counts_dict is None or sum(counts_dict.values()) == 0:
                try:
                    from lib.analytics_helpers import refresh_bloom_counts
                    refresh_results = refresh_bloom_counts(out_dir=Path(PROJECT_ROOT) / 'data' / 'analytics')
                    counts_dict = refresh_results.get(selected_course) or counts_dict
                except Exception:
                    counts_dict = counts_dict

            if not counts_dict or sum(counts_dict.values()) == 0:
                try:
                    if 'bloom' in recent.columns:
                        series = recent['bloom'].value_counts().reindex(ordered_labels).fillna(0).astype(int)
                        counts_dict = {k: int(series.get(k, 0)) for k in ordered_labels}
                    else:
                        try:
                            from lib.analytics_helpers import _local_infer_counts
                            c = _local_infer_counts(recent.to_dict(orient='records'))
                            counts_dict = {k: int(c.get(k, 0)) for k in ordered_labels}
                        except Exception:
                            counts_dict = {k: 0 for k in ordered_labels}
                except Exception:
                    counts_dict = {k: 0 for k in ordered_labels}

            try:
                import matplotlib.pyplot as plt
                # Render a compact progress-style horizontal bar chart similar
                # to the provided design: light grey background bars with
                # filled blue foreground bars and count labels at the end.
                labels = ordered_labels
                heights = [int(counts_dict.get(k, 0)) for k in labels]
                max_val = max(1, max(heights))

                try:
                    import numpy as np
                    cmap_vals = np.linspace(0.45, 0.85, len(labels)) if len(labels) > 0 else [0.6]
                    cmap = plt.get_cmap('Blues')
                    colors = [cmap(v) for v in cmap_vals]
                except Exception:
                    colors = ['#4f8cff'] * len(labels)

                fig, ax = plt.subplots(figsize=(6.2, 2.4))
                y_pos = list(range(len(labels)))

                # Background bars (light grey) to act as the rail
                ax.barh(y_pos, [max_val] * len(labels), color='#e9ecef', height=0.6)
                # Foreground bars (colored) representing counts
                for i, val in enumerate(heights):
                    col = colors[i] if i < len(colors) else colors[-1]
                    ax.barh(i, val, color=col, height=0.6)

                # Labels on the left; values annotated to the right of bars
                ax.set_yticks(y_pos)
                ax.set_yticklabels(labels, fontsize=10)
                ax.invert_yaxis()
                ax.xaxis.set_visible(False)
                for spine in ['top', 'right', 'left', 'bottom']:
                    ax.spines[spine].set_visible(False)

                for i, val in enumerate(heights):
                    ax.text(val + max_val * 0.02, i, str(val), va='center', fontsize=9, color='#222222')

                plt.tight_layout()
                st.pyplot(fig)
            except Exception:
                st.write('Could not render Bloom chart')

        # Right: At-Risk Students (compact table)
        with atrisk_col:
            st.markdown("**At-Risk Students**")
            st.markdown('<p style="color:#6c757d;font-size:0.9em;margin-top:4px;">Students who may need follow-up, intervention, or support</p>', unsafe_allow_html=True)
            ar_rows = []
            try:
                recent_df = recent.copy()

                def _row_has_error(ev: dict) -> bool:
                    data = ev.get('data') or {}
                    tags = data.get('error_tags') or ev.get('error_tags')
                    return bool(tags)

                bloom_order = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
                bloom_score = {k: i for i, k in enumerate(bloom_order, start=1)}

                student_col = None
                for c in ['student', 'student_name', 'student_id', 'studentId', 'studentName']:
                    if c in recent_df.columns:
                        student_col = c
                        break
                if student_col is None:
                    recent_df['student'] = recent_df.apply(lambda r: (r.get('student_name') or r.get('student') or r.get('student_id') or 'unknown'), axis=1)
                    student_col = 'student'

                for student, grp in recent_df.groupby(student_col):
                    try:
                        records = grp.to_dict(orient='records')
                        total = len(records)
                        err = sum(1 for ev in records if _row_has_error(ev))
                        error_rate = (err / total) if total > 0 else 0.0

                        if total <= 2:
                            engagement = 'Low'
                        elif total <= 6:
                            engagement = 'Medium'
                        else:
                            engagement = 'High'

                        bloom_vals = []
                        for ev in records:
                            data = ev.get('data') or {}
                            b = data.get('bloom') or ev.get('bloom')
                            if b and b in bloom_score:
                                bloom_vals.append(bloom_score[b])
                        if bloom_vals:
                            avg_num = sum(bloom_vals) / len(bloom_vals)
                            idx = min(range(len(bloom_order)), key=lambda i: abs((i+1) - avg_num))
                            avg_bloom = bloom_order[idx]
                        else:
                            avg_bloom = 'Understand' if total > 0 else 'N/A'

                        if error_rate > 0.3:
                            concern = 'Repeated confusion + low activity' if engagement == 'Low' else 'Repeated confusion + frequent errors'
                        elif error_rate > 0.15:
                            concern = 'Frequent retries + shallow responses'
                        elif err > 0 and total <= 2:
                            concern = 'Low activity with errors'
                        else:
                            concern = 'Improving steadily'

                        if (total >= 3 and error_rate > 0.15) or (error_rate > 0.3):
                            risk = 'High'
                        elif error_rate > 0.08 or (total >= 3 and error_rate > 0.06):
                            risk = 'Medium'
                        else:
                            risk = 'Low'

                        ar_rows.append({
                            'Student': student,
                            'Engagement': engagement,
                            'Avg Bloom': avg_bloom,
                            'Primary Concern': concern,
                            'Risk': risk,
                        })
                    except Exception:
                        continue
            except Exception:
                ar_rows = []

            ar_df = pd.DataFrame(ar_rows)
            if ar_df.empty:
                st.info('No at-risk students detected')
            else:
                try:
                    st.dataframe(ar_df)
                except Exception:
                    st.dataframe(ar_df)
                csv = ar_df.to_csv(index=False)
                st.download_button('Export List', csv, file_name='at_risk_students.csv')
    except Exception:
        # Fallback: render sequentially if columns fail
        st.markdown("**Bloom's Cognitive Depth Distribution**")
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 3.5))
            st.pyplot(fig)
        except Exception:
            pass


def student_home():
    """Placeholder for student home. Main app still renders student content."""
    st.markdown("<h2>Student Home</h2>", unsafe_allow_html=True)
    st.markdown("Use the main app navigation to access student features.")
