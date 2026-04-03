bl_info = {
    "name": "Save Tip",
    "author": "zeronofreya",
    "version": (0, 0, 1),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Save Tip",
    "description": "简单保存提醒：超过间隔提示，每次增加固定步长",
    "category": "3D View",
}

import bpy
import blf
import time
from bpy.types import AddonPreferences, Operator, Panel
from bpy.props import IntProperty, BoolProperty
from bpy.app.handlers import persistent

# ---------- 全局变量 ----------
_draw_handle = None
_reminder_message = ""
_last_save_time = 0          # 上次保存的时间戳
_current_threshold = 120     # 当前需要达到的秒数（阈值）


# ---------- 辅助函数 ----------
def get_prefs():
    return bpy.context.preferences.addons.get(__name__).preferences

def format_elapsed(seconds):
    seconds = int(seconds)  # 确保为整数
    if seconds < 60:
        return f"距上次保存已过 {seconds} 秒"
    else:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        if remaining_seconds == 0:
            return f"距上次保存已过 {minutes} 分钟"
        else:
            return f"距上次保存已过 {minutes} 分钟 {remaining_seconds} 秒"

def redraw_3d_views():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

def update_msg(msg=""):
    global _reminder_message
    _reminder_message = msg
    redraw_3d_views()
    return None       

def reset_status(prefs, msg=""):
    global _last_save_time, _current_threshold  
    _last_save_time = time.time()
    _current_threshold = prefs.reminder_interval
    update_msg(msg)        

# ---------- 回调函数 ----------
def update_interval(self, context):
    """用户修改提醒间隔时，更新基础间隔并重置阈值"""
    reset_status(self)
    if self.enabled:
        reset_timer(self)

def switch_plugin(self, context):
    update_interval(self, context)

# ---------- 偏好设置 ----------
class SaveReminderPreferences(AddonPreferences):
    bl_idname = __name__

    reminder_interval: IntProperty(
        name="提醒间隔(秒)",
        description="基础提醒间隔，每次提醒后增加此值",
        default=120,
        min=1,
        max=3600,
        update=update_interval)  # type: ignore
    enabled: BoolProperty(name="启用提醒", default=True, update=switch_plugin)  # type: ignore
    top_margin: IntProperty(name="顶部距离(px)", default=50, min=0, max=500)  # type: ignore
    left_margin: IntProperty(name="左侧距离(px)", default=200, min=0, max=500)  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enabled")
        layout.prop(self, "reminder_interval")
        layout.separator()
        layout.label(text="文字位置:")
        layout.prop(self, "top_margin")
        layout.prop(self, "left_margin")



# ---------- 核心逻辑 ----------
def check_and_remind(prefs):
    global _current_threshold   

    now = time.time()
    elapsed = now - _last_save_time
    if elapsed >= _current_threshold:
        # 触发提醒
        msg = format_elapsed(elapsed)
        update_msg(msg)
        bpy.app.timers.register(update_msg, first_interval=5.0)

        # 增加阈值（固定步长）
        _current_threshold += prefs.reminder_interval



# ---------- 定时器 ----------
def timer_callback():
    prefs = get_prefs()
    if not prefs.enabled:
        return None
    if _last_save_time == 0:
        reset_status(prefs)
    else:
        try:
            check_and_remind(prefs)
        except Exception as e:
            print("[Save Tip] 定时器错误:", e)
    return 1.0

def reset_timer(prefs):
    """保存文件时调用，重置计时状态"""
    timer_remove()    
    if not prefs.enabled:
        return
    bpy.app.timers.register(timer_callback, first_interval=1.0, persistent=True)
    

def timer_remove():
    try:
        bpy.app.timers.unregister(timer_callback)
    except ValueError:
        pass

# ---------- GPU 绘制 ----------
def draw_callback():
    prefs = get_prefs()
    if not prefs.enabled or not _reminder_message:
        return

    # 寻找第一个 3D 视图的 WINDOW 区域
    area = None
    for window in bpy.context.window_manager.windows:
        for a in window.screen.areas:
            if a.type == 'VIEW_3D':
                area = a
                break
        if area:
            break
    if not area:
        return
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    if not region:
        return

    font_id = 0
    blf.size(font_id, 24)
    tw, th = blf.dimensions(font_id, _reminder_message)

    x = prefs.left_margin
    y = region.height - th - prefs.top_margin
    x = max(0, min(x, region.width - tw))
    y = max(0, min(y, region.height - th))

    blf.position(font_id, x, y, 0)
    blf.color(font_id, 1.0, 0.6, 0.2, 1.0)
    blf.draw(font_id, _reminder_message)



# ---------- 事件处理器 ----------
@persistent
def save_post_handler(scene, depsgraph=None):
    prefs = get_prefs()
    reset_status(prefs)

@persistent
def load_post_handler(scene, depsgraph=None):
    prefs = get_prefs()
    reset_status(prefs)
    reset_timer(prefs)


# ---------- UI ----------
class SAVE_REMINDER_PT_panel(Panel):
    bl_label = "保存提醒"
    bl_idname = "SAVE_REMINDER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Save Tip"

    def draw(self, context):
        prefs = get_prefs()
        layout = self.layout
        layout.prop(prefs, "enabled")
        layout.prop(prefs, "reminder_interval")
        layout.separator()
        layout.prop(prefs, "top_margin")
        layout.prop(prefs, "left_margin")
        layout.operator("save_reminder.reset_timer", text="重置计时器")

class SAVE_REMINDER_OT_reset_timer(Operator):
    bl_idname = "save_reminder.reset_timer"
    bl_label = "重置计时器"
    def execute(self, context):
        prefs = get_prefs()
        reset_status(prefs, "计时器已重置")
        bpy.app.timers.register(update_msg, first_interval=3.0)
        reset_timer(prefs)
        return {'FINISHED'}

# ---------- 注册 ----------
classes = (SaveReminderPreferences, SAVE_REMINDER_PT_panel, SAVE_REMINDER_OT_reset_timer)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    global _draw_handle
    _draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback, (), 'WINDOW', 'POST_PIXEL')

    if save_post_handler not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(save_post_handler)
    if load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_post_handler)

    prefs = get_prefs()
    reset_timer(prefs)

    print("[Save Tip] 插件已启动")

def unregister():
    global _draw_handle
    if _draw_handle:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None

    if save_post_handler in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(save_post_handler)
    if load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post_handler)

    timer_remove()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("[Save Tip] 插件已卸载")

if __name__ == "__main__":
    register()