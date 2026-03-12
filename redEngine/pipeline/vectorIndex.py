import faiss
import numpy as np

def searchSimilar(queryVector, chunkVectors, chunks, k=10):

    vectors = np.array(chunkVectors).astype("float32")

    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)

    query = np.array(queryVector).astype("float32")

    if query.ndim == 1:
        query = query.reshape(1, -1)

    dim = vectors.shape[1]

    if query.shape[1] != dim:
        query = query[:, :dim]

    index = faiss.IndexFlatL2(dim)
    index.add(vectors)

    distances, ids = index.search(query, min(k, len(vectors)))

    results = []

    for i in ids[0]:
        if i < len(chunks):
            results.append(chunks[i])

    return results