import logging
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.provider import ProviderRequest
from astrbot.api import AstrBotConfig

logger = logging.getLogger("astrbot")

@register("persona_router", "Dev", "Router", "8.1.0")
class PersonaRouter(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    def _get_target_persona_id(self, event: AstrMessageEvent):
        """核心路由逻辑：精准解析 template_list 模板配置喵！"""
        try:
            # 1. 提取默认人格喵
            dp_config = self.config.get("default_persona", "YukiToOthers")
            if isinstance(dp_config, dict):
                default_id = dp_config.get("default", "YukiToOthers")
            else:
                default_id = dp_config

            gid = None
            if getattr(event, "message_obj", None) and getattr(event.message_obj, "group_id", None):
                gid = str(event.message_obj.group_id)
            uid = str(event.get_sender_id())
            
            # 统一群聊会话逻辑喵
            session_id = gid if gid else uid
            target = default_id
            
            # 2. 匹配全局规则 (遍历 template_list 列表) 喵
            gr_list = self.config.get("global_rules", [])
            if isinstance(gr_list, list):
                for item in gr_list:
                    if isinstance(item, dict) and str(item.get("user_id", "")).strip() == session_id:
                        target = item.get("persona_id", target)
                        break
                
            # 3. 匹配群组规则 (遍历 template_list 列表) 喵
            ggr_list = self.config.get("group_rules", [])
            if gid and isinstance(ggr_list, list):
                for item in ggr_list:
                    if isinstance(item, dict) and str(item.get("group_id", "")).strip() == gid:
                        target = item.get("persona_id", target)
                        break
                
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
                logger.warning(f"[Router] 找不到 ID 为 {target_id} 的人格，请在管理面板确认喵！")
        except Exception as e:
            logger.error(f"[Router] 注入人格过程出错: {e}喵")