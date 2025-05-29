#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.

import os
from google.adk.tools import VertexAiSearchTool
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag
from google.genai import types


project_id = os.getenv("PROJECT_ID")
search_engine_location = os.getenv("SEARCH_ENGINE_LOCATION")
search_engine_collection = os.getenv("SEARCH_ENGINE_COLLECTION")
search_engine_id = os.getenv("SEARCH_ENGINE_ID")


def get_rag_engine_tool():

    ask_vertex_retrieval = VertexAiRagRetrieval(
        name='ask_vertex_retrieval',
        description=(
            'Use this tool to retrieve documentation and reference materials for the question about name meanings and origins,'
        ),
        rag_resources=[
            rag.RagResource(
                rag_corpus= "projects/andrebargas-sandbox/locations/us-central1/ragCorpora/6917529027641081856"
            )
        ],
        similarity_top_k=10,
        vector_distance_threshold=0.3,
    )
    return ask_vertex_retrieval


def get_vertex_search_tool():
    
    vertex_ai_search_tool = VertexAiSearchTool(
        search_engine_id=search_engine_id
    )
    return vertex_ai_search_tool
