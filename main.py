from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# 1. 加载文档
loader = TextLoader("data/raw_docs/obe.txt", encoding="utf-8")
documents = loader.load()

# 2. 文本切分
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=50
)
docs = text_splitter.split_documents(documents)

# 3. 向量化
embedding = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# 4. 构建向量库
vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embedding,
    persist_directory="./chroma_db"
)

# 5. 检索测试
query = "什么是成果导向教育？"
results = vectorstore.similarity_search(query, k=2)

print("问题：", query)
print("检索结果：")
for i, doc in enumerate(results, 1):
    print(f"\n--- 文档 {i} ---")
    print(doc.page_content)
