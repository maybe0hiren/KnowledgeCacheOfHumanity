from keybert import KeyBERT

kwModel = KeyBERT()

def generateQueries(text):

    keywords = kwModel.extract_keywords(text, keyphrase_ngram_range=(1,3), stop_words="english", top_n=5)

    queries = [k[0] for k in keywords]

    queries.append(text)

    return queries