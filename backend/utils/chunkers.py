from langchain.text_splitter import RecursiveCharacterTextSplitter
# function definition----#
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50, split_by_words: bool = False):
    """
    Splits text into overlapping chunks using a recursive splitter.
    Safer than simple word-split for embeddings.

    Parameters:
        text (str): The input text to be chunked.
        chunk_size (int): The maximum size of each chunk (default is 500).
        overlap (int): The number of characters to overlap between chunks (default is 50).
        split_by_words (bool): If True, chunks will be split by words instead of characters (default is False).
    
    Returns:
        List[str]: A list of text chunks.
    """
    # Set up the text splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len if not split_by_words else lambda x: len(x.split())
    )
    
    try:
        # Split the text into chunks
        chunked_documents = splitter.create_documents([text])
        return [chunk.page_content for chunk in chunked_documents]
    except Exception as e:
        raise ValueError(f"Error chunking text: {e}")
