# app/core/firebase.py
import firebase_admin
from firebase_admin import credentials, firestore, db
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class FirebaseService:
    """Firebase Admin SDK 통합 서비스"""
    
    def __init__(self):
        self.firestore_db = None
        self.realtime_db = None
        self._initialize()
    
    def _initialize(self):
        """Firebase 초기화 (Firestore + Realtime DB)"""
        try:
            # 이미 초기화되었는지 확인
            firebase_admin.get_app()
            print("✅ Firebase 앱이 이미 초기화되어 있습니다.")
        except ValueError:
            # 서비스 계정 키 로드
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
            
            if not Path(cred_path).exists():
                raise FileNotFoundError(
                    f"❌ Firebase 서비스 계정 키를 찾을 수 없습니다: {cred_path}"
                )
            
            cred = credentials.Certificate(cred_path)
            
            # Firebase 초기화 (Realtime DB URL 포함)
            database_url = os.getenv('FIREBASE_DATABASE_URL')
            
            if database_url:
                firebase_admin.initialize_app(cred, {
                    'databaseURL': database_url
                })
                print("✅ Firebase Admin SDK 초기화 완료! (Firestore + Realtime DB)")
            else:
                firebase_admin.initialize_app(cred)
                print("✅ Firebase Admin SDK 초기화 완료! (Firestore만)")
                print("⚠️  Realtime Database URL이 설정되지 않았습니다.")
        
        # Firestore 클라이언트
        self.firestore_db = firestore.client()
        
        # Realtime Database 레퍼런스
        try:
            self.realtime_db = db.reference()
            print("✅ Realtime Database 연결 완료")
        except Exception as e:
            print(f"⚠️  Realtime Database 연결 실패: {str(e)}")
            self.realtime_db = None
    
    def test_firestore(self):
        """Firestore 연결 테스트"""
        try:
            test_ref = self.firestore_db.collection('_test').document('firestore_test')
            test_data = {
                'message': 'Firestore 연결 테스트',
                'timestamp': firestore.SERVER_TIMESTAMP,
                'database': 'firestore'
            }
            test_ref.set(test_data)
            
            doc = test_ref.get()
            if doc.exists:
                print("✅ Firestore 테스트 성공!")
                result = doc.to_dict()
                test_ref.delete()  # 테스트 데이터 삭제
                return True, result
            else:
                print("❌ Firestore: 문서를 찾을 수 없습니다.")
                return False, None
                
        except Exception as e:
            print(f"❌ Firestore 테스트 실패: {str(e)}")
            return False, str(e)
    
    def test_realtime_db(self):
        """Realtime Database 연결 테스트"""
        try:
            if not self.realtime_db:
                return False, "Realtime Database가 초기화되지 않았습니다."
            
            # 테스트 데이터 작성
            test_ref = self.realtime_db.child('_test/realtime_test')
            test_data = {
                'message': 'Realtime DB 연결 테스트',
                'timestamp': {'.sv': 'timestamp'},
                'database': 'realtime'
            }
            test_ref.set(test_data)
            
            # 데이터 읽기
            result = test_ref.get()
            if result:
                print("✅ Realtime Database 테스트 성공!")
                test_ref.delete()  # 테스트 데이터 삭제
                return True, result
            else:
                print("❌ Realtime Database: 데이터를 찾을 수 없습니다.")
                return False, None
                
        except Exception as e:
            print(f"❌ Realtime Database 테스트 실패: {str(e)}")
            return False, str(e)
    
    def test_all(self):
        """모든 Firebase 서비스 테스트"""
        print("\n" + "="*50)
        print("🔥 Firebase 통합 테스트 시작")
        print("="*50 + "\n")
        
        results = {}
        
        # Firestore 테스트
        print("1️⃣ Firestore 테스트 중...")
        firestore_success, firestore_data = self.test_firestore()
        results['firestore'] = {
            'success': firestore_success,
            'data': firestore_data
        }
        
        # Realtime Database 테스트
        print("\n2️⃣ Realtime Database 테스트 중...")
        realtime_success, realtime_data = self.test_realtime_db()
        results['realtime_db'] = {
            'success': realtime_success,
            'data': realtime_data
        }
        
        # 결과 요약
        print("\n" + "="*50)
        print("📊 테스트 결과 요약")
        print("="*50)
        print(f"Firestore: {'✅ 성공' if firestore_success else '❌ 실패'}")
        print(f"Realtime DB: {'✅ 성공' if realtime_success else '❌ 실패'}")
        print("="*50 + "\n")
        
        return results

# 싱글톤 인스턴스
firebase_service = FirebaseService()

# Export
firestore_db = firebase_service.firestore_db
realtime_db = firebase_service.realtime_db