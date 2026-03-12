from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-mpnet-base-v2")

def embedTexts(texts):

    vectors = model.encode(texts)

    return vectors