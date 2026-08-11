"""
腾讯云 COS 连接器模块
支持从 COS 拉取文件并同步到本地
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

from qcloud_cos import CosConfig, CosS3Client


class COSConnector:
    """COS 连接器"""
    
    def __init__(self, secret_id: str, secret_key: str, region: str):
        config = CosConfig(
            Region=region,
            SecretId=secret_id,
            SecretKey=secret_key,
            Scheme='https'
        )
        self.client = CosS3Client(config)
        self.region = region
    
    def list_files(self, bucket: str, prefix: str = "") -> List[Dict[str, Any]]:
        """列出 COS 桶中的文件"""
        marker = ""
        files = []
        
        while True:
            response = self.client.list_objects(
                Bucket=bucket,
                Prefix=prefix,
                Marker=marker,
                MaxKeys=1000
            )
            
            if 'Contents' in response:
                for item in response['Contents']:
                    # 跳过目录占位符
                    if item['Key'].endswith('/'):
                        continue
                    files.append({
                        'key': item['Key'],
                        'size': int(item['Size']),
                        'last_modified': item['LastModified'],
                        'etag': item['ETag'].strip('"')
                    })
            
            if response.get('IsTruncated') == 'false':
                break
            marker = response.get('NextMarker', '')
        
        return files
    
    def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        """下载单个文件到本地"""
        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            response = self.client.get_object(
                Bucket=bucket,
                Key=key
            )
            response['Body'].get_stream_to_file(local_path)
            return True
        except Exception as e:
            print(f"下载失败 {key}: {e}")
            return False
    
    def sync_prefix(self, bucket: str, prefix: str, local_dir: str) -> List[str]:
        """
        同步 COS 前缀下的所有文件到本地目录
        
        Returns:
            List[str]: 下载的文件路径列表
        """
        files = self.list_files(bucket, prefix)
        downloaded = []
        
        for file_info in files:
            key = file_info['key']
            # 计算本地路径，剥离前缀
            relative_path = key[len(prefix):] if prefix else key
            # 防止 relative_path 以 / 开头导致 os.path.join 覆盖根目录
            relative_path = relative_path.lstrip('/')
            
            # 跳过空路径（比如前缀本身作为目录被返回时）
            if not relative_path:
                continue
                
            local_path = os.path.join(local_dir, relative_path)
            
            # 确保本地目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 如果文件已存在且大小相同，跳过
            if os.path.exists(local_path):
                local_size = os.path.getsize(local_path)
                if local_size == file_info['size']:
                    continue
            
            if self.download_file(bucket, key, local_path):
                downloaded.append(local_path)
        
        return downloaded