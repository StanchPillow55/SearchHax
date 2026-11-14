"""Streamlit interface: pip install -r requirements.txt; streamlit run app.py"""
import os
import streamlit as st
import pandas as pd
from focus_attention import FocusAttentionModel, Passage

st.set_page_config(page_title='Context Frontier', layout='wide')
st.title('Context Frontier')
st.caption('Choose how tightly to stay on the question and how many searches the controller may use. Evidence selection, not truth verification.')
question = st.text_input('Original research question', 'Why might electric vehicle demand decline?')
st.subheader('Attention policy')
policy_col, budget_col = st.columns(2)
with policy_col:
    novelty = st.slider(
        'Evidence balance — Focused (left) → Exploratory (right)',
        min_value=0, max_value=100, value=50,
        help='Focused keeps the context close to the question. Exploratory admits more novel, intent-relevant evidence for investigation.',
    )
    st.caption('← **Focused** · tighter context | more novel findings · **Exploratory** →')
with budget_col:
    max_search_calls = st.slider(
        'Search budget — One search (left) → More follow-ups (right)',
        min_value=1, max_value=6, value=3,
        help='The maximum number of live retrieval calls, including the initial search.',
    )
    st.caption('← **One search** · lower cost | more follow-up searches · **More searches** →')
mode = st.selectbox('Source mode', ['Demo passages', 'Tavily', 'Telem', 'Both'])
latency_mode = st.radio(
    'Latency mode',
    ['Fast preview', 'Deep investigation'],
    horizontal=True,
    help='Fast preview makes one small retrieval call and uses snippets. Deep investigation may run follow-ups and fetch full pages before answering.',
)
semantic = st.checkbox('Use semantic embeddings (requires sentence-transformers)', value=False)
show_space = st.checkbox('Show interactive 3D context space', value=True)
generate_answer = st.checkbox('Generate cited answer (requires an answer-model API key)', value=False)
answer_provider = st.selectbox('Answer provider', ['Auto', 'Local', 'Gemini', 'OpenAI']) if generate_answer else 'Auto'

DEMO = [
    Passage('price', 'Electric vehicle demand can decline because purchase prices remain high.', 'https://demo.example/price', title='EV pricing'),
    Passage('price2', 'Electric vehicle demand can decline because purchase prices remain high.', 'https://another.example/price', title='EV pricing'),
    Passage('charge', 'Electric vehicle demand is affected by limited charging stations.', 'https://demo.example/charge', title='EV charging'),
    Passage('battery', 'Electric vehicle demand battery resale value and degradation concerns influence purchases.', 'https://demo.example/battery', title='Battery resale hypothesis'),
    Passage('space', 'Astronomers discover distant galaxy using a new telescope.', 'https://demo.example/space', title='Space news'),
]

if st.button('Run research selection', type='primary'):
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
