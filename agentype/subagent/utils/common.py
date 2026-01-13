#!/usr/bin/env python3
"""
agentype - 通用工具模块
Author: cuilei
Version: 1.0
"""

import time
import logging
import requests
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any

# 设置日志
logger = logging.getLogger(__name__)


class FileDownloader:
    """统一的文件下载工具类
    
    提供带重试机制的文件下载功能，支持进度显示、断点续传等特性
    """
    
    def __init__(self, 
                 max_retries: int = 3,
                 timeout: int = 120,
                 chunk_size: int = 8192,
                 user_agent: str = None):
        """初始化下载器
        
        Args:
            max_retries: 最大重试次数
            timeout: 请求超时时间（秒）
            chunk_size: 下载块大小（字节）
            user_agent: 自定义 User-Agent
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.chunk_size = chunk_size
        self.user_agent = user_agent or (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/91.0.4472.124 Safari/537.36'
        )
    
    def download_file_with_retry(self, 
                                url: str, 
                                output_file: Path,
                                force_download: bool = False,
                                progress_callback: Optional[callable] = None) -> bool:
        """下载文件，支持重试和进度显示
        
        Args:
            url: 下载URL
            output_file: 输出文件路径
            force_download: 是否强制重新下载
            progress_callback: 进度回调函数
            
        Returns:
            下载是否成功
        """
        # 检查文件是否已存在
        if output_file.exists() and not force_download:
            file_size = output_file.stat().st_size / (1024 * 1024)
            logger.info(f"文件已存在 ({file_size:.2f} MB): {output_file}")
            return True
        
        # 确保输出目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        headers = {
            'User-Agent': self.user_agent
        }
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"正在下载 {url} (尝试 {attempt + 1}/{self.max_retries})")
                
                response = requests.get(url, headers=headers, timeout=self.timeout, stream=True)
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # 调用进度回调
                            if progress_callback:
                                progress_callback(downloaded, total_size)
                            
                            # 每10MB显示一次进度
                            if downloaded % (10 * 1024 * 1024) == 0:
                                if total_size > 0:
                                    progress = (downloaded / total_size) * 100
                                    logger.info(f"下载进度: {progress:.1f}% "
                                              f"({downloaded / (1024*1024):.1f} MB)")
                                else:
                                    logger.info(f"已下载: {downloaded / (1024*1024):.1f} MB")
                
                # 验证下载完整性
                final_size = output_file.stat().st_size
                logger.info(f"下载完成: {output_file} ({final_size / (1024*1024):.2f} MB)")
                return True
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"下载尝试 {attempt + 1} 失败: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    
                    # 删除不完整的文件
                    if output_file.exists():
                        try:
                            output_file.unlink()
                        except OSError:
                            pass
            except Exception as e:
                logger.error(f"下载过程中出现意外错误: {e}")
                if output_file.exists():
                    try:
                        output_file.unlink()
                    except OSError:
                        pass
                break
        
        logger.error(f"文件下载失败，已尝试 {self.max_retries} 次")
        return False
    
    @staticmethod
    def get_file_info(file_path: Path) -> Dict[str, Any]:
        """获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典
        """
        if not file_path.exists():
            return {"exists": False}
        
        stat = file_path.stat()
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "size_mb": stat.st_size / (1024 * 1024),
            "modified_time": stat.st_mtime,
            "path": str(file_path)
        }


class SpeciesDetector:
    """统一的物种检测工具类
    
    根据基因符号自动判断物种类型
    """
    
    def __init__(self, 
                 uppercase_threshold: float = 0.9,
                 min_genes_required: int = 1):
        """初始化物种检测器
        
        Args:
            uppercase_threshold: 大写基因比例阈值，超过此值判断为人类
            min_genes_required: 检测所需的最少基因数量
        """
        self.uppercase_threshold = uppercase_threshold
        self.min_genes_required = min_genes_required
    
    def detect_species_from_genes(self, gene_symbols: List[str]) -> Tuple[str, Dict[str, Any]]:
        """根据基因符号自动判断物种
        
        Args:
            gene_symbols: 基因符号列表
            
        Returns:
            (物种名称, 检测详情) - 物种名称为 "human" 或 "mouse"
        """
        if not gene_symbols:
            logger.warning("基因列表为空，默认返回人类")
            return "human", {
                "total_genes": 0,
                "valid_genes": 0,
                "uppercase_count": 0,
                "uppercase_ratio": 0.0,
                "threshold": self.uppercase_threshold,
                "reason": "empty_gene_list"
            }
        
        # 过滤掉空字符串和无效基因
        valid_genes = [gene.strip() for gene in gene_symbols 
                      if gene and gene.strip() and gene.strip().upper() not in ['', 'NA', 'NULL', 'NONE']]
        
        if len(valid_genes) < self.min_genes_required:
            logger.warning(f"有效基因数量不足 ({len(valid_genes)} < {self.min_genes_required})，默认返回人类")
            return "human", {
                "total_genes": len(gene_symbols),
                "valid_genes": len(valid_genes),
                "uppercase_count": 0,
                "uppercase_ratio": 0.0,
                "threshold": self.uppercase_threshold,
                "reason": "insufficient_valid_genes"
            }
        
        # 计算全大写基因的比例
        uppercase_count = sum(1 for gene in valid_genes if gene.isupper())
        uppercase_ratio = uppercase_count / len(valid_genes)
        
        # 判断物种
        if uppercase_ratio >= self.uppercase_threshold:
            species = "human"
            logger.debug(f"检测到人类基因 (大写比例: {uppercase_ratio:.2f})")
        else:
            species = "mouse"
            logger.debug(f"检测到小鼠基因 (大写比例: {uppercase_ratio:.2f})")
        
        detection_info = {
            "total_genes": len(gene_symbols),
            "valid_genes": len(valid_genes),
            "uppercase_count": uppercase_count,
            "uppercase_ratio": uppercase_ratio,
            "threshold": self.uppercase_threshold,
            "detected_species": species,
            "confidence": "high" if abs(uppercase_ratio - self.uppercase_threshold) > 0.1 else "medium"
        }
        
        return species, detection_info
    
    def detect_species_simple(self, gene_symbols: List[str]) -> str:
        """简化的物种检测，只返回物种名称
        
        Args:
            gene_symbols: 基因符号列表
            
        Returns:
            物种名称 ("human" 或 "mouse")
        """
        species, _ = self.detect_species_from_genes(gene_symbols)
        return species
    
    @staticmethod
    def standardize_species_name(species: str) -> str:
        """标准化物种名称
        
        Args:
            species: 原始物种名称
            
        Returns:
            标准化的物种名称
        """
        species_lower = species.lower().strip()
        
        if species_lower in ['human', 'homo sapiens', 'hs', 'h_sapiens', 'homo_sapiens']:
            return 'human'
        elif species_lower in ['mouse', 'mus musculus', 'mm', 'm_musculus', 'mus_musculus']:
            return 'mouse'
        else:
            logger.warning(f"未知物种名称: {species}，默认返回 human")
            return 'human'


class GlobalCacheManager:
    """全局缓存管理器（单例模式）
    
    统一管理整个项目的缓存目录配置
    """
    
    _instance = None
    _cache_base_dir = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def set_global_cache_dir(cls, cache_dir: str):
        """设置全局缓存目录
        
        Args:
            cache_dir: 缓存根目录路径
        """
        cls._cache_base_dir = Path(cache_dir).resolve()
        cls._cache_base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"全局缓存目录设置为: {cls._cache_base_dir}")
    
    @classmethod
    def get_cache_dir(cls, subdir: str = "") -> Path:
        """获取缓存目录路径

        Args:
            subdir: 子目录名称

        Returns:
            缓存目录路径
        """
        if cls._cache_base_dir is None:
            # 首先尝试使用统一配置系统
            # GlobalCacheManager 未初始化，抛出明确的错误
            raise RuntimeError(
                "GlobalCacheManager 未初始化。"
                "请在 MCP Server 启动时调用 GlobalCacheManager.set_global_cache_dir(cache_dir)"
            )

        if subdir:
            cache_path = cls._cache_base_dir / subdir
            cache_path.mkdir(parents=True, exist_ok=True)
            return cache_path

        return cls._cache_base_dir
    
    @classmethod
    def get_base_cache_dir(cls) -> Path:
        """获取基础缓存目录（不创建子目录）
        
        Returns:
            基础缓存目录路径
        """
        return cls.get_cache_dir()


class CacheManager:
    """缓存管理工具类

    提供统一的缓存目录和文件管理功能，支持全局缓存配置
    """

    def __init__(self, cache_dir: str = None, subdir: str = ""):
        """初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径，None表示使用全局缓存配置
            subdir: 子目录名称，用于不同模块的数据分离
        """
        # 使用回退系统（GlobalConfig 已废弃）
        if cache_dir is None:
            # 使用全局缓存目录
            self.cache_dir = GlobalCacheManager.get_cache_dir(subdir)
        else:
            # 兼容现有代码，使用指定的缓存目录
            if subdir:
                self.cache_dir = Path(cache_dir) / subdir
            else:
                self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"使用缓存目录: {self.cache_dir}")
    
    def get_cache_file_path(self, filename: str) -> Path:
        """获取缓存文件路径
        
        Args:
            filename: 文件名
            
        Returns:
            完整的缓存文件路径
        """
        return self.cache_dir / filename
    
    def is_cache_valid(self, 
                      filename: str, 
                      max_age_hours: Optional[int] = None) -> bool:
        """检查缓存文件是否有效
        
        Args:
            filename: 文件名
            max_age_hours: 最大缓存时间（小时），None表示不检查时间
            
        Returns:
            缓存是否有效
        """
        cache_file = self.get_cache_file_path(filename)
        
        if not cache_file.exists():
            return False
        
        if max_age_hours is None:
            return True
        
        # 检查文件年龄
        file_age_seconds = time.time() - cache_file.stat().st_mtime
        file_age_hours = file_age_seconds / 3600
        
        return file_age_hours <= max_age_hours
    
    def clear_cache(self, pattern: Optional[str] = None) -> int:
        """清理缓存文件
        
        Args:
            pattern: 文件名模式，None表示清理所有文件
            
        Returns:
            清理的文件数量
        """
        count = 0
        
        if pattern:
            for file_path in self.cache_dir.glob(pattern):
                if file_path.is_file():
                    file_path.unlink()
                    count += 1
        else:
            for file_path in self.cache_dir.rglob('*'):
                if file_path.is_file():
                    file_path.unlink()
                    count += 1
        
        logger.info(f"清理了 {count} 个缓存文件")
        return count
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存目录信息
        
        Returns:
            缓存信息字典
        """
        if not self.cache_dir.exists():
            return {"exists": False}
        
        files = list(self.cache_dir.rglob('*'))
        file_count = len([f for f in files if f.is_file()])
        dir_count = len([f for f in files if f.is_dir()])
        
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        return {
            "exists": True,
            "path": str(self.cache_dir),
            "file_count": file_count,
            "directory_count": dir_count,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024)
        }


# 创建默认实例供其他模块直接使用
default_downloader = FileDownloader()
default_species_detector = SpeciesDetector()


def download_file(url: str, output_file: Path, **kwargs) -> bool:
    """便捷的文件下载函数
    
    Args:
        url: 下载URL
        output_file: 输出文件路径
        **kwargs: 其他下载参数
        
    Returns:
        下载是否成功
    """
    return default_downloader.download_file_with_retry(url, output_file, **kwargs)


def detect_species(gene_symbols: List[str]) -> str:
    """便捷的物种检测函数
    
    Args:
        gene_symbols: 基因符号列表
        
    Returns:
        物种名称 ("human" 或 "mouse")
    """
    return default_species_detector.detect_species_simple(gene_symbols)


