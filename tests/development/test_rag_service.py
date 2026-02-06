import os

from tools.rag_service import RAGService


def test_rag_service():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment")
        print("Please set it in .env file")
        return

    print("🧪 Testing RAG Service...\n")

    from google import genai

    # Инициализируем клиента (вместо genai.configure)
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    # Получаем список моделей
    for model in client.models.list():
        print(f"Доступная модель: {model.name}")

    rag = RAGService(google_api_key=api_key)

    test_queries = [
        "What is CostCare AI?",
        "What are the pricing plans?",
        "How does CostCare AI integrate with existing systems?",
        "What security features does CostCare AI have?",
    ]

    for query in test_queries:
        print(f"Query: {query}")
        print("-" * 60)

        context = rag.search(query, k=2)
        print(f"Context (truncated):\n{context[:300]}...\n")
        print("=" * 60 + "\n")


test_rag_service()
