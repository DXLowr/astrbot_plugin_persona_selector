import os
import json
import logging
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.provider import ProviderRequest

logger = logging.getLogger("astrbot")

@register("persona_router", "Dev", "Router", "8.1.0")
class PersonaRouter(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        # 初始化时读取配置，实现内存缓存喵
        self.config = self._load_config()

    def _load_config(self):
        """安全读取并返回配置字典喵"""
        if not os.path.exists(self.config_path):
            logger.warning(f"[Router] 配置文件不存在: {self.config_path}喵")
            return {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[Router] 解析配置文件失败: {e}喵")
            return {}

    def _get_target_persona_id(self, event: AstrMessageEvent):
        """核心路由逻辑：将群聊视为统一会话来源，满足主人的愿望喵！"""
        try:
            conf = self.config
            
            # 1. 提取默认人格喵
            dp_node = conf.get("default_persona", {})
            default_id = dp_node.get("default", "YukiToOthers") if isinstance(dp_node, dict) else "YukiToOthers"

            gid = None
            if getattr(event, "message_obj", None) and getattr(event.message_obj, "group_id", None):
                gid = str(event.message_obj.group_id)
            uid = str(event.get_sender_id())
            
            # 【核心改动】统一会话 ID：如果是群聊则使用群号，私聊则使用主人/用户的QQ号喵
            session_id = gid if gid else uid
            target = default_id
            
            # 2. 匹配全局规则，直接用 session_id 匹配喵
            gr_node = conf.get("global_rules", {})
            if isinstance(gr_node, dict):
                actual_global_rules = gr_node.get("default", {})
                if session_id in actual_global_rules:
                    target = actual_global_rules[session_id]
                
            # 3. 匹配群组规则喵
            ggr_node = conf.get("group_rules", {})
            if gid and isinstance(ggr_node, dict):
                actual_group_rules = ggr_node.get("default", {})
                # 现在的结构简化为直接映射: { "群号": "人格ID" } 喵
                if gid in actual_group_rules:
                    val = actual_group_rules[gid]
                    if isinstance(val, str):
                        target = val
                    elif isinstance(val, dict) and "default" in val:
                        target = val["default"]
                
            return target
        except Exception as e:
            logger.error(f"[Router] 路由解析崩溃: {e}喵")
            return "YukiToOthers"

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        msg = event.message_str.strip() if getattr(event, "message_str", None) else ""
        
        if msg.startswith("/") or getattr(event, "is_command", False):
            return 

        target_id = self._get_target_persona_id(event)

        try:
            persona_mgr = self.context.persona_manager
            all_personas = await persona_mgr.get_all_personas()
            
            matched = next((p for p in all_personas if str(p.persona_id).strip() == str(target_id).strip()), None)
            
            if matched:
                prompt = getattr(matched, "system_prompt", getattr(matched, "content", None))
                if prompt:
                    req.system_prompt = prompt
                    setattr(event, "persona_id", target_id)
                    logger.info(f"[Router] 已为主人的请求匹配并注入人格: {target_id} 喵！")
            else:
                logger.warning(f"[Router] 找不到 ID 为 {target_id} 的人格，请确认管理面板是否存在该 ID 喵！")
        except Exception as e:
            logger.error(f"[Router] 注入人格过程出错: {e}喵")