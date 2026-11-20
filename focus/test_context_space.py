"""Standalone chart axes and the installed Plotly selection limit."""

from pathlib import Path

from context_space import (
    AXIS_X,
    AXIS_Y,
    AXIS_Z,
    evidence_id_from_plotly_selection,
    figure_from_focus_decisions,
    points_from_recorded,
)
from focus_attention import FocusAttentionModel, Passage


def test_standalone_chart_keeps_named_axes_and_not_pca():
    model = FocusAttentionModel(
        "Why might electric vehicle demand decline?",
        unresolved_questions=("What important alternative hypotheses might explain the outcome?",),
    )
    decisions = model.rank([
        Passage("price", "Electric vehicle demand can decline because purchase prices remain high.", "https://demo.example/price", title="EV pricing"),
        Passage("charge", "Electric vehicle demand is affected by limited charging stations.", "https://demo.example/charge", title="EV charging"),
    ])
    figure = figure_from_focus_decisions(decisions)
    scene = figure.layout.scene
    assert scene.xaxis.title.text == AXIS_X
    assert scene.yaxis.title.text == AXIS_Y
    assert scene.zaxis.title.text == AXIS_Z
    assert "PC" not in scene.xaxis.title.text
    custom = []
    for trace in figure.data:
        data = trace.customdata
        if data is None:
            continue
        for row in data:
            custom.extend(row if not isinstance(row, str) else [row])
    assert "price" in custom
    assert "charge" in custom


def test_recorded_space_does_not_invent_missing_coordinates():
    trace = {"events": [{"id": "evt"}], "investigation_id": "inv", "search_event_count": 0}
    checkpoint = {
        "id": "cp",
        "step": 1,
        "state_json": {
            "policy_space": [{"evidence_id": "cand", "title": "Missing novelty"}],
            "snapshot": {"candidates": [{"id": "cand"}]},
        },
    }
    view = points_from_recorded(trace, [checkpoint], "cp")
    assert view.points == ()
    assert view.omitted == 1


def test_plotly_selection_parser_requires_an_evidence_id():
    assert evidence_id_from_plotly_selection(None) is None
    assert evidence_id_from_plotly_selection({"selection": {"points": []}}) is None
    assert evidence_id_from_plotly_selection({"points": [{"id": "sunburst", "parent": "root"}]}) is None
    assert evidence_id_from_plotly_selection({"points": [{"customdata": "cand_1"}]}) == "cand_1"
    assert evidence_id_from_plotly_selection({"selection": {"points": [{"customdata": ["cand_2", "inv"]}]}}) == "cand_2"


def test_installed_streamlit_discards_scatter3d_clicks_without_parent_id():
    streamlit = __import__("streamlit")
    matches = list(Path(streamlit.__file__).parent.glob("static/static/js/PlotlyChart*.js"))
    assert matches
    text = matches[0].read_text(errors="ignore")
    assert "i.id===void 0||i.parent===void 0" in text
    component = Path(__file__).resolve().parent / "context_space_component" / "index.html"
    html = component.read_text(encoding="utf-8")
    assert "plotly_click" in html
    assert "customdata" in html


def test_reader_does_not_call_the_focus_ranker():
    source = Path(__file__).resolve().parent.joinpath("context_space.py").read_text(encoding="utf-8")
    assert "FocusAttentionModel" not in source
    assert "PCA" not in source or "PCA is not" in source
