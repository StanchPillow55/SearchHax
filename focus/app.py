"""Streamlit interface: pip install -r requirements.txt; streamlit run app.py"""
import os
import streamlit as st
import pandas as pd
from focus_attention import FocusAttentionModel, Passage

st.set_page_config(page_title='TraceFork', page_icon='↗', layout='wide', initial_sidebar_state='expanded')
st.markdown("""
<style>
    :root { --tf-ink: #edf2ff; --tf-muted: #8f9bb8; --tf-panel: #121a2b; --tf-line: #26324b; --tf-accent: #8b7cff; --tf-cyan: #48d7d2; }
    [data-testid="stAppViewContainer"] { background: radial-gradient(circle at 85% 0%, #20264b 0%, #0b1020 42%, #080c16 100%); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: #0d1424; border-right: 1px solid var(--tf-line); }
    [data-testid="stSidebar"] > div:first-child { padding-top: 2rem; }
    .tf-brand { display: flex; align-items: center; gap: .75rem; margin-bottom: 2rem; }
    .tf-mark { display: grid; place-items: center; width: 2.2rem; height: 2.2rem; border-radius: .75rem; background: linear-gradient(135deg, var(--tf-accent), var(--tf-cyan)); color: #08101d; font-weight: 800; }
    .tf-name { color: var(--tf-ink); font-size: 1.25rem; font-weight: 700; letter-spacing: -.03em; }
    .tf-kicker { color: var(--tf-cyan); font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
    .tf-hero { padding: 1.25rem 1.5rem; border: 1px solid var(--tf-line); border-radius: 1rem; background: linear-gradient(135deg, rgba(25,35,62,.92), rgba(15,22,39,.82)); margin-bottom: 1.25rem; }
    .tf-hero h1 { margin: .2rem 0 .35rem; font-size: 2.4rem; letter-spacing: -.06em; }
    .tf-hero p { color: var(--tf-muted); margin: 0; }
    .tf-question { padding: .9rem 1rem; border-left: 3px solid var(--tf-accent); background: rgba(139,124,255,.09); border-radius: .35rem; color: var(--tf-ink); margin: 1rem 0 1.5rem; }
    .tf-section { color: var(--tf-muted); font-size: .74rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; margin: 1.5rem 0 .55rem; }
    div[data-testid="stMetric"] { background: rgba(18,26,43,.74); border: 1px solid var(--tf-line); padding: .75rem 1rem; border-radius: .8rem; }
    .stButton > button[kind="primary"] { background: linear-gradient(90deg, var(--tf-accent), #6258e8); border: 0; }
</style>
<div class="tf-brand"><div class="tf-mark">↗</div><div><div class="tf-name">TraceFork</div><div class="tf-kicker">Evidence routing system</div></div></div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="tf-kicker">Investigation controls</div>', unsafe_allow_html=True)
    question = st.text_area('Research question', 'Why might electric vehicle demand decline?', height=90)
    st.markdown('**Attention policy**')
    novelty = st.slider(
        'Evidence balance — Focused → Exploratory',
        min_value=0, max_value=100, value=50,
        help='Left keeps context tight. Right admits more novel, intent-relevant evidence.',
    )
    st.caption('← Focused · tighter context | more novelty · Exploratory →')
    max_search_calls = st.slider(
        'Search budget — One → More follow-ups',
        min_value=1, max_value=6, value=3,
        help='Maximum live query calls, including the initial search.',
    )
    st.caption('← One search · lower latency | more searches · More →')
    mode = st.selectbox('Retrieval providers', ['Demo passages', 'Tavily', 'Telem', 'Both'])
    latency_mode = st.radio(
        'Run mode', ['Fast preview', 'Deep investigation'],
        help='Fast uses one search and snippets. Deep runs the visible query plan and can fetch selected pages.',
    )
    semantic = st.checkbox('Use semantic embeddings', value=False, help='Downloads a sentence-transformer model on first use.')
    show_space = st.checkbox('Show 3D context space', value=True)
    generate_answer = st.checkbox('Generate cited answer', value=False, help='Uses the selected local or cloud answer model.')
    answer_provider = st.selectbox('Answer provider', ['Auto', 'Local', 'Gemini', 'OpenAI']) if generate_answer else 'Auto'
    run_clicked = st.button('Run investigation', type='primary', use_container_width=True)

st.markdown('<div class="tf-hero"><div class="tf-kicker">Trace the evidence</div><h1>From question to context.</h1><p>Keep the answer anchored while preserving the findings that could change it.</p></div>', unsafe_allow_html=True)
st.markdown(f'<div class="tf-question"><strong>Research question</strong><br>{question}</div>', unsafe_allow_html=True)

DEMO = [
    Passage('price', 'Electric vehicle demand can decline because purchase prices remain high.', 'https://demo.example/price', title='EV pricing'),
    Passage('price2', 'Electric vehicle demand can decline because purchase prices remain high.', 'https://another.example/price', title='EV pricing'),
    Passage('charge', 'Electric vehicle demand is affected by limited charging stations.', 'https://demo.example/charge', title='EV charging'),
    Passage('battery', 'Electric vehicle demand battery resale value and degradation concerns influence purchases.', 'https://demo.example/battery', title='Battery resale hypothesis'),
    Passage('space', 'Astronomers discover distant galaxy using a new telescope.', 'https://demo.example/space', title='Space news'),
]

if run_clicked:
    try:
        embedder = None
        if semantic:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        model = FocusAttentionModel(question, exploration=novelty / 100,
            unresolved_questions=('What important alternative hypotheses might explain the outcome?',),
            embedder=embedder)
        search_queries = []
        live_search = mode != 'Demo passages'
        fast_preview = latency_mode == 'Fast preview'
        effective_search_budget = 1 if fast_preview else max_search_calls
        result_limit = 5 if fast_preview else 8
        if mode == 'Demo passages':
            passages = DEMO
            decisions = model.rank(passages)
            search_queries = ['[demo fixture — no network search]']
        else:
            from retrieval_adapters import search
            from research_loop import run_research

            def retrieve(query):
                return search(query, mode.lower(), max_results=result_limit)

            # Exploration controls the bounded follow-up budget. A focused run
            # makes the initial call; an exploratory run can investigate novel
            # candidates with targeted queries.
            query_plan = ()
            if not fast_preview:
                query_plan = tuple(
                    f'{question} {angle}' for angle in (
                        'main causes evidence',
                        'evidence challenging the premise',
                        'recent statistics and trends',
                        'consumer behavior and affordability',
                        'industry response and forecasts',
                    )
                )
            run = run_research(
                model, retrieve,
                max_search_calls=effective_search_budget,
                max_stagnant_batches=effective_search_budget,
                query_plan=query_plan,
            )
            decisions = run.decisions
            search_queries = run.queries

        grounded = None
        answer_warning = None
        if generate_answer:
            from answer_composer import AnswerGenerationError, compose_answer
            try:
                if live_search and not fast_preview:
                    from retrieval_adapters import hydrate_decisions
                    decisions = hydrate_decisions(decisions)
                grounded = compose_answer(
                    question, decisions, provider=answer_provider.lower(),
                    strict_citations=False,
                )
                if not grounded.cited_source_ids:
                    answer_warning = 'The model returned no recognized source citations. Showing its exact answer for inspection.'
            except AnswerGenerationError as exc:
                answer_warning = str(exc)

        st.subheader('Answer')
        if grounded is not None:
            st.markdown(grounded.markdown)
            if answer_warning:
                st.warning(answer_warning)
        elif generate_answer and answer_warning:
            st.warning(answer_warning)
        else:
            st.caption('Enable “Generate cited answer” to produce a user-facing answer from the selected evidence.')

        st.subheader('Search trace')
        trace = pd.DataFrame({
            'Call': list(range(1, len(search_queries) + 1)),
            'Query actually sent': search_queries,
        })
        st.dataframe(trace, hide_index=True, use_container_width=True)
        if live_search:
            actual_query_calls = len(search_queries)
            provider_requests = actual_query_calls * (2 if mode == 'Both' else 1)
            m1, m2, m3 = st.columns(3)
            m1.metric('Query calls', f'{actual_query_calls} / {effective_search_budget}')
            m2.metric('Provider requests', provider_requests)
            m3.metric('Results per request', result_limit)
            st.caption(
                f'Actual query calls: {actual_query_calls}. Allowed query calls: {effective_search_budget}. '
                f'Each “Both” query makes two provider requests. Follow-ups are only created for sources routed to investigate.'
            )
        else:
            st.caption('Demo passages are a fixed offline fixture; change Source mode to Tavily, Telem, or Both to make live searches.')
        counts = {a: sum(d.action == a for d in decisions)
                  for a in ('consider', 'investigate', 'archive')}
        c1,c2,c3=st.columns(3)
        c1.metric('Consider', counts['consider'])
        c2.metric('Investigate', counts['investigate'])
        c3.metric('Archive', counts['archive'])
        if not decisions:
            st.warning('No usable new passages were found.')
        df = pd.DataFrame([dict(title=d.passage.title, action=d.action,
            relevance=round(d.score.relevance, 3), novelty=round(d.score.novelty, 3),
            redundancy=round(d.score.redundancy, 3), attention=round(d.score.attention, 3),
            url=d.passage.url, reason=d.reason) for d in decisions])
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        if show_space and len(decisions) >= 2:
            try:
                import plotly.express as px
                rows = [{
                    'Source': d.passage.title or d.passage.text[:80],
                    'Action': d.action,
                    'URL': d.passage.url,
                    'Relevance': round(d.score.relevance, 3),
                    'Novelty': round(d.score.novelty, 3),
                    'Graph gap': round(d.score.graph_gap, 3),
                    'Attention': round(d.score.attention, 3),
                } for d in decisions]

                # Keep these axes tied to named policy scores in every mode.
                # Embeddings may improve the scores, but PCA axes would not be
                # interpretable as relevance or novelty.
                x_label, y_label, z_label = 'Intent alignment', 'Novelty', 'Unresolved-question alignment'
                for row in rows:
                    row[x_label] = row['Relevance']
                    row[y_label] = row['Novelty']
                    row[z_label] = row['Graph gap']
                caption = 'Axes are policy scores: intent alignment, evidence novelty, and unresolved-question alignment.'

                plot_df = pd.DataFrame(rows)
                figure = px.scatter_3d(
                    plot_df, x=x_label, y=y_label, z=z_label, color='Action',
                    hover_name='Source', hover_data=['URL', 'Attention', 'Relevance', 'Novelty', 'Graph gap'],
                    color_discrete_map={'consider': '#2ca02c', 'investigate': '#ff7f0e', 'archive': '#7f7f7f'},
                    title='Evidence context space',
                )
                figure.update_traces(marker={'size': 8, 'opacity': 0.86})
                figure.update_layout(margin={'l': 0, 'r': 0, 't': 45, 'b': 0}, legend_title_text='Policy action')
                st.plotly_chart(
                    figure, use_container_width=True,
                    config={'scrollZoom': True, 'displaylogo': False},
                )
                st.caption(caption + ' Drag to rotate, scroll to zoom, and hover a dot for source details.')
            except ImportError as exc:
                st.warning(f'Install visualization dependencies to view the 3D space: {exc}')
        st.subheader('Compact evidence candidates')
        st.json(model.evidence_packet())
        st.info('Investigate is a review queue. Generated answers synthesize considered evidence, but do not independently verify claims.')
    except Exception as exc:
        st.error(f'Run failed: {exc}')
