def chunkDocuments(pages, chunkSize=500):

    chunks = []

    for page in pages:

        text  = page.get("content") or ""
        words = text.split()

        for i in range(0, len(words), chunkSize):
            part = " ".join(words[i:i+chunkSize])
            chunks.append({
                "text":  part,
                "url":   page["url"],
                "title": page["title"]
            })

    return chunks