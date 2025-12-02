"""
BentoML AI 추천 서비스 - OpenAI RAG 기반
기존 model/module.py를 BentoML로 통합
"""

import bentoml
from typing import Dict, List, Any, Optional
import json
import os
import requests
from openai import OpenAI


# ==================== Prompt ====================

WEB_RAG_PROMPT = """
너는 올리브영 제품 추천 전문가이다.

사용자 질문:
{query}

아래는 웹에서 수집한 올리브영 관련 정보이다:
{documents}

[규칙]
- 반드시 실제 올리브영에서 판매 중인 제품명만 추천해야 한다.
- 제품명은 일반 표현이 아니라 정확한 브랜드 + 제품명으로 작성한다.
- 최소 3개 이상 추천한다.
- 각 제품마다:
  1. 제품명
  2. 간단한 설명
  3. 왜 사용자의 요청("{query}")에 적합한지
  를 포함한다.
- 문서에 없는 제품은 절대 임의로 만들어내지 마라.

[출력 형식]
1. 제품명: ...
   설명: ...
   추천 이유: ...
   
답변:
"""


# ==================== Retriever ====================

class Retriever:
    """Tavily API 기반 웹 검색"""
    
    def __init__(self, api_key: str, top_k: int = 5):
        self.api_key = api_key
        self.endpoint = "https://api.tavily.com/search"
        self.top_k = top_k

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Tavily API로 검색"""
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": self.top_k,
            "include_answer": False,
            "include_images": False,
        }

        try:
            resp = requests.post(self.endpoint, json=payload, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            documents: List[Dict[str, Any]] = []

            for r in results[: self.top_k]:
                doc = {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", r.get("snippet", "")),
                }
                documents.append(doc)

            return documents
            
        except Exception as e:
            print(f"Tavily 검색 실패: {str(e)}")
            return []

    def web_retrieve(self, query: str) -> List[Dict[str, Any]]:
        """올리브영 사이트에서 상품 검색"""
        search_query = query + " site:oliveyoung.co.kr 상품 구매 후기"
        documents = self.search(search_query)
        return documents


# ==================== Generator ====================

class Generator:
    """OpenAI GPT 기반 추천 생성"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", 
                 max_token: int = 1000, temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.max_token = max_token
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key)

    def get_prompt(self, query: str, documents: List[Dict[str, Any]]) -> str:
        """문서를 프롬프트에 포함"""
        doc_blocks = []
        for idx, doc in enumerate(documents, start=1):
            title = doc.get("title", "")
            url = doc.get("url", "")
            content = doc.get("content", "")
            block = (
                f"[문서 {idx}]\n"
                f"제목: {title}\n"
                f"URL: {url}\n"
                f"내용: {content}\n"
            )
            doc_blocks.append(block)

        documents_text = "\n\n".join(doc_blocks)
        prompt = WEB_RAG_PROMPT.format(
            query=query,
            documents=documents_text
        )
        return prompt

    def generate(self, query: str, documents: List[Dict[str, Any]]) -> str:
        """OpenAI로 추천 생성"""
        prompt = self.get_prompt(query, documents)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """
- 반드시 실제 올리브영에서 판매 중인 제품명만 추천해야 한다.
- 제품명은 일반 표현이 아니라 정확한 브랜드 + 제품명으로 작성한다.
"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    },
                ],
                max_tokens=self.max_token,
                temperature=self.temperature,
            )

            generation = response.choices[0].message.content
            return generation
            
        except Exception as e:
            print(f"OpenAI 생성 실패: {str(e)}")
            return f"죄송합니다. 추천을 생성할 수 없습니다: {str(e)}"


# ==================== BentoML Service ====================

@bentoml.service(
    resources={"cpu": "2"},
    traffic={"timeout": 60},  # RAG는 시간이 더 걸림
)
class TemiAIRecommender:
    """Temi AI 추천 서비스 - OpenAI RAG 기반"""
    
    def __init__(self):
        # Config 로드
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            # 기본값 (환경 변수 사용)
            config = {
                "retriever": {
                    "api_key": os.getenv("TAVILY_API_KEY", ""),
                    "top_k": 5
                },
                "generator": {
                    "api_key": os.getenv("OPENAI_API_KEY", ""),
                    "model": "gpt-4o-mini",
                    "max_token": 1000,
                    "temperature": 0.7
                }
            }
        
        # Retriever & Generator 초기화
        self.retriever = Retriever(**config["retriever"])
        self.generator = Generator(**config["generator"])
        
        print("✅ TemiAIRecommender 초기화 완료 (OpenAI RAG)")
    
    @bentoml.api
    def chat(
        self, 
        query: str, 
        customer_id: Optional[str] = None, 
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        질문 기반 추천 (RAG)
        
        1. Tavily로 올리브영 웹 검색
        2. OpenAI GPT로 추천 생성
        """
        print(f"📝 질문: {query}")
        
        # 1. 웹 검색 (Retrieval)
        print("🔍 웹 검색 중...")
        documents = self.retriever.web_retrieve(query)
        print(f"   검색 결과: {len(documents)}개 문서")
        
        # 2. 추천 생성 (Generation)
        print("🤖 OpenAI 추천 생성 중...")
        answer = self.generator.generate(query, documents)
        print(f"   생성 완료: {len(answer)} 글자")
        
        return {
            "success": True,
            "query": query,
            "answer": answer,
            "documents_count": len(documents),
            "sources": [doc.get("url", "") for doc in documents[:3]]
        }
    
    @bentoml.api
    def recommend(
        self,
        skin_type: Optional[str] = None,
        category: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        필터 기반 추천 (RAG)
        필터를 자연어 질문으로 변환하여 처리
        """
        # 필터를 자연어로 변환
        query_parts = []
        
        if skin_type:
            query_parts.append(f"{skin_type} 피부")
        if category:
            query_parts.append(f"{category}")
        if price_max:
            query_parts.append(f"{price_max//10000}만원 이하")
        
        query = " ".join(query_parts) + "에 좋은 제품 추천해줘"
        
        # chat API 재사용
        return self.chat(query=query, limit=limit)
    
    @bentoml.api
    def health(self) -> Dict[str, Any]:
        """헬스 체크"""
        return {
            "status": "healthy",
            "service": "temi_ai_recommender",
            "mode": "OpenAI RAG",
            "retriever": "Tavily",
            "generator": "OpenAI GPT"
        }
