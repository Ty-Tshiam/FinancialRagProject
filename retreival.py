from pinecone import Pinecone
from ingestion import embedding
import os
from dotenv import find_dotenv, load_dotenv
import voyageai
load_dotenv(find_dotenv())




index = pc.Index(index_name)

vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


def query_vdb(query : str):

    # Use "query" input type for queries
    q_vector = embedding([query], input_type="query", client = vo, model_id = embed_model)

    results = index.query(
        namespace="ns1",
        vector=q_vector[0],
        top_k=5,
        include_values=False,
        include_metadata=True
    )

    return results["matches"]

import os 
from langchain_voyageai import VoyageAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from pinecone import Pinecone
from langchian_google_genai import ChatGoogleGenerativeAI

embed_model = "voyage-finance-2"

embeddings = VoyageAIEmbeddings(
    model = embed_model,
    voyage_api_key = os.environ["VOYAGE_API_KEY"]
)

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index_name = "voyage-finance-2"

vectore_store = PineconeVectorStore(
    index_name = index_name,
    embedding = embeddings
)

metadat_field_info = [
        AttributeInfo(name="ticker", description="The stock ticker symbol, e.g., 'TD'", type="string"),
        AttributeInfo(name="calendar_year", description="The calendar year of the report, e.g., '2025'", type="string"),
        AttributeInfo(name="fiscal_quarter", description="The quarter, e.g., 'Q1', 'Q3', 'Annual'", type="string"),
        AttributeInfo(name="is_table", description="true if the user wants hard data/numbers, false for narrative text", type="boolean"),
        AttributeInfo(name="financial_tags", description="List of financial concepts, e.g., ['Risk', 'Revenue', 'Capital']", type="list[string]"),
        AttributeInfo(name="is_audited", description="Whether the financial statement has been audited by an external firm. true for annual reports (10-K), false for quarterly reports (10-Q)", type="boolean"),
        AttributeInfo(name="document_type", description="The category of the document. e.g., '10-K', '10-Q', 'Earnings Transcript'", type="string"),
    ]

document_content_description = "A chunk of a financial quarterly, annual report, or earnings transcript."
retreiver = SelfQueryRetriever