"""Small reproducible offline demo; not an accuracy or market benchmark."""
from focus_attention import FocusAttentionModel, Passage

question='why is electric vehicle demand weakening'
passages=[
    Passage('1','why electric vehicle demand weakens due to high prices', 'https://a.example'),
    Passage('2','why electric vehicle demand weakens due to high prices', 'https://b.example'),
    Passage('3','electric vehicle demand battery resale', 'https://c.example'),
    Passage('4','electric vehicle demand charging limitations', 'https://d.example'),
    Passage('5','galaxies and distant telescope observations', 'https://e.example'),
]
model=FocusAttentionModel(question, exploration=0.7)
results=model.rank(passages)
for d in results:
    print(f'{d.action:12s}  rel={d.score.relevance:.2f} '
          f'novelty={d.score.novelty:.2f}  {d.passage.id}')
raw=sum(len(p.text.split()) for p in passages)
selected=sum(len(d.passage.text.split()) for d in model.state.accepted)
print(f'Example whitespace-token count: raw={raw}, selected={selected}; '
      'not a billed token measurement or answer-quality benchmark')
