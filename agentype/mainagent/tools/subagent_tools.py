#!/usr/bin/env python3
"""
agentype - Subagent Tools模块
Author: cuilei
Version: 1.0
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional, Union, List

# 导入MainAgent的配置管理器以支持配置传递
from agentype.mainagent.config.settings import ConfigManager as MainConfigManager

def get_subagent_config(agent_name: str, fallback_config: Optional[MainConfigManager] = None) -> Dict[str, Any]:
    """为指定的子Agent获取配置

    注意：此函数已简化，不再支持 JSON 配置文件加载。
    配置优先级：fallback_config > 环境变量 > 默认值

    Args:
        agent_name: 子Agent名称 ('celltypeSubagent', 'celltypeDataAgent', 'celltypeAppAgent')
        fallback_config: 主配置对象（从 MainAgent 传入）

    Returns:
        配置字典，包含该子Agent需要的所有配置参数
    """
    config_dict: Dict[str, Any] = {}

    # 1. 从传入的配置对象读取
    if fallback_config:
        config_dict.update({
            'openai_api_base': getattr(fallback_config, 'openai_api_base', None),
            'openai_api_key': getattr(fallback_config, 'openai_api_key', None),
            'openai_model': getattr(fallback_config, 'openai_model', None),
            'proxy': getattr(fallback_config, 'proxy', None),
            'language': getattr(fallback_config, 'language', None),
            'enable_streaming': getattr(fallback_config, 'enable_streaming', None),
            'cache_dir': getattr(fallback_config, 'cache_dir', None),
            'log_dir': getattr(fallback_config, 'log_dir', None)
        })

    # 2. 从环境变量补全缺失字段
    if not config_dict.get('openai_api_base'):
        config_dict['openai_api_base'] = os.getenv('OPENAI_API_BASE')

    if not config_dict.get('openai_api_key'):
        config_dict['openai_api_key'] = os.getenv('OPENAI_API_KEY')

    if not config_dict.get('openai_model'):
        config_dict['openai_model'] = os.getenv('OPENAI_MODEL', 'gpt-4o')

    if not config_dict.get('proxy'):
        config_dict['proxy'] = os.getenv('OPENAI_PROXY')

    # 3. 设置默认值
    if not config_dict.get('language'):
        config_dict['language'] = 'zh'

    if config_dict.get('enable_streaming') is None:
        config_dict['enable_streaming'] = True

    return config_dict


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # If there is already a running loop, execute in a new loop on a thread
    import concurrent.futures

    def runner():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    with concurrent.futures.ThreadPoolExecutor() as ex:
        fut = ex.submit(runner)
        return fut.result()


def process_data_via_subagent(input_data: Union[str, List[str], Any], species: Optional[str] = None, config: Optional[MainConfigManager] = None) -> Dict:
    from agentype.dataagent.agent.data_processor_agent import DataProcessorReactAgent

    async def _run():
        agent = None
        try:
            # 配置完整性检查
            if not config:
                return {"success": False, "error": "DataAgent配置对象为空"}

            if not config.openai_api_base or not config.openai_api_key:
                error_msg = f"DataAgent配置不完整: api_base={config.openai_api_base is not None}, api_key={config.openai_api_key is not None}"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}

            print(f"🔍 调试输出: API Base: {config.openai_api_base}")
            print(f"🔍 调试输出: API Key: {'***已设置***' if config.openai_api_key else 'None'}")
            print(f"🔍 调试输出: Model: {config.openai_model}")

            # 🌟 获取 MainAgent 的 session_id 准备传递
            from agentype.mainagent.config.session_config import get_session_id
            main_session_id = get_session_id()

            print(f"🔍 调试输出: 创建DataAgent实例，传递session_id: {main_session_id}")
            agent = DataProcessorReactAgent(
                config=config,
                language=config.language,
                enable_streaming=config.enable_streaming,
                console_output=False,
                file_output=True,
                session_id=main_session_id
            )

            print(f"🔍 调试输出: 初始化DataAgent...")
            if not await agent.initialize():
                error_msg = "DataAgent MCP服务器启动失败"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}

            print(f"🔍 调试输出: DataAgent初始化成功，开始处理数据...")
            print(f"🔍 调试输出: 传递物种参数: {species}")
            result = await agent.process_data(input_data, species=species)
            print(f"🔍 调试输出: 数据处理完成，结果: {result.get('success', False)}")

            # 🌟 提取 DataAgent 返回的物种信息
            detected_species = result.get("detected_species")
            if detected_species:
                print(f"✅ DataAgent检测到物种: {detected_species}")

            # 提取核心路径信息，用于防止LLM遗忘
            output_paths = result.get("output_file_paths", {})
            remember_paths = {
                "marker_genes_json": output_paths.get("marker_genes_json"),
                "h5_file": output_paths.get("h5_file"),
                "rds_file": output_paths.get("rds_file"),
                "h5ad_file": output_paths.get("h5ad_file"),
            }
            # 过滤掉None值
            remember_paths = {k: v for k, v in remember_paths.items() if v is not None}

            # DataAgent 的 LLM 会在内部自己调用 save_file_paths_bundle 保存路径
            # 不再需要在这里自动保存

            return {
                "success": result.get("success", True),
                "final_result": result.get("final_result"),
                "output_file_paths": output_paths,
                "remember_paths": remember_paths,  # 新增：核心路径信息，防止LLM遗忘
                "detected_species": detected_species,  # 🌟 新增：DataAgent检测到的物种
                "species_detection_info": result.get("species_detection_info"),  # 物种检测详情
            }
        except Exception as e:
            import traceback
            error_msg = f"DataAgent调用异常: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"🔍 调试输出: 异常详情:\n{traceback.format_exc()}")
            return {"success": False, "error": error_msg}
        finally:
            if agent:
                try:
                    print(f"🔍 调试输出: 清理DataAgent资源...")
                    await agent.cleanup()
                except Exception as cleanup_e:
                    print(f"⚠️ DataAgent资源清理失败: {cleanup_e}")

    return _run_async(_run())


def run_annotation_via_subagent(
    rds_path: Optional[str],
    h5ad_path: Optional[str],
    tissue_description: Optional[str] = None,
    marker_json_path: Optional[str] = None,
    species: Optional[str] = None,
    h5_path: Optional[str] = None,
    cluster_column: Optional[str] = None,
    detected_species_from_data: Optional[str] = None,  # 🌟 新增：从DataAgent传递的物种
    config: Optional[MainConfigManager] = None,
) -> Dict:
    from agentype.appagent.agent.celltype_annotation_agent import CelltypeAnnotationAgent

    async def _run():
        agent = None
        try:
            # 配置完整性检查
            if not config:
                return {"success": False, "error": "AppAgent配置对象为空"}

            # 🌟 获取 MainAgent 的 session_id 准备传递
            from agentype.mainagent.config.session_config import get_session_id
            main_session_id = get_session_id()

            # 🌟 物种优先级逻辑: 用户指定 > DataAgent检测
            final_species = species or detected_species_from_data
            if final_species:
                print(f"✅ 使用物种参数: {final_species} (来源: {'用户指定' if species else 'DataAgent检测'})")
            else:
                print(f"⚠️ 未提供物种参数，AppAgent将自行检测")

            print(f"🔍 调试输出: 创建AppAgent实例，传递session_id: {main_session_id}")
            agent = CelltypeAnnotationAgent(
                config=config,
                language=config.language,
                enable_streaming=config.enable_streaming,
                console_output=False,
                file_output=True,
                session_id=main_session_id
            )
            if not await agent.initialize():
                return {"success": False, "error": "Failed to start MCP server (AppAgent)"}

            result = await agent.annotate(
                rds_path=rds_path,
                h5ad_path=h5ad_path,
                tissue_description=tissue_description,
                marker_json_path=marker_json_path,
                species=final_species,  # 🌟 传递合并后的物种
                h5_path=h5_path,
                cluster_column=cluster_column,
            )

            # 提取核心路径信息，用于防止LLM遗忘
            output_paths = result.get("output_file_paths", {})
            remember_paths = {
                "singler_result": output_paths.get("singler_result"),
                "sctype_result": output_paths.get("sctype_result"),
                "celltypist_result": output_paths.get("celltypist_result"),
                "rds_file": rds_path,
                "h5ad_file": h5ad_path,
                "h5_file": h5_path,
                "marker_genes_json": marker_json_path,
            }
            # 过滤掉None值
            remember_paths = {k: v for k, v in remember_paths.items() if v is not None}

            # AppAgent 的 LLM 会在内部自己调用 save_file_paths_bundle 保存所有7个路径
            # 不再需要在这里自动保存

            return {
                "success": result.get("success", True),
                "final_answer": result.get("final_answer"),
                "output_file_paths": output_paths,
                "remember_paths": remember_paths,  # 新增：核心路径信息，防止LLM遗忘
            }
        except Exception as e:
            return {"success": False, "error": f"细胞类型注释失败: {str(e)}"}
        finally:
            if agent:
                try:
                    await agent.cleanup()
                except Exception:
                    pass

    return _run_async(_run())


def analyze_gene_list_via_subagent(
    gene_list: str,
    tissue_type: Optional[str] = None,
    species: Optional[str] = None,  # 🌟 新增：物种参数
    config: Optional[MainConfigManager] = None
) -> Dict:
    from agentype.subagent.agent.celltype_react_agent import CellTypeReactAgent

    async def _run():
        agent = None
        try:
            # 配置完整性检查
            if not config:
                return {"success": False, "error": "SubAgent配置对象为空"}

            # 🌟 获取 MainAgent 的 session_id 准备传递
            from agentype.mainagent.config.session_config import get_session_id
            main_session_id = get_session_id()

            # 🌟 记录物种信息
            if species:
                print(f"✅ 使用物种参数: {species} (传递给SubAgent)")
            else:
                print(f"⚠️ 未提供物种参数，SubAgent将自行检测")

            print(f"🔍 调试输出: 创建SubAgent实例，传递session_id: {main_session_id}")
            agent = CellTypeReactAgent(
                config=config,
                language=config.language,
                enable_streaming=config.enable_streaming,
                console_output=False,
                file_output=True,
                session_id=main_session_id
            )
            if not await agent.initialize():
                return {"success": False, "error": "Failed to start MCP server (Subagent)"}

            result = await agent.analyze_celltype(gene_list=gene_list, tissue_type=tissue_type, species=species)

            # 如果result已经是dict，在其中添加remember_paths
            if isinstance(result, dict):
                # 🆕 自动从当前会话路径包读取路径，防止长循环中路径丢失（第四阶段 - Subagent循环）
                remember_paths = {}
                try:
                    from agentype.mainagent.tools.file_paths_tools import load_file_paths_bundle

                    print(f"🔍 调试输出: 尝试从当前会话路径包读取路径...")

                    # 加载当前会话的路径包
                    loaded_paths = load_file_paths_bundle()
                    if loaded_paths.get("success"):
                        # 提取需要echo的路径
                        if loaded_paths.get("marker_genes_json"):
                            remember_paths["marker_genes_json"] = loaded_paths["marker_genes_json"]
                        if loaded_paths.get("singler_result"):
                            remember_paths["singler_result"] = loaded_paths["singler_result"]
                        if loaded_paths.get("sctype_result"):
                            remember_paths["sctype_result"] = loaded_paths["sctype_result"]
                        if loaded_paths.get("celltypist_result"):
                            remember_paths["celltypist_result"] = loaded_paths["celltypist_result"]

                        if remember_paths:
                            result["remember_paths"] = remember_paths
                            print(f"✅ 已从路径包读取并echo路径: {list(remember_paths.keys())}")
                    else:
                        print(f"⚠️ 加载路径包失败: {loaded_paths.get('error')}")

                except Exception as e:
                    print(f"⚠️ 读取路径包时出错: {e}")
                    import traceback
                    print(f"   详细信息: {traceback.format_exc()}")

                # 添加基因列表信息到返回值中，虽然不是文件路径，但有助于LLM记住上下文
                result["remember_context"] = {
                    "gene_list": gene_list[:200] if len(gene_list) > 200 else gene_list,  # 截断过长的基因列表
                    "tissue_type": tissue_type,
                }

            return result
        except Exception as e:
            return {"success": False, "error": f"基因列表分析失败: {str(e)}"}
        finally:
            if agent:
                try:
                    await agent.cleanup()
                except Exception:
                    pass

    return _run_async(_run())



# ========== 简化的函数名，与main_agent.py保持一致 ==========
def process_data(input_data: Union[str, List[str], Any], species: Optional[str] = None, config: Optional[MainConfigManager] = None) -> Dict:
    """调用 celltypeDataAgent 的数据处理 Agent - 简化版本"""
    return process_data_via_subagent(input_data, species=species, config=config)


def run_annotation_pipeline(
    rds_path: Optional[str],
    h5ad_path: Optional[str],
    tissue_description: Optional[str] = None,
    marker_json_path: Optional[str] = None,
    species: Optional[str] = None,
    h5_path: Optional[str] = None,
    cluster_column: Optional[str] = None,
    config: Optional[MainConfigManager] = None,
) -> Dict:
    """调用 celltypeAppAgent 的应用级注释 Agent - 简化版本"""
    return run_annotation_via_subagent(
        rds_path=rds_path,
        h5ad_path=h5ad_path,
        tissue_description=tissue_description,
        marker_json_path=marker_json_path,
        species=species,
        h5_path=h5_path,
        cluster_column=cluster_column,
        detected_species_from_data=None,  # 添加缺失的参数
        config=config,  # 使用关键字参数确保正确传递
    )


def analyze_gene_list(gene_list: str, tissue_type: Optional[str] = None, config: Optional[MainConfigManager] = None) -> Dict:
    """调用 celltypeSubagent 的基因列表分析 Agent - 简化版本"""
    return analyze_gene_list_via_subagent(
        gene_list=gene_list,
        tissue_type=tissue_type,
        species=None,  # 添加缺失的参数
        config=config  # 使用关键字参数
    )
