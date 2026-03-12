from sentence_transformers import CrossEncoder

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerankResults(query, chunks):

    pairs = [[query, c["text"]] for c in chunks]

    scores = model.predict(pairs)

    ranked = sorted(zip(scores, chunks), reverse=True)

    return [r[1] for r in ranked[:5]]