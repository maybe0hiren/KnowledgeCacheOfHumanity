from sentence_transformers import SentenceTransformer as ST
import numpy as np


model = ST("all-MiniLM-L6-v2")

def getEmbeddings(text: str):
    embeddings = model.encode(text)
    return embeddings

def getSimilarity(emb1, emb2):
    emb1 = np.array(emb1)
    emb2 = np.array(emb2)

    dot = np.dot(emb1, emb2)

    emb1 = np.linalg.norm(emb1)
    emb2 = np.linalg.norm(emb2)

    similarity = dot/(emb1*emb2)
    return similarity 
