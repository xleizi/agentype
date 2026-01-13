#!/usr/bin/env python3
"""
agentype - Python script to retrieve all project names and descripti...
Author: cuilei
Version: 1.0
"""

from typing import Dict, List, Any

class celldexProjectsInfo:
    """celldex项目信息获取类 / celldex projects information retrieval class"""
    
    def __init__(self, language="zh"):
        self.language = language
        self.projects_data = {
            "BlueprintEncodeData": {
                "name": "BlueprintEncodeData",
                "description": {
                    "zh": "Blueprint和ENCODE项目的参考数据集，包含来自人类细胞系和原代细胞的转录组数据",
                    "en": "Reference dataset from Blueprint and ENCODE projects, containing transcriptomic data from human cell lines and primary cells"
                },
                "species": {
                    "zh": "人类",
                    "en": "Human"
                },
                "cell_types": {
                    "zh": "多种人类细胞类型",
                    "en": "Various human cell types"
                },
                "source": "Blueprint and ENCODE consortiums",
                "data_type": "Bulk RNA-seq"
            },
            "DatabaseImmuneCellExpressionData": {
                "name": "DatabaseImmuneCellExpressionData", 
                "description": {
                    "zh": "Database of Immune Cell Expression (DICE)项目数据，专注于人类免疫细胞的基因表达",
                    "en": "Database of Immune Cell Expression (DICE) project data, focused on gene expression in human immune cells"
                },
                "species": {
                    "zh": "人类",
                    "en": "Human"
                },
                "cell_types": {
                    "zh": "免疫细胞类型",
                    "en": "Immune cell types"
                },
                "source": "DICE project",
                "data_type": "Bulk RNA-seq"
            },
            "HumanPrimaryCellAtlasData": {
                "name": "HumanPrimaryCellAtlasData",
                "description": {
                    "zh": "人类原代细胞图谱数据，包含多种人类原代细胞类型的基因表达谱",
                    "en": "Human Primary Cell Atlas data containing gene expression profiles of various human primary cell types"
                },
                "species": {
                    "zh": "人类",
                    "en": "Human"
                }, 
                "cell_types": {
                    "zh": "人类原代细胞",
                    "en": "Human primary cells"
                },
                "source": "Human Primary Cell Atlas",
                "data_type": "Microarray"
            },
            "ImmGenData": {
                "name": "ImmGenData",
                "description": {
                    "zh": "Immunological Genome Project数据，提供小鼠免疫系统细胞的全面基因表达谱",
                    "en": "Immunological Genome Project data providing comprehensive gene expression profiles of mouse immune system cells"
                },
                "species": {
                    "zh": "小鼠",
                    "en": "Mouse"
                },
                "cell_types": {
                    "zh": "小鼠免疫细胞",
                    "en": "Mouse immune cells"
                },
                "source": "ImmGen Consortium", 
                "data_type": "Microarray"
            },
            "MonacoImmuneData": {
                "name": "MonacoImmuneData",
                "description": {
                    "zh": "Monaco等人发表的人类免疫细胞数据集，包含人类PBMC中主要免疫细胞亚群",
                    "en": "Human immune cell dataset published by Monaco et al., containing major immune cell subsets from human PBMC"
                },
                "species": {
                    "zh": "人类",
                    "en": "Human"
                },
                "cell_types": {
                    "zh": "人类PBMC免疫细胞亚群",
                    "en": "Human PBMC immune cell subsets"
                },
                "source": "Monaco et al. 2019",
                "data_type": "Bulk RNA-seq"
            },
            "MouseRNAseqData": {
                "name": "MouseRNAseqData", 
                "description": {
                    "zh": "小鼠RNA测序数据集，包含多种小鼠细胞类型的转录组信息",
                    "en": "Mouse RNA-seq dataset containing transcriptomic information from various mouse cell types"
                },
                "species": {
                    "zh": "小鼠",
                    "en": "Mouse"
                },
                "cell_types": {
                    "zh": "多种小鼠细胞类型",
                    "en": "Various mouse cell types"
                },
                "source": "Various mouse RNA-seq studies",
                "data_type": "Bulk RNA-seq"
            },
            "NovershternHematopoieticData": {
                "name": "NovershternHematopoieticData",
                "description": {
                    "zh": "Novershtern等人的造血系统数据，包含人类造血干细胞和各阶段分化细胞",
                    "en": "Hematopoietic system data from Novershtern et al., including human hematopoietic stem cells and differentiated cells at various stages"
                },
                "species": {
                    "zh": "人类",
                    "en": "Human"
                }, 
                "cell_types": {
                    "zh": "人类造血系统细胞",
                    "en": "Human hematopoietic system cells"
                },
                "source": "Novershtern et al. 2011",
                "data_type": "Microarray"
            }
        }
        
    
    def get_all_projects(self) -> Dict[str, Any]:
        """获取所有项目信息 / Get all projects information"""
        projects = {}
        for name, data in self.projects_data.items():
            projects[name] = {
                "name": data["name"],
                "description": data["description"][self.language],
                "species": data["species"][self.language],
                "cell_types": data["cell_types"][self.language],
                "source": data["source"],
                "data_type": data["data_type"]
            }
        return projects
    
    def get_project_names(self) -> List[str]:
        """获取所有项目名称列表 / Get list of all project names"""
        return list(self.projects_data.keys())
    
    def get_project_info(self, project_name: str) -> Dict[str, Any]:
        """获取特定项目的详细信息 / Get detailed information for a specific project"""
        data = self.projects_data.get(project_name, {})
        if not data:
            return {}
        return {
            "name": data["name"],
            "description": data["description"][self.language],
            "species": data["species"][self.language],
            "cell_types": data["cell_types"][self.language],
            "source": data["source"],
            "data_type": data["data_type"]
        }
    
