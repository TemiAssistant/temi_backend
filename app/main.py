# app/main.py

import logging

# 로깅 설정 - DEBUG 레벨로
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.firebase import firebase_service, firestore_db, realtime_db
from firebase_admin import firestore
from dotenv import load_dotenv
import os
from datetime import datetime

# ==================== 👇 추가: API 라우터 import ====================
from app.api import products
from app.api import payment  # 결제 API 라우터
from app.api import inventory
from app.api.ai_recommendations import router as ai_router
from app.core.mqtt_client import mqtt_bridge

load_dotenv()

app = FastAPI(
    title=os.getenv("PROJECT_NAME", "올리브영 Smart Cart API"),
    version="1.0.0",  # 👈 수정: 0.1.0 → 1.0.0
    description="Temi 로봇 기반 스마트 쇼핑 시스템 - Firebase 통합",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ==================== 👇 추가: CORS 미들웨어 ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 specific origins 사용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 👇 추가: API 라우터 등록 ====================
app.include_router(products.router)
app.include_router(payment.router)  # 결제 API 라우터 등록
app.include_router(inventory.router)
app.include_router(ai_router)
# ==================== 기본 엔드포인트 ====================

@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "status": "healthy",
        "message": "올리브영 Smart Cart API",
        "version": "1.0.0",  # 👈 수정
        "firebase": {
            "firestore": "connected" if firestore_db else "disconnected",
            "realtime_db": "connected" if realtime_db else "disconnected"
        },
        "docs": "/docs",  # 👈 추가
        "endpoints": {  # 👈 추가: API 목록
            "ai_chat": "/api/ai/chat",
            "ai_recommend": "/api/ai/recommend",
            "products": "/api/products",
            "payments": "/api/payments",
            "inventory": "/api/inventory",
            "test": "/test"
        }
    }

@app.get("/health")
async def health_check():
    """헬스 체크 - 모든 서비스 상태 확인"""
    firestore_ok, _ = firebase_service.test_firestore()
    realtime_ok, _ = firebase_service.test_realtime_db()
    
    all_healthy = firestore_ok and realtime_ok
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": {
            "api": "running",
            "firestore": "connected" if firestore_ok else "disconnected",
            "realtime_db": "connected" if realtime_ok else "disconnected"
        },
        "timestamp": datetime.now().isoformat()
    }


@app.on_event("startup")
async def on_startup():
    """애플리케이션 시작 시 MQTT 브리지를 활성화."""
    mqtt_bridge.start()


@app.on_event("shutdown")
async def on_shutdown():
    """애플리케이션 종료 시 MQTT 연결을 정리."""
    mqtt_bridge.stop()


# ==================== Firestore 테스트 엔드포인트 ====================

@app.get("/test/firestore")
async def test_firestore_connection():
    """Firestore 연결 테스트"""
    try:
        success, data = firebase_service.test_firestore()
        
        if success:
            return {
                "success": True,
                "message": "Firestore 연결 성공!",
                "data": data
            }
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Firestore 연결 실패",
                    "error": data
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/test/firestore/write")
async def write_to_firestore(collection: str, document: str, data: dict):
    """Firestore 쓰기 테스트"""
    try:
        firestore_db.collection(collection).document(document).set({
            **data,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return {
            "success": True,
            "message": f"✅ Firestore에 데이터 저장 완료: {collection}/{document}",
            "data": data
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/test/firestore/read/{collection}/{document}")
async def read_from_firestore(collection: str, document: str):
    """Firestore 읽기 테스트"""
    try:
        doc = firestore_db.collection(collection).document(document).get()
        
        if doc.exists:
            return {
                "success": True,
                "message": "✅ Firestore 데이터 읽기 성공",
                "data": doc.to_dict(),
                "document_id": doc.id
            }
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": f"❌ 문서를 찾을 수 없습니다: {collection}/{document}"
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/test/firestore/list/{collection}")
async def list_firestore_collection(collection: str, limit: int = 10):
    """Firestore 컬렉션 목록 조회"""
    try:
        docs = firestore_db.collection(collection).limit(limit).stream()
        
        results = []
        for doc in docs:
            results.append({
                "id": doc.id,
                "data": doc.to_dict()
            })
        
        return {
            "success": True,
            "collection": collection,
            "count": len(results),
            "documents": results
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ==================== Realtime Database 테스트 엔드포인트 ====================

@app.get("/test/realtime")
async def test_realtime_connection():
    """Realtime Database 연결 테스트"""
    try:
        success, data = firebase_service.test_realtime_db()
        
        if success:
            return {
                "success": True,
                "message": "Realtime Database 연결 성공!",
                "data": data
            }
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Realtime Database 연결 실패",
                    "error": data
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/test/realtime/write")
async def write_to_realtime(path: str, data: dict):
    """Realtime Database 쓰기 테스트"""
    try:
        if not realtime_db:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "message": "Realtime Database가 초기화되지 않았습니다."
                }
            )
        
        ref = realtime_db.child(path)
        ref.set({
            **data,
            "timestamp": {'.sv': 'timestamp'}
        })
        
        return {
            "success": True,
            "message": f"✅ Realtime DB에 데이터 저장 완료: {path}",
            "data": data
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/test/realtime/read/{path:path}")
async def read_from_realtime(path: str):
    """Realtime Database 읽기 테스트"""
    try:
        if not realtime_db:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "message": "Realtime Database가 초기화되지 않았습니다."
                }
            )
        
        ref = realtime_db.child(path)
        data = ref.get()
        
        if data:
            return {
                "success": True,
                "message": "✅ Realtime DB 데이터 읽기 성공",
                "path": path,
                "data": data
            }
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": f"❌ 데이터를 찾을 수 없습니다: {path}"
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ==================== 통합 테스트 ====================

@app.get("/test/all")
async def test_all_services():
    """모든 Firebase 서비스 통합 테스트"""
    results = firebase_service.test_all()
    
    all_success = all(
        service['success'] 
        for service in results.values()
    )
    
    return {
        "success": all_success,
        "message": "✅ 모든 테스트 통과!" if all_success else "⚠️ 일부 테스트 실패",
        "results": results,
        "timestamp": datetime.now().isoformat()
    }
