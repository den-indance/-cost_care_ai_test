import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        knowledge_base_path: str = "./data/knowledge_base/",
        persist_directory: str = "./data/chroma_db/",
        google_api_key: Optional[str] = None,
        model_name: str = "models/gemini-embedding-001",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be provided or set in environment variables")

        self.knowledge_base_path = Path(knowledge_base_path)
        self.persist_directory = persist_directory
        self.model_name = model_name

        if chunk_size <= chunk_overlap:
            raise ValueError("chunk_size must be greater than chunk_overlap")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.embeddings = GoogleGenerativeAIEmbeddings(model=self.model_name, google_api_key=self.api_key)
        self.vectorstore = self._load_or_create_vectorstore()
        logger.info(f"RAG Service initialized with model: {self.model_name}")

    def _load_or_create_vectorstore(self) -> Chroma:
        persist_path = Path(self.persist_directory)
        sqlite_db = persist_path / "chroma.sqlite3"

        if persist_path.exists() and sqlite_db.exists():
            logger.info(f"Loading existing vector store from {self.persist_directory}")
            return Chroma(persist_directory=self.persist_directory, embedding_function=self.embeddings)

        return self._build_new_index()

    def _build_new_index(self) -> Chroma:
        logger.info("Creating new vector store from knowledge base...")

        if not self.knowledge_base_path.exists():
            raise FileNotFoundError(f"Path not found: {self.knowledge_base_path}")

        loader = DirectoryLoader(
            str(self.knowledge_base_path), glob="**/*.md", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}
        )

        documents = loader.load()
        if not documents:
            raise ValueError("No .md files found in knowledge base.")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap, separators=["\n\n", "\n", " ", ""]
        )

        splits = text_splitter.split_documents(documents)

        return Chroma.from_documents(
            documents=splits, embedding=self.embeddings, persist_directory=self.persist_directory
        )

    def search(self, query: str, k: int = 3) -> str:
        if not query.strip():
            return "Empty query provided."

        try:
            docs = self.vectorstore.similarity_search(query, k=k)
            if not docs:
                return "No relevant information found."

            return "\n\n---\n\n".join([doc.page_content for doc in docs])
        except Exception as e:
            logger.error(f"Search error: {e}")
            raise ValueError(f"Search error: {e}")

    def rebuild_index(self) -> None:
        logger.warning("Rebuilding index...")
        if Path(self.persist_directory).exists():
            shutil.rmtree(self.persist_directory)
        self.vectorstore = self._build_new_index()
