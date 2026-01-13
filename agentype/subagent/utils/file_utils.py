#!/usr/bin/env python3
"""
agentype - File Utils模块
Author: cuilei
Version: 1.0
"""

def load_gene_list_from_file(file_path: str, max_genes: int = 50) -> str:
    """从文件加载基因列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            genes = []
            for line in f:
                gene = line.strip()
                if gene and not gene.startswith('#'):  # 跳过空行和注释行
                    genes.append(gene)
                    if len(genes) >= max_genes:
                        break
        
        gene_list = ','.join(genes)
        print(f"📁 从文件加载基因: {file_path}")
        print(f"   📊 总基因数: {len(genes)}")
        print(f"   🧬 基因列表: {gene_list[:200]}{'...' if len(gene_list) > 200 else ''}")
        
        return gene_list
    except Exception as e:
        print(f"❌ 读取基因文件失败: {e}")
        return "CD3D,CD4,CD8A"  # fallback
