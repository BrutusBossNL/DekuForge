// DekuForge UI drawing primitives, at 1080-line logical scale.
#pragma once
#include <stdint.h>
#include "imgui.h"
void skin_art_prepare(int,uint8_t *,uint32_t,uint32_t);
void skin_art_halve(const uint8_t *,uint32_t,uint32_t,uint8_t *,uint32_t,uint32_t);
void skin_style(ImGuiStyle &);
void skin_atlas_add(ImFontAtlas *);
void skin_atlas_fill(ImFontAtlas *);
float skin_brand_height(float width);
void skin_brand(ImDrawList *,ImVec2,float width);
void skin_button(ImDrawList *,ImVec2,ImVec2,float,float,bool);
float skin_cursor_reach(float);
void skin_cursor_glow(ImDrawList *,ImVec2,ImVec2,float,float);
void skin_cursor_frame(ImDrawList *,ImVec2,ImVec2,float,float);
void skin_filigree(ImDrawList *,float,float,float,float,float alpha=1);
float skin_filigree_height(float);
void skin_panel(ImDrawList *,ImVec2,ImVec2,float,float alpha=1);
void skin_boot_panel(ImDrawList *,ImFont *,float,ImFont *,float,const char *,const char *,float,float,float,float,float);
bool skin_widget_button(const char *,ImVec2,float);
bool skin_tab_item(const char *,const char *,int,float,ImFont *);
#define SKIN_TEXT IM_COL32(231,242,225,255)
#define SKIN_TEXT_DIM IM_COL32(139,169,145,255)
#define SKIN_GOLD IM_COL32(186,218,126,255)
