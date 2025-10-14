#!/usr/bin/env python3
"""
Модуль для работы с S3 хранилищем state.json
"""
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path
from typing import Dict, Set
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class S3Storage:
    def __init__(self):
        # Параметры S3 из изображения
        self.endpoint_url = "https://s3.twcstorage.ru"
        self.bucket_name = "6ddcc6a4-ac782675-1c0e-4e0c-b26f-32ab5d7e6ff3"
        self.region = "ru-1"
        self.object_key = "vinyl-monitor/state.json"
        
        # Инициализируем S3 клиент
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )
    
    @property
    def access_key(self) -> str:
        """Получает S3 Access Key из переменных окружения"""
        import os
        key = os.getenv('S3_ACCESS_KEY')
        if not key:
            raise ValueError("S3_ACCESS_KEY не установлен в переменных окружения")
        return key
    
    @property
    def secret_key(self) -> str:
        """Получает S3 Secret Access Key из переменных окружения"""
        import os
        key = os.getenv('S3_SECRET_KEY')
        if not key:
            raise ValueError("S3_SECRET_KEY не установлен в переменных окружения")
        return key
    
    def download_state(self) -> Dict:
        """Загружает state.json из S3"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=self.object_key
            )
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.info("state.json не найден в S3, возвращаем пустое состояние")
                return {"known_items": {}}
            else:
                logger.error(f"Ошибка загрузки из S3: {e}")
                raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке из S3: {e}")
            raise
    
    def upload_state(self, state_data: Dict) -> bool:
        """Загружает state.json в S3"""
        try:
            json_content = json.dumps(state_data, ensure_ascii=False, indent=2)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=self.object_key,
                Body=json_content.encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.info("state.json успешно загружен в S3")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки в S3: {e}")
            return False
    
    def load_known_items(self) -> Set[str]:
        """Загружает список известных ID из S3"""
        try:
            data = self.download_state()
            if "known_items" in data and isinstance(data["known_items"], dict):
                # Импортируем normalize_url из основного модуля
                from vinyl_monitor import normalize_url
                return {normalize_url(item_id) for item_id in data["known_items"].keys()}
            else:
                return set()
        except Exception as e:
            logger.error(f"Ошибка загрузки известных элементов: {e}")
            return set()
    
    def save_new_items(self, known_ids: Set[str], new_items: list) -> bool:
        """Сохраняет новые элементы в S3"""
        try:
            # Загружаем текущее состояние
            existing_data = self.download_state()
            
            # Добавляем новые элементы
            if new_items:
                from datetime import datetime
                current_time = datetime.now().isoformat()
                
                for item in new_items:
                    item_id = item.get("id", "")
                    if item_id:
                        from vinyl_monitor import normalize_url
                        normalized_id = normalize_url(item_id)
                        existing_data.setdefault("known_items", {})[normalized_id] = {
                            "added_at": current_time,
                            "title": item.get("title", ""),
                            "source": item.get("source", "")
                        }
            
            # Сохраняем обратно в S3
            return self.upload_state(existing_data)
            
        except Exception as e:
            logger.error(f"Ошибка сохранения новых элементов: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Тестирует подключение к S3"""
        try:
            # Пробуем получить список объектов
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=self.object_key.rsplit('/', 1)[0],  # Папка
                MaxKeys=1
            )
            logger.info("✅ Подключение к S3 успешно")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к S3: {e}")
            return False


if __name__ == "__main__":
    # Тест подключения
    storage = S3Storage()
    if storage.test_connection():
        print("✅ S3 подключение работает")
        
        # Тест загрузки/сохранения
        state = storage.download_state()
        print(f"📊 Загружено {len(state.get('known_items', {}))} позиций из S3")
    else:
        print("❌ S3 подключение не работает")
