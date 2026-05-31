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
        """核心路由逻辑：实现严格的优先级覆盖 (默认 -> 全局用户 -> 群组 -> 群内特定用户) 喵！"""
        try:
            # 0. 提取默认人格 (兜底) 喵
            dp_config = self.config.get("default_persona", "YukiToOthers")
            target = dp_config.get("default", "YukiToOthers") if isinstance(dp_config, dict) else dp_config

            gid = None
            if getattr(event, "message_obj", None) and getattr(event.message_obj, "group_id", None):
                gid = str(event.message_obj.group_id)
            uid = str(event.get_sender_id())
            
            # 1. 匹配全局用户规则 (第二优先级) 喵
            gr_list = self.config.get("global_rules", [])
            if isinstance(gr_list, list):
                for item in gr_list:
                    if isinstance(item, dict) and str(item.get("user_id", "")).strip() == uid:
                        target = item.get("persona_id", target)
                        break
                
            # 2. 匹配群组规则 (第三优先级，如果是在群里，群规则会覆盖个人的全局规则) 喵
            ggr_list = self.config.get("group_rules", [])
            if gid and isinstance(ggr_list, list):
                for item in ggr_list:
                    if isinstance(item, dict) and str(item.get("group_id", "")).strip() == gid:
                        target = item.get("persona_id", target)
                        break

            # 3. 匹配群内特定用户规则 (最高优先级，精确匹配群和用户) 喵
            gur_list = self.config.get("group_user_rules", [])
            if gid and isinstance(gur_list, list):
                for item in gur_list:
                    if isinstance(item, dict) and str(item.get("group_id", "")).strip() == gid and str(item.get("user_id", "")).strip() == uid:
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
                    logger.info(f"[Router] 🎯 为 UID:{event.get_sender_id()} 注入人格: {target_id} 喵！")
            else:
                logger.warning(f"[Router] 找不到 ID 为 {target_id} 的人格，请在管理面板确认喵！")
        except Exception as e:
            logger.error(f"[Router] 注入人格过程出错: {e}喵")